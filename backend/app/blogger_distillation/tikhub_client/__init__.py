"""TikHub client, split into transport (base), parsers and per-platform clients.

Re-exported here so existing ``from app.blogger_distillation.tikhub_client import X``
imports keep working.
"""

from app.blogger_distillation.tikhub_client.base import (
    TikHubBaseClient,
    TikHubError,
    TikHubUsage,
    UserNotesResult,
    XhsPostCandidate,
    shared_http_client,
    summarize_payload,
)
from app.blogger_distillation.tikhub_client.douyin_client import TikHubDouyinClient
from app.blogger_distillation.tikhub_client.parsers import (
    first_int,
    first_str,
    parse_timestamp,
    recursive_find,
    unwrap_payload,
)
from app.blogger_distillation.tikhub_client.xhs_client import TikHubXhsClient

__all__ = [
    "TikHubBaseClient",
    "TikHubError",
    "TikHubUsage",
    "UserNotesResult",
    "XhsPostCandidate",
    "shared_http_client",
    "summarize_payload",
    "TikHubXhsClient",
    "TikHubDouyinClient",
    "first_int",
    "first_str",
    "parse_timestamp",
    "recursive_find",
    "unwrap_payload",
]
