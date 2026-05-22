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
    title: str
    url: str
    source: str
    region: NewsRegion
    published_at: datetime | None
    summary: str

    def to_prompt_dict(self) -> dict[str, str]:
        return {
            "title": self.title,
            "source": self.source,
            "region": self.region.value,
            "url": self.url,
            "published_at": self.published_at.isoformat() if self.published_at else "",
            "summary": self.summary,
        }
