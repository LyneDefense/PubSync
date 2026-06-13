"""平台规格:每个平台一套创作口径。新增平台只需往 PLATFORM_SPECS 加一项。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformSpec:
    name: str
    title_rule: str
    tone_rule: str
    cta_rule: str
    hashtag_rule: str
    compliance_note: str


PLATFORM_SPECS: dict[str, PlatformSpec] = {
    "xhs": PlatformSpec(
        name="小红书",
        title_rule="标题最多 20 字,要具体、有信息量或情绪钩子,避免标题党空话",
        tone_rule="第一人称真诚分享/种草口吻,口语自然,emoji 克制(全文 1-4 个,不堆砌)",
        cta_rule="结尾给一句轻量互动引导(求收藏/问问大家/欢迎评论区补充),不要硬广",
        hashtag_rule="6-10 个精准话题标签,垂类词+场景词混搭,不要带 # 号",
        compliance_note="不夸大功效、不承诺疗效、不编造数据;涉及专业信息用温和、可求证的表达",
    ),
    "douyin": PlatformSpec(
        name="抖音",
        title_rule="标题/开场钩子前置,前 3 秒就要抛出冲突或好处,制造继续看的理由",
        tone_rule="口语化、节奏快、有镜头感,适合念出来;短句为主",
        cta_rule="引导点赞关注收藏、在评论区追问或留话题,鼓励完播",
        hashtag_rule="3-6 个标签,热点话题+垂类标签混搭,不要带 # 号",
        compliance_note="不夸大功效、不承诺疗效、不编造数据;敏感品类避免违规表述",
    ),
    # 公众号槽位:架构预留,本轮不接线(service 仅放行 xhs/douyin)。
    "wechat": PlatformSpec(
        name="公众号",
        title_rule="(占位)公众号标题口径待定",
        tone_rule="(占位)",
        cta_rule="(占位)",
        hashtag_rule="(占位)",
        compliance_note="(占位)",
    ),
}
