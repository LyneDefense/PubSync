from urllib.parse import urlsplit

from app.models import ContentGroup
from app.news_fetching.models import NewsSourceConfig


DEFAULT_GROUP_SOURCES = {
    "global": [
        ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
        ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
        ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
        ("InfoQ AI", "https://feed.infoq.com/ai-ml-data-eng"),
        ("Hacker News AI", "https://hnrss.org/newest?q=AI"),
        ("Hacker News OpenAI", "https://hnrss.org/newest?q=OpenAI"),
    ],
    "china": [
        ("36Kr", "https://36kr.com/feed"),
        ("InfoQ CN", "https://www.infoq.cn/feed"),
    ],
    "pet-health": [
        ("Pet Health Network", "https://www.pethealthnetwork.com/rss.xml"),
        ("Preventive Vet Dogs", "https://www.preventivevet.com/dogs/rss.xml"),
        ("Preventive Vet Cats", "https://www.preventivevet.com/cats/rss.xml"),
        ("Vet Help Direct", "https://vethelpdirect.com/vetblog/feed/"),
        ("Veterinary Practice News", "https://www.veterinarypracticenews.com/feed/"),
    ],
    "pet-knowledge": [
        ("AKC Expert Advice", "https://www.akc.org/expert-advice/feed/"),
        ("Whole Dog Journal", "https://www.whole-dog-journal.com/feed/"),
        ("Animal Wellness Magazine", "https://animalwellnessmagazine.com/feed/"),
        ("Fear Free Happy Homes", "https://www.fearfreehappyhomes.com/feed/"),
        ("Canine Journal", "https://www.caninejournal.com/feed/"),
        ("DogTime", "https://dogtime.com/feed"),
        ("Catster", "https://www.catster.com/feed/"),
        ("Cats.com", "https://cats.com/feed"),
        ("Modern Cat", "https://moderncat.com/feed/"),
    ],
    "pet-industry": [
        ("DVM360", "https://www.dvm360.com/rss"),
        ("Veterinary Practice News", "https://www.veterinarypracticenews.com/feed/"),
    ],
}


def default_source_urls(group_key: str) -> str:
    return ",".join(f"{name}|{url}" for name, url in DEFAULT_GROUP_SOURCES.get(group_key, []))


def build_source_configs(content_groups: list[ContentGroup], per_source_limit: int) -> list[NewsSourceConfig]:
    max_items = max(1, per_source_limit)
    enabled_groups = [group for group in content_groups if group.enabled]
    has_configured_sources = any(group.source_urls.strip() for group in enabled_groups)
    sources: list[NewsSourceConfig] = []
    for group in enabled_groups:
        configured = parse_configured_sources(group, max_items)
        if configured:
            sources.extend(configured)
        elif not has_configured_sources:
            sources.extend(default_sources_for_group(group, max_items))
    return sources


def parse_configured_sources(group: ContentGroup, max_items: int) -> list[NewsSourceConfig]:
    sources: list[NewsSourceConfig] = []
    for index, item in enumerate(url.strip() for url in group.source_urls.split(",") if url.strip()):
        if "|" in item:
            name, url = (part.strip() for part in item.split("|", 1))
        else:
            name = f"{group.name}-{index + 1}"
            url = item
        name = clean_source_name(name) or f"{group.name}-{index + 1}"
        if not is_valid_source_url(url):
            continue
        sources.append(source_config(group, name, url, max_items))
    return sources


def default_sources_for_group(group: ContentGroup, max_items: int) -> list[NewsSourceConfig]:
    return [source_config(group, name, url, max_items) for name, url in DEFAULT_GROUP_SOURCES.get(group.group_key, [])]


def source_config(group: ContentGroup, name: str, url: str, max_items: int) -> NewsSourceConfig:
    return NewsSourceConfig(
        name=name,
        url=url,
        group_key=group.group_key,
        group_name=group.name,
        max_items=max_items,
        enabled=group.enabled,
    )


def clean_source_name(name: str) -> str:
    return " ".join(name.split())


def is_valid_source_url(url: str) -> bool:
    if not url or any(ord(char) < 32 for char in url):
        return False
    parsed = urlsplit(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
