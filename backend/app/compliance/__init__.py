"""合规模块:词库 + 共享引擎(L1 词库正则 / L2 语义 / 品类感知 / 结构化分级 + 合规分)。

- wordlists：分级词库 + 品类红线 + 官方依据。
- engine：compliance_scan(texts, platform, industry, use_llm) → {score, grade, hits, has_ban}，三处复用。
- scan：scan_creation_output(创作产出闸门，向后兼容)。
"""

from app.compliance.wordlists import (
    CATEGORY_HINTS,
    SEVERITY_BAN,
    SEVERITY_NOTICE,
    SEVERITY_THROTTLE,
    build_blocklist,
    category_basis,
    category_severity,
    flatten_blocklist,
    prompt_guidance,
)
from app.compliance.scan import scan_creation_output
from app.compliance.engine import compliance_scan, compliance_score, scan_l1, scan_l2, verdict

__all__ = [
    "scan_creation_output",
    "build_blocklist",
    "flatten_blocklist",
    "CATEGORY_HINTS",
    "prompt_guidance",
    "category_severity",
    "category_basis",
    "compliance_scan",
    "compliance_score",
    "scan_l1",
    "scan_l2",
    "verdict",
    "SEVERITY_BAN",
    "SEVERITY_THROTTLE",
    "SEVERITY_NOTICE",
]
