import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from app.config import Settings
from app.news_fetching.models import (
    NewsFetchReport,
    NewsFetchResult,
    NewsSourceConfig,
    RawNewsCandidate,
    SourceFetchReport,
)
from app.news_fetching.parser import parse_feed
from app.news_fetching.sources import build_source_configs


logger = logging.getLogger(__name__)


def fetch_news_candidates(settings: Settings, content_groups: list | None = None) -> list[RawNewsCandidate]:
    return fetch_news(settings, content_groups or []).candidates


def fetch_news(settings: Settings, content_groups: list) -> NewsFetchResult:
    sources = build_source_configs(content_groups, per_source_limit=settings.news_per_source_limit)
    return fetch_raw_news_candidates(settings, sources, content_groups)


def fetch_raw_news_candidates(settings: Settings, sources: list[NewsSourceConfig], content_groups: list) -> NewsFetchResult:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(24, settings.news_lookback_hours))
    all_candidates: list[RawNewsCandidate] = []
    source_reports: list[SourceFetchReport] = []
    seen_urls: set[str] = set()
    group_limits = {group.group_key: max(0, group.candidate_limit) for group in content_groups if group.enabled}

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; PubSync/0.1; +https://github.com/LyneDefense/PubSync)",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
    }
    with httpx.Client(timeout=20, follow_redirects=True, headers=headers) as client:
        for source in sources:
            if not source.enabled:
                continue
            source_candidates, report = fetch_source_candidates(client, source, cutoff)
            added_for_source = 0
            for candidate in source_candidates:
                normalized_url = normalize_url(candidate.url)
                if not normalized_url or normalized_url in seen_urls:
                    continue
                seen_urls.add(normalized_url)
                all_candidates.append(
                    RawNewsCandidate(
                        candidate_id="",
                        title=candidate.title,
                        source=candidate.source,
                        group_key=candidate.group_key,
                        group_name=candidate.group_name,
                        url=normalized_url,
                        published_at=candidate.published_at,
                        summary=candidate.summary,
                    )
                )
                added_for_source += 1
                if added_for_source >= source.max_items:
                    break
            report.accepted_count = added_for_source
            source_reports.append(report)
            log_source_report(report)

    selected = select_by_group(all_candidates, group_limits)
    assigned = assign_candidate_ids(selected[: max(1, settings.max_news_candidates)])
    report = NewsFetchReport(
        sources=source_reports,
        candidate_count=len(all_candidates),
        selected_count=len(assigned),
        group_counts=count_by_group(assigned),
    )
    return NewsFetchResult(candidates=assigned, report=report)


def fetch_source_candidates(
    client: httpx.Client,
    source: NewsSourceConfig,
    cutoff: datetime,
) -> tuple[list[RawNewsCandidate], SourceFetchReport]:
    report = SourceFetchReport(source=source.name, url=source.url, group_key=source.group_key, group_name=source.group_name)
    try:
        response = client.get(source.url)
        response.raise_for_status()
    except (httpx.HTTPError, httpx.InvalidURL) as exc:
        report.error = f"{type(exc).__name__}: {exc}"
        return [], report

    candidates = parse_feed(response.text, source)
    report.fetched_count = len(candidates)
    report.parsed_count = len(candidates)
    filtered = [
        candidate
        for candidate in candidates
        if not candidate.published_at or candidate.published_at >= cutoff
    ]
    report.filtered_count = len(filtered)
    return sorted(filtered, key=candidate_sort_key, reverse=True), report


def log_source_report(report: SourceFetchReport) -> None:
    if report.error:
        logger.warning(
            "新闻源抓取失败：来源=%s，区域=%s，地址=%s，错误=%s",
            report.source,
            report.group_name,
            report.url,
            report.error,
        )
        return
    if report.parsed_count == 0:
        logger.warning(
            "新闻源没有解析出可用条目：来源=%s，区域=%s，地址=%s",
            report.source,
            report.group_name,
            report.url,
        )
        return
    logger.info(
        "新闻源抓取完成：来源=%s，区域=%s，解析=%s，过滤后=%s，采纳=%s",
        report.source,
        report.group_name,
        report.parsed_count,
        report.filtered_count,
        report.accepted_count,
    )


def candidate_sort_key(candidate: RawNewsCandidate) -> datetime:
    return candidate.published_at or datetime.min.replace(tzinfo=timezone.utc)


def select_by_group(
    candidates: list[RawNewsCandidate],
    group_limits: dict[str, int],
) -> list[RawNewsCandidate]:
    selected: list[RawNewsCandidate] = []
    ordered_group_keys = list(group_limits)
    for group_key in ordered_group_keys:
        group_candidates = sorted(
            [candidate for candidate in candidates if candidate.group_key == group_key],
            key=candidate_sort_key,
            reverse=True,
        )
        limit = group_limits[group_key]
        selected.extend(group_candidates[:limit] if limit else group_candidates)
    return sorted(selected, key=candidate_sort_key, reverse=True)


def count_by_group(candidates: list[RawNewsCandidate]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for candidate in candidates:
        counts[candidate.group_key] = counts.get(candidate.group_key, 0) + 1
    return counts


def assign_candidate_ids(candidates: list[RawNewsCandidate]) -> list[RawNewsCandidate]:
    return [
        RawNewsCandidate(
            candidate_id=f"c_{index:03d}",
            title=candidate.title,
            source=candidate.source,
            group_key=candidate.group_key,
            group_name=candidate.group_name,
            url=candidate.url,
            published_at=candidate.published_at,
            summary=candidate.summary,
        )
        for index, candidate in enumerate(candidates, start=1)
    ]


def normalize_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.lower().startswith("utm_") and key.lower() not in {"ref", "fbclid", "gclid"}
        ],
        doseq=True,
    )
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/") or "/", query, ""))
