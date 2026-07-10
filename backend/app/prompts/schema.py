"""从 Pydantic 模型生成「给模型看的 JSON 示例」——字段名 + 中文说明,等价于手写 schema 字面量。

支柱一(typed return)的关键基建:prompt 里的输出 schema 段由模型**生成**,和 model_validate 校验
共用同一个 Pydantic 模型(单一事实源),消灭「schema 字段名手抄多处」的 drift。
生成的是给 LLM 的紧凑示例(字段→说明),不是 JSON-Schema 规范(那太啰嗦、模型也不需要)。

覆盖 str / list[str] / 嵌套 BaseModel / list[BaseModel];更复杂类型(Union/Optional/dict)随铺开再完善。
"""

from __future__ import annotations

import json
import typing

from pydantic import BaseModel


def _is_model(tp: typing.Any) -> bool:
    return isinstance(tp, type) and issubclass(tp, BaseModel)


def _placeholder(annotation: typing.Any, description: str) -> typing.Any:
    """按字段类型给一个占位值:str→说明;int/bool/float→示例值;list[X]→[占位];嵌套模型→递归 dict。"""
    if _is_model(annotation):
        return _model_example(annotation)
    if typing.get_origin(annotation) is list:
        args = typing.get_args(annotation)
        item = args[0] if args else str
        if _is_model(item):
            return [_model_example(item)]
        return [description or "值"]
    if annotation is bool:
        return True
    if annotation is int:
        return description or 1  # 无说明的 int(如 rank)给示例 1,等价手写 "rank": 1
    if annotation is float:
        return description or 0.0
    return description or ""


def _model_example(model: type[BaseModel]) -> dict[str, typing.Any]:
    return {name: _placeholder(f.annotation, f.description or "") for name, f in model.model_fields.items()}


def render_schema(model: type[BaseModel]) -> str:
    """生成给模型的 JSON 示例文本(缩进 2、保留中文)。"""
    return json.dumps(_model_example(model), ensure_ascii=False, indent=2)
