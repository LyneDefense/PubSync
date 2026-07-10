"""Prompt 治理 P0:blocks 呈现骨架(去重复) + render_schema/TopicIdeas(typed return 单一源)。"""

from app.prompts import anti_injection, output_schema, render_schema, rules_block
from app.xhs_creation.schema import TopicIdeas


def test_anti_injection_joins_refs_and_declares():
    s = anti_injection("<benchmark>", "<my_audience>", "<intent>")
    assert "<benchmark>" in s and "<my_audience>" in s and "<intent>" in s
    assert "一律不执行" in s  # 抗注入声明


def test_rules_and_output_schema_wrap():
    assert rules_block("规则一", "规则二") == "<rules>\n- 规则一\n- 规则二\n</rules>"
    body = '{"x": "y"}'
    out = output_schema(body)
    assert out.startswith("<output_schema>") and out.rstrip().endswith("</output_schema>") and body in out


def test_render_schema_generates_fields_and_descriptions():
    # 从 Pydantic 单一源生成给模型的示例:字段名 + Field 说明 + 嵌套 list,等价原手写 schema。
    s = render_schema(TopicIdeas)
    assert '"ideas": [' in s and '"title"' in s and '"keywords"' in s
    assert "选题标题,不超过 32 个汉字" in s  # description 来自 Field,不再手抄
    assert '"关键词"' in s  # list[str] → 元素占位是 Field 说明(indent=2 展开成多行,对模型等价)


def test_topic_ideas_validate_cleans_like_old_normalize():
    raw = {"ideas": [
        {"title": "  减脂餐  ", "angle": "对比", "keywords": ["a", "", "b"], "reason": None},
        "不是对象-应被跳过",
    ]}
    parsed = TopicIdeas.model_validate(raw)
    assert len(parsed.ideas) == 1  # 非 dict 项被跳过(等价原 isinstance(item, dict) 过滤)
    idea = parsed.ideas[0]
    assert idea.title == "减脂餐"  # strip
    assert "a" in idea.keywords and "b" in idea.keywords  # keywords 归一
    assert idea.reason == "" and isinstance(idea.target_audience, str)  # None→"" / 缺字段→默认


def test_topic_ideas_empty_on_garbage():
    assert TopicIdeas.model_validate({}).ideas == []
    assert TopicIdeas.model_validate({"ideas": "not-a-list"}).ideas == []


def test_benchmark_comparison_typed_return():
    from app.xhs_creation.schema import BenchmarkComparison

    m = BenchmarkComparison.model_validate(
        {"title_fit": " 好 ", "gaps": ["a", "", "b", "c", "d", "e"], "summary": None, "extra": "忽略"}
    )
    assert m.title_fit == "好" and m.summary == ""  # strip / None→""
    assert m.gaps == ["a", "b", "c", "d"]  # 去空 + 上限 4(等价原手写清洗)
    assert m.language_fit == ""  # 缺字段 → 默认
