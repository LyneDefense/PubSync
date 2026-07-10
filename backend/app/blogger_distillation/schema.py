"""蒸馏输出的 typed return(Pydantic 单一源)。见 docs/prompt治理_方案设计.md 支柱一 + backlog distill-schema-single-source。

一份模型同时驱动:(a) prompt 的 <output_schema> 段(render_schema 生成) (b) normalize 的解析校验
(model_validate) (c) 下游静态类型。字段名/说明只活在这里,消灭「手抄 7 处」的 drift。

`_LooseModel` 承接旧 normalize 的宽松清洗:list 字段单值转 list/None→[](旧 `_as_list`)、str 字段 None→''、
extra=ignore 丢 schema 外字段、缺字段补默认。model_validate(raw).model_dump() 的结构 == 旧 normalize 产出,
故 sensor/质量分/artifacts/creation_kit(全收 dict)零改动。
"""

from __future__ import annotations

import typing

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _as_list(value: typing.Any) -> list:
    return value if isinstance(value, list) else ([] if value in (None, "") else [value])


class _LooseModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: typing.Any) -> typing.Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        for name, field in cls.model_fields.items():
            if name not in out:
                continue
            ann = field.annotation
            if typing.get_origin(ann) is list:
                items = _as_list(out[name])
                args = typing.get_args(ann)
                item_type = args[0] if args else str
                if isinstance(item_type, type) and issubclass(item_type, BaseModel):
                    items = [x for x in items if isinstance(x, dict)]  # 非对象项跳过(等价旧宽松)
                out[name] = items
            elif ann is str and out[name] is None:
                out[name] = ""
        return out


# —— 内核(认知 / 策略 / 人设) —— #

class Persona(_LooseModel):
    identity: str = Field("", description="身份感/人设")
    stance: str = Field("", description="表达姿态")
    trust_source: str = Field("", description="信任来源")


class Voice(_LooseModel):
    self_ref: str = Field("", description="自称方式（如'阿璐我啊'）")
    tone: str = Field("", description="语气一句话")
    catchphrases: list[str] = Field(default_factory=list, description="高频口头禅/标志性表达")


class CognitiveLayer(_LooseModel):
    core_beliefs: list[str] = Field(default_factory=list, description="核心信念：TA 默认相信什么")
    opinion_tensions: list[str] = Field(default_factory=list, description="观点张力/反共识：TA 常对抗的常识")
    value_stance: list[str] = Field(default_factory=list, description="价值立场")


class AngleLayer(_LooseModel):
    topic_method: list[str] = Field(
        default_factory=list,
        description="选题方法/思路（最高杠杆、可迁移到别的赛道）：TA 怎么**决定做什么题**，如'从已验证爆款反推可复用结构，再套自己话术二次表达'",
    )
    topic_angles: list[str] = Field(default_factory=list, description="从观点张力推出的选题角度（可迁移的'从什么角度切'，不是具体标题）")
    trend_hijacking: list[str] = Field(default_factory=list, description="蹭热点/借势方式")


class SelfDiagnosis(_LooseModel):
    strengths: list[str] = Field(default_factory=list, description="模式B：账号优势")
    weaknesses: list[str] = Field(default_factory=list, description="模式B：明显短板")
    action_plan: list[str] = Field(default_factory=list, description="模式B：可立即执行的增长动作")


class CoreDistillation(_LooseModel):
    one_glance: str = Field("", description="一句话说清这个账号的价值和爆款原因（带关键数字）")
    persona: Persona = Field(default_factory=Persona)
    voice: Voice = Field(default_factory=Voice)
    audience: str = Field("", description="目标读者画像")
    cognitive_layer: CognitiveLayer = Field(default_factory=CognitiveLayer)
    angle_layer: AngleLayer = Field(default_factory=AngleLayer)
    comment_insights: list[str] = Field(default_factory=list, description="评论区暴露的读者真实需求和互动机会")
    do_not_do: list[str] = Field(default_factory=list, description="创作禁区/不该模仿的部分")
    self_diagnosis: SelfDiagnosis = Field(default_factory=SelfDiagnosis)
    core_conclusion: str = Field("", description="给用户的核心使用建议（一段话）")

    @field_validator("persona", mode="before")
    @classmethod
    def _persona_wrap(cls, v: typing.Any) -> typing.Any:
        # 旧 normalize:persona 非 dict → {identity: str(persona)}。
        return v if isinstance(v, dict) else {"identity": str(v or ""), "stance": "", "trust_source": ""}

    @field_validator("voice", "cognitive_layer", "angle_layer", "self_diagnosis", mode="before")
    @classmethod
    def _nested_dict(cls, v: typing.Any) -> typing.Any:
        # 旧 normalize:非 dict → {}(再由子模型默认补齐)。
        return v if isinstance(v, dict) else {}


# —— 车道(内容层,按模态) —— #

class TopPostBreakdown(_LooseModel):
    rank: int = Field(0)
    title_ref: str = Field("", description="该车道爆款样本标题(可截断)")
    source: str = Field("", description="external_id 或标题")
    why_viral: str = Field("", description="为什么火（贴数据）")
    reusable_tactic: str = Field("", description="可复用的具体技巧")


class LaneContent(_LooseModel):
    title_formulas: list[str] = Field(default_factory=list, description="标题公式 TOP5，结合 title_patterns 的占比")
    opening_templates: list[str] = Field(default_factory=list, description="开头模板 TOP3，结合 opening_patterns")
    body_structures: list[str] = Field(default_factory=list, description="图文正文结构，只能基于 body_text；非图文车道见车道说明")
    video_script_structures: list[str] = Field(default_factory=list, description="视频口播/字幕结构，只能基于 transcript；无转写则空数组")
    emotional_rhythm: list[str] = Field(default_factory=list, description="情绪节奏/留人钩子公式")
    language_dna: list[str] = Field(default_factory=list, description="语言 DNA：高频表达、句式节奏、人称策略、口头禅（按车道说明加「书面：」/「口播：」前缀）")
    cta_strategy: list[str] = Field(default_factory=list, description="CTA/互动引导策略，结合 cta_patterns")
    cover_text_rules: list[str] = Field(default_factory=list, description="封面文案规律")
    visual_layout_patterns: list[str] = Field(default_factory=list, description="图内信息编排/版式套路：图内要点如何分屏/分卡/分步编排（图文车道；非图文留空数组）")
    hashtag_strategy: list[str] = Field(default_factory=list, description="标签策略，结合 frequent_hashtags")
    top_post_breakdowns: list[TopPostBreakdown] = Field(default_factory=list)
