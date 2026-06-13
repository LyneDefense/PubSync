from app.pipeline.context import PipelineContext
from app.pipeline.steps.base import PipelineStep
from app.tools.wechat_tool import WechatTool


class PublishWechatDraftStep(PipelineStep):
    name = "公众号草稿"
    start_message = "开始发送文章到公众号草稿箱"

    def __init__(self, wechat_tool: WechatTool | None = None) -> None:
        self.wechat_tool = wechat_tool or WechatTool()

    def run(self, context: PipelineContext) -> tuple[str, dict | None]:
        if context.article is None:
            raise RuntimeError("缺少文章，无法发送公众号草稿")
        context.article = self.wechat_tool.send_to_draft(context.db, context.article)
        context.published_to_wechat = True
        return "公众号草稿发送完成", {"文章ID": context.article.id}
