"""可被后台覆盖的配置字段白名单 + 元数据。

只收录「运营/AI 相关」字段。**基础设施字段**(database_url / redis_url / auth_secret /
config_encryption_key / static_dir / use_task_queue / cors_origins / 队列连接等)**不在此**,
仍只走 .env,避免在运行时把自己锁死或泄露引导密钥。
"""

from __future__ import annotations

from dataclasses import dataclass

FieldType = str  # "str" | "int" | "bool" | "float"


@dataclass(frozen=True)
class ConfigField:
    key: str
    group: str
    label: str
    type: FieldType = "str"
    is_secret: bool = False


# 分组展示顺序与中文名。
GROUPS: list[tuple[str, str]] = [
    ("model", "模型与生成"),
    ("tikhub", "采集 / TikHub"),
    ("benchmark", "对标博主搜寻"),
    ("asr", "ASR 语音转写"),
    ("vision", "视觉理解(图片)"),
    ("dashboard", "效果看板"),
]


OVERRIDABLE: list[ConfigField] = [
    # —— 模型与生成 ——
    ConfigField("llm_provider", "model", "文本模型供应商 (openai/minimax/claude/glm)"),
    ConfigField("image_provider", "model", "图像模型供应商 (openai/minimax)"),
    ConfigField("glm_base_url", "model", "智谱 GLM Base URL"),
    ConfigField("glm_api_key", "model", "智谱 GLM API Key", is_secret=True),
    ConfigField("glm_text_model", "model", "GLM 文本模型 (如 glm-4.6 / glm-4.7-flash)"),
    ConfigField("glm_image_model", "model", "GLM 图像模型 (CogView, 如 cogview-4-250304)"),
    ConfigField("glm_asr_model", "model", "GLM 语音识别模型 (glm-asr-2512)"),
    ConfigField("openai_base_url", "model", "OpenAI Base URL"),
    ConfigField("openai_api_key", "model", "OpenAI API Key", is_secret=True),
    ConfigField("openai_text_model", "model", "OpenAI 文本模型"),
    ConfigField("openai_image_model", "model", "OpenAI 图像模型"),
    ConfigField("minimax_base_url", "model", "MiniMax Base URL"),
    ConfigField("minimax_api_key", "model", "MiniMax API Key", is_secret=True),
    ConfigField("minimax_text_model", "model", "MiniMax 文本模型"),
    ConfigField("minimax_image_model", "model", "MiniMax 图像模型"),
    ConfigField("anthropic_base_url", "model", "Anthropic Base URL"),
    ConfigField("anthropic_api_key", "model", "Anthropic/Claude API Key", is_secret=True),
    ConfigField("anthropic_text_model", "model", "Claude 文本模型 (如 claude-sonnet-4-6)"),
    ConfigField("distill_text_model", "model", "蒸馏/体检专用文本模型(留空=用上面的)"),
    ConfigField("blogger_auto_tag_enabled", "model", "采集后自动打内容标签(LLM)", "bool"),
    ConfigField("blogger_tag_model", "model", "标签提炼专用模型(留空=用蒸馏模型)"),
    ConfigField("blogger_tag_max", "model", "自动标签数量上限", "int"),
    ConfigField("synthesis_max_revise_iterations", "model", "蒸馏-最大修订次数", "int"),
    ConfigField("synthesis_min_quality_score", "model", "蒸馏-质量阈值", "int"),
    ConfigField("synthesis_llm_critic_enabled", "model", "蒸馏-启用 LLM 评审", "bool"),
    ConfigField("distill_evidence_char_budget", "model", "蒸馏-证据字符预算", "int"),
    ConfigField("distill_evidence_legacy", "model", "蒸馏-用旧证据供给(A/B对照)", "bool"),
    # —— 博主档案 ——
    ConfigField("dossier_default_full_count", "dossier", "建档-默认详情级篇数(最新N)", "int"),
    ConfigField("dossier_incremental_known_streak", "dossier", "笔记池增量-连续已知即停条数", "int"),
    ConfigField("portrait_stale_new_posts", "dossier", "画像过时-新增笔记阈值", "int"),
    ConfigField("portrait_stale_days", "dossier", "画像过时-天数阈值", "int"),
    ConfigField("creation_max_revise_iterations", "model", "创作-最大修订次数", "int"),
    ConfigField("creation_min_quality_score", "model", "创作-质量阈值", "int"),
    ConfigField("creation_llm_critic_enabled", "model", "创作-启用 LLM 评审", "bool"),
    ConfigField("creation_compliance_enabled", "model", "创作-启用限流词规避", "bool"),
    ConfigField("audit_max_revise_iterations", "model", "体检-最大修订次数", "int"),
    ConfigField("audit_min_quality_score", "model", "体检-质量阈值", "int"),
    ConfigField("audit_llm_critic_enabled", "model", "体检-启用 LLM 评审", "bool"),
    # —— 效果看板 ——
    ConfigField("dashboard_minutes_write_per_post", "dashboard", "省时-手写一篇估时(分钟)", "int"),
    ConfigField("dashboard_minutes_ai_draft_per_post", "dashboard", "省时-AI起草一篇估时(分钟)", "int"),
    ConfigField("dashboard_minutes_research_per_distill", "dashboard", "省时-一次蒸馏省下研究估时(分钟)", "int"),
    ConfigField("dashboard_viral_multiplier", "dashboard", "爆款判定倍数(高于自身均值)", "float"),
    # —— 采集 / TikHub ——
    ConfigField("tikhub_base_url", "tikhub", "TikHub Base URL"),
    ConfigField("tikhub_api_key", "tikhub", "TikHub API Key", is_secret=True),
    ConfigField("tikhub_request_price_usd", "tikhub", "单请求估价 (USD)", "float"),
    ConfigField("tikhub_min_request_price_usd", "tikhub", "单请求估价下限 (USD)", "float"),
    ConfigField("tikhub_max_request_price_usd", "tikhub", "单请求估价上限 (USD)", "float"),
    ConfigField("tikhub_min_request_interval_seconds", "tikhub", "请求最小间隔(秒,0=不限)", "float"),
    # —— 对标博主搜寻 ——
    ConfigField("benchmark_weight_relevance", "benchmark", "综合分权重-方向契合", "float"),
    ConfigField("benchmark_weight_learnability", "benchmark", "综合分权重-可对标性", "float"),
    ConfigField("benchmark_weight_popularity", "benchmark", "综合分权重-火爆度", "float"),
    ConfigField("benchmark_weight_transferability", "benchmark", "综合分权重-可迁移度", "float"),
    ConfigField("benchmark_candidate_pool_cap", "benchmark", "候选池上限(个)", "int"),
    ConfigField("benchmark_list_sample", "benchmark", "每个候选取列表笔记数", "int"),
    ConfigField("benchmark_search_terms_max", "benchmark", "搜索词扩展上限(个)", "int"),
    ConfigField("benchmark_inactive_days", "benchmark", "不活跃判定阈值(天)", "int"),
    # —— ASR ——
    ConfigField("asr_enabled", "asr", "启用 ASR(全局;用户端不可选)", "bool"),
    ConfigField("modality_density_high_cps", "asr", "模态-口播密度上阈(字/秒,≥判口播)", "float"),
    ConfigField("modality_density_low_cps", "asr", "模态-非口播密度下阈(字/秒,≤判非口播)", "float"),
    ConfigField("modality_llm_adjudicate_enabled", "asr", "模态-模糊带启用 LLM 语义裁决", "bool"),
    ConfigField("asr_provider", "asr", "ASR 供应商 (glm_asr / tencent_rec_task)"),
    ConfigField("asr_max_duration_seconds", "asr", "最大时长(秒)", "int"),
    ConfigField("asr_poll_interval_seconds", "asr", "轮询间隔(秒)", "int"),
    ConfigField("asr_timeout_seconds", "asr", "总超时(秒)", "int"),
    ConfigField("tencent_asr_secret_id", "asr", "腾讯 ASR SecretId", is_secret=True),
    ConfigField("tencent_asr_secret_key", "asr", "腾讯 ASR SecretKey", is_secret=True),
    ConfigField("tencent_asr_region", "asr", "腾讯 ASR Region"),
    ConfigField("tencent_asr_engine_model_type", "asr", "腾讯 ASR 引擎模型"),
    ConfigField("tencent_cos_secret_id", "asr", "腾讯 COS SecretId", is_secret=True),
    ConfigField("tencent_cos_secret_key", "asr", "腾讯 COS SecretKey", is_secret=True),
    ConfigField("tencent_cos_region", "asr", "腾讯 COS Region"),
    ConfigField("tencent_cos_bucket", "asr", "腾讯 COS Bucket"),
    ConfigField("tencent_cos_prefix", "asr", "腾讯 COS 路径前缀"),
    # —— 视觉理解(图片) ——
    ConfigField("vision_enabled", "vision", "启用视觉理解(全局;用户端不可选)", "bool"),
    ConfigField("vision_provider", "vision", "视觉供应商 (glm)"),
    ConfigField("vision_model", "vision", "视觉模型 (glm-4.6v / glm-4.5v / glm-4v-plus-0111)"),
    ConfigField("vision_scope", "vision", "解析范围 (cover=仅封面 / cover_body=封面+正文图)"),
    ConfigField("vision_max_images_per_note", "vision", "每篇正文图上限(封面另计)", "int"),
]

FIELDS_BY_KEY: dict[str, ConfigField] = {f.key: f for f in OVERRIDABLE}


def coerce(field: ConfigField, raw: str):
    """把存库的字符串值转成对应的 Python 类型,用于 setattr 到 Settings。"""
    value = (raw or "").strip()
    if field.type == "bool":
        return value.lower() in {"1", "true", "yes", "on"}
    if field.type == "int":
        return int(value or "0")
    if field.type == "float":
        return float(value or "0")
    return raw  # str:保留原值(可含前后空白以外的内容)
