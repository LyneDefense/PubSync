"""博主诊断·需模型判的维度:垂直度(硬实力第5维)+ 软实力(对路 / 可学 / 可蒸馏)。

都走 create_json_response,失败/坏格式 → 中性兜底(score=50 + 说明),绝不阻断诊断。
对路用「三面法」:把对标意图拆成 题材 / 形态 / 调性,再从博主真实笔记刻画同样三面、逐面比 + 引证。
软实力只在「诊断别人」时跑(诊断自己无所谓对不对路、能不能学自己)。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.config import Settings
from app.services.ai_service import create_json_response

logger = logging.getLogger(__name__)


@dataclass
class JudgedDim:
    key: str
    label: str
    score: int
    detail: str
    evidence: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)


def _clamp_score(value: Any, default: int = 50) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return default


_VERTICAL_PROMPT = """你在判断一个小红书账号的「垂直度」——内容是不是聚焦在一个细分赛道(定位摇摆是大忌)。
下面是该账号近期笔记标题:
{titles}
只输出 JSON:{{"score": 0-100(越聚焦越高), "niche": "它主要做什么赛道", "reason": "一句话依据(举它反复出现的主题)"}}"""


def judge_vertical(titles: list[str], settings: Settings) -> JudgedDim:
    """垂直度:近 N 篇标题是否聚焦一个赛道。"""
    joined = "\n".join(f"- {t}" for t in titles if t)[:3000]
    if not joined:
        return JudgedDim("vertical", "垂直度", 50, "无标题可判,给中性分")
    try:
        data = create_json_response(settings, _VERTICAL_PROMPT.format(titles=joined))
    except Exception as exc:  # noqa: BLE001
        logger.warning("垂直度判断失败,中性兜底:%s", exc)
        return JudgedDim("vertical", "垂直度", 50, "模型判断失败,给中性分")
    if not isinstance(data, dict):
        return JudgedDim("vertical", "垂直度", 50, "返回格式异常,给中性分")
    niche = str(data.get("niche") or "").strip()
    reason = str(data.get("reason") or "").strip()
    return JudgedDim("vertical", "垂直度", _clamp_score(data.get("score")),
                     reason or "—", extra={"niche": niche})


_SOFT_PROMPT = """你在帮一个博主判断「另一个账号值不值得他对标学习」。

用户的对标意图(他想学什么样的博主):{intent}

先把这个意图拆成三面:题材(什么赛道)、形态(图文/视频、科普/种草/测评/vlog、专业还是轻松)、调性目标(涨粉做IP / 纯销售获客 / 卖课等)。
再从下面这个账号的真实笔记,刻画它的同样三面,然后判断:

被评估账号的近期笔记(标题 + 摘要):
{notes}

只输出 JSON:
{{
 "intent_facets": {{"题材":"", "形态":"", "调性":""}},
 "account_facets": {{"题材":"", "形态":"", "调性":""}},
 "对路": {{"score":0-100, "reason":"逐面说匹配/不匹配,引具体笔记", "题材匹配":true/false, "形态匹配":true/false, "调性匹配":true/false}},
 "可学": {{"score":0-100, "reason":"选题需求驱动还是标题党?框架模板化吗?是否依赖个人IP/认证/特殊资源?原生分享还是硬广?有没有AI模板痕迹?"}},
 "可蒸馏": {{"score":0-100, "reason":"代表作是否清晰、能不能拆出可复用的方法论"}}
}}"""


def _dim_from(block: Any, key: str, label: str) -> JudgedDim:
    if not isinstance(block, dict):
        return JudgedDim(key, label, 50, "模型未给出,中性兜底")
    return JudgedDim(key, label, _clamp_score(block.get("score")),
                     str(block.get("reason") or "—").strip())


def judge_soft(intent: str, notes_brief: str, settings: Settings) -> dict[str, JudgedDim]:
    """软实力(诊断别人用):对路(三面法)/ 可学 / 可蒸馏。失败 → 三项中性兜底。"""
    fallback = {
        "fit": JudgedDim("fit", "对路", 50, "模型判断失败,给中性分"),
        "learnable": JudgedDim("learnable", "可学", 50, "模型判断失败,给中性分"),
        "distillable": JudgedDim("distillable", "可蒸馏", 50, "模型判断失败,给中性分"),
    }
    if not (intent or "").strip() or not (notes_brief or "").strip():
        return fallback
    prompt = _SOFT_PROMPT.format(intent=intent.strip(), notes=notes_brief.strip()[:7000])
    try:
        data = create_json_response(settings, prompt)
    except Exception as exc:  # noqa: BLE001
        logger.warning("软实力判断失败,中性兜底:%s", exc)
        return fallback
    if not isinstance(data, dict):
        return fallback
    fit = _dim_from(data.get("对路"), "fit", "对路")
    fit.extra = {
        "intent_facets": data.get("intent_facets") or {},
        "account_facets": data.get("account_facets") or {},
        "facet_match": {k: bool((data.get("对路") or {}).get(k)) for k in ("题材匹配", "形态匹配", "调性匹配")},
    }
    return {
        "fit": fit,
        "learnable": _dim_from(data.get("可学"), "learnable", "可学"),
        "distillable": _dim_from(data.get("可蒸馏"), "distillable", "可蒸馏"),
    }
