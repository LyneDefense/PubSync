"""把合成循环的内部事件翻译成面向用户的「思考过程」短句。

原则:通俗、口语、适度;绝不出现代码、字段名、JSON、传感器类名、英文术语。
只播关键节点(起草→自检→优化→达标),不逐条 dump 原始 issues(那些可能含技术措辞)。
"""

from __future__ import annotations

from typing import Any


def _score_txt(score: Any) -> str:
    return f"(质量打分 {score})" if isinstance(score, int) else ""


def humanize_event(kind: str, payload: dict[str, Any], *, subject: str, gerund: str) -> tuple[str, str, str] | None:
    """返回 (阶段, 状态, 文案);返回 None 表示这条不展示。

    subject:名词,如「内容」「博主方法论」「账号对比」。
    gerund:动词短语,如「起草」「提炼」「分析」。
    """
    attempt = payload.get("attempt")
    if kind == "attempt_start":
        if attempt and attempt > 1:
            return ("思考过程", "running", f"正在第 {attempt} 版重新{gerund}{subject}…")
        return ("思考过程", "running", f"正在{gerund}{subject}…")
    if kind == "verified":
        if payload.get("passed"):
            return None  # 通过的话由 final 统一播报,避免重复
        n = len(payload.get("issues") or [])
        hint = f"发现 {n} 处可以更好的地方" if n else "感觉还能更到位"
        return ("自检", "running", f"自检了一遍,{hint}{_score_txt(payload.get('score'))},正在优化…")
    if kind == "reviewing":
        return ("深度评审", "running", "再换个审稿视角挑挑毛病…")
    if kind == "revising":
        return None  # 已由 verified 的「正在优化」覆盖,避免啰嗦
    if kind == "final":
        revisions = payload.get("revisions") or 0
        score_txt = _score_txt(payload.get("score"))
        if payload.get("passed"):
            tail = f",共自我优化 {revisions} 次" if revisions else ",一次到位"
            return ("完成", "running", f"{subject}达标{score_txt}{tail}。")
        return ("完成", "running", f"已尽力打磨({revisions} 次),先给出当前最好的一版{score_txt}。")
    return None
