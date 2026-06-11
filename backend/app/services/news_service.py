from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import NewsItem


def list_news(db: Session, tenant_id: int, limit: int | None = None, offset: int = 0) -> list[NewsItem]:
    stmt = (
        select(NewsItem)
        .where(NewsItem.tenant_id == tenant_id)
        .order_by(
            NewsItem.selected.desc(),
            NewsItem.importance_score.desc(),
            NewsItem.published_at.desc(),
        )
    )
    if limit is not None:
        stmt = stmt.offset(offset).limit(limit)
    return list(db.scalars(stmt))
