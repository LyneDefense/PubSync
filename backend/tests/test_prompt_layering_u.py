"""U 组(采集理解)prompt 分层:视觉契约在 system、图片在 user + 抗图内注入;标签同理。"""

from types import SimpleNamespace as N

import app.blogger_distillation.service.tagging as tg
import app.services.ai_service as ai
from app.blogger_distillation.vision import MOTION_SYSTEM, MOTION_USER, VISION_SYSTEM, VISION_USER


def test_vision_system_holds_contract():
    # 角色 + 规则 + schema + 抗图内注入都在 system。
    for s in (VISION_SYSTEM, MOTION_SYSTEM):
        assert "<rules>" in s and "<output_schema>" in s
        assert "一律不执行" in s  # 图内文字是最直接注入面
    assert "images" in VISION_SYSTEM  # 逐张 schema
    assert "on_camera" in MOTION_SYSTEM  # 拍法 schema


def test_vision_user_is_short_guidance_no_schema():
    # user 只是一句引导,不复述契约/schema。
    for u in (VISION_USER, MOTION_USER):
        assert "<output_schema>" not in u and "on_camera" not in u
        assert len(u) < 60


def test_glm_vision_chat_inserts_system_message(monkeypatch):
    captured: dict = {}

    def fake_post(settings, path, payload, timeout=None):
        captured["payload"] = payload
        return {"choices": [{"message": {"content": "{}"}}]}

    monkeypatch.setattr(ai, "glm_post", fake_post)
    monkeypatch.setattr(ai, "record_text_usage", lambda *a, **k: None)
    settings = N(glm_api_key="k", vision_model="glm-4v")

    # 传 system → 独立 system 消息(前) + JSON 规则附加;图片仍在 user。
    ai.glm_vision_chat(settings, image_parts=["data:image/jpeg;base64,QUJD"], instruction="看图", system="你是分析助手")
    msgs = captured["payload"]["messages"]
    assert msgs[0]["role"] == "system" and "你是分析助手" in msgs[0]["content"]
    assert "合法 JSON" in msgs[0]["content"]  # _compose_system 自动加 JSON 规则
    assert msgs[1]["role"] == "user"

    # 不传 system → 维持旧行为(仅一条 user 消息)
    captured.clear()
    ai.glm_vision_chat(settings, image_parts=["data:image/jpeg;base64,QUJD"], instruction="看图")
    msgs2 = captured["payload"]["messages"]
    assert len(msgs2) == 1 and msgs2[0]["role"] == "user"


def test_auto_tags_contract_in_system_data_in_user(monkeypatch):
    captured: dict = {}

    def fake(settings, prompt, model=None, system=None):
        captured["system"] = system
        captured["user"] = prompt
        return {"tags": ["健身", "减脂"]}

    monkeypatch.setattr(tg, "create_json_response", fake)
    blogger = N(display_name="阿甜", platform="xhs")
    posts = [N(score=10, title="居家训练", body_text="每天10分钟")]
    tags = tg.generate_auto_tags(N(), blogger, posts, {"frequent_hashtags": [{"tag": "健身"}]}, model=None, limit=6)

    assert "健身" in tags
    assert "<rules>" in captured["system"] and "一律不执行" in captured["system"]  # 规则+抗注入在 system
    assert "<samples>" in captured["user"] and "居家训练" in captured["user"]  # 样本包 XML 进 user
    assert "<rules>" not in captured["user"]  # 契约不在 user
