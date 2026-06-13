"""轻量 LLM 合成循环：在一次性模型调用外，加上
指南(guide) / 传感器(sensor) / 有界生成-校验-修订循环 / 预算 / 轨迹观测。

不替代 app/pipeline/（那是任务编排步骤流水线）；本模块作用在「模型调用」这一层，
由各 service 调用，包裹 ai_service.create_json_response。
"""

from app.synthesis.agent import Agent, run_agent
from app.synthesis.budget import SynthesisBudget
from app.synthesis.guide import TaskGuide, with_feedback
from app.synthesis.loop import Critic, ProgressSink, run_synthesis
from app.synthesis.progress import humanize_event
from app.synthesis.sensors import Sensor, SensorResult, SensorVerdict, evaluate_sensors
from app.synthesis.trace import AttemptRecord, SynthesisTrace

__all__ = [
    "Agent",
    "run_agent",
    "SynthesisBudget",
    "TaskGuide",
    "with_feedback",
    "Critic",
    "ProgressSink",
    "run_synthesis",
    "humanize_event",
    "Sensor",
    "SensorResult",
    "SensorVerdict",
    "evaluate_sensors",
    "AttemptRecord",
    "SynthesisTrace",
]
