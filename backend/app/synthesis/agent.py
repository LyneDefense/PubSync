from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.synthesis.budget import SynthesisBudget
from app.synthesis.guide import TaskGuide
from app.synthesis.loop import Critic, ProgressSink, run_synthesis
from app.synthesis.sensors import Sensor
from app.synthesis.trace import SynthesisTrace


@dataclass
class Agent:
    """一个「agent」= 指南 + 传感器 + 预算 +（可选）评审 + 模型 的统一装配。

    把 distill / create / audit 各自的 guide/sensors/critic/budget 打成一包，
    使三者读起来一致；run_agent 只是转调 run_synthesis，不引入新行为。
    """

    name: str
    guide: TaskGuide
    sensors: list[Sensor]
    budget: SynthesisBudget
    critic: Critic | None = None
    model: str | None = None


def run_agent(
    settings: Settings,
    agent: Agent,
    context: Any,
    on_event: ProgressSink | None = None,
) -> tuple[dict[str, Any], SynthesisTrace]:
    """运行一个 agent：等价于用 agent 的各字段调用 run_synthesis。"""
    return run_synthesis(
        settings,
        agent.guide,
        context,
        agent.sensors,
        agent.budget,
        model=agent.model,
        critic=agent.critic,
        on_event=on_event,
    )
