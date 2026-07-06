"""创作套件装配(build_creation_kit):按内容类型选模态车道 + 内核声音 + 选题 + 红线(纯函数,无 LLM)。"""

from app.xhs_creation.agent.creation_kit import build_creation_kit


def _dist():
    return {
        "one_glance": "确定性叙事",
        "voice": {"self_ref": "阿璐", "tone": "克制专业", "catchphrases": ["别踩坑"]},
        "angle_layer": {"topic_method": ["对比反推"], "topic_angles": ["A vs B"]},
        "comment_insights": ["多少钱", "适合谁"],
        "compliance_watchouts": ["绝对化用语：顶级"],
        "do_not_do": ["别抄原文"],
        "content_lanes": {
            "image_text": {"title_formulas": ["数字型标题"], "cover_text_rules": ["三段式封面"], "language_dna": ["书面：短句"]},
            "talking_video": {"title_formulas": ["口播钩子标题"], "video_script_structures": ["痛点开场"]},
        },
    }


def test_creation_kit_picks_lane_by_content_type():
    kit_img = build_creation_kit(_dist(), "image_note")
    assert "数字型标题" in kit_img and "三段式封面" in kit_img  # 图文车道
    assert "口播钩子标题" not in kit_img  # 不混口播车道
    kit_spk = build_creation_kit(_dist(), "spoken_script")
    assert "口播钩子标题" in kit_spk and "痛点开场" in kit_spk  # 口播车道


def test_creation_kit_includes_voice_topic_redlines():
    kit = build_creation_kit(_dist(), "image_note")
    assert "阿璐" in kit and "克制专业" in kit            # 人设声音
    assert "对比反推" in kit                               # 选题方法
    assert "多少钱" in kit                                 # 读者最常问
    assert "绝对化用语：顶级" in kit and "别抄原文" in kit  # 红线


def test_creation_kit_empty_when_no_lanes():
    assert build_creation_kit(None, "image_note") == ""
    assert build_creation_kit({}, "image_note") == ""
    assert build_creation_kit({"content_lanes": {}}, "image_note") == ""


def test_creation_kit_falls_back_to_any_present_lane():
    # video_script 映射非口播车道;缺则回落到有内容的车道(口播)
    d = {"content_lanes": {"talking_video": {"title_formulas": ["口播标题"]}}}
    kit = build_creation_kit(d, "video_script")
    assert "口播标题" in kit
