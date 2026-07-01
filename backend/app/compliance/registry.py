"""规则包注册表:按平台 + 赛道激活对应的包(通用包永远激活)。"""

from __future__ import annotations

from app.compliance.packs import ALL_PACKS
from app.compliance.types import Rule, RulePack


def activate_packs(platform: str, verticals: list[str] | None = None) -> list[RulePack]:
    """返回该平台 + 该账号赛道下应生效的规则包。

    - universal:永远激活。
    - platform:平台匹配才激活。
    - vertical:账号赛道命中才激活(不命中的行业包**完全不参与扫描** → 从根上消灭跨赛道误报)。
    """
    vset = set(verticals or [])
    packs: list[RulePack] = []
    for pack in ALL_PACKS:
        if pack.scope == "universal":
            packs.append(pack)
        elif pack.scope == "platform":
            if platform in pack.platforms:
                packs.append(pack)
        elif pack.scope == "vertical":
            if vset & set(pack.activate_verticals):
                packs.append(pack)
    return packs


def make_custom_pack(extra_words: list[str] | None) -> RulePack | None:
    """把用户自定义扩展词包成一个临时规则包(限流级、certain)。"""
    words = tuple(w for w in (extra_words or []) if w and w.strip())
    if not words:
        return None
    from app.compliance.types import Confidence, Severity

    return RulePack(
        id="custom",
        label="自定义",
        scope="universal",
        rules=(Rule(id="custom_words", category="自定义", words=words,
                    severity=Severity.THROTTLE, confidence=Confidence.CERTAIN,
                    basis="自定义扩展词", hint="按需替换或删除"),),
    )
