from dataclasses import dataclass

from app.models import NewsItem


@dataclass(frozen=True)
class GroupSelectionRule:
    group_key: str
    group_name: str
    minimum: int
    target: int
    maximum: int
    position: int

    def normalized(self, article_limit: int) -> "GroupSelectionRule":
        maximum = max(0, min(self.maximum, article_limit))
        target = max(0, min(self.target, maximum))
        minimum = max(0, min(self.minimum, target))
        return GroupSelectionRule(
            group_key=self.group_key,
            group_name=self.group_name,
            minimum=minimum,
            target=target,
            maximum=maximum,
            position=self.position,
        )


@dataclass(frozen=True)
class ArticleSelectionResult:
    news_items: list[NewsItem]
    group_counts: dict[str, int]
    total_available: int
