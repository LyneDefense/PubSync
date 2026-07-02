"""把 analysis 产出的 stats 字典渲染成「给蒸馏 LLM 的证据文本」。

背景(实测坐实):旧实现是 `json.dumps(stats)[:16000]`——把 8 万多字符的大字典整包序列化后
盲砍前 16000。模型实际只读到前 18%,20 条代表样本一条没进、图内文字仅 20% 进、认知层金句池
(偏移 8 万+)完全没进 → 蒸馏一直半盲。

这里改成「结构化证据装配 + 按优先级填充 + 尾部兜底截断」,并在物料层再去一道噪:
- role 过滤:图内要点只取内容性 role,跳过实拍/截图/路人/商品这类低内容密度的;
- desc 优先、text 兜底:desc 是 VLM 已提炼过的(抗噪),逐字 text 限长补充;
- 单块限长:防单条多图爆款的图内文字爆表、喧宾夺主;
- 跨样本共性天然稀释单点噪音(蒸馏从 N 条找规律,不信单条)。

legacy=True 走旁路(复现旧的整包截断),供新旧 A/B 对照。
"""

from __future__ import annotations

import json
from typing import Any

from app.blogger_distillation.modality import subtype_label

_LEGACY_CHAR_LIMIT = 16000       # 旧实现的盲截长度(A/B 旁路复现用)
_BLOCK_CHAR_CAP = 600            # 单条证据块字符硬上限
_CONTENT_ROLES = ("封面", "标题", "清单", "教程", "步骤", "对比", "数据", "金句", "要点", "卡片", "合集")
_NOISE_ROLES = ("实拍", "截图", "路人", "商品", "背景", "水印")
_STRONG_OPINION = ("我觉得", "我发现", "其实", "真正", "关键", "本质", "一定", "最重要", "核心", "建议", "不要")


def render_stats_digest(
    stats: dict[str, Any], *, char_budget: int, scope: str = "core", legacy: bool = False
) -> str:
    """把 stats 渲染成蒸馏 prompt 的证据文本。按优先级分段填充,只在尾部兜底截断。

    scope="core"(认知,金句多给) / "lane"(内容层,金句少给、证据块为主)。
    """
    if legacy:  # A/B 旁路:复现旧的整包盲截
        return json.dumps(stats, ensure_ascii=False, default=str)[:_LEGACY_CHAR_LIMIT]

    out: list[str] = []
    remaining = char_budget

    def push(block: str, *, force: bool) -> bool:
        """加一块。force=必进(不受预算限);否则预算不足则不加、返回 False。"""
        nonlocal remaining
        block = (block or "").strip()
        if not block:
            return True
        if not force and len(block) + 2 > remaining:
            return False
        out.append(block)
        remaining -= len(block) + 2
        return True

    # 段1 账号统计 + 段2 观点金句池:信息密度高,必进。
    push(_account_summary(stats), force=True)
    push(_opinion_pool(stats, limit=24 if scope == "core" else 10), force=True)

    # 段3 爆款证据块:top3 必进,其余在预算内追加。
    hot = stats.get("hot_posts") or []
    for i, sample in enumerate(hot):
        if not push(_titled(f"爆款证据 #{i + 1}", _evidence_block(sample)), force=(i < 3)):
            break
    hot_ids = {s.get("external_id") for s in hot if isinstance(s, dict)}

    # 段4 代表样本精简行:去 hot 冗余,逐行填满剩余预算。
    push(_fill_lines("【代表样本 · 补充广度(标题｜互动｜信号)】", _representative_lines(stats, hot_ids), remaining), force=True)

    # 段5 评论洞察:尾部,有余量才进。
    push(_comment_insights(stats, limit=12), force=False)

    return "\n\n".join(out)


# ============================ 分段 ============================

def _account_summary(stats: dict[str, Any]) -> str:
    """账号级统计紧凑成行(不 dumps 大数组):互动、模态、模式占比、节奏、趋势、标签、结构。"""
    lines = ["【账号概览】"]
    lines.append(
        f"样本 {stats.get('sample_count', 0)} 篇｜均赞 {stats.get('average_like', 0)}"
        f"｜均藏 {stats.get('average_favorite', 0)}｜均评 {stats.get('average_comment', 0)}"
        f"｜藏赞比 {stats.get('favorite_like_ratio', 0)}"
    )
    if stats.get("modality_comparison"):
        lines.append(f"模态对比：{stats['modality_comparison']}")
    subtype = stats.get("subtype_counts") or {}
    if subtype:
        lines.append("形态分布：" + "、".join(f"{_subtype_label_cn(k)}×{v}" for k, v in subtype.items()))
    for label, key, n in (("标题模式", "title_patterns", 5), ("开头模式", "opening_patterns", 3), ("CTA", "cta_patterns", 3)):
        top = _top_patterns(stats.get(key), n)
        if top:
            lines.append(f"{label}：" + "；".join(top))
    freq = stats.get("frequency_info") or {}
    if freq.get("pattern"):
        lines.append(f"发布节奏：{freq['pattern']}（均隔 {freq.get('avg_days_between')} 天）")
    growth = stats.get("growth_trend") or {}
    if growth.get("summary"):
        lines.append(f"成长趋势：{growth['summary']}")
    tags = stats.get("frequent_hashtags") or []
    tag_names = [f"#{t.get('tag')}" for t in tags[:12] if isinstance(t, dict) and t.get("tag")]
    if tag_names:
        lines.append("高频标签：" + "、".join(tag_names))
    si = stats.get("structure_info") or {}
    if si.get("avg_length"):
        lines.append(f"图文正文：均长 {si.get('avg_length')} 字，清单体 {si.get('list_format_count', 0)} 篇")
    ti = stats.get("transcript_info") or {}
    if ti.get("transcript_count"):
        lines.append(f"视频转写：{ti.get('transcript_count')} 条有转写，均长 {ti.get('avg_transcript_length')} 字")
    return "\n".join(lines)


def _opinion_pool(stats: dict[str, Any], limit: int) -> str:
    """观点/金句池(含图内文字):子串去重(保留长句)+ 强观点信号词加权,前置。"""
    raw = [(s or "").strip() for s in (stats.get("opinion_sentences") or [])]
    raw = [s for s in raw if s]
    uniq: list[str] = []
    for s in sorted(set(raw), key=len, reverse=True):  # 先长后短,子串被长句吸收
        if not any(s in kept for kept in uniq):
            uniq.append(s)
    uniq.sort(key=lambda s: sum(w in s for w in _STRONG_OPINION), reverse=True)  # 稳定排序,同权重保留长度序
    picked = uniq[:limit]
    if not picked:
        return ""
    return "【观点/金句池（含图内文字，博主的立场与主张）】\n" + "\n".join(f"· {s}" for s in picked)


def _representative_lines(stats: dict[str, Any], exclude_ids: set) -> list[str]:
    """代表样本精简行(排除已在 hot 的,去冗余):标题｜赞藏｜一句关键信号。"""
    lines: list[str] = []
    for s in stats.get("representative_posts") or []:
        if not isinstance(s, dict) or s.get("external_id") in exclude_ids:
            continue
        title = (s.get("title") or "(无标题)").strip()
        lines.append(f"· {title}｜赞{_human_num(s.get('like_count'))}藏{_human_num(s.get('favorite_count'))}｜{_one_signal(s)}")
    return lines


def _comment_insights(stats: dict[str, Any], limit: int) -> str:
    """评论区高频声音(读者真实需求),采样若干条。"""
    picked: list[str] = []
    for c in stats.get("comment_insights_source") or []:
        text = str(c.get("content") or c.get("text") or "").strip() if isinstance(c, dict) else str(c or "").strip()
        if len(text) >= 4:
            picked.append(text[:60])
        if len(picked) >= limit:
            break
    if not picked:
        return ""
    return "【评论区高频声音（读者真实需求）】\n" + "\n".join(f"· {c}" for c in picked)


# ============================ 单条证据块 ============================

def _evidence_block(sample: dict[str, Any]) -> str:
    """一条样本的结构化证据块,按模态分型;视觉信号提到显眼位置,单块限长。"""
    if not isinstance(sample, dict):
        return ""
    lines = [_head_line(sample)]
    if sample.get("content_type") == "video":
        transcript = (sample.get("transcript_excerpt") or "").strip()
        if transcript:
            lines.append(f"  口播摘要：{transcript[:280]}")
        else:
            lines.append("  （无转写：口播内容未覆盖，以下为封面/首帧信号）")
        lines.extend(_visual_lines(sample, max_points=2))  # 视频只取封面/少量
    else:  # 图文:视觉信号为主,正文为辅
        lines.extend(_visual_lines(sample, max_points=6))
        body = (sample.get("body_excerpt") or "").strip()
        if body:
            lines.append(f"  正文摘要：{body[:200]}")
    return "\n".join(lines)[:_BLOCK_CHAR_CAP]


def _head_line(sample: dict[str, Any]) -> str:
    title = (sample.get("title") or "(无标题)").strip()
    return (
        f"标题：{title}｜赞{_human_num(sample.get('like_count'))}"
        f"藏{_human_num(sample.get('favorite_count'))}评{_human_num(sample.get('comment_count'))}"
        f"｜来源:{sample.get('external_id') or '?'}"
    )


def _visual_lines(sample: dict[str, Any], *, max_points: int) -> list[str]:
    """从 visual_digest 抽视觉证据:封面钩子/版式/风格 + 逐张要点(role 过滤、desc 优先、text 限长)。"""
    digest = sample.get("visual_digest")
    if not isinstance(digest, dict) or not digest:
        it = (sample.get("image_text_excerpt") or "").strip()  # 无结构化 digest 时退回图内文字
        return [f"  图内文字：{it[:200]}"] if it else []
    lines: list[str] = []
    hook = str(digest.get("cover_hook") or "").strip()
    if hook:
        lines.append(f"  封面钩子：{hook}")
    meta = "｜".join(
        x for x in (f"版式:{digest.get('layout')}" if digest.get("layout") else "",
                    f"风格:{digest.get('style')}" if digest.get("style") else "") if x
    )
    if meta:
        lines.append(f"  {meta}")
    images = [im for im in (digest.get("images") or []) if isinstance(im, dict)]
    picked: list[str] = []
    for im in sorted(images, key=_role_rank):  # 内容性 role 在前
        if _role_rank(im) >= 2:  # 噪音 role 直接跳过(实拍/截图/路人/商品/水印)
            continue
        role = str(im.get("role") or "").strip()
        desc = str(im.get("desc") or "").strip()   # VLM 已提炼,抗噪
        text = str(im.get("text") or "").strip()    # 逐字,可能带噪,限长
        label = f"第{im.get('index')}张" if im.get("index") else "图"
        if role:
            label += f"({role})"
        body = desc or text[:80]
        detail = f"｜逐字:{text[:100]}" if (text and desc) else ""
        picked.append(f"    {label}：{body}{detail}")
        if len(picked) >= max_points:
            break
    if picked:
        lines.append("  图内要点：")
        lines.extend(picked)
    return lines


def _one_signal(sample: dict[str, Any]) -> str:
    """代表样本行的一句关键信号:封面钩子 > 图内文字 > 口播 > 正文,取其一、限长。"""
    digest = sample.get("visual_digest")
    if isinstance(digest, dict) and str(digest.get("cover_hook") or "").strip():
        return f"封面:{str(digest['cover_hook']).strip()[:40]}"
    for key, prefix in (("image_text_excerpt", "图内"), ("transcript_excerpt", "口播"), ("body_excerpt", "正文")):
        val = (sample.get(key) or "").strip()
        if val:
            return f"{prefix}:{val[:40]}"
    return "—"


# ============================ 小工具 ============================

def _role_rank(im: dict[str, Any]) -> int:
    """图内要点排序键:内容性 role=0(优先)、未知=1、噪音 role=2(跳过)。"""
    role = str(im.get("role") or "")
    if any(r in role for r in _CONTENT_ROLES):
        return 0
    if any(r in role for r in _NOISE_ROLES):
        return 2
    return 1


def _titled(title: str, block: str) -> str:
    block = (block or "").strip()
    return f"【{title}】\n{block}" if block else ""


def _fill_lines(header: str, lines: list[str], remaining: int) -> str:
    """把行贪心塞进剩余预算(含 header);一行都塞不下则返回空。"""
    if remaining < 300 or not lines:
        return ""
    picked: list[str] = []
    used = len(header) + 2
    for line in lines:
        if used + len(line) + 1 > remaining:
            break
        picked.append(line)
        used += len(line) + 1
    return header + "\n" + "\n".join(picked) if picked else ""


def _top_patterns(pat: Any, n: int) -> list[str]:
    """{型:{count,examples,pct}} → 取 pct>0 的按占比降序 top n,格式 '型 pct%'。"""
    if not isinstance(pat, dict):
        return []
    items = [(k, v.get("pct", 0)) for k, v in pat.items() if isinstance(v, dict) and v.get("pct", 0) > 0]
    items.sort(key=lambda x: x[1], reverse=True)
    return [f"{k} {p}%" for k, p in items[:n]]


def _subtype_label_cn(key: Any) -> str:
    try:
        return subtype_label(key) if key else "未知"
    except Exception:  # noqa: BLE001 - 标签仅用于展示,未知形态兜底原值
        return str(key or "未知")


def _human_num(n: Any) -> str:
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "0"
    return f"{n / 10000:.1f}w" if n >= 10000 else str(n)
