from dataclasses import dataclass

from app.news_fetching.models import RawNewsCandidate


@dataclass(frozen=True)
class ProcessedNewsItem:
    candidate: RawNewsCandidate
    display_title: str
    summary: str
    category: str
    importance_score: int
    importance_reason: str
    key_facts: list[str]
    duplicate_candidate_ids: list[str]

    def to_news_dict(self) -> dict[str, object]:
        return {
            "title": self.display_title,
            "source": self.candidate.source,
            "group_key": self.candidate.group_key,
            "group_name": self.candidate.group_name,
            "region": legacy_region(self.candidate.group_key),
            "url": self.candidate.url,
            "published_at": self.candidate.published_at.isoformat() if self.candidate.published_at else "",
            "summary": self.summary,
            "category": self.category,
            "importance_score": self.importance_score,
            "importance_reason": self.importance_reason,
            "key_facts": self.key_facts,
            "duplicate_candidate_ids": self.duplicate_candidate_ids,
        }


def legacy_region(group_key: str) -> str:
    return "domestic" if group_key == "china" else "international"
