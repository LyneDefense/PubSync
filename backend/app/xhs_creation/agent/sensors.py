from __future__ import annotations

from typing import Any

from app.compliance import scan_creation
from app.synthesis import SensorResult
from app.xhs_creation.agent.context import CreationContext

# 配图 prompt 合规黑名单(出现即判不合规)。
IMAGE_BANNED = ("logo", "brand", "品牌", "真人", "celebrity", "明星", "ui screenshot", "截图")
# 简单的互动/CTA 词典(命中视为结尾有引导)。
CTA_HINTS = ("收藏", "关注", "评论", "点赞", "转发", "试试", "你们", "大家", "欢迎", "留言", "码住", "蹲")


class CreationSchemaSensor:
    """计算型阻断传感器:按内容类型校验必填,缺失则强制修订。"""

    name = "结构完整性"

    def check(self, result: dict[str, Any], ctx: CreationContext) -> SensorResult:
        missing: list[str] = []
        if not str(result.get("title") or "").strip():
            missing.append("缺少标题,请补一个具体、有吸引力的标题")
        if not str(result.get("body_text") or "").strip():
            missing.append("缺少正文,请补全可直接发布的正文")
        if not (result.get("hashtags") or []):
            missing.append("缺少话题标签,至少给 3 个")
        if ctx.content_type == "image_note":
            plan = result.get("image_plan") or []
            if not plan or any(not str(p.get("prompt") or "").strip() for p in plan):
                missing.append("图文类型缺少配图计划或绘图描述,请为每张图补上 prompt")
        if ctx.content_type in ("spoken_script", "video_script"):
            segments = (result.get("script") or {}).get("segments") or []
            if not segments:
                missing.append("脚本类型缺少分段脚本,请按时间轴给出每段口播/画面")
        if missing:
            return SensorResult(passed=False, issues=missing, corrective_feedback="；".join(missing))
        return SensorResult(passed=True)


class CreationComplianceSensor:
    """计算型阻断传感器:扫描产出里的平台限流/违禁词,命中则强制重写。"""

    name = "平台合规"

    def check(self, result: dict[str, Any], ctx: CreationContext) -> SensorResult:
        niche = getattr(ctx.blogger, "niche", "") or ""
        hits = scan_creation(result, ctx.platform, niche=niche, extra_words=ctx.extra_block_words).creation_dict()["hits"]
        if not hits:
            return SensorResult(passed=True)
        # 人类可读问题:词(类别·所在字段)
        issues = [f"{h['word']}（{h['category']}·{h['field']}）" for h in hits]
        # 给模型的纠错指令:每个命中自带改法 hint,按类别去重。
        fixes_by_cat: dict[str, str] = {}
        for h in hits:
            fixes_by_cat.setdefault(h["category"], h.get("hint") or "换成不踩线的表达")
        fixes = "；".join(f"{c}:{hint}" for c, hint in fixes_by_cat.items())
        feedback = (
            f"以下词会被平台限流/违禁,必须改掉后重写(不要再出现这些词):{ '、'.join(dict.fromkeys(h['word'] for h in hits)) }。"
            f"改法:{fixes}。"
        )
        return SensorResult(passed=False, issues=[f"命中限流词:{ '、'.join(issues) }"], corrective_feedback=feedback)


class CreationQualitySensor:
    """计算型评分传感器:确定性打分并附改进项。"""

    name = "质量评分"

    def check(self, result: dict[str, Any], ctx: CreationContext) -> SensorResult:
        quality = evaluate_creation_quality(result, ctx)
        feedback = "；".join(quality["issues"]) if quality["issues"] else ""
        return SensorResult(passed=True, score=quality["score"], issues=quality["issues"], corrective_feedback=feedback)


def evaluate_creation_quality(generated: dict[str, Any], ctx: CreationContext) -> dict[str, Any]:
    """用确定性规则给创作产物打分(扣分制),并列出可改进项。"""
    issues: list[str] = []
    checks: list[dict[str, Any]] = []
    score = 100

    def deduct(amount: int, name: str, ok: bool, detail: str) -> None:
        nonlocal score
        checks.append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            score -= amount
            issues.append(detail)

    title = str(generated.get("title") or "").strip()
    body = str(generated.get("body_text") or "").strip()
    hashtags = generated.get("hashtags") or []

    deduct(15, "标题长度", 4 <= len(title) <= 40, f"标题长度 {len(title)} 字,建议 4-40 字之间")
    deduct(10, "正文篇幅", len(body) >= 60, f"正文偏短({len(body)} 字),建议展开到 ≥60 字")
    paragraphs = [p for p in body.replace("\r", "").split("\n") if p.strip()]
    deduct(10, "正文分段", len(paragraphs) >= 2, "正文没有分段,建议拆成多段更易读")
    deduct(15, "标签数量", 3 <= len(hashtags) <= 12, f"话题标签 {len(hashtags)} 个,建议 3-12 个")
    deduct(10, "标签干净", all("#" not in h for h in hashtags), "话题标签里不要带 # 号")
    has_cta = any(hint in body for hint in CTA_HINTS)
    deduct(10, "结尾互动", has_cta, "结尾缺少互动引导,建议加一句轻量互动")

    if ctx.content_type == "image_note":
        plan = generated.get("image_plan") or []
        deduct(15, "配图计划", bool(plan), "图文类型还没有配图计划")
        bad = sum(1 for p in plan if any(w in str(p.get("prompt") or "").lower() for w in IMAGE_BANNED))
        deduct(15, "配图合规", bad == 0, f"有 {bad} 张配图描述疑似含真人/品牌/截图,请改成干净的概念图")
    elif ctx.content_type in ("spoken_script", "video_script"):
        segments = (generated.get("script") or {}).get("segments") or []
        deduct(15, "脚本分段", len(segments) >= 2, f"脚本只有 {len(segments)} 段,建议 ≥2 段")
        if ctx.content_type == "video_script":
            with_scene = sum(1 for s in segments if str(s.get("scene") or "").strip())
            deduct(10, "分镜画面", segments and with_scene >= max(1, len(segments) // 2), "视频脚本的分镜缺少画面/镜头建议")

    score = max(0, min(100, score))
    grade = "优" if score >= 85 else ("良" if score >= 70 else "待改进")
    return {"score": score, "grade": grade, "issues": issues, "checks": checks, "content_type": ctx.content_type}
