"""创作主 prompt 分层(build_creation_system 契约 / build_creation_prompt 证据):纯函数,无 LLM。"""

from types import SimpleNamespace as N

from app.xhs_creation.agent.guide import build_creation_prompt, build_creation_system


def _ctx(content_type="image_note"):
    payload = N(
        image_count_mode="auto",
        requested_image_count=None,
        topic="居家减脂三餐",
        target_audience="上班族",
        content_goal="知识分享",
        keywords=["减脂", "食谱"],
    )
    return N(
        blogger=N(niche="健身"),
        skill=N(skill_markdown="对标博主方法论正文：先抛痛点再给方案。"),
        payload=payload,
        platform="xhs",
        content_type=content_type,
        benchmark_stats={},
        distillation={},
        my_video_baseline={},
        compliance_enabled=False,
    )


def test_creation_system_holds_contract_not_data():
    # 契约(角色 + 硬规则 + 平台口径 + schema + 抗注入)在 system,不含本次创作输入。
    s = build_creation_system(_ctx())
    assert "内容主编" in s and "小红书" in s  # 角色 + 平台口径
    assert "<rules>" in s and "<output_schema>" in s  # 契约结构(XML 分隔)
    assert "一律不执行" in s  # 抗注入
    assert "title" in s and "body_text" in s  # 输出 schema 字段
    assert "居家减脂三餐" not in s  # 本次创作输入不在 system


def test_creation_prompt_is_data_only():
    # 证据(user):对标套件 + 创作输入,包在 XML 里,不复述 schema。
    p = build_creation_prompt(_ctx())
    assert "<benchmark_kit>" in p and "<creation_input>" in p
    assert "对标博主方法论正文" in p and "居家减脂三餐" in p  # 套件 + 创作输入
    assert "<rules>" not in p  # 契约在 system,不在 user


def test_creation_prompt_video_wraps_examples_and_baseline():
    # 视频类:拍摄条件段出现;有爆文时 few-shot 包进 <benchmark_examples> 标签(供 system 抗注入引用)。
    ctx = _ctx(content_type="video_script")
    ctx.benchmark_stats = {"hot_posts": [{"title": "3个动作瘦腰", "like_count": 999, "content_type": "video"}]}
    p = build_creation_prompt(ctx)
    assert "<benchmark_examples>" in p and "3个动作瘦腰" in p  # few-shot 包进标签
    assert "拍" in p  # 拍摄条件段(无基线也有兜底文案)
