"""对标发现「搜索」侧:关键词搜索博主(附火爆度速览)。"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import current_tenant, settings
from app.benchmark_discovery.engine import popularity_score
from app.blogger_distillation.search import search_bloggers
from app.blogger_distillation.tikhub_client import TikHubError
from app.models import Tenant
from app.schemas import BloggerSearchResultRead

router = APIRouter()


@router.get("/bloggers/search", response_model=list[BloggerSearchResultRead])
def search_bloggers_endpoint(
    platform: str = Query(default="xhs", pattern="^(xhs|douyin)$"),
    keyword: str = Query(min_length=1, max_length=100),
    page: int = Query(default=1, ge=1, le=20),
    tenant: Tenant = Depends(current_tenant),
) -> list:
    _ = tenant
    try:
        results = search_bloggers(settings, platform, keyword, page)
    except TikHubError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # 附火爆度速览(仅按粉丝数粗算,免费);完整「智能推荐 + 候选打分」已下线。
    return [{**r.__dict__, "quick_popularity": popularity_score(r.follower_count, [])} for r in results]
