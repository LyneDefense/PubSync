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
            "图文笔记加配图:正文配合多张图阅读。**我们不替用户生成图,只给「配图方案」**——"
            "规划每张配图:用途、图上短文案、版式/画幅(如 竖版3:4·封面/步骤图/对比图)、以及一段可直接拿去 AI 工具生图的**中文** prompt(面向中文用户,prompt 全程用中文写)。"
            "绘图 prompt 禁止出现真人姓名、真人肖像、logo、品牌标识、平台 UI 截图,用干净可商用的概念图/场景图。"
        ),
        schema_fragment="""  "suitable_image_count": 0,
  "image_plan": [
    {"slot": 1, "purpose": "这张图的作用", "caption": "图上短文案", "format": "版式/画幅,如 竖版3:4·封面", "prompt": "中文生图提示词,例如:扁平插画风,一只橘猫蹲在猫粮碗前,暖色调,竖版3:4"}
  ]""",
        required_fields=["title", "body_text", "hashtags", "image_plan"],
    ),
    "spoken_script": ContentTypeSpec(
        label="口播脚本",
        instruction=(
            "口播脚本:为一个人对着镜头讲话设计。照上方对标博主的「开头钩子/拍法」来(不是通用模板)。"
            "script.hook 单列开头 3 秒钩子;segments 按时间轴给每段口播文案与字幕,中间信息密度高,结尾有引导。"
            "body_text 写一段发布说明。"
        ),
        schema_fragment="""  "script": {
    "duration_seconds": 0,
    "hook": "开头 3 秒钩子:第一句话怎么抓住人",
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
            "视频脚本:为成片设计分镜,照上方对标博主的「拍法·分镜/节奏/开头结构」来(不是通用模板)。"
            "script.hook 单列开头 3 秒钩子;script.pacing 给整体节奏(镜头快慢/平均几秒一切);"
            "segments 每段含景别/运镜(shot_type)、画面(scene)、口播旁白(voiceover)、字幕(subtitle)。"
            "产出是用户可照着拍的分镜蓝图(不是成片):运镜给方向,拍摄细节靠人。body_text 写一段发布说明。"
        ),
        schema_fragment="""  "script": {
    "duration_seconds": 0,
    "hook": "开头 3 秒钩子:第一句话/第一个画面怎么留住人",
    "pacing": "整体节奏建议,如 镜头偏快·平均 3-4 秒一切 / 慢节奏叙事",
    "segments": [
      {"start": "0s", "end": "5s", "shot_type": "景别/运镜,如 近景怼脸·固定 / 中景·手持跟拍", "scene": "画面/镜头建议", "voiceover": "口播/旁白", "subtitle": "屏幕字幕"}
    ],
    "shooting_notes": ["拍摄建议(器材/光线/剪辑)"]
  }""",
        required_fields=["title", "body_text", "hashtags", "script"],
    ),
}
