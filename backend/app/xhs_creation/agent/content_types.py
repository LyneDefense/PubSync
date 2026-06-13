"""内容类型规格:四种创作类型各自的结构指令、输出字段片段、必填项。

新增类型只需往 CONTENT_TYPE_SPECS 加一项。base 字段(标题/正文/标签/封面文案)所有类型共有,
这里的 schema_fragment 只补该类型额外需要的字段。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ContentTypeSpec:
    label: str
    instruction: str
    schema_fragment: str
    required_fields: list[str] = field(default_factory=list)


# 所有类型共有的基础输出字段(在 guide 里和各类型 schema_fragment 拼接)。
BASE_SCHEMA = """  "title": "标题",
  "body_text": "可直接复制发布的正文(分段、口语自然)",
  "hashtags": ["话题标签,不要带#号"],
  "cover_text": "封面文案,最多 18 个字\""""


CONTENT_TYPE_SPECS: dict[str, ContentTypeSpec] = {
    "text_note": ContentTypeSpec(
        label="纯文字笔记",
        instruction=(
            "纯文字笔记:不配图、不写脚本。正文要靠文字本身留住人——开头一句钩子,中间分段讲清楚一个点,"
            "结尾给互动引导。image_plan 和 script 都留空。"
        ),
        schema_fragment="",
        required_fields=["title", "body_text", "hashtags"],
    ),
    "image_note": ContentTypeSpec(
        label="图文笔记加配图",
        instruction=(
            "图文笔记加配图:正文配合多张图阅读。需要规划每张配图(用途、图上短文案、英文绘图 prompt)。"
            "绘图 prompt 禁止出现真人姓名、真人肖像、logo、品牌标识、平台 UI 截图,用干净可商用的概念图/场景图。"
        ),
        schema_fragment="""  "suitable_image_count": 0,
  "image_plan": [
    {"slot": 1, "purpose": "这张图的作用", "caption": "图上短文案", "prompt": "English image generation prompt"}
  ]""",
        required_fields=["title", "body_text", "hashtags", "image_plan"],
    ),
    "spoken_script": ContentTypeSpec(
        label="口播脚本",
        instruction=(
            "口播脚本:为一个人对着镜头讲话设计。script.segments 按时间轴给出每段的口播文案与字幕,"
            "开头要有强钩子,中间信息密度高,结尾有引导。body_text 写一段发布说明。"
        ),
        schema_fragment="""  "script": {
    "duration_seconds": 0,
    "segments": [
      {"start": "0s", "end": "5s", "voiceover": "口播原话", "subtitle": "屏幕字幕"}
    ],
    "shooting_notes": ["口播/拍摄建议"]
  }""",
        required_fields=["title", "body_text", "hashtags", "script"],
    ),
    "video_script": ContentTypeSpec(
        label="视频脚本",
        instruction=(
            "视频脚本:为成片设计分镜。script.segments 每段含画面/镜头建议(scene)、口播旁白、字幕;"
            "开头钩子前置,注意节奏。body_text 写一段发布说明。"
        ),
        schema_fragment="""  "script": {
    "duration_seconds": 0,
    "segments": [
      {"start": "0s", "end": "5s", "scene": "画面/镜头建议", "voiceover": "口播/旁白", "subtitle": "屏幕字幕"}
    ],
    "shooting_notes": ["拍摄建议"]
  }""",
        required_fields=["title", "body_text", "hashtags", "script"],
    ),
}
