"""端点池路由:池全部失败时必须抛 TikHubError(而非裸 RuntimeError)。

回归保护:曾因抛裸 RuntimeError,导致采集里 `except TikHubError` 的评论优雅降级接不住,
一条评论 400 掀翻整批采集(见问题清单 / commit)。
"""

import pytest

from app.blogger_distillation.endpoint_router import Endpoint, EndpointRouter
from app.blogger_distillation.tikhub_client.base import TikHubError


def test_pool_exhaustion_raises_tikhub_error():
    def always_fail(path, params):
        raise TikHubError("boom")  # status_code=None → 降级 → 耗尽后应抛 TikHubError

    router = EndpointRouter(always_fail, {"comments": [Endpoint(group="g", path="/x", params={})]})
    with pytest.raises(TikHubError):
        router.call("comments", {})


def test_tikhub_error_is_runtimeerror_subclass():
    # 上层 `except (TikHubError, RuntimeError)` 的兜底依赖这一继承关系。
    assert issubclass(TikHubError, RuntimeError)
