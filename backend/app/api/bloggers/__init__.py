"""博主域 API。原 bloggers.py(845 行)按职责拆成子路由,本包把它们合到一个 router 再对外暴露
(main.py 仍 ``include_router(bloggers.router, ...)``,所有路径/方法不变)。

- :mod:`.crud`         —— 对标库 CRUD(增删改查 / 收藏 / 刷新资料)+ 笔记列表 + Skill 列表
- :mod:`.recommend`    —— 关键词搜索 + 智能推荐 + 单博主评分(对标发现的「评分」侧)
- :mod:`.skill_opt`    —— Skill 优化(训练)发起 + 训练记录
- :mod:`.collection`   —— 笔记采集(主页增量 / URL 定向)+ 采集批次 + 成本预估
- :mod:`.distillation` —— 蒸馏发起 + 选材快照 + 蒸馏记录
- :mod:`.dossier`      —— 博主档案:一键建档 + 聚合读 + 笔记池同步 + 爆文归因

注:各子路由都挂在无前缀的 ``/bloggers``…``/benchmark``…``/skill-training`` 等绝对路径上,
合并顺序不影响匹配(不存在裸 ``/bloggers/{id}`` 路由,字面量路径不会被参数路径遮蔽)。
"""

from fastapi import APIRouter

from . import collection, crud, distillation, dossier, recommend, skill_opt

router = APIRouter()
router.include_router(crud.router)
router.include_router(recommend.router)
router.include_router(skill_opt.router)
router.include_router(collection.router)
router.include_router(distillation.router)
router.include_router(dossier.router)

__all__ = ["router"]
