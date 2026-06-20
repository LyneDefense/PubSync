# Skill 训练方案设计（基于 SkillOpt 思路）

> 起草 2026-06-20。目标：把"一次性蒸馏出的静态 Skill"升级为"可训练、且能给出可量化提升数据"的资产。
> 本文是方向性设计，未写代码。决策门控见每阶段「Gate」。

## 0. 一句话目标
对每个对标博主，产出一份**训练后的 `best_skill.md`**，并用**该博主自己从未参与训练的真实笔记（test 集）**量出"训练前 vs 训练后"的风格保真度提升数（例：62 → 78，+16 分），作为是否值得推广的依据。

---

## 1. 背景与现状
- **现状链路**：采集博主笔记 → 一次性蒸馏出 `skill_markdown`（`blogger_distillation/service/distillation.py`，静态，提炼完即定）→ 创作时把 skill 喂给 `xhs_creation/agent/*`，每篇靠 synthesis harness 自检修订（推理时成本）。
- **痛点**：skill 是"一次猜中"，没有反馈回路；好不好全凭蒸馏 prompt，无法度量、无法改进。
- **SkillOpt 是什么**：微软开源库（`pip install skillopt`，MIT）。不训练模型权重，而用"文本梯度"反复改写一份 `skill.md`；循环为 `rollout → reflect → aggregate → select → update → evaluate`，**validation-gated**（只有验证集变好才保留改写），产出精炼 `best_skill.md`。支持 Claude 后端。
  - 来源：https://github.com/microsoft/SkillOpt

## 2. 关键洞察：博主真实笔记 = gold 标签
SkillOpt 自带 benchmark 有客观答案；我们"模仿博主写小红书"没有标准答案。**但博主自己的真实笔记，就是"这个博主会怎么写"的黄金答案。** 于是把任务转成一个有监督设置：

- 给定博主真实笔记的**选题/标题**为输入，让 skill 生成一篇，去**对比该博主真实那篇**的相似度（风格、结构、语言 DNA）。
- 相似度越高 = skill 越"懂"这个博主。

这把"无标签"难题解掉了，是整套方案能成立的根基。

## 3. 数据划分（每个博主一套）
要求该博主在架（status != delisted）笔记 **≥ 24 篇**（不足则不训练，提示用户多采）。同模态优先；混模态也允许（引擎内部已分书面/口播）。

| 集合 | 占比 | 用途 |
|---|---|---|
| **train** | ~60% | 蒸出种子 skill + rollout 的 few-shot 范例 |
| **val** | ~20% | 验证门控：候选 skill 只有在 val 上提升才保留（防过拟合 train） |
| **test** | ~20% | 全程不参与训练，**最终提升数只在此集上报告** |

- 划分按"选题去重 + 时间分层"随机，避免把同主题系列拆到训练/测试两边造成泄漏。
- rollout/eval 的"题目" = val/test 笔记的真实选题与核心信息点（不泄漏正文）。

## 4. 度量体系（成败核心，必须先做扎实）

**原则：全程零人工标注。** 面向客户的产品不能要求任何人（客户或我们）手动给样本打分来背书评委。可信度改由"博主真实笔记自身"作锚点自动建立。度量分三层，越靠前越客观、越难被刷。

### 4.1 客观风格指纹距离 StyleDist（确定性，无 LLM、无人工）
从博主真实笔记建一份**风格指纹**（纯文本统计，可复现）：标题模式正则命中分布、句长/段落数分布、emoji 率、话题标签数、开篇类型分布、高频 n-gram/口头禅词表、书面 vs 口播比例等。对候选算它到该指纹的距离（越近越像）。
- 完全确定性，无模型调用、无人工；可作奖励分量，也是评委的"客观对照"。
- 复用已有：`blogger_distillation/analysis.py`、`quality.py`、`compliance`。

### 4.2 风格归属判别 StyleAttribution（自动，有客观标签）
把候选与"该博主真实笔记 / 其它博主真实笔记"一起做归属：嵌入向量最近邻 / 轻量分类器判"这像不像该博主"。**因为我们知道每篇的真实作者，标签是客观的，不需要人标。** 报 AUC/准确率。

### 4.3 可辨别度 Detectability（自动，有客观标签，最难刷）
判别器看"候选 + 一篇该博主真实笔记"，指认哪个是 AI 写的。**我们知道谁真谁假，标签客观。** 判别越难（越接近随机 50%）= 越像真人。比 rubric 更难被 reward hacking。

### 4.4 LLM 评委 SFS（0–100，rubric 细分，用于反思的"文本梯度"）
一个冻结的强模型评委，按 rubric 逐维打分 + 给理由（理由喂给反思阶段当文本梯度）：选题契合(20)/标题钩子(20)/正文结构(25)/语言DNA(25)/合规(10，硬门)。
- 训练阶段需要它的"理由"来指导改写，所以保留；但它**不单独决定"提升数"**——见 4.5。

### 4.5 评委凭什么可信：自动锚点电池（替代原 Gate 0 人工打分）
不让人打分，改让评委通过一组**用现有数据就能自动构造的 sanity 测试**（锚点电池），全自动、可重复、客户无感：
1. **单调分离**：喂"该博主真实笔记 → 应高分"、"其它博主真实笔记 → 应低分"、"通用 AI 套话 → 更低"、"打乱/胡言 → 最低"。评委分数若不能单调拉开，就是不可信 → 调 prompt/模型，不进训练。
2. **判别校准**：在已知真假的对子上测评委判别准确率（4.3）。在"真 vs 真"对子上应接近 50%（不该乱猜），在"真 vs 烂"对子上应接近 100%。
3. **与客观层一致性**：评委 SFS 必须与 StyleDist/StyleAttribution **方向一致**（同升同降）才采信；不一致时以客观层为准。

> 结论：最终对客户展示的"提升数"由**客观层(4.1–4.3)主导 + 评委(4.4)佐证**，三者方向一致才报。任何人都不用手动打分。

## 5. 训练循环（SkillOpt 适配版，每个博主）
1. **种子 skill** = 现有一次性蒸馏输出（train 集蒸）。
2. for epoch in 1..E：
   - **Rollout**：抽 K 个 train/val 选题，用当前 skill（模型冻结）各生成一篇。
   - **Reflect（文本梯度）**：评委给每篇打 SFS + 指出差距；反思 LLM 读"低分案例 + 差距 + 对应真实笔记"，产出对 skill 的**具体改写建议**（如"标题缺『数字+悬念』公式""正文应痛点开篇，你写成了功能罗列"）。
   - **Aggregate + Update**：合并建议 → 候选 skill。
   - **Validation gate**：候选在 **val** 上测 SFS；优于当前最优（超噪声阈值）才采纳，否则丢进 rejected-edit buffer（避免重复同类无效改写）。
3. 取 val SFS 最高者为 `best_skill.md`。
4. **最终评估**：在 **test** 集上跑 种子 vs best 的 SFS + Detectability + 给几对并排样例 → 这就是"可量化提升数据"。

> 早停：val SFS 连续两轮无提升即停，省成本。

## 6. 用库还是自研？
我们已有 80% 机件：synthesis harness（`run_agent`、critic、sensors、revisions 计数）、任务队列（RQ）、成本记账（CostEvent）、事件流（LiveProgress）。
- **Phase 0 PoC 用 SkillOpt 库**：它有现成、验证过的循环（textual learning-rate、rejected-edit buffer、meta-update），最快验证"+X% 提升"在我们数据上成不成立；支持 Claude 后端。
- **若 PoC 成立**：再决定"保留库当离线训练器"还是"把循环移植进自家 harness（更贴合、可控）"。**先别过早移植**。
- **隔离**：训练器藏在一个接口后（`SkillTrainer.train(seed, datasets) -> TrainResult`），库只是其中一个实现，便于将来替换。

## 7. 集成架构（PoC 通过后）
- **离线训练任务**：`run_skill_training_task`（RQ task，与采集/蒸馏同款）。发 `record_task_event` → 在 LiveProgress 面板显示 epoch、val SFS 曲线、当前最优。
- **数据模型**：新增 `SkillTrainingRun`：`blogger_id, seed_skill_id, best_skill_md, baseline_sfs, best_sfs, lift, detectability_before/after, val_curve_json, test_report_json, epochs, cost_tokens, status`。Alembic 迁移。
- **存储**：best_skill 作为一个新的 skill 版本挂在 run 上；创作时可选"用训练后的 skill"。
- **模型/参数**（入 `config.py` + admin 可调）：评委模型、生成模型、反思模型；E（epochs）、K（rollouts）、min_notes、val/test 比例、噪声阈值、预算上限。
- **成本记账**：训练每次 LLM 调用挂进 CostEvent，run 汇总 `cost_tokens`，后台可见。
- **前端**：蒸馏页某个 skill 上加「训练这个 Skill」→ 训练进度 → 完成后一张 **「训练前/后对比卡」**：`test SFS 62→78（+16）`、`可辨别度 81%→58%`、几对并排示例。这张卡就是你要的"可量化效果提升数据"。

## 8. 成本模型（说实话给数量级）
每博主单次训练 ≈ `E×(K 生成 + K 评判 + 1 反思) + 每轮 val 评估 + 1 次 test 评估`。
- 取 E=4、K=6、val=4、test 集 ~5：≈ 每轮 6 生成+6 评判+1 反思+4 val生成+4 val评判 ≈ 21 次；×4 ≈ 84 次 + test ~10 ≈ **~95 次 LLM 调用/博主**。
- 生成用中端模型、评委用强模型；**一次性离线成本**，之后这个博主所有创作都复用训练后的 skill（推理更省、自检修订更少），可摊薄。
- 全程受预算上限护栏；超预算早停并保留当前最优。

## 9. 风险与对策
| 风险 | 对策 |
|---|---|
| 评委不可信/可被刷 | **零人工**：自动锚点电池(4.5) + 客观层(StyleDist/归属/判别)主导，评委仅佐证、全程冻结 |
| 过拟合 val | test 集严格隔离，**只报 test 提升** |
| Reward hacking（skill 变啰嗦/堆词） | 长度惩罚 + 合规硬门 + Detectability 兜底 |
| 成本失控 | E/K 上限、val 早停、CostEvent 预算护栏 |
| 小样本博主 | 强制 ≥24 篇，否则不训练 |
| SkillOpt 库尚新（v0.1.0） | 仅作 PoC 依赖，藏接口后，可换自研循环 |
| 选题泄漏 | 划分按选题去重 + 时间分层；rollout 只给选题不给正文 |

## 10. 分阶段计划与决策门控
- **Phase 0 · PoC（离线脚本，不进产品，零人工标注）**
  1. 选 1–2 个 ≥24 篇的干净博主。
  2. 建客观度量层（StyleDist/归属/判别）+ LLM 评委；跑**自动锚点电池(4.5)**自检评委——真实笔记>其它博主>套话>胡言能否单调拉开、判别校准是否合理。全自动、无人参与。
  3. baseline：种子 skill 在 test 选题上生成 → 客观层 + 评委 + Detectability。
  4. 跑 SkillOpt 训练 → best skill → test 上再测。
  5. 产出对比报告 + 并排样例（客观层主导、评委佐证、方向一致才报）。
  - **Gate 1**：test 上提升真实、且客观层与评委方向一致 → 继续；否则停（便宜地学到"不值得"）。
- **Phase 1 · 后端**：`SkillTrainingRun` 模型 + 迁移；训练器 RQ 任务 + 事件流 + 成本记账；config/admin 参数。
- **Phase 2 · 前端**：「训练 Skill」入口 + 进度 + 训练前/后对比卡；创作可选训练后 skill。
- **Phase 3 · 迭代**：打磨评委/奖励；视情况把循环移植进自家 harness。

## 11. 与近期改动的衔接
- 蒸馏已简化为"选笔记→一个 Skill"（去掉模态标签，引擎内部仍分书面/口播）。训练只是在这份 Skill 之上加优化，不冲突。
- 训练产出仍是**一个** best_skill.md，沿用现有 skill 存储与创作消费路径。

## 12. 待你拍板的点（不阻塞 Phase 0 设计）
1. PoC 先拿哪个/哪些博主（需 ≥24 篇在架笔记）。
2. 评委用 Opus（更准更贵）还是 Sonnet（便宜）做 PoC。
3. PoC 是否就地写成一次性脚本（最快出数），产品化留到 Gate 1 之后。
