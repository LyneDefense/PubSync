from app.config import Settings
from app.news_fetching.models import RawNewsCandidate
from app.news_processing.prompts import build_news_processing_prompt
from app.news_processing.validators import validate_processed_items
from app.services.ai_service import AIServiceError, create_json_response


def process_news_candidates(settings: Settings, candidates: list[RawNewsCandidate]) -> list[dict[str, object]]:
    if not candidates:
        raise AIServiceError("没有从新闻源抓取到候选新闻，请检查新闻源配置")

    data = create_json_response(settings=settings, prompt=build_news_processing_prompt(candidates))
    items = validate_processed_items(data.get("items"), candidates)
    if not items:
        raise AIServiceError("AI 新闻后处理没有返回可用新闻，请检查候选源质量或模型输出")
    return [item.to_news_dict() for item in items]
