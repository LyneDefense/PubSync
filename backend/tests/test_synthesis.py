from app.synthesis import SynthesisBudget, SensorResult, TaskGuide, run_synthesis
from app.synthesis import loop as synthesis_loop
from app.config import Settings


def _settings() -> Settings:
    return Settings(auth_secret="unit-test-secret")


class _ScriptedModel:
    """假模型：按顺序吐预设响应，并记录调用次数。"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def __call__(self, settings, prompt, model=None):
        self.calls += 1
        return self.responses[min(self.calls - 1, len(self.responses) - 1)]


class _ScoreSensor:
    """评分传感器：按 attempt 顺序给分；<80 视为有改进项并给反馈。"""

    name = "score"

    def __init__(self, scores):
        self.scores = list(scores)
        self.index = 0

    def check(self, result, ctx):
        score = self.scores[min(self.index, len(self.scores) - 1)]
        self.index += 1
        below = score < 80
        return SensorResult(
            passed=True,
            score=score,
            issues=["分数偏低"] if below else [],
            corrective_feedback="请提高质量" if below else "",
        )


class _BlockingOnceSensor:
    """阻断传感器：第一次不通过，之后通过。"""

    name = "schema"

    def __init__(self):
        self.index = 0

    def check(self, result, ctx):
        self.index += 1
        if self.index == 1:
            return SensorResult(passed=False, issues=["结构缺失"], corrective_feedback="补全结构")
        return SensorResult(passed=True)


class _ScriptedSensor:
    """按 attempt 顺序返回预设的 (passed, score)。"""

    name = "scripted"

    def __init__(self, verdicts):
        self.verdicts = list(verdicts)
        self.index = 0

    def check(self, result, ctx):
        passed, score = self.verdicts[min(self.index, len(self.verdicts) - 1)]
        self.index += 1
        return SensorResult(passed=passed, score=score, corrective_feedback="" if passed else "修一下")


def _guide() -> TaskGuide:
    return TaskGuide(name="t", build_prompt=lambda ctx: "base-prompt")


def _budget(max_attempts=2, min_score=80) -> SynthesisBudget:
    return SynthesisBudget(max_attempts=max_attempts, min_score=min_score)


def test_passes_first_try_no_extra_calls(monkeypatch):
    model = _ScriptedModel([{"v": 1}])
    monkeypatch.setattr(synthesis_loop, "create_json_response", model)
    result, trace = run_synthesis(_settings(), _guide(), None, [_ScoreSensor([95])], _budget())
    assert model.calls == 1
    assert trace.revisions == 0
    assert trace.final_passed is True
    assert trace.final_score == 95


def test_fails_once_then_revises_to_pass(monkeypatch):
    model = _ScriptedModel([{"v": 1}, {"v": 2}])
    monkeypatch.setattr(synthesis_loop, "create_json_response", model)
    result, trace = run_synthesis(_settings(), _guide(), None, [_ScoreSensor([50, 90])], _budget(max_attempts=2))
    assert model.calls == 2
    assert trace.revisions == 1
    assert trace.final_passed is True
    assert trace.final_score == 90
    assert result == {"v": 2}
    # 第二次尝试应带上纠错反馈
    assert trace.attempts[1].revised_with


def test_budget_exhausted_returns_best_so_far(monkeypatch):
    model = _ScriptedModel([{"v": 1}, {"v": 2}])
    monkeypatch.setattr(synthesis_loop, "create_json_response", model)
    result, trace = run_synthesis(_settings(), _guide(), None, [_ScoreSensor([40, 60])], _budget(max_attempts=2))
    assert model.calls == 2
    assert trace.final_passed is False
    assert trace.final_score == 60  # 取分数最高的那一版
    assert result == {"v": 2}


def test_blocking_sensor_forces_revision(monkeypatch):
    model = _ScriptedModel([{"v": 1}, {"v": 2}])
    monkeypatch.setattr(synthesis_loop, "create_json_response", model)
    # 分数一直 100，但首轮结构阻断 → 仍需修订一次
    result, trace = run_synthesis(
        _settings(), _guide(), None, [_BlockingOnceSensor(), _ScoreSensor([100, 100])], _budget(max_attempts=3)
    )
    assert model.calls == 2
    assert trace.revisions == 1
    assert trace.final_passed is True


def test_budget_exhausted_prefers_passing_over_higher_scoring_failed(monkeypatch):
    # attempt1: 通过但分数 60（未达 80，不停）；attempt2: 不通过但分数 95。
    # 预算用尽后应返回「通过」的那一版（attempt1 / {"v":1}），而不是分数更高但不通过的 attempt2。
    model = _ScriptedModel([{"v": 1}, {"v": 2}])
    monkeypatch.setattr(synthesis_loop, "create_json_response", model)
    result, trace = run_synthesis(
        _settings(), _guide(), None, [_ScriptedSensor([(True, 60), (False, 95)])], _budget(max_attempts=2)
    )
    assert trace.final_passed is False
    assert result == {"v": 1}
    assert trace.final_score == 60


def test_critic_runs_only_before_revision(monkeypatch):
    model = _ScriptedModel([{"v": 1}, {"v": 2}])
    monkeypatch.setattr(synthesis_loop, "create_json_response", model)
    critic_calls = {"n": 0}

    def critic(result, ctx):
        critic_calls["n"] += 1
        return "深度建议"

    # 第一轮就达标 → critic 不应被调用
    run_synthesis(_settings(), _guide(), None, [_ScoreSensor([95])], _budget(), critic=critic)
    assert critic_calls["n"] == 0

    # 第一轮不达标 → critic 调用一次后修订达标
    model2 = _ScriptedModel([{"v": 1}, {"v": 2}])
    monkeypatch.setattr(synthesis_loop, "create_json_response", model2)
    critic_calls["n"] = 0
    run_synthesis(_settings(), _guide(), None, [_ScoreSensor([50, 90])], _budget(max_attempts=2), critic=critic)
    assert critic_calls["n"] == 1
