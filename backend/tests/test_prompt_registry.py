"""Prompt registry(P1):装饰器登记「函数身份」+ list_prompts 一览;调用方式不变。"""

from app.prompts import get, list_prompts, load_all_sites, prompt
from app.prompts.registry import PROMPT_REGISTRY


def test_decorator_registers_and_returns_original():
    calls = []

    @prompt("test.site", version="v1", model="glm-x", kind="one_shot", owner="me", note="hi")
    def build(x):
        calls.append(x)
        return f"prompt:{x}"

    assert build("A") == "prompt:A" and calls == ["A"]  # 原样返回,调用不变
    site = get("test.site")
    assert site.version == "v1" and site.model == "glm-x" and site.kind == "one_shot"
    assert site.owner == "me" and site.meta == {"note": "hi"} and site.func is build
    PROMPT_REGISTRY.pop("test.site", None)


def test_load_all_sites_lists_real_prompts():
    load_all_sites()
    names = {s.name for s in list_prompts()}
    assert {"distill.core.system", "distill.lane.system", "distill.critic", "creation.system"} <= names
