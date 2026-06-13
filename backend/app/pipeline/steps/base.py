from abc import ABC, abstractmethod

from app.pipeline.context import PipelineContext
from app.pipeline.events import record_event


class PipelineStep(ABC):
    name: str
    start_message: str

    def execute(self, context: PipelineContext) -> None:
        record_event(context, self.name, "running", self.start_message)
        try:
            message, payload = self.run(context)
        except Exception as exc:
            context.db.rollback()
            record_event(context, self.name, "failed", f"{self.name}失败：{exc}")
            raise
        record_event(context, self.name, "succeeded", message, payload)

    @abstractmethod
    def run(self, context: PipelineContext) -> tuple[str, dict | None]:
        raise NotImplementedError
