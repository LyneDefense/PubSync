from sqlalchemy.orm import Session

from app.models import Article
from app.services.wechat_service import send_article_to_wechat_draft


class WechatTool:
    def send_to_draft(self, db: Session, article: Article) -> Article:
        return send_article_to_wechat_draft(db, article)
