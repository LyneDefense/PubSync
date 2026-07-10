"""Prompt 治理公共层:呈现骨架(blocks) + schema 渲染(render_schema)。

见 docs/prompt治理_方案设计.md。支柱一(typed return)靠 render_schema 从 Pydantic 单一源生成
prompt 里的 schema 段;支柱二(去重复)靠 blocks 把抗注入/rules/output_schema 骨架收敛到一处。
"""

from app.prompts.blocks import anti_injection, output_schema, rules_block
from app.prompts.schema import render_schema

__all__ = ["anti_injection", "output_schema", "rules_block", "render_schema"]
