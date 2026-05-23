from dataclasses import dataclass, field
from typing import Any


@dataclass
class DuplicateDecision:
    is_duplicate: bool
    duplicate_of_id: int | None
    reason: str
    similarity: float
    method: str


@dataclass
class DeduplicationReport:
    input_count: int
    unique_count: int
    duplicate_count: int
    direct_duplicate_count: int
    llm_duplicate_count: int
    review_count: int
    duplicates: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "输入": self.input_count,
            "保留": self.unique_count,
            "重复": self.duplicate_count,
            "直接判重": self.direct_duplicate_count,
            "大模型判重": self.llm_duplicate_count,
            "大模型复核": self.review_count,
            "重复明细": self.duplicates,
        }
