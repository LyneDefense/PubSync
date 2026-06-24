"""PubSync 的 SkillOpt 环境适配:把"博主真笔记 + 风格相似度"接成 SkillOpt 的 env。

只在跑训练的进程(worker/PoC runner)里 import,**不**进 app 包 __init__(主进程不依赖 skillopt)。

- dataloader:服务我们预切好的 train/val/test 样本(见 dataset.py),不让 SkillOpt 再切。
- rollout:用当前 skill 就样本选题生成(模态对齐)→ StyleDist 相似度当 soft、归属判别当 hard。
- 训练奖励/门控只用客观 StyleDist(问题清单#10:LLM 评委会被骗)。
"""

from __future__ import annotations

import random
from collections.abc import Callable

from skillopt.datasets.base import BaseDataLoader, BatchSpec
from skillopt.envs.base import EnvAdapter

from app.config import Settings
from app.skill_optimization.dataset import Sample
from app.skill_optimization.rollout import generate_with_skill
from app.skill_optimization.style_metrics import StyleProfile, attribution, style_similarity

EventFn = Callable[[str, str], None]


def _to_item(s: Sample) -> dict:
    return {"id": s.id, "topic": s.topic, "gold": s.gold, "modality": s.modality}


class PubSyncStyleDataLoader(BaseDataLoader):
    """服务预切样本:train 出训练批,val/test 出评估批。"""

    def __init__(self, train: list[Sample], val: list[Sample], test: list[Sample]) -> None:
        super().__init__()
        self._items = {
            "train": [_to_item(s) for s in train],
            "val": [_to_item(s) for s in val],
            "test": [_to_item(s) for s in test],
        }

    def build_train_batch(self, batch_size: int, seed: int, **kwargs) -> BatchSpec:
        pool = self._items["train"]
        if batch_size <= 0 or batch_size >= len(pool):
            payload = list(pool)
        else:
            payload = random.Random(seed).sample(pool, batch_size)
        return BatchSpec(phase="train", split="train", seed=seed, batch_size=len(payload), payload=payload)

    def build_eval_batch(self, env_num: int, split: str, seed: int, **kwargs) -> BatchSpec:
        pool = self._items.get(split if split in self._items else "val", self._items["val"])
        payload = pool if env_num <= 0 else pool[:env_num]
        return BatchSpec(phase="eval", split=split, seed=seed, batch_size=len(payload), payload=list(payload))

    def get_train_size(self) -> int:
        return len(self._items["train"])


class PubSyncStyleAdapter(EnvAdapter):
    """rollout = 用 skill 生成对齐模态内容,按 StyleDist 打分(soft)+ 归属(hard)。"""

    def __init__(
        self,
        settings: Settings,
        train: list[Sample],
        val: list[Sample],
        test: list[Sample],
        self_profile: StyleProfile,
        floor_profile: StyleProfile,
        *,
        gen_model: str | None = None,
        on_event: EventFn | None = None,
        analyst_workers: int = 2,
        failure_only: bool = False,
        minibatch_size: int = 8,
        edit_budget: int = 3,
    ) -> None:
        self.settings = settings
        self.self_profile = self_profile
        self.floor_profile = floor_profile
        self.gen_model = gen_model
        self.on_event = on_event
        # reflect 阶段(优化器产出编辑)需要的参数,默认 reflect 实现会读 self.*。
        self.analyst_workers = analyst_workers
        self.failure_only = failure_only
        self.minibatch_size = minibatch_size
        self.edit_budget = edit_budget
        self.dataloader = PubSyncStyleDataLoader(train, val, test)

    # —— env 装配 ——
    def setup(self, cfg: dict) -> None:
        super().setup(cfg)
        self.dataloader.setup(cfg)

    def get_dataloader(self):
        return self.dataloader

    def build_env_from_batch(self, batch: BatchSpec, **kwargs):
        return list(batch.payload or [])

    def build_train_env(self, batch_size: int, seed: int, **kwargs):
        return self.build_env_from_batch(self.dataloader.build_train_batch(batch_size=batch_size, seed=seed))

    def build_eval_env(self, env_num: int, split: str, seed: int, **kwargs):
        return self.build_env_from_batch(self.dataloader.build_eval_batch(env_num=env_num, split=split, seed=seed))

    def requires_ray(self) -> bool:
        return False

    def get_task_types(self) -> list[str]:
        return ["style_imitation"]

    def reflect(self, results: list[dict], skill_content: str, out_dir: str, **kwargs) -> list[dict | None]:
        """优化器:把打了分的 rollout 变成对 skill 的编辑。

        显式实现(PyPI v0.1.0 把它设为抽象方法),委托给库内标准 minibatch reflect。
        """
        import os

        from skillopt.gradient.reflect import run_minibatch_reflect

        return run_minibatch_reflect(
            results=results,
            skill_content=skill_content,
            prediction_dir=kwargs.get("prediction_dir", os.path.join(out_dir, "predictions")),
            patches_dir=kwargs.get("patches_dir", os.path.join(out_dir, "patches")),
            workers=self.analyst_workers,
            failure_only=self.failure_only,
            minibatch_size=self.minibatch_size,
            edit_budget=self.edit_budget,
            random_seed=kwargs.get("random_seed"),
            error_system=self.get_error_minibatch_prompt(),
            success_system=self.get_success_minibatch_prompt(),
            step_buffer_context=kwargs.get("step_buffer_context", ""),
            meta_skill_context=kwargs.get("meta_skill_context", ""),
            update_mode=getattr(self, "_cfg", {}).get("skill_update_mode", "patch"),
        )

    # —— 核心:用 skill 生成 + 打分 ——
    def score_text(self, text: str) -> tuple[int, float]:
        """返回 (hard 0/1, soft 0-1)。soft=StyleDist 相似度;hard=是否归到本博主名下。"""
        soft = style_similarity(text, self.self_profile) / 100.0
        who = attribution(text, {"self": self.self_profile, "floor": self.floor_profile})
        return (1 if who == "self" else 0, round(soft, 4))

    def rollout(self, env_manager, skill_content: str, out_dir: str, **kwargs) -> list[dict]:
        items: list[dict] = env_manager
        results: list[dict] = []
        skipped = 0
        for idx, item in enumerate(items, start=1):
            gen = ""
            for _attempt in range(3):  # 瞬时超时重试,避免把网络抖动当成"不像"
                try:
                    gen = generate_with_skill(
                        self.settings, skill_content, item["topic"], item["modality"], model=self.gen_model
                    )
                    if gen:
                        break
                except Exception:  # noqa: BLE001 - 重试,持续失败则跳过该条(不计 0 分污染信号)
                    gen = ""
            if not gen:
                skipped += 1
                continue  # 跳过:缺数据而非"风格差",不拉低均分
            hard, soft = self.score_text(gen)
            results.append(
                {
                    "id": item["id"],
                    "hard": hard,
                    "soft": soft,
                    "topic": item["topic"],
                    "predicted": gen,
                    "gold": item["gold"],
                }
            )
        if self.on_event:
            avg = round(sum(r["soft"] for r in results) / max(len(results), 1) * 100, 1)
            note = f"(跳过 {skipped} 条生成失败)" if skipped else ""
            self.on_event("rollout", f"生成并打分 {len(results)} 条,平均风格相似度 {avg}{note}")
        return results
