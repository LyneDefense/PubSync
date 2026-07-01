"""合规组件的公共类型:分级 / 置信度 / 规则 / 规则包 / 命中 / 扫描结果。

设计见 docs/合规检测_架构重构方案.md。这些类型是整个合规组件的「词汇表」,
matcher(一层)/ adjudicator(二层)/ grade(三层)/ 各 packs 都围绕它们协作。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    """严重度三档,对齐平台阶梯处罚(限流 / 暂停 / 封号)。"""

    BAN = "封号级"      # 导流 / 保证收益 / 医疗疗效 / 三品一械:轻则下架限流,重则封号
    THROTTLE = "限流级"  # 绝对化 / 夸大 / 抢购:笔记限流、文案被屏蔽
    NOTICE = "提示级"    # 边界 / 易误报:仅优化建议,不算违规

    @property
    def rank(self) -> int:
        return {"封号级": 3, "限流级": 2, "提示级": 1}[self.value]


class Confidence(str, Enum):
    """命中置信度。决定一层直接定性还是交二层 LLM 裁 / 降级为提示。"""

    CERTAIN = "certain"  # 几乎必违规(保本 / 加微信 / 治愈):直接按 severity 判
    WEAK = "weak"        # 易误报(顶级 / 独家 / 免费领取):诊断降为提示,创作仍提醒;有 LLM 则交裁


# 赛道枚举 → 展示名。行业包用 id 挂载,前端用 label 展示「按 X 赛道检测」。
VERTICAL_LABELS: dict[str, str] = {
    "cosmetics": "美妆护肤",
    "medical": "医疗健康",
    "food_health": "食品保健",
    "maternal": "母婴",
    "finance": "金融保险",
    "education": "教育培训",
    "fitness": "减肥健身",
    "recruit": "招商加盟",
}


def vertical_label(vid: str) -> str:
    return VERTICAL_LABELS.get(vid, vid)


@dataclass(frozen=True)
class Rule:
    """一条合规规则。词 / 正则 + 白名单 + 上下文 + 分级 + 依据 + 改法 + 置信度。"""

    id: str
    category: str                          # 面向用户的中文类别名(如「医疗功效·疗效宣称」)
    words: tuple[str, ...] = ()            # 字面词
    patterns: tuple[str, ...] = ()         # 正则(含上下文)
    allow_words: tuple[str, ...] = ()      # 例外更长词:命中词落在其中则抑制(抗皱⊃皱、办公安排⊃公安)
    allow_context: tuple[str, ...] = ()    # 例外语境正则:命中片段匹配则抑制(口语「还是最好」)
    require_context: tuple[str, ...] = ()  # 必须邻近语境才算(平台名 only if 邻近 去/搜/私域)
    severity: Severity = Severity.NOTICE
    confidence: Confidence = Confidence.CERTAIN
    basis: str = ""                        # 法规 / 平台条文依据
    hint: str = ""                         # 通俗改法


@dataclass(frozen=True)
class RulePack:
    """一个规则包。通用(所有人)/ 行业(按赛道)/ 平台(按平台)三种 scope。"""

    id: str
    label: str
    scope: str                              # "universal" | "vertical" | "platform"
    rules: tuple[Rule, ...] = ()
    activate_verticals: tuple[str, ...] = ()  # scope=vertical:命中其一则激活
    platforms: tuple[str, ...] = ()           # scope=platform:限定平台
    version: str = ""                         # 法规时效标注


@dataclass
class Hit:
    """一层匹配产出的候选命中(或最终确认的)。"""

    pack_id: str
    rule_id: str
    category: str
    matched: str
    quote: str
    field: str
    severity: Severity
    confidence: Confidence
    basis: str = ""
    hint: str = ""
    note_index: int = 0     # 命中所在文本序号(算覆盖率用)
    layer: str = "rule"     # "rule" | "llm"


@dataclass
class ScanResult:
    """扫描最终结果。既服务诊断(富报告),也服务创作闸门(扁平命中)。"""

    score: int = 100
    grade: str = "干净"
    has_ban: bool = False
    verticals: list[str] = field(default_factory=list)     # 激活的赛道 id
    violations: list[dict[str, Any]] = field(default_factory=list)  # 封号/限流,归并后,需处置
    advisories: list[dict[str, Any]] = field(default_factory=list)  # 提示级,优化建议,不计入违规
    flat_hits: list[dict[str, Any]] = field(default_factory=list)   # 扁平命中(创作闸门/兼容用)
    by_severity: dict[str, int] = field(default_factory=dict)

    def to_report_dict(self) -> dict[str, Any]:
        """诊断报告 / 前端用的结构。保留旧字段(hits/score/grade/has_ban)不炸旧逻辑。"""
        return {
            "score": self.score,
            "grade": self.grade,
            "has_ban": self.has_ban,
            "verticals": self.verticals,
            "vertical_labels": [vertical_label(v) for v in self.verticals],
            "violations": self.violations,
            "advisories": self.advisories,
            "by_severity": self.by_severity,
            "hits": self.flat_hits,  # 兼容:旧前端读 compliance.hits
        }

    def creation_dict(self) -> dict[str, Any]:
        """创作闸门用:{enabled, passed, hits}。hits 为需处置的扁平命中。"""
        blocking = [h for h in self.flat_hits if h.get("severity") in (Severity.BAN.value, Severity.THROTTLE.value)]
        return {"enabled": True, "passed": not blocking, "hits": blocking}
