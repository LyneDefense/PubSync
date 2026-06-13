"""轻量 LLM 合成 harness：在一次性模型调用外，加上 harness engineering 的
指南(guide) / 传感器(sensor) / 有界生成-校验-修订循环 / 预算 / 轨迹观测。

不替代 app/harness/（那是任务编排步骤流水线）；本模块作用在「模型调用」这一层，
由各 service 调用，包裹 ai_service.create_json_response。
"""

from app.agent_harness.budget import HarnessBudget
from app.agent_harness.guide import TaskGuide, with_feedback
from app.agent_harness.loop import Critic, run_synthesis
from app.agent_harness.sensors import Sensor, SensorResult, SensorVerdict, evaluate_sensors
from app.agent_harness.trace import AttemptRecord, HarnessTrace

__all__ = [
    "HarnessBudget",
    "TaskGuide",
    "with_feedback",
    "Critic",
    "run_synthesis",
    "Sensor",
    "SensorResult",
    "SensorVerdict",
    "evaluate_sensors",
    "AttemptRecord",
    "HarnessTrace",
]
