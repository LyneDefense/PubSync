from html import escape
from html.parser import HTMLParser

from app.models import LayoutSettings


class WeChatArticleHTMLFormatter(HTMLParser):
    allowed_tags = {"section", "h2", "h3", "p", "ul", "li", "blockquote", "a", "img", "strong", "br"}

    styles = {
        "section": "margin:0 0 28px;padding:0 0 8px;",
        "h2": (
            "margin:34px 0 18px;padding:0 0 10px;border-bottom:2px solid rgba(148,163,184,0.65);"
            "background:transparent;color:inherit;font-size:19px;line-height:1.45;font-weight:700;"
        ),
        "h3": "margin:28px 0 14px;color:inherit;font-size:18px;line-height:1.5;font-weight:700;",
        "p": "margin:0 0 14px;color:inherit;font-size:15px;line-height:1.85;letter-spacing:0;text-align:justify;",
        "ul": "margin:8px 0 16px;padding-left:20px;color:inherit;",
        "li": "margin:0 0 8px;color:inherit;font-size:15px;line-height:1.75;",
        "blockquote": (
            "margin:18px 0 18px 2px;padding:2px 0 2px 14px;border-left:3px solid rgba(100,116,139,0.75);"
            "background:transparent;color:inherit;font-size:15px;line-height:1.75;"
        ),
        "a": "color:#0f766e;text-decoration:none;border-bottom:1px solid #99f6e4;",
        "img": "display:block;width:100%;height:auto;margin:18px 0;border-radius:8px;",
        "strong": "color:inherit;font-weight:700;",
    }

    def __init__(self, layout_settings: LayoutSettings | None = None) -> None:
        super().__init__(convert_charrefs=True)
        self.styles = build_styles(layout_settings)
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


def format_wechat_article_html(content_html: str, layout_settings: LayoutSettings | None = None) -> str:
    parser = WeChatArticleHTMLFormatter(layout_settings)
    parser.feed(content_html.replace("<h1", "<h2").replace("</h1>", "</h2>"))
    parser.close_remaining_tags()
    formatted = "".join(parser.parts).strip()
    return (
        f'<section style="margin:0;padding:0;color:{css_value(layout_settings.text_color if layout_settings else "inherit")};'
        f'font-size:{font_size(layout_settings.body_font_size if layout_settings else 16)}px;'
        f'line-height:{line_height(layout_settings.line_height if layout_settings else "1.75")};'
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


def build_styles(layout: LayoutSettings | None) -> dict[str, str]:
    primary = css_value(layout.primary_color if layout else "#0f766e")
    accent = css_value(layout.accent_color if layout else "#64748b")
    text = css_value(layout.text_color if layout else "inherit")
    heading = css_value(layout.heading_color if layout else "inherit")
    body_size = font_size(layout.body_font_size if layout else 15)
    heading_size = font_size(layout.heading_font_size if layout else 19)
    line = line_height(layout.line_height if layout else "1.85")
    spacing = number(layout.section_spacing if layout else 28, 12, 48)
    radius = number(layout.image_radius if layout else 8, 0, 24)
    return {
        "section": f"margin:0 0 {spacing}px;padding:0 0 8px;",
        "h2": (
            f"margin:{spacing + 6}px 0 18px;padding:0 0 10px;border-bottom:2px solid {accent};"
            f"background:transparent;color:{heading};font-size:{heading_size}px;line-height:1.45;font-weight:700;"
        ),
        "h3": f"margin:{spacing}px 0 14px;color:{heading};font-size:{max(14, heading_size - 1)}px;line-height:1.5;font-weight:700;",
        "p": f"margin:0 0 14px;color:{text};font-size:{body_size}px;line-height:{line};letter-spacing:0;text-align:justify;",
        "ul": f"margin:8px 0 16px;padding-left:20px;color:{text};",
        "li": f"margin:0 0 8px;color:{text};font-size:{body_size}px;line-height:{line};",
        "blockquote": (
            f"margin:18px 0 18px 2px;padding:2px 0 2px 14px;border-left:3px solid {accent};"
            f"background:transparent;color:{text};font-size:{body_size}px;line-height:{line};"
        ),
        "a": f"color:{primary};text-decoration:none;border-bottom:1px solid {primary};",
        "img": f"display:block;width:100%;height:auto;margin:18px 0;border-radius:{radius}px;",
        "strong": "color:inherit;font-weight:700;",
    }


def css_value(value: str) -> str:
    value = (value or "inherit").strip()
    if value == "inherit":
        return value
    if value.startswith("#") and len(value) in {4, 7}:
        return value
    return "inherit"


def font_size(value: int) -> int:
    return number(value, 12, 26)


def line_height(value: str) -> str:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return "1.85"
    return str(max(1.4, min(2.2, parsed)))


def number(value: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return minimum
    return max(minimum, min(maximum, parsed))
