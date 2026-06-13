from __future__ import annotations

import html
import re
from typing import Any

from app.blogger_distillation.tikhub_client import TikHubUsage
from app.models import BloggerProfile


# 三层方法论各子项的中文小标题，渲染报告/Skill 时复用。
COGNITIVE_LABELS = {
    "core_beliefs": "核心信念",
    "opinion_tensions": "观点张力 / 反共识",
    "value_stance": "价值立场",
    "thinking_models": "思维模式",
}
STRATEGY_LABELS = {
    "series_planning": "系列 / 选题规划",
    "trend_hijacking": "蹭热点 / 借势",
    "ops_habits": "运营习惯",
}
CONTENT_LABELS = {
    "title_formulas": "标题公式",
    "opening_templates": "开头模板",
    "body_structures": "图文正文结构",
    "video_script_structures": "视频口播 / 字幕结构",
    "emotional_rhythm": "情绪节奏",
    "language_dna": "语言 DNA",
    "cta_strategy": "CTA / 互动引导",
    "cover_text_rules": "封面文案",
    "hashtag_strategy": "标签策略",
}


def report_title(blogger: BloggerProfile, mode: str) -> str:
    if mode == "B":
        return f"{blogger.display_name} 账号诊断与创作基因报告"
    return f"{blogger.display_name} 内容蒸馏报告"


def render_report_html(
    blogger: BloggerProfile,
    stats: dict[str, Any],
    distillation: dict[str, Any],
    usage: TikHubUsage,
    mode: str = "A",
    quality: dict[str, Any] | None = None,
) -> str:
    cognitive = distillation.get("cognitive_layer", {})
    strategy = distillation.get("strategy_layer", {})
    content = distillation.get("content_layer", {})

    body: list[str] = [
        f"<h1>{html.escape(report_title(blogger, mode))}</h1>",
        render_meta_line(blogger, stats, usage, mode),
    ]
    if quality:
        body.append(render_quality_panel(quality))

    warnings = (stats.get("quality_report") or {}).get("warnings") or []
    if warnings:
        body.append("<h2>样本质量提醒</h2>")
        body.append("<ul>" + "".join(f"<li>{html.escape(str(item))}</li>" for item in warnings) + "</ul>")

    # 1. 一眼看清
    body += section("一眼看清", distillation.get("one_glance"))
    # 2. 人设拆解
    body += section("人设拆解", render_persona(distillation.get("persona")))
    # 3. 目标读者
    body += section("目标读者", distillation.get("audience"))
    # 4. 认知层（怎么想）
    body += layer_block("认知层 · 怎么想", cognitive, COGNITIVE_LABELS)
    # 5. 策略层（怎么运营）
    body += layer_block("策略层 · 怎么运营", strategy, STRATEGY_LABELS, tail=("发布节奏", strategy.get("posting_rhythm")))
    # 6. 内容层（怎么写）
    body += layer_block("内容层 · 怎么写", content, CONTENT_LABELS)
    # 7. TOP 爆款逐条拆解
    body.append("<h2>TOP 爆款逐条拆解</h2>")
    body.append(render_breakdowns(distillation.get("top_post_breakdowns"), stats.get("hot_posts", [])))
    # 8. 评论洞察
    body += section("评论区洞察", distillation.get("comment_insights"))
    # 9. 数据面板
    body.append("<h2>数据面板</h2>")
    body.append(render_value(render_data_panel(stats, usage)))
    # 10. 发展趋势
    body += section("发展趋势", distillation.get("growth_trend") or (stats.get("growth_trend") or {}).get("summary"))
    # 选题灵感 / 对比示例 / 创作禁区
    body += section("选题灵感", distillation.get("sample_topics"))
    body.append("<h2>对比示例</h2>")
    body.append(render_contrast(distillation.get("contrast_examples")))
    body += section("创作禁区", distillation.get("do_not_do"))
    # 模式 B：账号诊断
    if mode == "B":
        body.append("<h2>账号诊断（你的账号）</h2>")
        body.append(render_diagnosis(distillation.get("self_diagnosis")))
    # 核心结论
    body += section("核心结论", distillation.get("core_conclusion"))
    return "\n".join(body)


def render_meta_line(blogger: BloggerProfile, stats: dict[str, Any], usage: TikHubUsage, mode: str) -> str:
    mode_label = "诊断我的账号（模式 B）" if mode == "B" else "拆解对标博主（模式 A）"
    transcript_info = stats.get("transcript_info") or {}
    return (
        f"<p>{html.escape(mode_label)}｜样本 {stats.get('sample_count', 0)} 条，"
        f"采样评论 {stats.get('comment_total', 0)} 条，"
        f"视频样本 {transcript_info.get('video_count', 0)} 条（已解析口播 {transcript_info.get('transcript_count', 0)} 条）。"
        f"TikHub 请求 {usage.request_count} 次，估算费用 ${usage.estimated_cost_usd:.4f}"
        f"（区间 ${usage.cost_min_usd:.4f} - ${usage.cost_max_usd:.4f}）。</p>"
    )


def render_quality_panel(quality: dict[str, Any]) -> str:
    score = quality.get("score", 0)
    grade = quality.get("grade", "")
    issues = quality.get("issues") or []
    revisions = quality.get("revisions")
    revise_note = f"，已自我修订 {revisions} 次" if isinstance(revisions, int) and revisions > 0 else "（一次通过）"
    parts = [
        '<div class="distill-quality">',
        f"<h2>蒸馏质量自检：{html.escape(str(score))} 分 · {html.escape(str(grade))}{html.escape(revise_note)}</h2>",
    ]
    if issues:
        parts.append("<p>可改进项：</p>")
        parts.append("<ul>" + "".join(f"<li>{html.escape(str(item))}</li>" for item in issues) + "</ul>")
    else:
        parts.append("<p>未发现明显问题，覆盖度与基于数据的支撑较完整。</p>")
    parts.append("</div>")
    return "".join(parts)


def layer_block(title: str, layer: dict[str, Any], labels: dict[str, str], tail: tuple[str, Any] | None = None) -> list[str]:
    out = [f"<h2>{html.escape(title)}</h2>"]
    rendered_any = False
    for key, label in labels.items():
        value = layer.get(key)
        if not value:
            continue
        rendered_any = True
        out.append(f"<h3>{html.escape(label)}</h3>")
        out.append(render_value(value))
    if tail and tail[1]:
        rendered_any = True
        out.append(f"<h3>{html.escape(tail[0])}</h3>")
        out.append(render_value(tail[1]))
    if not rendered_any:
        out.append("<p>暂无</p>")
    return out


def section(title: str, value: Any) -> list[str]:
    return [f"<h2>{html.escape(title)}</h2>", render_value(value)]


def render_persona(persona: Any) -> Any:
    if isinstance(persona, dict):
        mapping = {
            "身份感": persona.get("identity"),
            "表达姿态": persona.get("stance"),
            "信任来源": persona.get("trust_source"),
        }
        return {key: val for key, val in mapping.items() if val}
    return persona


def render_breakdowns(breakdowns: Any, hot_posts: list[dict[str, Any]]) -> str:
    if not isinstance(breakdowns, list) or not breakdowns:
        if not hot_posts:
            return "<p>暂无爆款样本</p>"
        items = []
        for index, item in enumerate(hot_posts[:10], 1):
            comment_label = format_comment_metric(item.get("comment_count", 0), item.get("sampled_comment_count", 0))
            items.append(
                f"<li>{index}. {html.escape(str(item.get('title', '')))} ｜ 点赞 {item.get('like_count', 0)} / 收藏 {item.get('favorite_count', 0)} / {comment_label}</li>"
            )
        return "<ul>" + "".join(items) + "</ul>"
    cards = []
    for index, item in enumerate(breakdowns[:10], 1):
        if not isinstance(item, dict):
            cards.append(f'<div class="distill-breakdown"><p>{html.escape(str(item))}</p></div>')
            continue
        rank = item.get("rank") or index
        title_ref = html.escape(str(item.get("title_ref") or ""))
        source = html.escape(str(item.get("source") or ""))
        why = html.escape(str(item.get("why_viral") or ""))
        tactic = html.escape(str(item.get("reusable_tactic") or ""))
        source_html = f'<span class="distill-breakdown-source">来源：{source}</span>' if source else ""
        cards.append(
            '<div class="distill-breakdown">'
            f"<h4>#{html.escape(str(rank))} {title_ref} {source_html}</h4>"
            f"<p><strong>为什么火：</strong>{why}</p>"
            f"<p><strong>可复用：</strong>{tactic}</p>"
            "</div>"
        )
    return "".join(cards)


def render_contrast(examples: Any) -> str:
    if not isinstance(examples, list) or not examples:
        return "<p>暂无</p>"
    rows = []
    for item in examples:
        if isinstance(item, dict):
            plain = html.escape(str(item.get("plain") or ""))
            better = html.escape(str(item.get("better") or ""))
            rows.append(f"<li><strong>普通：</strong>{plain}<br><strong>更好：</strong>{better}</li>")
        else:
            rows.append(f"<li>{html.escape(str(item))}</li>")
    return "<ul>" + "".join(rows) + "</ul>"


def render_diagnosis(diagnosis: Any) -> str:
    if not isinstance(diagnosis, dict):
        return "<p>暂无</p>"
    blocks = []
    for key, label in (("strengths", "已经做对的"), ("weaknesses", "明显短板"), ("action_plan", "立即可执行的增长动作")):
        value = diagnosis.get(key)
        if value:
            blocks.append(f"<h3>{html.escape(label)}</h3>")
            blocks.append(render_value(value))
    return "".join(blocks) or "<p>暂无</p>"


def build_skill_markdown(blogger: BloggerProfile, stats: dict[str, Any], distillation: dict[str, Any], mode: str = "A") -> str:
    name = slug_skill_name(blogger.display_name, mode)
    transcript_info = stats.get("transcript_info") or {}
    cognitive = distillation.get("cognitive_layer", {})
    strategy = distillation.get("strategy_layer", {})
    content = distillation.get("content_layer", {})

    if mode == "B":
        heading = f"# {blogger.display_name} 创作基因 Skill（账号诊断）"
        description = f"基于你自己的小红书账号 {blogger.display_name} 蒸馏出的创作基因，用于复用强项、补齐短板。"
        usage_note = (
            "这是对你自己账号的诊断结果。用它来强化你已经做对的部分、补齐短板，"
            "在生成新内容前先对照「账号诊断」里的增长动作。"
        )
    else:
        heading = f"# {blogger.display_name} 内容方法论 Skill"
        description = f"基于小红书博主 {blogger.display_name} 公开内容蒸馏出的创作方法论。不要冒充原博主，不要复制原文。"
        usage_note = (
            "你不是原博主本人，不要冒充原博主。你学习的是公开内容里的认知、策略与表达方法，"
            "输出时必须服务于用户自己的账号定位，不能复用原文、原图、私密经历或身份。"
        )

    sections = [
        f"---\nname: {name}\ndescription: {description}\n---\n",
        heading,
        "",
        "## 1. 使用说明",
        "",
        usage_note,
        "",
        f"适用平台：小红书图文 / 视频口播脚本，也可迁移到公众号短内容选题。样本规模：{stats.get('sample_count', 0)} 条笔记，"
        f"{stats.get('comment_total', 0)} 条采样评论；视频样本 {transcript_info.get('video_count', 0)} 条，"
        f"已解析字幕/口播 {transcript_info.get('transcript_count', 0)} 条。",
        "",
        "## 2. 认知层（怎么想）",
        "",
        layer_markdown(cognitive, COGNITIVE_LABELS),
        "## 3. 策略层（怎么运营）",
        "",
        layer_markdown(strategy, STRATEGY_LABELS, tail=("发布节奏", strategy.get("posting_rhythm"))),
        "## 4. 内容层（怎么写）",
        "",
        layer_markdown(content, CONTENT_LABELS),
        "## 5. 创作禁区",
        "",
        markdown_list(distillation.get("do_not_do")),
        "- 不复制原博主原文、原图，不冒充原博主身份。",
        "- 不虚构个人经历、病例、数据或用户反馈。",
        "",
        "## 6. 对比示例",
        "",
        contrast_markdown(distillation.get("contrast_examples")),
        "## 7. 选题灵感",
        "",
        markdown_list(distillation.get("sample_topics")),
        "",
    ]
    if mode == "B":
        diagnosis = distillation.get("self_diagnosis", {})
        sections += [
            "## 8. 账号诊断",
            "",
            "### 已经做对的",
            markdown_list(diagnosis.get("strengths")),
            "### 明显短板",
            markdown_list(diagnosis.get("weaknesses")),
            "### 立即可执行的增长动作",
            markdown_list(diagnosis.get("action_plan")),
            "",
            "## 9. 局限性与自检清单",
        ]
    else:
        sections.append("## 8. 局限性与自检清单")
    sections += [
        "",
        "- 样本只代表该账号公开内容，不代表其完整创作体系。",
        "- 视频字幕/ASR 转写只用于分析口播结构和信息密度，不等同于图文正文长度。",
        "- 发布前检查：事实是否准确、经历是否属于用户自己、是否有原创增量、是否规避医疗/金融/法律等高风险断言。",
        "- 如果用户不知道发什么，先生成 20 个候选选题，再按收藏潜力、评论潜力、账号匹配度排序。",
        "",
    ]
    return "\n".join(sections)


def layer_markdown(layer: dict[str, Any], labels: dict[str, str], tail: tuple[str, Any] | None = None) -> str:
    out: list[str] = []
    for key, label in labels.items():
        value = layer.get(key)
        if not value:
            continue
        out.append(f"### {label}")
        out.append(markdown_list(value))
        out.append("")
    if tail and tail[1]:
        out.append(f"### {tail[0]}")
        out.append(markdown_list(tail[1]))
        out.append("")
    return "\n".join(out) or "- 暂无\n"


def contrast_markdown(examples: Any) -> str:
    if not isinstance(examples, list) or not examples:
        return "- 暂无\n"
    rows = []
    for item in examples:
        if isinstance(item, dict):
            rows.append(f"- 普通：{item.get('plain', '')} → 更好：{item.get('better', '')}")
        else:
            rows.append(f"- {item}")
    return "\n".join(rows) + "\n"


def format_comment_metric(comment_count: Any, sampled_comment_count: Any) -> str:
    try:
        count = int(comment_count or 0)
    except (TypeError, ValueError):
        count = 0
    try:
        sampled = int(sampled_comment_count or 0)
    except (TypeError, ValueError):
        sampled = 0
    if count > 0:
        return f"评论 {count}"
    if sampled > 0:
        return f"评论未知 / 采样评论 {sampled}"
    return "评论未知"


def render_data_panel(stats: dict[str, Any], usage: TikHubUsage) -> dict[str, Any]:
    return {
        "样本数": stats.get("sample_count", 0),
        "采样评论数": stats.get("comment_total", 0),
        "均赞": stats.get("average_like", 0),
        "均藏": stats.get("average_favorite", 0),
        "藏赞比": stats.get("favorite_like_ratio", 0),
        "发布频率": (stats.get("frequency_info") or {}).get("pattern", ""),
        "视频样本": (stats.get("transcript_info") or {}).get("video_count", 0),
        "已解析口播": (stats.get("transcript_info") or {}).get("transcript_count", 0),
        "TikHub 请求": usage.request_count,
    }


def render_value(value: Any) -> str:
    if isinstance(value, str):
        escaped = html.escape(value)
        if "\n" in escaped:
            return "<ul>" + "".join(f"<li>{line}</li>" for line in escaped.splitlines() if line.strip()) + "</ul>"
        return f"<p>{escaped}</p>" if escaped.strip() else "<p>暂无</p>"
    if isinstance(value, list):
        if not value:
            return "<p>暂无</p>"
        return "<ul>" + "".join(f"<li>{html.escape(str(item))}</li>" for item in value) + "</ul>"
    if isinstance(value, dict):
        if not value:
            return "<p>暂无</p>"
        return "<ul>" + "".join(f"<li><strong>{html.escape(str(key))}</strong>：{html.escape(str(val))}</li>" for key, val in value.items()) + "</ul>"
    return f"<p>{html.escape(str(value or '暂无'))}</p>"


def markdown_list(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(f"- {item}" for item in value) or "- 暂无"
    if isinstance(value, dict):
        return "\n".join(f"- {key}：{val}" for key, val in value.items()) or "- 暂无"
    if value:
        return f"- {value}"
    return "- 暂无"


def slug_skill_name(name: str, mode: str = "A") -> str:
    slug = re.sub(r"[^a-zA-Z0-9一-鿿_-]+", "-", name.strip()).strip("-").lower()
    suffix = "self" if mode == "B" else "distilled"
    return f"xhs-{slug or 'blogger'}-{suffix}"
