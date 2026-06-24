"""M1 干净 PoC:对一个博主跑一次 SkillOpt 优化,报告训练前后的风格 gap_closed。

只在装了 skillopt 的环境(worker/容器)里跑。用法(容器内):
    PYTHONPATH=. python -m app.skill_optimization.poc_runner --blogger-id 12 --tenant-id 1 --epochs 2

目的:验证"用 StyleDist 当奖励 + 模态对齐"能否练出真实提升(上次 PoC 被模态错配污染)。
"""

from __future__ import annotations

import argparse
import os
import tempfile

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import BloggerProfile, BloggerSkill
from app.skill_optimization.dataset import load_active_posts, split_notes
from app.skill_optimization.rollout import gold_text, modality_of
from app.skill_optimization.style_metrics import build_profile, style_similarity

# SkillOpt 基础配置(取自 configs/_base_/default.yaml 的扁平结果,避免依赖库内 configs 目录)。
DEFAULT_CFG: dict = {
    "model_backend": "azure_openai", "optimizer_model": "gpt-5.5", "target_model": "gpt-5.5",
    "optimizer_backend": "openai_chat", "target_backend": "openai_chat",
    "reasoning_effort": "medium", "rewrite_reasoning_effort": "", "rewrite_max_completion_tokens": 64000,
    "codex_exec_path": "codex", "codex_exec_sandbox": "workspace-write", "codex_exec_profile": "",
    "codex_exec_full_auto": False, "codex_exec_reasoning_effort": "none", "codex_exec_use_sdk": "auto",
    "codex_exec_network_access": False, "codex_exec_web_search": False, "codex_exec_approval_policy": "never",
    "claude_code_exec_path": "claude", "claude_code_exec_profile": "", "claude_code_exec_use_sdk": "auto",
    "claude_code_exec_effort": "medium", "claude_code_exec_max_thinking_tokens": 16384,
    "codex_trace_to_optimizer": True,
    "azure_openai_endpoint": "", "azure_openai_api_version": "2024-12-01-preview", "azure_openai_api_key": "",
    "azure_openai_auth_mode": "", "azure_openai_ad_scope": "https://cognitiveservices.azure.com/.default",
    "azure_openai_managed_identity_client_id": "",
    "optimizer_azure_openai_endpoint": "", "optimizer_azure_openai_api_version": "2024-12-01-preview",
    "optimizer_azure_openai_api_key": "", "optimizer_azure_openai_auth_mode": "",
    "optimizer_azure_openai_ad_scope": "https://cognitiveservices.azure.com/.default",
    "optimizer_azure_openai_managed_identity_client_id": "",
    "target_azure_openai_endpoint": "", "target_azure_openai_api_version": "2024-12-01-preview",
    "target_azure_openai_api_key": "", "target_azure_openai_auth_mode": "",
    "target_azure_openai_ad_scope": "https://cognitiveservices.azure.com/.default",
    "target_azure_openai_managed_identity_client_id": "",
    "minimax_base_url": "", "minimax_api_key": "", "minimax_model": "MiniMax-M2.7",
    "minimax_temperature": "0.7", "minimax_max_tokens": "8000", "minimax_enable_thinking": "false",
    "num_epochs": 4, "train_size": 0, "batch_size": 40, "accumulation": 1, "seed": 42,
    "minibatch_size": 8, "merge_batch_size": 8, "analyst_workers": 16, "failure_only": False,
    "max_analyst_rounds": 3, "edit_budget": 4, "min_edit_budget": 2, "lr_scheduler": "cosine",
    "lr_control_mode": "fixed", "skill_update_mode": "patch", "use_slow_update": True,
    "slow_update_samples": 20, "slow_update_gate_with_selection": False, "longitudinal_pair_policy": "mixed",
    "use_meta_skill": True, "use_skill_aware_reflection": False, "skill_aware_appendix_source": "both",
    "skill_aware_consolidate_threshold": 0, "use_gate": True, "sel_env_num": 0, "test_env_num": 0,
    "eval_test": True, "env": "", "skill_init": "", "out_root": "", "split_mode": "ratio",
    "split_seed": 42, "split_dir": "", "data_path": "", "split_output_dir": "", "exec_timeout": 120,
}


def _other_blogger_golds(db, tenant_id: int, platform: str, exclude_id: int, modality: str, cap: int = 40) -> list[str]:
    """同平台其它对标博主的笔记 gold(同模态),用作 floor 锚点。"""
    stmt = (
        select(BloggerProfile)
        .where(
            BloggerProfile.tenant_id == tenant_id,
            BloggerProfile.platform == platform,
            BloggerProfile.id != exclude_id,
        )
    )
    golds: list[str] = []
    for other in db.scalars(stmt):
        for post in load_active_posts(db, tenant_id, other.id):
            if modality_of(getattr(post, "content_subtype", "")) != modality:
                continue
            g = gold_text(post, modality)
            if g.strip():
                golds.append(g)
            if len(golds) >= cap:
                return golds
    return golds


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def run_poc(blogger_id: int, tenant_id: int = 1, epochs: int = 2, out_root: str | None = None) -> dict:
    settings = get_settings()
    model = settings.minimax_text_model
    log = print
    db = SessionLocal()
    try:
        blogger = db.get(BloggerProfile, blogger_id)
        if not blogger or blogger.tenant_id != tenant_id:
            raise SystemExit(f"博主 {blogger_id} 不存在")
        skill = db.scalar(
            select(BloggerSkill)
            .where(BloggerSkill.blogger_id == blogger_id, BloggerSkill.status == "active")
            .order_by(BloggerSkill.id.desc())
        )
        if not skill:
            raise SystemExit("该博主没有 active skill,先去蒸馏")

        posts = load_active_posts(db, tenant_id, blogger_id)
        split = split_notes(posts, min_total=12)
        log(f"博主「{blogger.display_name}」主模态={split.main_modality} "
            f"train {len(split.train)} / val {len(split.val)} / test {len(split.test)}(丢弃异模态 {split.dropped_minority})")

        self_profile = build_profile([s.gold for s in split.train])
        floor_golds = _other_blogger_golds(db, tenant_id, blogger.platform, blogger_id, split.main_modality)
        floor_profile = build_profile(floor_golds) if floor_golds else build_profile([])

        # 锚点(相似度 0-100,都对 self_profile 量)
        held = split.val + split.test
        ceiling = _avg([style_similarity(s.gold, self_profile) for s in held])           # 同博主天花板
        floor = _avg([style_similarity(g, self_profile) for g in floor_golds])            # 其它博主下限
        log(f"锚点:floor(其它博主)={floor} ceiling(真笔记)={ceiling}")

        seed_skill = skill.skill_markdown
    finally:
        db.close()

    # —— 配 MiniMax 后端 ——
    from skillopt.engine.trainer import ReflACTTrainer
    from skillopt.model import (
        configure_minimax_chat,
        set_optimizer_backend,
        set_optimizer_deployment,
        set_target_backend,
        set_target_deployment,
    )

    configure_minimax_chat(
        base_url=settings.minimax_base_url, api_key=settings.minimax_api_key,
        max_tokens=8000, temperature=0.7, enable_thinking=False,
    )
    set_target_backend("minimax_chat")
    set_optimizer_backend("minimax_chat")
    set_target_deployment(model)
    set_optimizer_deployment(model)

    out_root = out_root or tempfile.mkdtemp(prefix=f"skillpoc_{blogger_id}_")
    os.makedirs(out_root, exist_ok=True)
    seed_path = os.path.join(out_root, "seed_skill.md")
    with open(seed_path, "w") as f:
        f.write(seed_skill)

    from app.skill_optimization.skillopt_env import PubSyncStyleAdapter

    adapter = PubSyncStyleAdapter(
        settings, split.train, split.val, split.test, self_profile, floor_profile,
        gen_model=model, on_event=lambda stage, msg: log(f"[{stage}] {msg}"),
    )

    # whiteboard(白板 AI,无 skill)+ before(种子 skill)在 test 上
    test_items = adapter.build_eval_env(0, "test", 42)
    wb_res = adapter.rollout(test_items, "", os.path.join(out_root, "eval_whiteboard"))
    before_res = adapter.rollout(test_items, seed_skill, os.path.join(out_root, "eval_seed"))
    whiteboard = _avg([r["soft"] * 100 for r in wb_res])
    before = _avg([r["soft"] * 100 for r in before_res])

    cfg = dict(DEFAULT_CFG)
    cfg.update({
        "target_backend": "minimax_chat", "optimizer_backend": "minimax_chat",
        "target_model": model, "optimizer_model": model, "minimax_model": model,
        "minimax_base_url": settings.minimax_base_url, "minimax_api_key": settings.minimax_api_key,
        "num_epochs": epochs, "batch_size": len(split.train),
        "minibatch_size": min(8, len(split.train)), "merge_batch_size": min(8, len(split.train)),
        "analyst_workers": 2, "edit_budget": 3, "min_edit_budget": 1,
        "use_slow_update": False, "use_meta_skill": False,
        "use_gate": True, "gate_metric": "soft", "sel_env_num": 0, "eval_test": False,
        "out_root": out_root, "skill_init": seed_path, "env": "pubsync_style", "seed": 42,
    })

    log(f"开始训练({epochs} epoch,门控=soft/StyleDist)…")
    ReflACTTrainer(cfg, adapter).train()

    best_path = os.path.join(out_root, "best_skill.md")
    best_skill = open(best_path).read() if os.path.exists(best_path) else seed_skill
    after_res = adapter.rollout(test_items, best_skill, os.path.join(out_root, "eval_best"))
    after = _avg([r["soft"] * 100 for r in after_res])

    def gc(sim: float) -> float:
        span = ceiling - floor
        return round(max(0.0, min(100.0, (sim - floor) / span * 100)), 1) if span > 1e-6 else 0.0

    report = {
        "blogger": blogger.display_name, "modality": split.main_modality,
        "anchors": {"floor": floor, "ceiling": ceiling, "whiteboard": whiteboard},
        "before_sim": before, "after_sim": after,
        "before_gap_closed": gc(before), "after_gap_closed": gc(after),
        "delta_sim": round(after - before, 2), "out_root": out_root,
    }
    log("\n===== PoC 报告 =====")
    log(f"博主:{report['blogger']}  模态:{report['modality']}")
    log(f"锚点  floor={floor}  whiteboard={whiteboard}  ceiling={ceiling}")
    log(f"风格相似度  种子={before} → 优化后={after}  (Δ {report['delta_sim']})")
    log(f"gap_closed  种子={report['before_gap_closed']}% → 优化后={report['after_gap_closed']}%")
    log(f"产物目录:{out_root}")
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blogger-id", type=int, required=True)
    ap.add_argument("--tenant-id", type=int, default=1)
    ap.add_argument("--epochs", type=int, default=2)
    args = ap.parse_args()
    run_poc(args.blogger_id, args.tenant_id, args.epochs)


if __name__ == "__main__":
    main()
