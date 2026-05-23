from app.harness.context import HarnessContext
from app.harness.steps.base import HarnessStep
from app.tools.article_tool import ArticleTool, normalize_article_title
from app.tools.image_tool import ImageTool
from app.tools.llm_tool import LLMTool
from app.tools.storage_tool import persist_article


class SelectArticleNewsStep(HarnessStep):
    name = "文章选题"
    start_message = "开始按工作空间分组规则选择文章新闻"

    def __init__(self, article_tool: ArticleTool | None = None) -> None:
        self.article_tool = article_tool or ArticleTool()

    def run(self, context: HarnessContext) -> tuple[str, dict | None]:
        selection = self.article_tool.select_news(
            context.db,
            context.settings,
            context.tenant.id,
            context.profile,
            context.content_groups,
        )
        context.selection = selection
        context.selected_news = selection.news_items
        if not context.selected_news:
            raise ValueError(f"最近 {context.settings.article_news_lookback_hours} 小时内没有可生成文章的已选新闻")
        return (
            "文章选题完成",
            {
                "总数": len(context.selected_news),
                "分组数量": selection.group_counts,
                "可用候选": selection.total_available,
            },
        )


class PrepareArticlePayloadStep(HarnessStep):
    name = "文章素材准备"
    start_message = "开始整理文章生成素材"

    def __init__(self, article_tool: ArticleTool | None = None) -> None:
        self.article_tool = article_tool or ArticleTool()

    def run(self, context: HarnessContext) -> tuple[str, dict | None]:
        context.news_payload = self.article_tool.build_news_payload(context.selected_news, context.content_groups)
        return "文章素材准备完成", {"素材数": len(context.news_payload)}


class GenerateImagesStep(HarnessStep):
    name = "正文配图"
    start_message = "开始规划并生成正文配图"

    def __init__(self, image_tool: ImageTool | None = None) -> None:
        self.image_tool = image_tool or ImageTool()

    def run(self, context: HarnessContext) -> tuple[str, dict | None]:
        if not context.settings.generate_article_images:
            return "配置已关闭正文配图生成", {"已生成": 0}
        generated_count = self.image_tool.apply_article_images(
            context.settings,
            context.selected_news,
            context.news_payload,
            context.profile,
        )
        return "正文配图完成", {"已生成": generated_count}


class ComposeArticleStep(HarnessStep):
    name = "正文生成"
    start_message = "开始生成公众号正文结构"

    def __init__(self, article_tool: ArticleTool | None = None, llm_tool: LLMTool | None = None) -> None:
        self.article_tool = article_tool or ArticleTool()
        self.llm_tool = llm_tool or LLMTool()

    def run(self, context: HarnessContext) -> tuple[str, dict | None]:
        if self.article_tool.ai_enabled(context.settings):
            context.composed_article = self.llm_tool.compose_article(
                context.settings,
                context.news_payload,
                context.profile,
                context.content_groups,
            )
            context.title = normalize_article_title(context.composed_article.title, context.profile.title_prefix)[:300]
            context.intro = context.composed_article.intro
            return "正文生成完成", {"段落数": len(context.composed_article.sections), "标题": context.title}

        context.title, context.intro, context.content_html, context.cover_image_url = self.article_tool.build_basic_article(
            context.selected_news,
            context.profile,
        )
        return "未启用大模型，已使用基础正文", {"标题": context.title}


class LayoutArticleStep(HarnessStep):
    name = "公众号排版"
    start_message = "开始生成公众号 HTML 排版"

    def __init__(self, article_tool: ArticleTool | None = None) -> None:
        self.article_tool = article_tool or ArticleTool()

    def run(self, context: HarnessContext) -> tuple[str, dict | None]:
        if context.content_html:
            return "公众号排版已由基础模板完成", {"页面字符数": len(context.content_html)}
        if context.composed_article is None:
            raise RuntimeError("缺少文章正文结构，无法排版")
        context.content_html = self.article_tool.render_article(
            context.composed_article,
            context.profile,
            context.layout_settings,
        )
        return "公众号排版完成", {"页面字符数": len(context.content_html)}


class GenerateCoverStep(HarnessStep):
    name = "封面生成"
    start_message = "开始生成文章封面"

    def __init__(self, image_tool: ImageTool | None = None) -> None:
        self.image_tool = image_tool or ImageTool()

    def run(self, context: HarnessContext) -> tuple[str, dict | None]:
        if context.cover_image_url:
            return "已使用基础封面", {"封面": context.cover_image_url}
        cover_prompt = context.composed_article.cover_prompt if context.composed_article else ""
        context.cover_image_url = self.image_tool.generate_cover(
            context.settings,
            context.selected_news,
            cover_prompt,
            context.profile,
        )
        return "封面生成完成", {"封面": context.cover_image_url}


class PersistArticleStep(HarnessStep):
    name = "文章入库"
    start_message = "开始保存生成后的文章"

    def run(self, context: HarnessContext) -> tuple[str, dict | None]:
        context.article = persist_article(
            context.db,
            context.tenant.id,
            context.title,
            context.intro,
            context.content_html,
            context.cover_image_url,
            context.selected_news,
        )
        return "文章入库完成", {"文章ID": context.article.id, "标题": context.article.title}
