from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class NewsRegion(StrEnum):
    domestic = "domestic"
    international = "international"


@dataclass(frozen=True)
class NewsSourceConfig:
    name: str
    url: str
    region: NewsRegion
    max_items: int = 8
    enabled: bool = True


@dataclass(frozen=True)
class RawNewsCandidate:
    candidate_id: str
    title: str
    url: str
    source: str
    region: NewsRegion
    published_at: datetime | None
    summary: str

    def to_prompt_dict(self) -> dict[str, str]:
        return {
            "title": self.title,
            "candidate_id": self.candidate_id,
            "source": self.source,
            "region": self.region.value,
            "url": self.url,
            "published_at": self.published_at.isoformat() if self.published_at else "",
            "summary": self.summary,
        }


@dataclass
class SourceFetchReport:
    source: str
    url: str
    region: NewsRegion
    fetched_count: int = 0
    parsed_count: int = 0
    filtered_count: int = 0
    accepted_count: int = 0
    error: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "url": self.url,
            "region": self.region.value,
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
    domestic_count: int
    international_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_count": self.candidate_count,
            "selected_count": self.selected_count,
            "domestic_count": self.domestic_count,
            "international_count": self.international_count,
            "sources": [source.to_dict() for source in self.sources],
        }


@dataclass(frozen=True)
class NewsFetchResult:
    candidates: list[RawNewsCandidate]
    report: NewsFetchReport
