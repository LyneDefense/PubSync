from app.harness.context import HarnessContext
from app.harness.steps.base import HarnessStep
from app.news_deduplication import deduplicate_processed_news
from app.services.ai_service import AIServiceError
from app.tools.llm_tool import LLMTool
from app.tools.news_fetch_tool import NewsFetchTool
from app.tools.storage_tool import persist_processed_news


class FetchNewsStep(HarnessStep):
    name = "新闻抓取"
    start_message = "开始从新闻源抓取候选新闻"

    def __init__(self, fetch_tool: NewsFetchTool | None = None) -> None:
        self.fetch_tool = fetch_tool or NewsFetchTool()

    def run(self, context: HarnessContext) -> tuple[str, dict | None]:
        fetch_result = self.fetch_tool.fetch(context.settings)
        context.fetch_result = fetch_result
        context.raw_candidates = fetch_result.candidates
        return (
            "新闻候选准备完成",
            {
                "候选总数": len(fetch_result.candidates),
                "国际": fetch_result.report.international_count,
                "国内": fetch_result.report.domestic_count,
            },
        )


class ProcessNewsStep(HarnessStep):
    name = "新闻后处理"
    start_message = "开始用大模型筛选、评分、分类候选新闻"

    def __init__(self, llm_tool: LLMTool | None = None) -> None:
        self.llm_tool = llm_tool or LLMTool()

    def run(self, context: HarnessContext) -> tuple[str, dict | None]:
        if not context.raw_candidates:
            raise AIServiceError("没有可处理的候选新闻")
        context.processed_items = self.llm_tool.process_news(context.settings, context.raw_candidates, context.profile)
        return "新闻后处理完成", {"可用条数": len(context.processed_items)}


class DeduplicateNewsStep(HarnessStep):
    name = "新闻去重"
    start_message = "开始对比最近历史新闻并过滤重复事件"

    def run(self, context: HarnessContext) -> tuple[str, dict | None]:
        unique_items, report = deduplicate_processed_news(
            context.db,
            context.settings,
            context.tenant.id,
            context.processed_items,
        )
        context.processed_items = unique_items
        context.dedup_report = report
        return "新闻去重完成", report.to_dict()


class PersistNewsStep(HarnessStep):
    name = "新闻入库"
    start_message = "开始保存新闻处理结果"

    def run(self, context: HarnessContext) -> tuple[str, dict | None]:
        if context.fetch_result is None:
            raise RuntimeError("缺少新闻抓取结果")
        created_items, skipped_existing, skipped_invalid = persist_processed_news(
            context.db,
            context.tenant.id,
            context.fetch_result,
            context.processed_items,
        )
        context.created_news = created_items
        return (
            "新闻入库完成",
            {
                "新增": len(created_items),
                "跳过重复": skipped_existing,
                "跳过无效": skipped_invalid,
            },
        )
