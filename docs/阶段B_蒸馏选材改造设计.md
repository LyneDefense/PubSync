# 阶段 B:博主资产改版 + 蒸馏选材改造(问题清单 #5)

> 砍掉"采集历史(批次)"视图,博主详情改"笔记按类型分类 + 单篇详情";蒸馏选材从"选采集批次"
> 改为"从笔记池选材"。决策已与用户敲定,见下。

## 决策(已定)
- **蒸馏两种入口**:
  - **自动蒸馏**:一键,预设 = **高赞 top-N**(取该博主笔记池里分数最高的 N 篇),内部按模态分车道,产出通用 skill。**不创建快照**(临时)。
  - **自定义蒸馏**:用户选一个**已有快照** 或 **手选 N 篇** → 蒸馏;**自定义这次自动存成一个快照**(可复用/回看)。
- **不自动补样本**;数量不足给提示。**最低硬下限 8 篇**(<8 拦截),**软建议 ≥15**(界面提示越多越准)。
- **单篇详情 = 右侧抽屉**,只展示:标题 / 类型·赞藏评·发布时间 / 正文或口播逐字稿摘要(~200 字,可「展开全文」)/ 话题标签 / TOP3 热评。
- **采集历史(批次)**前端隐藏(后端保留,增量/下架对账要用);**蒸馏历史**保留,按时间列。

## 数据模型
- 新增表 **`blogger_snapshots`**:`id / tenant_id / blogger_id / name / post_ids_json / created_at`。自定义蒸馏自动建一条(默认名「自定义 · M月D日 HH:mm」,可后续重命名)。
- `BloggerDistillationRun` 加列 **`snapshot_id: int|None`**(自定义蒸馏指向快照;自动蒸馏为 NULL)+ **`selection_json`**(记录这次实际蒸的 `post_ids` 与来源 auto/custom,便于回看/复现)。`collection_run_id` 保留兼容旧数据。
- 迁移 `0010_blogger_snapshot.py`:建表 + 加两列(幂等)。

## 后端
- **配置**(`config.py`):`blogger_auto_distill_top_n: int = 30`、`distill_min_samples: int = 8`、`distill_recommend_samples: int = 15`。
- **蒸馏入参改造**:`run_blogger_distillation(... )` 由 `collection_run_id` 改为接受 **`post_ids: list[int]`**(从池子选)+ `source`(auto/custom)+ `snapshot_id|None`。
  - 取 posts:`BloggerPost.id in post_ids`、同博主、`status != delisted`。
  - 校验 `len(posts) >= settings.distill_min_samples` 否则报错(带提示)。
  - `scope` 由所选 posts 的 `content_subtype` 集合推导(替代旧的手选 subtypes 入参)。
  - 其余(analyze_posts 分车道、harness、artifacts、质量分)复用。
- **接口**:
  - `POST /bloggers/{id}/distill`:body `{source:"auto"|"custom", post_ids?:[], snapshot_id?:int, name?:str}`。
    - auto:服务端取高赞 top-N → post_ids;不建快照。
    - custom:用 post_ids 或 snapshot 的 post_ids;**自动建/复用快照**;校验下限 8。
  - 快照 CRUD:`GET /bloggers/{id}/snapshots`、`POST /bloggers/{id}/snapshots`(名+post_ids)、`DELETE /snapshots/{id}`、`PATCH` 改名。
- 任务层 `run_blogger_distillation_task` 透传新入参。

## 前端(博主资产改版)
- **笔记池按类型分组**(图文/口播视频/非口播视频/未知)的列表,替代"采集批次"视图;每条可勾选。
- **单篇详情右侧抽屉**(内容如上,精简 + 展开全文)。
- **蒸馏区**:
  - 「自动蒸馏」按钮(一键,高赞 top-N);
  - 「自定义蒸馏」:勾选笔记(显示已选数 + 「需 ≥8,建议 ≥15」提示,<8 禁用)/ 选已有快照 → 蒸馏(自动存快照)。
  - 快照列表(选择/重命名/删除)。
- **蒸馏历史**按时间展示(去掉"来自第几次采集");**采集历史/批次前端移除**。
- types/api:`BloggerSnapshot` 类型 + 快照 CRUD;`distillBlogger` 入参改 source/post_ids/snapshot_id。

## 分期(B 内部)
- **B1 后端**:迁移 0010 + 快照表/列 + distill 改 post_ids + auto/custom + 快照 CRUD + 配置 + 任务透传 + 单测。
- **B2 前端**:博主资产改版(分组列表 + 抽屉 + 自动/自定义蒸馏 + 快照管理 + 蒸馏历史按时间 + 移除批次视图)。
- B1 先上(后端可独立测),B2 再上。

## 验证
- B1:auto 蒸馏取高赞 top-N 跑通;custom 手选/快照跑通并自动建快照;<8 篇被拦;scope 按所选模态;ruff+pytest;迁移 0010 幂等。
- B2:博主详情分组+抽屉可用;自动/自定义蒸馏入口跑通;快照可选/改名/删;蒸馏历史按时间;无批次视图;build 通过。
- 按 CLAUDE.md:提交(无 co-author)+ push + 部署(有迁移走 `update`)。

## 不做 / 注意
- 不删采集批次表(增量/下架对账仍依赖);只是蒸馏不再用它选材、前端不展示。
- 自动蒸馏不建快照(临时);只有自定义建。
- 旧蒸馏记录(带 collection_run_id 的)仍能正常展示。
