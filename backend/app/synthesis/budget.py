from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SynthesisBudget:
    """合成循环的停止条件（停止条件 stop conditions）。

    max_attempts：模型调用总次数上限（首次生成算第 1 次，之后每次修订 +1）。
    min_score：质量分达到该阈值即视为通过，可提前停止。
    """

    max_attempts: int = 2
    min_score: int = 80
