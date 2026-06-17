import json

from app.blogger_distillation.service import tagging
from app.config import Settings
from app.models import BloggerPost, BloggerProfile


def _settings() -> Settings:
    return Settings(auth_secret="unit-test-secret")


def _tags(existing_json: str) -> list[tuple[str, str]]:
    return [(t["name"], t["source"]) for t in json.loads(existing_json)]


def test_merge_tags_replaces_auto_keeps_manual():
    existing = json.dumps(
        [
            {"name": "职场", "source": "manual"},
            {"name": "旧自动", "source": "auto"},
        ],
        ensure_ascii=False,
    )
    result = tagging.merge_tags(existing, ["新主题", "效率"])
    assert _tags(result) == [
        ("职场", "manual"),
        ("新主题", "auto"),
        ("效率", "auto"),
    ]


def test_merge_tags_dedupes_auto_against_manual():
    existing = json.dumps([{"name": "美妆", "source": "manual"}], ensure_ascii=False)
    result = tagging.merge_tags(existing, ["美妆", "护肤"])
    # 与 manual 同名的 auto 被丢弃。
    assert _tags(result) == [("美妆", "manual"), ("护肤", "auto")]


def test_merge_tags_handles_bad_json_and_limit():
    result = tagging.merge_tags("not-json", ["a", "b", "c"], limit=2)
    assert _tags(result) == [("a", "auto"), ("b", "auto")]


def test_set_manual_tags_replaces_manual_keeps_auto():
    existing = json.dumps(
        [
            {"name": "旧手动", "source": "manual"},
            {"name": "自动标签", "source": "auto"},
        ],
        ensure_ascii=False,
    )
    result = tagging.set_manual_tags(existing, ["手动A", "手动B"])
    assert _tags(result) == [
        ("手动A", "manual"),
        ("手动B", "manual"),
        ("自动标签", "auto"),
    ]


def test_set_manual_tags_dedupes_auto_against_new_manual():
    existing = json.dumps([{"name": "重叠", "source": "auto"}], ensure_ascii=False)
    result = tagging.set_manual_tags(existing, ["重叠", "独有"])
    # auto 与新 manual 同名时被丢弃,manual 优先。
    assert _tags(result) == [("重叠", "manual"), ("独有", "manual")]


def test_generate_auto_tags_cleans_and_caps(monkeypatch):
    def fake_model(settings, prompt, model=None):
        return {"tags": ["#带井号", " 留白 ", "留白", "超过十二个字的标签算太长了不要", "正常", "再一个", "第七个"]}

    monkeypatch.setattr(tagging, "create_json_response", fake_model)
    blogger = BloggerProfile(id=1, tenant_id=1, platform="xhs", display_name="测试", homepage_url="h")
    posts = [
        BloggerPost(id=1, tenant_id=1, blogger_id=1, external_id="p1", title="标题", body_text="正文", score=9.0)
    ]
    stats = {"frequent_hashtags": [{"tag": "话题A", "count": 3}]}
    tags = tagging.generate_auto_tags(_settings(), blogger, posts, stats, limit=5)
    # 去 # 号、去重(留白)、过滤超长、截断到 limit。
    assert tags == ["带井号", "留白", "正常", "再一个", "第七个"]
