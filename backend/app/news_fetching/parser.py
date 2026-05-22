import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

from app.news_fetching.models import NewsSourceConfig, RawNewsCandidate


def parse_feed(xml_text: str, source: NewsSourceConfig) -> list[RawNewsCandidate]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    items: list[RawNewsCandidate] = []
    for node in root.findall(".//item"):
        title = text_of(node, "title")
        url = text_of(node, "link")
        published = text_of(node, "pubDate") or text_of(node, "published")
        summary = text_of(node, "description")
        candidate = build_candidate(title, url, published, summary, source)
        if candidate:
            items.append(candidate)

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for node in root.findall(".//atom:entry", ns):
        title = text_of(node, "atom:title", ns)
        url = atom_link(node, ns)
        published = text_of(node, "atom:published", ns) or text_of(node, "atom:updated", ns)
        summary = text_of(node, "atom:summary", ns) or text_of(node, "atom:content", ns)
        candidate = build_candidate(title, url, published, summary, source)
        if candidate:
            items.append(candidate)
    return items


def build_candidate(title: str, url: str, published: str, summary: str, source: NewsSourceConfig) -> RawNewsCandidate | None:
    clean_title = clean_text(title)[:500]
    clean_url = urljoin(source.url, url.strip())
    if not clean_title or not clean_url:
        return None
    return RawNewsCandidate(
        candidate_id="",
        title=clean_title,
        source=source.name,
        region=source.region,
        url=clean_url,
        published_at=parse_datetime(published),
        summary=clean_text(strip_html(summary))[:1000],
    )


def atom_link(node: ET.Element, ns: dict[str, str]) -> str:
    fallback = ""
    for link in node.findall("atom:link", ns):
        href = link.attrib.get("href", "")
        rel = link.attrib.get("rel", "alternate")
        if href and rel == "alternate":
            return href
        if href and not fallback:
            fallback = href
    return fallback


def text_of(node: ET.Element, path: str, ns: dict[str, str] | None = None) -> str:
    child = node.find(path, ns or {})
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
