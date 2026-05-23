from urllib.parse import urlsplit

from app.news_fetching.models import NewsRegion, NewsSourceConfig


DEFAULT_INTERNATIONAL_SOURCES = [
    NewsSourceConfig("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/", NewsRegion.international),
    NewsSourceConfig("VentureBeat AI", "https://venturebeat.com/category/ai/feed/", NewsRegion.international),
    NewsSourceConfig("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", NewsRegion.international),
    NewsSourceConfig("InfoQ AI", "https://feed.infoq.com/ai-ml-data-eng", NewsRegion.international),
    NewsSourceConfig("Hacker News AI", "https://hnrss.org/newest?q=AI", NewsRegion.international),
    NewsSourceConfig("Hacker News OpenAI", "https://hnrss.org/newest?q=OpenAI", NewsRegion.international),
]


DEFAULT_DOMESTIC_SOURCES = [
    NewsSourceConfig("36Kr", "https://36kr.com/feed", NewsRegion.domestic),
    NewsSourceConfig("InfoQ CN", "https://www.infoq.cn/feed", NewsRegion.domestic),
]


def build_source_configs(
    international_urls: str,
    domestic_urls: str,
    legacy_urls: str,
    per_source_limit: int,
) -> list[NewsSourceConfig]:
    max_items = max(1, per_source_limit)
    international = parse_configured_sources(
        international_urls or legacy_urls,
        NewsRegion.international,
        max_items=max_items,
    ) or with_limit(DEFAULT_INTERNATIONAL_SOURCES, max_items)
    domestic = parse_configured_sources(domestic_urls, NewsRegion.domestic, max_items=max_items) or with_limit(
        DEFAULT_DOMESTIC_SOURCES,
        max_items,
    )
    return [*international, *domestic]


def parse_configured_sources(value: str, region: NewsRegion, max_items: int) -> list[NewsSourceConfig]:
    sources: list[NewsSourceConfig] = []
    for index, item in enumerate(url.strip() for url in value.split(",") if url.strip()):
        if "|" in item:
            name, url = (part.strip() for part in item.split("|", 1))
        else:
            name = f"{region.value}-{index + 1}"
            url = item
        if not is_valid_source_url(url):
            continue
        sources.append(NewsSourceConfig(name=name, url=url, region=region, max_items=max_items))
    return sources


def is_valid_source_url(url: str) -> bool:
    if not url or any(ord(char) < 32 for char in url):
        return False
    parsed = urlsplit(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def with_limit(sources: list[NewsSourceConfig], max_items: int) -> list[NewsSourceConfig]:
    return [
        NewsSourceConfig(
            name=source.name,
            url=source.url,
            region=source.region,
            max_items=max_items,
            enabled=source.enabled,
        )
        for source in sources
    ]
