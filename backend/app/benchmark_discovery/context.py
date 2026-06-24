from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.account_audit.service import build_account_content


@dataclass
class BenchmarkContext:
    """评估一个候选博主时的参照系:意图永远在,我的账号画像可选(在则解锁可迁移度)。"""

    platform: str
    niche: str
    audience: str = ""
    goal: str = ""
    content_form: str = "any"
    my_account_profile: str = ""  # 我的账号最近笔记画像;空=没绑/没采

    @property
    def has_account(self) -> bool:
        return bool(self.my_account_profile.strip())


def build_context(
    db: Session,
    tenant_id: int,
    platform: str,
    intent: dict,
    my_account_id: int | None = None,
) -> BenchmarkContext:
    """由 intent(+可选我的账号)构建评估上下文。账号画像复用 account_audit 的拼装逻辑(取最近笔记)。"""
    profile = ""
    if my_account_id:
        # 空 post_ids → build_account_content 自动取该账号最近若干篇;没采过则返回空串。
        profile = build_account_content(db, tenant_id, my_account_id, [])
    return BenchmarkContext(
        platform=platform,
        niche=str(intent.get("niche", "")).strip(),
        audience=str(intent.get("audience", "")).strip(),
        goal=str(intent.get("goal", "")).strip(),
        content_form=str(intent.get("content_form", "any")).strip() or "any",
        my_account_profile=profile or "",
    )
