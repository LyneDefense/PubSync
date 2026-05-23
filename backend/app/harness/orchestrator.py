from sqlalchemy.orm import Session

from app.config import Settings
from app.harness.context import HarnessContext
from app.harness.events import record_event
from app.harness.steps import (
    ComposeArticleStep,
    FetchNewsStep,
    GenerateCoverStep,
    GenerateImagesStep,
    LayoutArticleStep,
    PersistArticleStep,
    PersistNewsStep,
    PrepareArticlePayloadStep,
    ProcessNewsStep,
    PublishWechatDraftStep,
    SelectArticleNewsStep,
)
from app.models import Article, NewsItem
from app.services.ai_service import AIServiceError, is_ai_enabled

class PubSyncHarness:
    def __init__(self, db: Session, settings: Settings, task_id: str, task_type: str) -> None:
        self.context = HarnessContext(
            task_id=task_id,
            task_type=task_type,
            db=db,
            settings=settings,
        )

    def run_news_fetch(self) -> list[NewsItem]:
        self._ensure_ai_enabled()
        record_event(self.context, "流程", "running", "新闻抓取流程开始")
        self._run_steps([FetchNewsStep(), ProcessNewsStep(), PersistNewsStep()])
        record_event(
            self.context,
            "流程",
            "succeeded",
            "新闻抓取流程完成",
            {"新增": len(self.context.created_news)},
        )
        return self.context.created_news

    def run_article_generation(self) -> Article:
        record_event(self.context, "流程", "running", "文章生成流程开始")
        self._run_steps(self._article_steps())
        if self.context.article is None:
            raise RuntimeError("文章生成流程没有生成文章")
        record_event(
            self.context,
            "流程",
            "succeeded",
            "文章生成流程完成",
            {"文章ID": self.context.article.id, "标题": self.context.article.title},
        )
        return self.context.article

    def run_daily_publish(self, should_publish: bool) -> Article:
        self._ensure_ai_enabled()
        self.context.should_publish = should_publish
        record_event(self.context, "流程", "running", "每日自动流程开始")
        self._run_steps([FetchNewsStep(), ProcessNewsStep(), PersistNewsStep(), *self._article_steps()])
        if self.context.article is None:
            raise RuntimeError("每日自动流程没有生成文章")
        if should_publish:
            self._run_steps([PublishWechatDraftStep()])
        record_event(
            self.context,
            "流程",
            "succeeded",
            "每日自动流程完成",
            {
                "文章ID": self.context.article.id,
                "已发送公众号草稿": self.context.published_to_wechat,
            },
        )
        return self.context.article

    def _article_steps(self) -> list:
        steps = [SelectArticleNewsStep(), PrepareArticlePayloadStep()]
        if is_ai_enabled(self.context.settings):
            steps.append(GenerateImagesStep())
        steps.extend([ComposeArticleStep(), LayoutArticleStep(), GenerateCoverStep(), PersistArticleStep()])
        return steps

    def _run_steps(self, steps: list) -> None:
        for step in steps:
            step.execute(self.context)

    def _ensure_ai_enabled(self) -> None:
        if not is_ai_enabled(self.context.settings):
            raise AIServiceError("未配置可用的大模型 provider，请设置 LLM_PROVIDER 和对应 API key")
