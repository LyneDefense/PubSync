from datetime import datetime
from html import escape
from html.parser import HTMLParser

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Article, ArticleNewsItem, ArticleStatus, NewsItem
from app.services.ai_service import AIServiceError, generate_image, generate_wechat_article, is_ai_enabled, plan_article_images


DEFAULT_COVER = "https://images.unsplash.com/photo-1677442136019-21780ecad995?auto=format&fit=crop&w=1200&q=80"


def generate_article_from_selected_news(db: Session) -> Article:
    selected_news = list(
        db.scalars(
            select(NewsItem)
            .where(NewsItem.selected.is_(True))
            .order_by(NewsItem.importance_score.desc(), NewsItem.published_at.desc())
            .limit(10)
        )
    )
    if not selected_news:
        raise ValueError("请先选择至少一条新闻")

    settings = get_settings()
    if is_ai_enabled(settings):
        title, intro, content_html, cover_image_url = generate_ai_article_content(settings, selected_news)
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        title = normalize_article_title(f"{today} 重要动态")
        intro = f"今天精选 {len(selected_news)} 条 AI 行业大事件，覆盖模型、产品、基础设施和监管动态。"
        content_html = render_article_html(intro, selected_news)
        cover_image_url = DEFAULT_COVER

    article = Article(
        title=title,
        intro=intro,
        content_html=content_html,
        cover_image_url=cover_image_url,
        status=ArticleStatus.generated,
    )
    db.add(article)
    db.flush()

    for position, news in enumerate(selected_news, start=1):
        db.add(ArticleNewsItem(article_id=article.id, news_item_id=news.id, position=position))

    db.commit()
    db.refresh(article)
    return article


def generate_ai_article_content(settings, selected_news: list[NewsItem]) -> tuple[str, str, str, str]:
    news_payload = [
        {
            "title": item.title,
            "source": item.source,
            "url": item.url,
            "published_at": item.published_at.isoformat(),
            "summary": item.summary,
            "category": item.category,
            "importance_score": item.importance_score,
            "image_url": None,
        }
        for item in selected_news
    ]

    if settings.generate_article_images:
        apply_planned_images(settings, selected_news, news_payload)

    article_data = generate_wechat_article(settings, news_payload)
    try:
        cover_image_url = generate_image(
            settings,
            str(article_data.get("cover_prompt") or build_cover_prompt(selected_news)),
            "cover",
        )
    except AIServiceError:
        cover_image_url = None
    return (
        normalize_article_title(str(article_data["title"]))[:300],
        str(article_data["intro"]),
        normalize_article_html(str(article_data["content_html"])),
        cover_image_url or DEFAULT_COVER,
    )


def normalize_article_title(title: str) -> str:
    clean_title = " ".join(title.strip().split())
    prefix = "AI科技早报 | "
    if not clean_title:
        return f"{prefix}今日 AI 行业重要动态"
    if clean_title.startswith(prefix):
        return clean_title
    if clean_title.startswith("AI科技早报|"):
        return f"{prefix}{clean_title.split('|', 1)[1].strip()}"
    for stale_prefix in ("AI 早报：", "AI早报：", "AI科技早报："):
        if clean_title.startswith(stale_prefix):
            clean_title = clean_title.removeprefix(stale_prefix).strip()
            break
    return f"{prefix}{clean_title}"


def normalize_article_html(content_html: str) -> str:
    normalized = content_html.replace("<h1", "<h2").replace("</h1>", "</h2>")
    return format_wechat_article_html(normalized)


class WeChatArticleHTMLFormatter(HTMLParser):
    allowed_tags = {"section", "h2", "h3", "p", "ul", "li", "blockquote", "a", "img", "strong", "br"}

    styles = {
        "section": (
            "margin:0 0 28px;padding:0 0 24px;border-bottom:1px solid rgba(148,163,184,0.45);"
        ),
        "h2": (
            "margin:30px 0 18px;padding:2px 0 2px 14px;border-left:4px solid #14b8a6;"
            "background:transparent;color:inherit;font-size:18px;line-height:1.45;font-weight:700;"
        ),
        "h3": (
            "margin:20px 0 10px;color:inherit;font-size:16px;line-height:1.5;font-weight:700;"
        ),
        "p": (
            "margin:0 0 14px;color:inherit;font-size:15px;line-height:1.85;"
            "letter-spacing:0;text-align:justify;"
        ),
        "ul": "margin:8px 0 16px;padding-left:20px;color:inherit;",
        "li": "margin:0 0 8px;color:inherit;font-size:15px;line-height:1.75;",
        "blockquote": (
            "margin:18px 0;padding:14px 16px;border-left:4px solid #14b8a6;"
            "background:transparent;color:inherit;font-size:15px;line-height:1.75;"
        ),
        "a": "color:#0f766e;text-decoration:none;border-bottom:1px solid #99f6e4;",
        "img": (
            "display:block;width:100%;height:auto;margin:18px 0;border-radius:8px;"
        ),
        "strong": "color:inherit;font-weight:700;",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.open_tags: list[str] = []
        self.skipped_tags: list[str] = []
        self.pending_text_tags: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag not in self.allowed_tags:
            return
        if tag == "br":
            self.parts.append("<br />")
            return
        if tag == "img":
            src = self.attr_value(attrs, "src")
            if not src:
                return
            alt = self.attr_value(attrs, "alt") or "文章配图"
            self.parts.append(
                f'<img src="{escape(src, quote=True)}" alt="{escape(alt, quote=True)}" '
                f'style="{self.styles["img"]}" />'
            )
            return

        attrs_html = self.build_attrs(tag, attrs)
        if tag in {"p", "blockquote", "h2", "h3", "li"}:
            self.pending_text_tags.append((tag, attrs_html))
            return
        self.flush_pending_text_tags()
        self.parts.append(f"<{tag}{attrs_html}>")
        self.open_tags.append(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.skipped_tags:
            while self.skipped_tags:
                current = self.skipped_tags.pop()
                if current == tag:
                    break
            return
        if self.pending_text_tags and self.pending_text_tags[-1][0] == tag:
            self.pending_text_tags.pop()
            return
        if tag not in self.allowed_tags or tag in {"br", "img"}:
            return
        self.flush_pending_text_tags()
        if tag in self.open_tags:
            while self.open_tags:
                current = self.open_tags.pop()
                self.parts.append(f"</{current}>")
                if current == tag:
                    break

    def handle_data(self, data: str) -> None:
        if self.skipped_tags:
            return
        if data:
            if self.pending_text_tags and should_skip_public_paragraph(data):
                self.skipped_tags.append(self.pending_text_tags.pop()[0])
                return
            self.flush_pending_text_tags()
            self.parts.append(escape(data))

    def handle_entityref(self, name: str) -> None:
        self.flush_pending_text_tags()
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.flush_pending_text_tags()
        self.parts.append(f"&#{name};")

    def close_remaining_tags(self) -> None:
        self.flush_pending_text_tags()
        while self.open_tags:
            self.parts.append(f"</{self.open_tags.pop()}>")

    def flush_pending_text_tags(self) -> None:
        while self.pending_text_tags:
            tag, attrs_html = self.pending_text_tags.pop(0)
            self.parts.append(f"<{tag}{attrs_html}>")
            self.open_tags.append(tag)

    def build_attrs(self, tag: str, attrs: list[tuple[str, str | None]]) -> str:
        parts = [f'style="{self.styles.get(tag, "")}"'] if tag in self.styles else []
        if tag == "a":
            href = self.attr_value(attrs, "href")
            if href:
                parts.append(f'href="{escape(href, quote=True)}"')
        return " " + " ".join(parts) if parts else ""

    @staticmethod
    def attr_value(attrs: list[tuple[str, str | None]], name: str) -> str | None:
        for key, value in attrs:
            if key.lower() == name and value:
                return value
        return None


def format_wechat_article_html(content_html: str) -> str:
    parser = WeChatArticleHTMLFormatter()
    parser.feed(content_html)
    parser.close_remaining_tags()
    formatted = "".join(parser.parts).strip()
    return (
        '<section style="margin:0;padding:0;color:inherit;font-size:16px;line-height:1.75;'
        'letter-spacing:0;background:transparent;">'
        f"{formatted}"
        "</section>"
    )


def should_skip_public_paragraph(text: str) -> bool:
    compact = " ".join(text.strip().split())
    if not compact:
        return False
    internal_markers = ("发布于", "分类：", "重要性：", "重要性", "importance")
    return sum(marker in compact for marker in internal_markers) >= 2


def apply_planned_images(settings, selected_news: list[NewsItem], news_payload: list[dict]) -> None:
    max_images = max(0, settings.max_article_images)
    min_images = max(0, min(settings.min_article_images, max_images))
    if max_images <= 0:
        return

    planning_items = [
        {
            "index": index,
            "title": item.title,
            "summary": item.summary,
            "category": item.category,
            "source": item.source,
        }
        for index, item in enumerate(selected_news)
    ]
    try:
        plan = plan_article_images(settings, planning_items, min_images=min_images, max_images=max_images)
    except AIServiceError:
        plan = {"items": [], "fallback_prompts": []}

    generated_count = 0
    for item_plan in plan.get("items", []):
        if generated_count >= max_images:
            break
        if not isinstance(item_plan, dict) or not item_plan.get("should_generate"):
            continue
        try:
            index = int(item_plan.get("index"))
        except (TypeError, ValueError):
            continue
        if index < 0 or index >= len(selected_news):
            continue
        prompt = str(item_plan.get("prompt") or "").strip()
        if not prompt or not is_safe_image_prompt(prompt):
            continue
        try:
            image_url = generate_image(settings, prompt, f"news-{selected_news[index].id}")
        except AIServiceError:
            continue
        news_payload[index]["image_url"] = image_url
        generated_count += 1

    fallback_prompts = [str(prompt) for prompt in plan.get("fallback_prompts", []) if str(prompt).strip()]
    fallback_index = 0
    while generated_count < min_images and generated_count < max_images:
        target_index = first_news_without_image(news_payload)
        if target_index is None:
            break
        prompt = fallback_prompts[fallback_index] if fallback_index < len(fallback_prompts) else build_fallback_section_prompt(selected_news)
        fallback_index += 1
        if not is_safe_image_prompt(prompt):
            prompt = build_fallback_section_prompt(selected_news)
        try:
            image_url = generate_image(settings, prompt, f"fallback-{generated_count + 1}")
        except AIServiceError:
            break
        news_payload[target_index]["image_url"] = image_url
        generated_count += 1


def first_news_without_image(news_payload: list[dict]) -> int | None:
    for index, item in enumerate(news_payload):
        if not item.get("image_url"):
            return index
    return None


def is_safe_image_prompt(prompt: str) -> bool:
    lower = prompt.lower()
    required_negative_terms = ["no human", "no face", "no logo", "no brand"]
    risky_terms = [
        "portrait",
        "celebrity",
        "person",
        "people",
        "human face",
        "real logo",
        "photorealistic news",
        "screenshot",
    ]
    return all(term in lower for term in required_negative_terms) and not any(term in lower for term in risky_terms)


def build_fallback_section_prompt(news_items: list[NewsItem]) -> str:
    topics = "; ".join(item.category for item in news_items[:5])
    return (
        "Abstract AI technology editorial infographic, 16:9, visualizing multiple AI news themes with chips, "
        "network lines, data flows, cloud infrastructure, charts, and geometric shapes. "
        "No human, no face, no celebrity, no real person, no fictional person, no logo, no brand mark, "
        "no photorealistic news scene, no UI screenshot, no text. "
        f"Themes: {topics}"
    )


def build_cover_prompt(news_items: list[NewsItem]) -> str:
    topics = "; ".join(item.title for item in news_items[:5])
    return (
        "Modern Chinese AI newsletter cover image, 16:9 composition, abstract technology infographic, "
        "no human, no face, no celebrity, no real person, no fictional person, no logo, no brand mark, "
        "no photorealistic news scene, no UI screenshot, no text, polished editorial style. Topics: "
        f"{topics}"
    )


def render_article_html(intro: str, news_items: list[NewsItem]) -> str:
    sections = [
        "<section>",
        f"<p>{escape(intro)}</p>",
        "</section>",
    ]
    for index, item in enumerate(news_items, start=1):
        sections.extend(
            [
                "<section style=\"margin-top: 24px;\">",
                f"<h2>{index}. {escape(item.title)}</h2>",
                f"<p>{escape(item.summary)}</p>",
                f"<p>来源：<a href=\"{escape(item.url)}\">{escape(item.source)}</a></p>",
                "</section>",
            ]
        )

    sections.append("<p>以上内容由 PubSync 自动整理，发布前请人工核对来源和事实。</p>")
    return format_wechat_article_html("\n".join(sections))


def update_article(db: Session, article: Article, **values: str | None) -> Article:
    for key, value in values.items():
        if value is not None:
            setattr(article, key, value)
    db.commit()
    db.refresh(article)
    return article


def replace_article_items(db: Session, article: Article, news_ids: list[int]) -> Article:
    db.execute(delete(ArticleNewsItem).where(ArticleNewsItem.article_id == article.id))
    for position, news_id in enumerate(news_ids, start=1):
        db.add(ArticleNewsItem(article_id=article.id, news_item_id=news_id, position=position))
    db.commit()
    db.refresh(article)
    return article
