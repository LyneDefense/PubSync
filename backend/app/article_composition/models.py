from dataclasses import dataclass


@dataclass(frozen=True)
class ArticleSection:
    news_index: int
    group_key: str
    group_name: str
    heading: str
    paragraphs: list[str]
    editor_note: str
    image_url: str
    source_name: str
    source_url: str


@dataclass(frozen=True)
class ComposedArticle:
    title: str
    intro: str
    cover_prompt: str
    sections: list[ArticleSection]
