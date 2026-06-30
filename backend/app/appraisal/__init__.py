"""博主诊断内核:硬实力(hard,纯算)+ 软实力/垂直度(judge,模型)+ 合规(复用 compliance 引擎)。

诊断别人:硬+软+合规;诊断自己:硬+合规。编排在 service.py(P4)。
"""

from app.appraisal.hard import AccountStat, HardDim, PostStat, hard_dimensions
from app.appraisal.intent import suggest_intent
from app.appraisal.judge import JudgedDim, judge_soft, judge_vertical
from app.appraisal.service import run_appraisal

__all__ = [
    "AccountStat",
    "PostStat",
    "HardDim",
    "hard_dimensions",
    "JudgedDim",
    "judge_vertical",
    "judge_soft",
    "suggest_intent",
    "run_appraisal",
]
