from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppSetting, NewsItem


MOCK_NEWS = [
    {
        "title": "OpenAI 发布新一代多模态模型能力更新",
        "source": "OpenAI Blog",
        "url": "https://example.com/openai-multimodal-update",
        "summary": "官方披露模型在文本、视觉和工具调用上的能力更新，重点面向生产环境的稳定性和成本控制。",
        "category": "模型发布",
        "importance_score": 95,
    },
    {
        "title": "Google DeepMind 公布 Gemini 系列研究进展",
        "source": "Google DeepMind",
        "url": "https://example.com/deepmind-gemini-research",
        "summary": "研究团队展示长上下文、推理和代理任务方面的新实验结果，继续推动通用助手能力边界。",
        "category": "研究进展",
        "importance_score": 91,
    },
    {
        "title": "Anthropic 强化企业 AI 安全与合规工具",
        "source": "Anthropic News",
        "url": "https://example.com/anthropic-enterprise-safety",
        "summary": "面向企业客户新增安全评估、权限控制和审计能力，说明 AI 助手正在深入高合规场景。",
        "category": "企业应用",
        "importance_score": 88,
    },
    {
        "title": "Meta 发布新的开源大模型生态工具",
        "source": "Meta AI",
        "url": "https://example.com/meta-open-model-tools",
        "summary": "围绕开源模型训练、评测和部署提供新工具，进一步降低开发者使用开放模型的门槛。",
        "category": "开源项目",
        "importance_score": 85,
    },
    {
        "title": "NVIDIA 扩展 AI 推理芯片和软件栈",
        "source": "NVIDIA Blog",
        "url": "https://example.com/nvidia-inference-stack",
        "summary": "新硬件和推理优化工具聚焦低延迟、高吞吐场景，影响云厂商和企业私有化部署成本。",
        "category": "基础设施",
        "importance_score": 84,
    },
    {
        "title": "Hugging Face 新增模型评测排行榜维度",
        "source": "Hugging Face",
        "url": "https://example.com/huggingface-eval-leaderboard",
        "summary": "新的评测维度更强调真实任务表现和可复现性，帮助开发者筛选更适合生产使用的模型。",
        "category": "开发者工具",
        "importance_score": 79,
    },
    {
        "title": "AI 编程助手市场竞争继续升温",
        "source": "Tech News",
        "url": "https://example.com/ai-coding-assistant-market",
        "summary": "多家公司更新代码生成、代码审查和仓库级代理能力，AI 编程正在从补全走向任务执行。",
        "category": "产品更新",
        "importance_score": 76,
    },
    {
        "title": "多国监管机构讨论生成式 AI 内容标识标准",
        "source": "Policy Watch",
        "url": "https://example.com/ai-content-labeling-policy",
        "summary": "围绕水印、来源追踪和平台责任的讨论升温，未来可能影响内容平台和模型服务商。",
        "category": "政策监管",
        "importance_score": 74,
    },
]


def fetch_latest_news(db: Session) -> list[NewsItem]:
    now = datetime.now(timezone.utc)
    created_items: list[NewsItem] = []

    for index, item in enumerate(MOCK_NEWS):
        exists = db.scalar(select(NewsItem).where(NewsItem.url == item["url"]))
        if exists:
            continue

        news = NewsItem(
            title=item["title"],
            source=item["source"],
            url=item["url"],
            published_at=now - timedelta(hours=index + 1),
            summary=item["summary"],
            category=item["category"],
            importance_score=item["importance_score"],
            selected=item["importance_score"] >= 80,
        )
        db.add(news)
        created_items.append(news)

    db.merge(AppSetting(key="last_fetch_at", value=now.isoformat()))
    db.commit()

    for news in created_items:
        db.refresh(news)
    return created_items


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
