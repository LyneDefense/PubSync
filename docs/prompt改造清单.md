# Prompt 站点改造清单

> 全库 24 处 prompt + 2 处生图。总诊断:**内容普遍在线,问题系统性地集中在「分层」——角色 + 稳定规则 + 输出 schema + few-shot 全塞进 user,business-level system 为空。**
> 逐项改,改完打勾、记 commit。

## 根因 / 地基(最高杠杆)
`services/ai_service.py` 的 `create_json_response` 原来只收一个 `prompt`(进 user),system 是各 provider 写死的通用句 → 没有地方放业务 system。
**地基改动**(已提交):给 `create_json_response` + 四个 provider 加可选 `system=` 参 + `_compose_system`(传业务 system 就用「业务角色 + JSON 契约」,不传退回旧通用句,向后兼容)。之后每个站点把角色 / 硬边界 / schema 契约上移 system。

## 改造四原则(每项都按这个改)
1. **分层**:角色 + 硬规则 + 输出契约 → `system`;本次可变数据(证据 / 草稿 / 抓取内容)→ `user`。
2. **抗注入**:凡 user 里塞了**抓来的不可信内容**(笔记 / 评论 / 新闻原文),契约必须在 system,别和脏数据同层。← 本轮最实际的收益。
3. **枚举化**:能枚举的字段(category / role / layout / content_goal / aspect)给死枚举,别开放。
4. **输出强约束**:能 code 侧强制的(字数 / 必填 / 枚举)别只写 prompt;一次性站点补「解析失败 / schema 不符重试一次」。

## 改造顺序(value-first:高频 + 吃脏数据优先)
`D1 D2`(蒸馏)→ `C1 C2`(创作)→ `W1 W3`(公众号)→ `G1`(受众)→ `U1 U2`(vision 热身)→ critic 三兄弟 `D3 C4 P2`(最后抽公共骨架)→ 其余。

---

## 站点清单

图例:`[ ]` 待改 · `[x]` 已改 · 👍样板 · ⚠️重点 · 💤已弃用

### 蒸馏 · blogger_distillation
- [x] **D1** `service/distill_engine.py` — 蒸馏**内核**(认知/策略/人设,跨模态)· 拆 `build_core_system`(契约)/ `build_core_prompt`(证据)+ 抗注入;synthesis loop 支持 `build_system`(D2/C1/P1 复用)
- [x] **D2** `service/distill_engine.py` — 蒸馏**分车道**· 拆 `build_lane_system`/`build_lane_prompt` + XML + trim `_LANE_FRAMING[VIDEO]` + few-shot;加规则「拍法只进 video_script_structures、别重复进 language_dna」治冗余
- [ ] **D3** `service/distill_engine.py:248` — 蒸馏**质量评审** critic(抽公共骨架)

### 创作 · xhs_creation
- [ ] **C1** `agent/guide.py`（经 `service.py:324` run_agent）— 创作**主 prompt**（发布包草稿)👍唯一系统性 few-shot
- [ ] **C2** `service.py:252` — **选题**生成(对标法 × 我的受众 × 意图)
- [ ] **C3** `agent/benchmark.py:44` — **对标对比**(草稿 vs 对标画像)
- [ ] **C4** `agent/critic.py:30` — 创作 critic(并入公共骨架)

### 诊断 / 体检 · appraisal + account_audit
- [ ] **P1** `account_audit/agent/guide.py`（经 `service.py:94`）— **我的账号体检**主 prompt · agent-loop
- [ ] **P2** `account_audit/agent/critic.py:24` — 体检 critic(并入公共骨架)
- [ ] **P3** `appraisal/intent.py:92` — **意图澄清**(想学什么 / 想诊断什么)
- [ ] **P4** `appraisal/gap.py:81` — **我 vs 对标 打法差距** 👍aspect 枚举 + 字数上限
- [ ] **P5** `appraisal/judge.py:49` — 账号**垂直度**判定 👍枚举明确
- [ ] **P6** `appraisal/judge.py:105 / 157` — **对标价值**判定(值不值得学,2 次)
- [ ] **P7** `appraisal/judge.py:196` — 笔记与意图**相关性**

### 采集理解 · blogger_distillation
- [ ] **U1** `vision.py:138`(VISION_PROMPT)— 图文**视觉**(图内文字 / 封面 OCR)⚠️VLM 链路无 system,`glm_vision_chat` 先加 system 参;role/layout 枚举
- [ ] **U2** `vision.py:150`(MOTION_PROMPT)— 视频**拍法**(代表帧 VLM:出镜 / 景别 / 字幕 / 转场)⚠️同 U1
- [ ] **U3** `service/tagging.py:120` — 内容**主题标签**(3–N 个)+ 数量硬约束
- [ ] **U4** `modality_adjudicator.py:58` — **模态裁决**(口播 / 非口播)👍全库最健康 💤已弃用留档,可能不用改

### 建档 · blogger_dossier
- [ ] **G1** `audience.py:63` — **受众需求**(读者最常问)👍诚实边界样板(评论<8 直接拒)

### 公众号 · news / article
- [ ] **W1** `news_processing/service.py:24` — 新闻**清洗 / 结构化**(category 开放 → 枚举)
- [ ] **W2** `news_deduplication/service.py:150` — 新闻**去重**
- [ ] **W3** `article_composition/service.py:20` — 文章**正文成文**(写作规范最重,压 user 最多)

### 生图(另算)
- [ ] **I1** `services/ai_service.py:~55` — 新闻**配图决策 + 英文生图词**(should_generate + prompt + fallback + 安全约束)
- [ ] **I2** `tools/image_tool.py:120`(build_cover_prompt)— **封面**生图词

---

## Backlog · 结构性重构(定了方案,暂缓)

**蒸馏 schema 单一事实源(Pydantic 模型)** — 2026-07-09 review distill_engine.py 时定。
- **问题**:蒸馏输出 schema 字段名(`body_structures`/`core_beliefs`/`title_formulas`…)**手抄在 ~7 处、跨 3 文件**(prompt schema 字面量 / `normalize`(`_LANE_LIST_KEYS`、`_CORE_LAYERS`+`_COGNITIVE_KEYS` 同组抄两遍)/ 质量分 / 阻断传感器+is_*_empty / artifacts label / creation_kit),无共享定义 → 改名漏一处 = silent 空字段。
- **方案**(用户认可):建 `blogger_distillation/schema.py` 的 Pydantic 模型 `CoreDistillation`/`LaneContent`,**description 挂在字段上**(现在 prompt 里 `"one_glance":"一句话说清…"` 那句挂 `Field(description=...)`);prompt schema 段改成 `render_skeleton(model)` **生成**;`normalize_*`→`model_validate`(`_as_list` 做 `field_validator(mode="before")`;`extra="ignore"`+默认值 兼容老 report_json);质量分权重挂 `Field(json_schema_extra=...)` 放第二步。**顺带吃掉 D2**(车道 schema 生成后进 system)。
- **状态**:DEFERRED(用户"先记下来,先不急着改")。等 prompt 分层收尾或下次大改 schema 时,作独立小重构。守卫测试临时方案已被否决(要根治)。

## 进度日志
| 项 | commit | 说明 |
|----|--------|------|
| 地基 | `29050d2` | ai_service `system=` 参 + `_compose_system` |
| D1 | `8e58e56` | synthesis loop 支持 `build_system`;蒸馏内核拆 system(契约)/user(证据)+ 抗注入。样板确立 |
| D1+ | _(本次)_ | 内核 prompt 按最佳实践优化:XML 分隔(`<rules>`/`<quality_bar>`/`<output_schema>`/`<evidence>`)+ 加 few-shot 质量标杆(打"正确的废话")。查证 GLM 已开 JSON 模式 + temp 0.2,故 ④⑥ 无需动 |
