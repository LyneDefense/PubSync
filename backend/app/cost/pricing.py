"""模型单价表:内置默认 + 后台覆盖(SystemConfig 的 ``model_prices`` JSON)。

供应商只返回 token / 图数,不返回金额;这里用单价折算估算金额。单价可在后台编辑。
- 文本:每 1000 token 单价(分输入/输出),USD。
- 图像:每张单价,USD。
默认值取自公开定价的近似值,仅作初值,管理员应按实际账单校准。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models import SystemConfig

logger = logging.getLogger(__name__)

CONFIG_KEY = "model_prices"

# model -> {"input_per_1k": x, "output_per_1k": y} (USD)
TEXT_PRICES: dict[str, dict[str, float]] = {
    "gpt-4.1": {"input_per_1k": 0.002, "output_per_1k": 0.008},
    "MiniMax-M2.7": {"input_per_1k": 0.001, "output_per_1k": 0.001},
}
# model -> price per image (USD)
IMAGE_PRICES: dict[str, float] = {
    "gpt-image-1": 0.04,
    "image-01": 0.01,
}

# 未知模型的兜底单价。
DEFAULT_TEXT = {"input_per_1k": 0.001, "output_per_1k": 0.001}
DEFAULT_IMAGE = 0.02


def default_prices() -> dict[str, Any]:
    return {"text": dict(TEXT_PRICES), "image": dict(IMAGE_PRICES)}


def load_prices(db: Session) -> dict[str, Any]:
    """合并内置单价 + 后台覆盖(SystemConfig.model_prices)。"""
    prices = default_prices()
    row = db.get(SystemConfig, CONFIG_KEY)
    if row and row.value:
        try:
            override = json.loads(row.value)
            for section in ("text", "image"):
                if isinstance(override.get(section), dict):
                    prices[section].update(override[section])
        except (ValueError, TypeError):
            logger.warning("model_prices 覆盖解析失败,使用内置单价")
    return prices


def price_text(prices: dict[str, Any], model: str | None, prompt_tokens: int, completion_tokens: int) -> float:
    table = prices.get("text", {})
    entry = table.get(model or "", DEFAULT_TEXT)
    cost = (prompt_tokens / 1000.0) * float(entry.get("input_per_1k", DEFAULT_TEXT["input_per_1k"]))
    cost += (completion_tokens / 1000.0) * float(entry.get("output_per_1k", DEFAULT_TEXT["output_per_1k"]))
    return round(cost, 6)


def price_image(prices: dict[str, Any], model: str | None, n: int = 1) -> float:
    table = prices.get("image", {})
    unit = float(table.get(model or "", DEFAULT_IMAGE))
    return round(unit * max(0, n), 6)
