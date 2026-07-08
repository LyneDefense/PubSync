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
    # video_script 映射视频车道;缺则回落到有内容的车道(老 skill 的口播)
    d = {"content_lanes": {"talking_video": {"title_formulas": ["口播标题"]}}}
    kit = build_creation_kit(d, "video_script")
    assert "口播标题" in kit


def _dist_collapsed():
    """lane-collapse 之后的画像:content_lanes 只有 image_text / video 两条(话术+拍法合一)。"""
    return {
        "content_lanes": {
            "image_text": {"title_formulas": ["图文数字标题"], "cover_text_rules": ["三段式封面"]},
            "video": {
                "title_formulas": ["视频钩子标题"],
                "opening_templates": ["开头怼脸提问"],
                "video_script_structures": ["3秒怼脸抛问题", "中景演示分3步"],
            },
        },
    }


def test_creation_kit_video_reads_collapsed_video_lane():
    # 回归:车道收敛后,口播脚本 + 视频脚本都读 video 车道(拍法),绝不回落到图文车道。
    d = _dist_collapsed()
    for content_type in ("spoken_script", "video_script"):
        kit = build_creation_kit(d, content_type)
        assert "视频钩子标题" in kit and "3秒怼脸抛问题" in kit  # 视频车道拍法
        assert "图文数字标题" not in kit                          # 不落到图文车道


def test_creation_kit_video_lane_labels_shooting_method():
    # video 车道把「结构骨架」显式呈现为拍法,让创作照这个博主的拍法来。
    kit = build_creation_kit(_dist_collapsed(), "video_script")
    assert "拍法·分镜/节奏/开头结构" in kit


def test_creation_kit_image_still_reads_image_lane_after_collapse():
    kit = build_creation_kit(_dist_collapsed(), "image_note")
    assert "图文数字标题" in kit and "视频钩子标题" not in kit
