from types import SimpleNamespace

from app.skill_optimization import rollout as ro


def _post(**kw):
    base = dict(title="标题A", body_text="正文内容", transcript_text="", content_subtype="image_text")
    base.update(kw)
    return SimpleNamespace(**base)


def test_modality_of():
    assert ro.modality_of("talking_video") == "talking_video"
    assert ro.modality_of("image_text") == "image_text"
    assert ro.modality_of("visual_video") == "image_text"
    assert ro.modality_of("unknown") == "image_text"


def test_extract_topic_prefers_title():
    assert ro.extract_topic(_post(title="如何省钱")) == "如何省钱"
    assert ro.extract_topic(_post(title="", body_text="第一行\n第二行")) == "第一行"


def test_gold_text_image_text():
    g = ro.gold_text(_post(title="标题", body_text="正文"), "image_text")
    assert "标题" in g and "正文" in g


def test_gold_text_video_strips_timestamps():
    p = _post(content_subtype="talking_video", transcript_text="大家好[0:0.000,1:0.280]今天聊省钱")
    g = ro.gold_text(p, "talking_video")
    assert "[0:0.000,1:0.280]" not in g
    assert "大家好" in g and "今天聊省钱" in g


def test_build_prompt_contains_topic_skill_and_modality():
    prompt = ro.build_generation_prompt("我的打法XYZ", "省钱技巧", "talking_video")
    assert "省钱技巧" in prompt and "我的打法XYZ" in prompt and "口播" in prompt
    prompt2 = ro.build_generation_prompt("skill", "topic", "image_text")
    assert "图文" in prompt2


def test_generate_with_skill_parses_content(monkeypatch):
    monkeypatch.setattr(ro, "create_json_response", lambda *a, **k: {"content": "生成的正文"})
    out = ro.generate_with_skill(object(), "skill", "topic", "image_text")
    assert out == "生成的正文"
