"""Skill 优化产品服务:跑一次优化(SkillOpt + 我们的 StyleDist 奖励)→ 详细过程 + 前后对比 +
明确建议(没提升就劝退);用户确认后才把优化版存为新 active Skill。

进度走 operation_task_events(LiveProgress);优化器(reflect/编辑)用 MiniMax,生成(rollout)走
应用配置的文本供应商。详见 docs/Skill优化_方案设计.md。
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.blogger_distillation.service import record_task_event
from app.blogger_distillation.service.crud import archive_active_skills
from app.config import Settings
from app.models import BloggerProfile, BloggerSkill, SkillTrainingRun
from app.services.ai_service import AIServiceError, is_ai_enabled
from app.skill_optimization.dataset import load_active_posts, split_notes
from app.skill_optimization.poc_runner import DEFAULT_CFG, _avg, _other_blogger_golds
from app.skill_optimization.style_metrics import build_profile, gap_closed, style_similarity

logger = logging.getLogger(__name__)

IMPROVE_MIN = 1.5   # 相似度提升 ≥ 此值才算"有效",建议采纳
REGRESS_MAX = -1.0  # 相似度下降 ≤ 此值算"变差"


def _read_changelog(out_root: str) -> tuple[list[dict], list[str]]:
    """读 SkillOpt 产物,提炼「优化器每步做了什么 + 门控结果」。best-effort,失败返回空。"""
    epochs: list[dict] = []
    changelog: list[str] = []
    try:
        hist_path = os.path.join(out_root, "history.json")
        history = json.load(open(hist_path)) if os.path.exists(hist_path) else []
    except Exception:  # noqa: BLE001
        history = []
    for rec in history if isinstance(history, list) else []:
        if not isinstance(rec, dict):
            continue
        step = rec.get("step") or rec.get("global_step")
        action = str(rec.get("action", ""))
        edits = _read_step_edits(out_root, step)
        epochs.append({
            "step": step,
            "action": action,
            "val_score": rec.get("current_score") or rec.get("cand_score"),
            "edits": edits,
        })
        if action in ("accept", "accept_new_best", "force_accept") and edits:
            changelog.extend(edits)
    return epochs, changelog


def _read_step_edits(out_root: str, step) -> list[str]:
    if step is None:
        return []
    titles: list[str] = []
    for fname in ("ranked_edits.json", "merged_patch.json"):
        path = os.path.join(out_root, "steps", f"step_{int(step):04d}", fname)
        if not os.path.exists(path):
            continue
        try:
            data = json.load(open(path))
        except Exception:  # noqa: BLE001
            continue
        items = data.get("edits") if isinstance(data, dict) else data
        for e in items if isinstance(items, list) else []:
            if isinstance(e, dict):
                title = str(e.get("title") or e.get("instruction") or e.get("op") or e.get("type") or "").strip()
                if title:
                    titles.append(title[:120])
        if titles:
            break
    return titles


def _verdict(delta: float) -> tuple[str, bool, str]:
    if delta >= IMPROVE_MIN:
        return "improved", True, "优化有效,生成内容更贴近该博主风格,建议采纳新版本。"
    if delta <= REGRESS_MAX:
        return "regressed", False, "优化后反而更不像,建议放弃本次结果、保留原 Skill。"
    return (
        "no_gain",
        False,
        "本次优化没有明显提升(变化在噪声范围内),建议暂不采纳、保留原 Skill;"
        "可在采集更多笔记后或调参重试。",
    )


def run_skill_optimization(
    db: Session,
    settings: Settings,
    task_id: str,
    tenant_id: int,
    blogger_id: int,
    epochs: int = 2,
) -> SkillTrainingRun:
    if not is_ai_enabled(settings):
        raise AIServiceError("未配置可用的大模型 API Key")
    if not settings.minimax_api_key:
        raise AIServiceError("Skill 优化当前用 MiniMax 作为优化器,请先在后台配置 MiniMax API Key")

    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant_id:
        raise ValueError("博主不存在")
    seed = db.scalar(
        select(BloggerSkill)
        .where(BloggerSkill.blogger_id == blogger_id, BloggerSkill.status == "active")
        .order_by(BloggerSkill.id.desc())
    )
    if not seed:
        raise ValueError("该博主还没有 active Skill,请先去蒸馏")

    run = SkillTrainingRun(
        tenant_id=tenant_id, blogger_id=blogger_id, base_skill_id=seed.id,
        task_id=task_id, status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    def ev(step: str, status: str, msg: str) -> None:
        record_task_event(db, tenant_id, task_id, step, status, msg)

    # 1) 数据划分(时间留出)
    posts = load_active_posts(db, tenant_id, blogger_id)
    split = split_notes(posts, min_total=12)
    run.modality = split.main_modality
    db.commit()
    ev("划分数据", "succeeded",
       f"主模态「{split.main_modality}」· 训练 {len(split.train)} / 验证 {len(split.val)} / 测试 {len(split.test)} 篇"
       + (f"(丢弃异模态 {split.dropped_minority} 篇,保证口径一致)" if split.dropped_minority else ""))

    # 2) 锚点(让分数可解释)
    self_profile = build_profile([s.gold for s in split.train])
    floor_golds = _other_blogger_golds(db, tenant_id, blogger.platform, blogger_id, split.main_modality)
    floor_profile = build_profile(floor_golds) if floor_golds else build_profile([])
    held = split.val + split.test
    ceiling = _avg([style_similarity(s.gold, self_profile) for s in held])
    floor = _avg([style_similarity(g, self_profile) for g in floor_golds])
    ev("量基准锚点", "succeeded",
       f"其它博主基线 {floor} 分 · 该博主真笔记天花板 {ceiling} 分(满分100,越高越像本人)")

    # 3) 配后端 + 适配器 + 锚点
    from skillopt.engine.trainer import ReflACTTrainer
    from skillopt.model import (
        configure_minimax_chat, set_optimizer_backend, set_optimizer_deployment,
        set_target_backend, set_target_deployment,
    )
    from app.skill_optimization.skillopt_env import PubSyncStyleAdapter

    configure_minimax_chat(
        base_url=settings.minimax_base_url, api_key=settings.minimax_api_key,
        max_tokens=8000, temperature=0.7, enable_thinking=False,
    )
    set_target_backend("minimax_chat")
    set_optimizer_backend("minimax_chat")
    set_target_deployment(settings.minimax_text_model)
    set_optimizer_deployment(settings.minimax_text_model)

    out_root = tempfile.mkdtemp(prefix=f"skillopt_{blogger_id}_")
    seed_path = os.path.join(out_root, "seed_skill.md")
    with open(seed_path, "w") as f:
        f.write(seed.skill_markdown)

    adapter = PubSyncStyleAdapter(
        settings, split.train, split.val, split.test, self_profile, floor_profile,
        on_event=lambda stage, msg: ev("生成与打分", "running", msg),
        analyst_workers=2, minibatch_size=min(8, len(split.train)), edit_budget=3,
    )

    # 4) 基线:白板 + 种子 在 test 上
    test_items = adapter.build_eval_env(0, "test", 42)
    ev("跑基线", "running", "用当前 Skill 在测试集生成内容并打分(作为优化前基准)…")
    before_res = adapter.rollout(test_items, seed.skill_markdown, os.path.join(out_root, "eval_seed"))
    before = _avg([r["soft"] * 100 for r in before_res])
    ev("跑基线", "succeeded", f"优化前风格相似度 {before} 分(gap_closed {gap_closed(before, floor, ceiling)}%)")

    # 5) 训练(SkillOpt:生成→反思编辑→验证门控)
    cfg = dict(DEFAULT_CFG)
    cfg.update({
        "target_backend": "minimax_chat", "optimizer_backend": "minimax_chat",
        "target_model": settings.minimax_text_model, "optimizer_model": settings.minimax_text_model,
        "minimax_model": settings.minimax_text_model,
        "minimax_base_url": settings.minimax_base_url, "minimax_api_key": settings.minimax_api_key,
        "num_epochs": epochs, "batch_size": len(split.train),
        "minibatch_size": min(8, len(split.train)), "merge_batch_size": min(8, len(split.train)),
        "analyst_workers": 2, "edit_budget": 3, "min_edit_budget": 1,
        "use_slow_update": False, "use_meta_skill": False,
        "use_gate": True, "gate_metric": "soft", "sel_env_num": 0, "eval_test": False,
        "out_root": out_root, "skill_init": seed_path, "env": "pubsync_style", "seed": 42,
    })
    ev("优化训练", "running", f"开始 {epochs} 轮优化:每轮生成→对比真笔记找差距→改写 Skill→验证集严格变好才采纳…")
    ReflACTTrainer(cfg, adapter).train()
    epochs_detail, changelog = _read_changelog(out_root)
    accepted = sum(1 for e in epochs_detail if str(e.get("action", "")).startswith("accept"))
    ev("优化训练", "succeeded", f"训练完成,共 {len(epochs_detail)} 步,门控采纳 {accepted} 处改写")

    # 6) 优化后在 test 上
    best_path = os.path.join(out_root, "best_skill.md")
    optimized = open(best_path).read() if os.path.exists(best_path) else seed.skill_markdown
    after_res = adapter.rollout(test_items, optimized, os.path.join(out_root, "eval_best"))
    after = _avg([r["soft"] * 100 for r in after_res])

    before_gap = gap_closed(before, floor, ceiling)
    after_gap = gap_closed(after, floor, ceiling)
    delta = round(after - before, 2)
    verdict, recommend, rec_text = _verdict(delta)
    ev("出对比报告", "succeeded",
       f"优化前 {before} → 优化后 {after}(Δ {delta:+});{rec_text}")

    # 样例三栏(同选题:优化前生成 / 优化后生成 / 真笔记)
    samples = []
    for b, a in zip(before_res[:3], after_res[:3]):
        samples.append({
            "topic": b.get("topic", ""),
            "seed_text": b.get("predicted", ""), "seed_sim": round(b.get("soft", 0) * 100, 1),
            "optimized_text": a.get("predicted", ""), "optimized_sim": round(a.get("soft", 0) * 100, 1),
            "real_text": b.get("gold", ""),
        })

    report = {
        "anchors": {"floor": floor, "ceiling": ceiling},
        "counts": {"train": len(split.train), "val": len(split.val), "test": len(split.test),
                   "dropped_minority": split.dropped_minority},
        "epochs": epochs_detail,
        "changelog": changelog,
        "samples": samples,
        "process_note": (
            "优化方法:用该博主真笔记当目标,反复「用当前 Skill 生成内容 → 和真笔记比对找出风格差距 → "
            "由优化器改写 Skill → 只有在验证集上风格相似度严格变好才采纳该改写」。打分用客观风格指纹(StyleDist),"
            "不靠 AI 评委(评委会被讨好型改写骗)。"
        ),
    }
    run.before_score, run.after_score = before, after
    run.before_gap, run.after_gap, run.delta = before_gap, after_gap, delta
    run.verdict, run.recommend_adopt = verdict, recommend
    run.optimized_skill_markdown = optimized
    run.report_json = json.dumps(report, ensure_ascii=False)
    run.status = "pending_confirmation"
    db.commit()
    db.refresh(run)
    return run


def confirm_skill_optimization(db: Session, tenant_id: int, run_id: int, adopt: bool) -> SkillTrainingRun:
    run = db.get(SkillTrainingRun, run_id)
    if not run or run.tenant_id != tenant_id:
        raise ValueError("优化记录不存在")
    if run.status != "pending_confirmation":
        raise ValueError("该优化结果已处理")

    if not adopt:
        run.status = "abandoned"
        db.commit()
        db.refresh(run)
        return run

    blogger = db.get(BloggerProfile, run.blogger_id)
    base = db.get(BloggerSkill, run.base_skill_id) if run.base_skill_id else None
    if not blogger or not base:
        raise ValueError("基础 Skill 或博主不存在")
    # 采纳:旧 active 归档,优化版存为新 active 版本(沿用基础 skill 的 run_id 表示血缘)。
    archive_active_skills(db, tenant_id, blogger.id)
    new_skill = BloggerSkill(
        tenant_id=tenant_id, blogger_id=blogger.id, run_id=base.run_id,
        name=f"[优化] {base.name}", description=f"由 Skill 优化得到(相似度 {run.before_score}→{run.after_score})",
        skill_markdown=run.optimized_skill_markdown, scope_json=base.scope_json, status="active",
    )
    db.add(new_skill)
    db.flush()
    run.result_skill_id = new_skill.id
    run.status = "succeeded"
    blogger.last_distilled_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return run
