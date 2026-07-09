from __future__ import annotations

from app.config import Settings
from app.synthesis import Agent, SynthesisBudget, TaskGuide
from app.xhs_creation.agent.context import CreationContext
from app.xhs_creation.agent.critic import make_creation_critic
from app.xhs_creation.agent.guide import build_creation_prompt, build_creation_system, normalize_creation_output
from app.xhs_creation.agent.sensors import CreationComplianceSensor, CreationQualitySensor, CreationSchemaSensor


def build_creation_agent(settings: Settings, ctx: CreationContext) -> Agent:
    """装配创作 agent:guide(平台×类型组合) + 结构/合规/质量传感器 + 评审 + 预算。"""
    model = (settings.distill_text_model or "").strip() or None
    guide = TaskGuide(
        name="内容创作",
        build_prompt=build_creation_prompt,
        build_system=build_creation_system,
        normalize=normalize_creation_output,
    )
    # 合规(限流词)传感器为阻断型,放在结构之后、质量之前;命中即强制重写。
    sensors = [CreationSchemaSensor()]
    if settings.creation_compliance_enabled:
        sensors.append(CreationComplianceSensor())
    sensors.append(CreationQualitySensor())
    critic = make_creation_critic(settings, model) if settings.creation_llm_critic_enabled else None
    budget = SynthesisBudget(
        max_attempts=1 + max(0, settings.creation_max_revise_iterations),
        min_score=settings.creation_min_quality_score,
    )
    return Agent(name="内容创作", guide=guide, sensors=sensors, budget=budget, critic=critic, model=model)
