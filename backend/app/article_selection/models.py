from dataclasses import dataclass

from app.models import NewsItem


@dataclass(frozen=True)
class RegionSelectionRule:
    region: str
    minimum: int
    target: int
    maximum: int

    def normalized(self, article_limit: int) -> "RegionSelectionRule":
        maximum = max(0, min(self.maximum, article_limit))
        target = max(0, min(self.target, maximum))
        minimum = max(0, min(self.minimum, target))
        return RegionSelectionRule(
            region=self.region,
            minimum=minimum,
            target=target,
            maximum=maximum,
        )


@dataclass(frozen=True)
class ArticleSelectionResult:
    news_items: list[NewsItem]
    domestic_count: int
    international_count: int
    total_available: int
