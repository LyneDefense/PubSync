from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import NewsItem


def list_news(db: Session) -> list[NewsItem]:
    return list(
        db.scalars(
            select(NewsItem).order_by(
                NewsItem.selected.desc(),
                NewsItem.importance_score.desc(),
                NewsItem.published_at.desc(),
            )
        )
    )
