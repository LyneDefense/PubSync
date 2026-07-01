"""平台规则包(按平台生效):竞品 / 站外平台导流。

关键:平台名**只在邻近导流语境**(去/上/搜/买/同款/下单/私域)才算违规——
只是提到「在抖音刷到」不算,「去淘宝搜同款」才算。用 require_context 实现。
"""

from __future__ import annotations

from app.compliance.types import Confidence, Rule, RulePack, Severity

# 站外导流语境:必须邻近这些词才算「引流去别的平台」。刻意避开「到」(会误伤刷到/搬到)等泛字。
_DIVERSION_CTX = (r"(去|上|搜|下单|同款|链接|旗舰店|店铺|主页|优惠券|领券|购物车|挂车|买它|蹲一个)",)

XHS_PACK = RulePack(
    id="platform_xhs",
    label="平台·小红书",
    scope="platform",
    platforms=("xhs",),
    rules=(
        Rule(
            id="offsite_platform",
            category="竞品·站外导流",
            words=("淘宝", "天猫", "京东", "拼多多", "抖音", "快手", "TikTok"),
            require_context=_DIVERSION_CTX,
            severity=Severity.THROTTLE,
            confidence=Confidence.CERTAIN,  # 已被导流语境筛过,命中即较确定
            basis="导流治理·平台规则",
            hint="不要引导去站外平台交易,换成不具体指向的说法或站内互动",
        ),
    ),
)

DOUYIN_PACK = RulePack(
    id="platform_douyin",
    label="平台·抖音",
    scope="platform",
    platforms=("douyin",),
    rules=(
        Rule(
            id="offsite_platform",
            category="竞品·站外导流",
            words=("淘宝", "天猫", "京东", "拼多多", "小红书", "快手", "B站"),
            require_context=_DIVERSION_CTX,
            severity=Severity.THROTTLE,
            confidence=Confidence.CERTAIN,  # 已被导流语境筛过,命中即较确定
            basis="导流治理·平台规则",
            hint="不要引导去站外平台交易,换成站内自然表达",
        ),
    ),
)

WECHAT_PACK = RulePack(
    id="platform_wechat",
    label="平台·公众号",
    scope="platform",
    platforms=("wechat",),
    rules=(
        Rule(
            id="offsite_platform",
            category="竞品·站外导流",
            words=("抖音", "小红书", "淘宝", "拼多多"),
            require_context=_DIVERSION_CTX,
            severity=Severity.THROTTLE,
            confidence=Confidence.CERTAIN,  # 已被导流语境筛过,命中即较确定
            basis="导流治理·平台规则",
            hint="不要引导去站外平台,换成不具体指向的说法",
        ),
    ),
)

PLATFORM_PACKS = (XHS_PACK, DOUYIN_PACK, WECHAT_PACK)
