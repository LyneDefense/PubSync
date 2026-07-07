"""P3 爆文 few-shot:创作 prompt 前置对标博主真实爆文示例。

锁:
1. 有 hot_posts → 渲染标题/互动/片段/标签 + 「严禁照抄」护栏。
2. 无 hot_posts / benchmark_stats 空 → 空串(不挡路)。
3. 按内容形态挑同模态(图文创作挑图文爆文,视频创作挑视频爆文);同模态缺失则回落全部。
"""

from types import SimpleNamespace

from app.xhs_creation.agent.guide import _hot_examples_block


def _ctx(content_type, hot):
    return SimpleNamespace(content_type=content_type, benchmark_stats={"hot_posts": hot})


_IMG = {"title": "3步看懂配料表", "content_type": "normal", "like_count": 1200, "favorite_count": 300,
        "body_excerpt": "第一位是肉才算合格\n别被包装骗了", "hashtags": ["#猫粮", "#避坑"]}
_VID = {"title": "养猫第一年踩的坑", "content_type": "video", "like_count": 5000, "favorite_count": 800,
        "body_excerpt": "", "hashtags": []}


def test_empty_when_no_hot_posts():
    assert _hot_examples_block(_ctx("text_note", [])) == ""
    assert _hot_examples_block(SimpleNamespace(content_type="text_note", benchmark_stats={})) == ""


def test_renders_title_engagement_and_guard():
    block = _hot_examples_block(_ctx("image_note", [_IMG]))
    assert "3步看懂配料表" in block
    assert "1200赞" in block and "300藏" in block
    assert "第一位是肉才算合格" in block  # 片段换行被压平
    assert "#猫粮" in block
    assert "严禁照抄" in block


def test_prefers_same_modality():
    # 图文创作 → 只挑图文爆文(normal),不选视频那条
    block = _hot_examples_block(_ctx("text_note", [_VID, _IMG]))
    assert "3步看懂配料表" in block
    assert "养猫第一年踩的坑" not in block


def test_falls_back_to_all_when_no_same_modality():
    # 视频创作但只有图文爆文 → 回落展示图文,不至于空
    block = _hot_examples_block(_ctx("video_script", [_IMG]))
    assert "3步看懂配料表" in block


def test_caps_to_limit():
    many = [dict(_IMG, title=f"标题{i}") for i in range(10)]
    block = _hot_examples_block(_ctx("text_note", many), limit=3)
    assert block.count("赞·") == 3
