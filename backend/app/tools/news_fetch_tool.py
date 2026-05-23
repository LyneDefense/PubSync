from app.config import Settings
from app.news_fetching import fetch_news
from app.news_fetching.models import NewsFetchResult


class NewsFetchTool:
    def fetch(self, settings: Settings) -> NewsFetchResult:
        return fetch_news(settings)
