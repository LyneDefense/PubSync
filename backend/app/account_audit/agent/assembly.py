from __future__ import annotations

from app.account_audit.agent.context import AuditContext
from app.account_audit.agent.critic import make_audit_critic
from app.account_audit.agent.guide import build_audit_prompt, normalize_audit_output
from app.account_audit.agent.sensors import AuditQualitySensor, AuditSchemaSensor
from app.config import Settings
from app.synthesis import Agent, SynthesisBudget, TaskGuide


def build_audit_agent(settings: Settings, ctx: AuditContext) -> Agent:
    """装配账号诊断 agent(对标诊断/诊断我的);guide 按 ctx.kind 内部分流。"""
    model = (settings.distill_text_model or "").strip() or None
    name = "诊断我的" if ctx.kind == "self" else "对标诊断"
    guide = TaskGuide(name=name, build_prompt=build_audit_prompt, normalize=normalize_audit_output)
    sensors = [AuditSchemaSensor(), AuditQualitySensor()]
    critic = make_audit_critic(settings, model) if settings.audit_llm_critic_enabled else None
    budget = SynthesisBudget(
        max_attempts=1 + max(0, settings.audit_max_revise_iterations),
        min_score=settings.audit_min_quality_score,
    )
    return Agent(name=name, guide=guide, sensors=sensors, budget=budget, critic=critic, model=model)
