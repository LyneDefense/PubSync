from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class NewsSourceConfig:
    name: str
    url: str
    group_key: str
    group_name: str
    max_items: int = 8
    enabled: bool = True


@dataclass(frozen=True)
class RawNewsCandidate:
    candidate_id: str
    title: str
    url: str
    source: str
    group_key: str
    group_name: str
    published_at: datetime | None
    summary: str

    def to_prompt_dict(self) -> dict[str, str]:
        return {
            "title": self.title,
            "candidate_id": self.candidate_id,
            "source": self.source,
            "group_key": self.group_key,
            "group_name": self.group_name,
            "url": self.url,
            "published_at": self.published_at.isoformat() if self.published_at else "",
            "summary": self.summary,
        }


@dataclass
class SourceFetchReport:
    source: str
    url: str
    group_key: str
    group_name: str
    fetched_count: int = 0
    parsed_count: int = 0
    filtered_count: int = 0
    accepted_count: int = 0
    error: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "url": self.url,
            "group_key": self.group_key,
            "group_name": self.group_name,
            "fetched_count": self.fetched_count,
            "parsed_count": self.parsed_count,
            "filtered_count": self.filtered_count,
            "accepted_count": self.accepted_count,
            "error": self.error,
        }


@dataclass(frozen=True)
class NewsFetchReport:
    sources: list[SourceFetchReport]
    candidate_count: int
    selected_count: int
    group_counts: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_count": self.candidate_count,
            "selected_count": self.selected_count,
            "group_counts": self.group_counts,
            "sources": [source.to_dict() for source in self.sources],
        }


@dataclass(frozen=True)
class NewsFetchResult:
    candidates: list[RawNewsCandidate]
    report: NewsFetchReport
