"""规则包汇总。新增赛道 = 加一个 pack 文件并在这里登记,引擎零改动。"""

from __future__ import annotations

from app.compliance.packs.common import COMMON_PACK
from app.compliance.packs.cosmetics import COSMETICS_PACK
from app.compliance.packs.education import EDUCATION_PACK
from app.compliance.packs.finance import FINANCE_PACK
from app.compliance.packs.fitness import FITNESS_PACK
from app.compliance.packs.food_health import FOOD_HEALTH_PACK
from app.compliance.packs.maternal import MATERNAL_PACK
from app.compliance.packs.medical import MEDICAL_PACK
from app.compliance.packs.platform import PLATFORM_PACKS
from app.compliance.packs.recruit import RECRUIT_PACK

# 通用包(所有人) + 平台包(按平台) + 行业包(按赛道)
ALL_PACKS = (
    COMMON_PACK,
    *PLATFORM_PACKS,
    COSMETICS_PACK,
    MEDICAL_PACK,
    FOOD_HEALTH_PACK,
    MATERNAL_PACK,
    FINANCE_PACK,
    EDUCATION_PACK,
    FITNESS_PACK,
    RECRUIT_PACK,
)

__all__ = ["ALL_PACKS"]
