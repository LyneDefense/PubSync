from __future__ import annotations

import html
import re
from typing import Any

from app.blogger_distillation.tikhub_client import TikHubUsage
from app.models import BloggerProfile


def render_report_html(blogger: BloggerProfile, stats: dict[str, Any], distillation: dict[str, Any], usage: TikHubUsage) -> str:
    sections = [
        ("一眼看清", distillation.get("one_glance") or distillation.get("positioning")),
        ("人设拆解", distillation.get("persona")),
        ("认知层", distillation.get("cognitive_model")),
        ("策略层", distillation.get("topic_strategy")),
        ("TOP10 爆款", render_hot_posts(stats.get("hot_posts", []))),
        ("内容公式", distillation.get("content_formula")),
        ("选题灵感", distillation.get("sample_topics")),
        ("数据面板", render_data_panel(stats, usage)),
        ("发展趋势", distillation.get("growth_insights") or stats.get("growth_trend", {}).get("summary")),
        ("核心结论", distillation.get("core_conclusion")),
    ]
    body = [
        f"<h1>{html.escape(blogger.display_name)} 小红书图文蒸馏报告</h1>",
        f"<p>样本 {stats.get('sample_count', 0)} 条，评论 {stats.get('comment_total', 0)} 条，TikHub 请求 {usage.request_count} 次，估算费用 ${usage.estimated_cost_usd:.4f}（区间 ${usage.cost_min_usd:.4f} - ${usage.cost_max_usd:.4f}）。</p>",
    ]
    quality = stats.get("quality_report") or {}
    warnings = quality.get("warnings") or []
    if warnings:
        body.append("<h2>样本质量提醒</h2>")
        body.append("<ul>" + "".join(f"<li>{html.escape(str(item))}</li>" for item in warnings) + "</ul>")
    for title, value in sections:
        body.append(f"<h2>{html.escape(title)}</h2>")
        body.append(render_value(value))
    return "\n".join(body)


def build_skill_markdown(blogger: BloggerProfile, stats: dict[str, Any], distillation: dict[str, Any]) -> str:
    name = slug_skill_name(blogger.display_name)
    return f"""---
name: {name}
description: 基于小红书博主 {blogger.display_name} 公开图文内容蒸馏出的创作方法论。不要冒充原博主，不要复制原文。
---

# {blogger.display_name} 图文创作方法论 Skill

## 使用说明

你不是原博主本人，不要冒充原博主。你学习的是公开内容里的选题、结构、表达节奏、封面文案和读者洞察。输出时必须服务于用户自己的账号定位，不能复用原文、原图、私密经历或身份。

适用平台：小红书图文笔记。也可以迁移到公众号短内容选题。

样本规模：{stats.get("sample_count", 0)} 条图文笔记，{stats.get("comment_total", 0)} 条评论。

## 认知层

{markdown_list(distillation.get("cognitive_model"))}

## 策略层

{markdown_list(distillation.get("topic_strategy"))}

## 内容层

### 标题公式

{markdown_list(distillation.get("title_patterns"))}

### 开头节奏

{markdown_list(distillation.get("opening_patterns"))}

### 正文公式

{markdown_list(distillation.get("body_structures") or distillation.get("content_formula"))}

### 语言 DNA

{markdown_list(distillation.get("language_dna"))}

### 封面文案

{markdown_list(distillation.get("cover_text_rules"))}

## 创作禁区

{markdown_list(distillation.get("do_not_do"))}
- 不复制原博主原文。
- 不复用原博主图片。
- 不冒充原博主身份。
- 不虚构个人经历、病例、数据或用户反馈。

## 对比示例

{markdown_list(distillation.get("contrast_examples"))}

## 选题灵感

{markdown_list(distillation.get("sample_topics"))}

## 局限性与自检清单

- 样本只代表该博主公开图文内容，不代表其完整创作体系。
- 发布前检查：事实是否准确、经历是否属于用户自己、表达是否有原创增量、是否规避医疗/金融/法律等高风险断言。
- 如果用户不知道发什么，先生成 20 个候选选题，再按收藏潜力、评论潜力、账号匹配度排序。
- 如果用户已有主题，先判断是否适配该方法论，再输出标题、正文、封面文案、标签和评论引导。
"""


def render_hot_posts(posts: list[dict[str, Any]]) -> str:
    if not posts:
        return "暂无爆款样本"
    items = []
    for index, item in enumerate(posts[:10], 1):
        items.append(
            f"{index}. {item.get('title', '')} | 点赞 {item.get('like_count', 0)} / 收藏 {item.get('favorite_count', 0)} / 评论 {item.get('comment_count', 0)}"
        )
    return "\n".join(items)


def render_data_panel(stats: dict[str, Any], usage: TikHubUsage) -> dict[str, Any]:
    return {
        "样本数": stats.get("sample_count", 0),
        "评论数": stats.get("comment_total", 0),
        "均赞": stats.get("average_like", 0),
        "均藏": stats.get("average_favorite", 0),
        "藏赞比": stats.get("favorite_like_ratio", 0),
        "发布频率": (stats.get("frequency_info") or {}).get("pattern", ""),
        "TikHub 请求": usage.request_count,
    }


def render_value(value: Any) -> str:
    if isinstance(value, str):
        escaped = html.escape(value)
        if "\n" in escaped:
            return "<ul>" + "".join(f"<li>{line}</li>" for line in escaped.splitlines() if line.strip()) + "</ul>"
        return f"<p>{escaped}</p>"
    if isinstance(value, list):
        return "<ul>" + "".join(f"<li>{html.escape(str(item))}</li>" for item in value) + "</ul>"
    if isinstance(value, dict):
        return "<ul>" + "".join(f"<li><strong>{html.escape(str(key))}</strong>：{html.escape(str(val))}</li>" for key, val in value.items()) + "</ul>"
    return f"<p>{html.escape(str(value or ''))}</p>"


def markdown_list(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(f"- {item}" for item in value) or "- 暂无"
    if isinstance(value, dict):
        return "\n".join(f"- {key}：{val}" for key, val in value.items()) or "- 暂无"
    if value:
        return f"- {value}"
    return "- 暂无"


def slug_skill_name(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_-]+", "-", name.strip()).strip("-").lower()
    return f"xhs-{slug or 'blogger'}-distilled"
