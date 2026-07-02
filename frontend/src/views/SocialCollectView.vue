<script setup lang="ts">
// 社媒·数据采集:四步向导(选择博主 → 配置采集 → 执行采集 → 查看结果)。
// 纯展示重构:状态/方法全部沿用 useWorkspaceStore;采集实时进度复用全站任务事件(taskCountProgress/liveStage)。
import { computed, ref, watch } from 'vue'
import StatusChip from '../components/StatusChip.vue'
import {
  benchmarkAccounts,
  bloggerCollectionRuns,
  bloggerDistillForm,
  collectContentTypes,
  collectFetchAll,
  collectOrder,
  currentSocialPlatformName,
  currentSocialTab,
  formatDate,
  goNextXhsCollectStep,
  goPreviousXhsCollectStep,
  handleCollectBlogger,
  handleCollectByUrls,
  isSocialPlatform,
  lastCollectSummary,
  liveStage,
  liveStageMessage,
  pendingAction,
  selectBlogger,
  selectCollectionRun,
  selectedBlogger,
  selectedBloggerId,
  selectedCollectionRunId,
  setCurrentSocialTab,
  subtypeLabel,
  taskCountProgress,
  collectBreakdown,
  collectPartialResult,
  refreshSelectedBlogger,
  taskElapsedLabel,
  taskFailure,
  urlCollectInput,
  xhsCollectStep,
  xhsCollectStepLabels
} from '../composables/useWorkspaceStore'

const collecting = computed(() => pendingAction.value === 'collect')
const urlOpen = ref(false)

// 采集失败/中断后拉一次该博主笔记池,让"已采成果卡"能对上标题与图数。
watch(
  () => Boolean(taskFailure.value && taskFailure.value.action === 'collect' && !collecting.value),
  (failed) => {
    if (failed && selectedBloggerId.value) refreshSelectedBlogger()
  }
)

// 步骤条:点已完成节点回退(采集中禁止跳转)。
function goToStep(n: number) {
  if (collecting.value) return
  if (n < xhsCollectStep.value) xhsCollectStep.value = n
}
function restart() {
  xhsCollectStep.value = 1
}

// 内容范围勾选。
function toggleContentType(value: string) {
  const index = collectContentTypes.value.indexOf(value)
  if (index >= 0) collectContentTypes.value.splice(index, 1)
  else collectContentTypes.value.push(value)
}

// 步进器:±5,夹在区间内。
function stepSample(delta: number) {
  const v = (bloggerDistillForm.sample_limit || 0) + delta
  bloggerDistillForm.sample_limit = Math.min(200, Math.max(5, v))
}
function stepComments(delta: number) {
  const v = (bloggerDistillForm.comments_per_post || 0) + delta
  bloggerDistillForm.comments_per_post = Math.min(100, Math.max(0, v))
}

// 第 2 步「下一步」:博主已选 + 至少勾一个拉取范围。
const nextDisabled = computed(() => {
  if (xhsCollectStep.value === 1) return !selectedBloggerId.value
  if (xhsCollectStep.value === 2) return !selectedBloggerId.value || collectContentTypes.value.length === 0
  return false
})

// 配置回看条文案。
const CONTENT_LABEL: Record<string, string> = { image: '图文', video: '视频' }
const rangeText = computed(() =>
  collectContentTypes.value.length ? collectContentTypes.value.map((t) => CONTENT_LABEL[t] || t).join(' + ') : '未选'
)
const amountText = computed(() => (collectFetchAll.value ? '全部' : `${bloggerDistillForm.sample_limit} 条`))
const orderText = computed(() => (collectOrder.value === 'top_liked' ? '高赞优先' : '最新优先'))

// 结果指标:null 的不显示;爆款/新增分别用暖色/绿色强调。
const metrics = computed(() => {
  const s = lastCollectSummary.value
  if (!s) return []
  const list: Array<{ key: string; label: string; value: number; tone?: string }> = [
    { key: 'post', label: '本批笔记', value: s.postCount }
  ]
  if (s.newCount !== null) list.push({ key: 'new', label: '新增', value: s.newCount, tone: 'ok' })
  if (s.refreshedCount !== null) list.push({ key: 'refreshed', label: '刷新', value: s.refreshedCount })
  if (s.delistedCount) list.push({ key: 'delisted', label: '已下架', value: s.delistedCount, tone: 'danger' })
  list.push({ key: 'hot', label: '爆款', value: s.hotCount, tone: 'warn' })
  list.push({ key: 'comment', label: '评论', value: s.commentCount })
  return list
})
</script>

<template>
  <section v-if="isSocialPlatform && currentSocialTab === 'collect'" class="collect">
    <header class="page-head">
      <h1>{{ currentSocialPlatformName }}数据采集</h1>
      <p>先选择博主，再配置采样数量与评论数量；采集结果会进入「博主资产」。视频转写已默认开启。</p>
    </header>

    <!-- 步骤条 -->
    <ol class="stepper" aria-label="采集步骤">
      <li
        v-for="(label, index) in xhsCollectStepLabels"
        :key="label"
        class="step"
        :class="{ current: xhsCollectStep === index + 1, done: xhsCollectStep > index + 1 }"
      >
        <button
          type="button"
          class="step-dot"
          :aria-current="xhsCollectStep === index + 1 ? 'step' : undefined"
          @click="goToStep(index + 1)"
        >
          <span v-if="xhsCollectStep > index + 1" aria-hidden="true">✓</span>
          <span v-else>{{ index + 1 }}</span>
        </button>
        <span class="step-label">{{ label }}</span>
      </li>
    </ol>

    <!-- 第 1 步:选择博主 -->
    <section v-if="xhsCollectStep === 1" class="card">
      <div class="card-head">
        <div>
          <span class="eyebrow">01 选择博主</span>
          <h3>选择要采集的博主</h3>
        </div>
        <button type="button" class="btn btn--ghost" @click="setCurrentSocialTab('assets')">去博主资产创建</button>
      </div>
      <div v-if="benchmarkAccounts.length" class="bca-grid">
        <button
          v-for="blogger in benchmarkAccounts"
          :key="blogger.id"
          type="button"
          class="bca"
          :class="{ sel: selectedBloggerId === blogger.id }"
          @click="selectBlogger(blogger.id)"
        >
          <span class="bca-avatar">{{ (blogger.display_name || '?').slice(0, 1) }}</span>
          <span class="bca-body">
            <span class="bca-name">{{ blogger.display_name }}</span>
            <span class="bca-sub">{{ blogger.niche || '未设置领域' }} · 样本 {{ blogger.sample_count }} · {{ blogger.last_distilled_at ? formatDate(blogger.last_distilled_at) : '未蒸馏' }}</span>
          </span>
          <span class="bca-radio" aria-hidden="true"></span>
        </button>
      </div>
      <p v-else class="empty-region pad">还没有对标博主档案。请到「博主资产」创建博主后再来采集。</p>
    </section>

    <!-- 第 2 步:配置采集 -->
    <section v-if="xhsCollectStep === 2" class="card">
      <div class="card-head">
        <div>
          <span class="eyebrow">02 配置采集</span>
          <h3>设置样本和评论范围</h3>
        </div>
      </div>

      <div class="cfg-grid">
        <div class="field">
          <span class="field-label">采样笔记数</span>
          <div class="stepper-input">
            <button type="button" :disabled="bloggerDistillForm.sample_limit <= 5" @click="stepSample(-5)">−</button>
            <span class="si-value">{{ bloggerDistillForm.sample_limit }}</span>
            <button type="button" :disabled="bloggerDistillForm.sample_limit >= 200" @click="stepSample(5)">+</button>
          </div>
        </div>
        <div class="field">
          <span class="field-label">每条评论数</span>
          <div class="stepper-input">
            <button type="button" :disabled="bloggerDistillForm.comments_per_post <= 0" @click="stepComments(-5)">−</button>
            <span class="si-value">{{ bloggerDistillForm.comments_per_post }}</span>
            <button type="button" :disabled="bloggerDistillForm.comments_per_post >= 100" @click="stepComments(5)">+</button>
          </div>
        </div>
      </div>

      <div class="field">
        <span class="field-label">拉取范围 <em>（不勾选视频可省去视频详情与 ASR 开销）</em></span>
        <div class="chip-row">
          <label class="chip-check" :class="{ on: collectContentTypes.includes('image') }">
            <input type="checkbox" :checked="collectContentTypes.includes('image')" @change="toggleContentType('image')" />
            <span class="cc-box" aria-hidden="true"></span>图文
          </label>
          <label class="chip-check" :class="{ on: collectContentTypes.includes('video') }">
            <input type="checkbox" :checked="collectContentTypes.includes('video')" @change="toggleContentType('video')" />
            <span class="cc-box" aria-hidden="true"></span>视频
          </label>
        </div>
      </div>

      <div class="cfg-grid">
        <div class="field">
          <span class="field-label">选材排序</span>
          <div class="seg">
            <button type="button" :class="{ on: collectOrder === 'top_liked' }" @click="collectOrder = 'top_liked'">高赞优先</button>
            <button type="button" :class="{ on: collectOrder === 'latest' }" @click="collectOrder = 'latest'">最新优先</button>
          </div>
        </div>
        <div class="field">
          <span class="field-label">采集数量</span>
          <div class="seg">
            <button type="button" :class="{ on: !collectFetchAll }" @click="collectFetchAll = false">{{ bloggerDistillForm.sample_limit }} 条</button>
            <button type="button" :class="{ on: collectFetchAll }" @click="collectFetchAll = true">全部</button>
          </div>
        </div>
      </div>

      <p class="card-foot">这些配置只影响本次采集批次，后续可基于不同批次分别蒸馏。视频字幕/口播转写已默认开启（由后台统一控制）。</p>
    </section>

    <!-- 第 3 步:执行采集 -->
    <section v-if="xhsCollectStep === 3" class="card">
      <div class="card-head">
        <div>
          <span class="eyebrow">03 执行采集</span>
          <h3>提交后台采集任务</h3>
        </div>
        <button
          v-if="!collecting"
          type="button"
          class="btn btn--accent"
          :disabled="!selectedBloggerId"
          :title="!selectedBloggerId ? '请先在第 1 步选择博主' : ''"
          @click="handleCollectBlogger"
        >
          <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M8 5v14l11-7z" fill="currentColor" /></svg>
          开始采集
        </button>
      </div>

      <!-- 配置回看 -->
      <div v-if="selectedBlogger" class="recap">
        <span class="recap-chip">博主 <b>{{ selectedBlogger.display_name }}</b></span>
        <span class="recap-chip">采样 <b>{{ amountText }}</b></span>
        <span class="recap-chip">评论 <b>{{ bloggerDistillForm.comments_per_post }}/条</b></span>
        <span class="recap-chip">范围 <b>{{ rangeText }}</b></span>
        <span class="recap-chip">排序 <b>{{ orderText }}</b></span>
      </div>

      <p v-if="!selectedBloggerId" class="card-foot">还没选择博主——请回第 1 步「选择博主」选择一个博主。</p>
      <p v-else-if="!collecting" class="card-foot">采集耗时取决于样本数量、评论数量和视频转写。重复采集只补新笔记、刷新老笔记，不会重复扣费。</p>

      <!-- 采集失败:持久错误横幅(不像 toast 一闪而过),点「开始采集」重试会自动清除 -->
      <div v-if="taskFailure && taskFailure.action === 'collect' && !collecting" class="collect-error" role="alert">
        <strong>采集失败</strong>
        <span>{{ taskFailure.message }}</span>
      </div>

      <!-- 采集中断/失败,也展示已采成果(数据已增量入库) -->
      <div v-if="taskFailure && taskFailure.action === 'collect' && !collecting && collectPartialResult" class="partial-card">
        <div class="pcard-head">
          <strong>本次已采集 {{ collectPartialResult.total }} 篇</strong>
          <span class="pcard-sub">已保存到笔记池，可直接重新采集（增量，自动跳过已采）</span>
        </div>
        <div class="pcard-sum">
          <span>图文 {{ collectPartialResult.imageNotes }} · 图片理解 {{ collectPartialResult.visionOk }}</span>
          <span>视频 {{ collectPartialResult.videoNotes }} · 字幕 {{ collectPartialResult.subtitleOk }} / 转写 {{ collectPartialResult.asrOk }}</span>
        </div>
        <ul class="pcard-list">
          <li v-for="(it, i) in collectPartialResult.items.slice(0, 12)" :key="i">
            <span class="pcard-type">{{ it.isVideo ? '视频' : '图文' }}</span>
            <span class="pcard-title">{{ it.title }}</span>
            <span class="pcard-cap" :class="{ ok: it.ok }">{{ it.capture }}</span>
          </li>
        </ul>
        <p v-if="collectPartialResult.total > 12" class="pcard-more">仅显示前 12 条 · 全部在笔记池</p>
      </div>

      <!-- 采集中:复用真实任务进度,不杜撰数字 -->
      <div v-if="collecting" class="progress-card">
        <div class="pc-head">
          <span class="pulse" aria-hidden="true"></span>
          <strong>采集进行中…</strong>
          <span class="pc-pct">{{ taskCountProgress.total ? `第 ${taskCountProgress.current} / ${taskCountProgress.total} 篇 · ${taskCountProgress.pct}%` : '进行中' }}<template v-if="collectBreakdown && collectBreakdown.backfill"> · 新增 {{ collectBreakdown.new }} 补采 {{ collectBreakdown.backfill }}</template></span>
        </div>
        <div class="pc-track">
          <span class="pc-fill" :class="{ indet: !taskCountProgress.total }" :style="taskCountProgress.total ? { width: taskCountProgress.pct + '%' } : {}"></span>
        </div>
        <div class="pc-stage">
          <span class="pcs-name">{{ liveStage }}</span>
          <span class="pcs-msg">{{ liveStageMessage }}</span>
          <span class="pcs-elapsed">{{ taskElapsedLabel }}</span>
        </div>
      </div>

      <!-- 链接定向采集(折叠) -->
      <div class="url-collect" :class="{ open: urlOpen }">
        <button type="button" class="uc-toggle" @click="urlOpen = !urlOpen">
          <svg class="uc-chevron" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 6l6 6-6 6" /></svg>
          采不到想要的笔记？粘贴链接定向采集
        </button>
        <div v-if="urlOpen" class="uc-body">
          <p class="card-foot">打开小红书 → 进入该笔记 →「分享」→「复制链接」→ 粘到下面（一行一个）；链接需带 <code>xsec_token</code>（复制分享链接即可），短链会自动展开。逐条结果见顶部进度。</p>
          <textarea
            v-model="urlCollectInput"
            rows="4"
            placeholder="https://www.xiaohongshu.com/explore/xxxx?xsec_token=...&#10;一行一个，最多 20 条"
          ></textarea>
          <button type="button" class="btn btn--ghost" :disabled="!selectedBloggerId || Boolean(pendingAction)" @click="handleCollectByUrls">
            {{ collecting ? '采集中…' : '定向采集' }}
          </button>
        </div>
      </div>
    </section>

    <!-- 第 4 步:查看结果 -->
    <section v-if="xhsCollectStep === 4" class="card">
      <div class="card-head">
        <div>
          <span class="eyebrow">04 查看结果</span>
          <h3>采集批次和样本预览</h3>
        </div>
        <button type="button" class="btn btn--ghost" @click="setCurrentSocialTab('assets')">查看博主资产 →</button>
      </div>

      <div v-if="lastCollectSummary && selectedBlogger" class="ok-banner">
        <span class="ok-ico" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5 9-11" /></svg>
        </span>
        <div>
          <strong>本批采集完成</strong>
          <p>{{ lastCollectSummary.postCount }} 条笔记已进入「{{ selectedBlogger.display_name }}」的博主资产</p>
        </div>
      </div>

      <div v-if="metrics.length" class="metric-grid">
        <article v-for="m in metrics" :key="m.key" class="metric" :class="m.tone ? `m--${m.tone}` : ''">
          <span>{{ m.label }}</span>
          <b>{{ m.value }}</b>
        </article>
      </div>

      <div v-if="lastCollectSummary && Object.keys(lastCollectSummary.subtypeCounts).length" class="chip-row chip-row--wrap">
        <span v-for="(count, key) in lastCollectSummary.subtypeCounts" :key="key" class="tag-chip tag-chip--auto">{{ subtypeLabel(key) }} {{ count }}</span>
      </div>

      <div v-if="selectedBlogger" class="history">
        <div class="history-head">
          <strong>采集历史</strong>
          <span class="count">{{ bloggerCollectionRuns.length }} 次</span>
        </div>
        <button
          v-for="run in bloggerCollectionRuns"
          :key="run.id"
          type="button"
          class="run-row"
          :class="{ sel: selectedCollectionRunId === run.id }"
          @click="selectCollectionRun(run.id)"
        >
          <span class="run-id">#{{ run.id }} · {{ formatDate(run.created_at) }}</span>
          <span class="run-meta">
            <StatusChip :status="run.status" />
            样本 {{ run.post_count }} · 评论 {{ run.comment_count }} · ASR {{ run.asr_enabled ? '开启' : '关闭' }}
          </span>
        </button>
        <p v-if="!bloggerCollectionRuns.length" class="empty-region pad">还没有采集批次。回第 1 步开始一次采集。</p>
      </div>
      <p v-else class="empty-region pad">请先选择博主。</p>
    </section>

    <!-- 底部导航 -->
    <div class="nav">
      <button v-if="xhsCollectStep > 1 && !(xhsCollectStep === 3 && collecting)" type="button" class="btn btn--ghost" @click="goPreviousXhsCollectStep">← 上一步</button>
      <span class="nav-spacer"></span>
      <button v-if="xhsCollectStep < 3" type="button" class="btn btn--accent" :disabled="nextDisabled" @click="goNextXhsCollectStep">下一步 →</button>
      <button v-if="xhsCollectStep === 4" type="button" class="btn btn--accent" @click="restart">↻ 再采集一批</button>
    </div>
  </section>
</template>

<style scoped>
.collect {
  max-width: 840px;
  margin: 0 auto;
}
.page-head {
  margin-bottom: 18px;
}
.page-head h1 {
  margin: 0 0 6px;
  font-size: 21px;
  font-weight: 680;
  letter-spacing: -0.01em;
}
.page-head p {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.6;
  color: var(--color-ink-2);
}

/* 步骤条 */
.stepper {
  display: flex;
  list-style: none;
  margin: 0 0 18px;
  padding: 16px 8px;
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-lg);
}
.step {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  position: relative;
}
.step:not(:first-child)::before {
  content: '';
  position: absolute;
  top: 15px;
  right: 50%;
  left: -50%;
  height: 2px;
  background: var(--color-rule);
}
.step.current::before,
.step.done::before {
  background: var(--color-accent-soft-bd);
}
.step-dot {
  position: relative;
  z-index: 1;
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: 50%;
  background: var(--color-paper-3);
  color: var(--color-ink-3);
  font-size: 13px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  cursor: default;
}
.step.current .step-dot {
  background: var(--color-accent);
  color: #fff;
}
.step.done .step-dot {
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
  cursor: pointer;
}
.step-label {
  font-size: 13px;
  color: var(--color-ink-3);
  white-space: nowrap;
}
.step.current .step-label,
.step.done .step-label {
  color: var(--color-ink);
  font-weight: 600;
}

/* 卡片 + 卡头 */
.card {
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-lg);
  padding: 20px 22px;
}
.card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}
.eyebrow {
  display: block;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.03em;
  color: var(--color-accent-ink);
}
.card-head h3 {
  margin: 3px 0 0;
  font-size: 18px;
  font-weight: 680;
}
.card-foot {
  margin: 12px 0 0;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--color-ink-3);
}
.card-foot code {
  padding: 1px 5px;
  border-radius: 5px;
  background: var(--color-paper-3);
  font-size: 12px;
}

/* 按钮 */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 38px;
  padding: 0 16px;
  border-radius: 10px;
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: background 140ms var(--ease-out), border-color 140ms var(--ease-out);
}
.btn--accent {
  border: 0;
  background: var(--color-accent);
  color: #fff;
}
.btn--accent:hover {
  background: var(--color-accent-press);
}
.btn--ghost {
  border: 1px solid var(--color-field-border);
  background: var(--color-surface);
  color: var(--color-ink-2);
}
.btn--ghost:hover {
  background: #f7f8f9;
}
.btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* 第 1 步:博主网格 */
.bca-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(248px, 1fr));
  gap: 10px;
}
.bca {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid var(--color-rule);
  border-radius: 12px;
  background: var(--color-surface);
  cursor: pointer;
  text-align: left;
  transition: border-color 120ms var(--ease-out), background 120ms var(--ease-out);
}
.bca:hover {
  border-color: var(--color-accent-soft-bd);
}
.bca.sel {
  border-color: var(--color-accent);
  background: var(--color-accent-tint);
}
.bca-avatar {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 11px;
  background: var(--color-paper-3);
  color: var(--color-ink-3);
  font-size: 16px;
  font-weight: 600;
  flex: 0 0 auto;
}
.bca.sel .bca-avatar {
  background: var(--color-accent);
  color: #fff;
}
.bca-body {
  flex: 1;
  min-width: 0;
}
.bca-name {
  display: block;
  font-size: 14px;
  font-weight: 620;
  color: var(--color-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.bca-sub {
  display: block;
  margin-top: 2px;
  font-size: 11.5px;
  color: var(--color-ink-3);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.bca-radio {
  flex: 0 0 auto;
  width: 20px;
  height: 20px;
  border: 1.5px solid var(--color-rule-strong);
  border-radius: 50%;
  position: relative;
}
.bca.sel .bca-radio {
  border-color: var(--color-accent);
  background: var(--color-accent);
}
.bca.sel .bca-radio::after {
  content: '✓';
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: #fff;
  font-size: 12px;
  font-weight: 800;
}

/* 第 2 步:配置 */
.cfg-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
  margin-bottom: 18px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 18px;
}
.cfg-grid .field {
  margin-bottom: 0;
}
.field-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-ink);
}
.field-label em {
  font-style: normal;
  font-weight: 400;
  font-size: 12px;
  color: var(--color-ink-3);
}
.stepper-input {
  display: flex;
  align-items: center;
  height: 48px;
  border: 1px solid var(--color-field-border);
  border-radius: 10px;
  background: #fafbfc;
  overflow: hidden;
}
.stepper-input button {
  width: 48px;
  height: 100%;
  border: 0;
  background: transparent;
  color: var(--color-ink-2);
  font-size: 20px;
  cursor: pointer;
  transition: background 120ms var(--ease-out);
}
.stepper-input button:hover:not(:disabled) {
  background: var(--color-paper-3);
}
.stepper-input button:disabled {
  color: var(--color-rule-strong);
  cursor: not-allowed;
}
.si-value {
  flex: 1;
  text-align: center;
  font-size: 17px;
  font-weight: 650;
  color: var(--color-ink);
  font-variant-numeric: tabular-nums;
}

/* 勾选 chip(图文/视频) */
.chip-row {
  display: flex;
  gap: 10px;
}
.chip-row--wrap {
  flex-wrap: wrap;
  margin-top: 14px;
}
.chip-check {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  padding: 10px 16px;
  border: 1px solid var(--color-field-border);
  border-radius: 10px;
  font-size: 13.5px;
  font-weight: 550;
  color: var(--color-ink);
  cursor: pointer;
  transition: border-color 120ms var(--ease-out), background 120ms var(--ease-out);
}
.chip-check.on {
  border-color: var(--color-accent);
  background: var(--color-accent-tint);
  color: var(--color-accent-ink);
}
.chip-check input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}
.cc-box {
  flex: 0 0 auto;
  width: 18px;
  height: 18px;
  border: 1.5px solid var(--color-rule-strong);
  border-radius: 5px;
  display: grid;
  place-items: center;
  transition: background 110ms var(--ease-out), border-color 110ms var(--ease-out);
}
.chip-check.on .cc-box {
  border-color: var(--color-accent);
  background: var(--color-accent);
}
.chip-check.on .cc-box::after {
  content: '✓';
  color: #fff;
  font-size: 12px;
  font-weight: 800;
}

/* 段控 */
.seg {
  display: flex;
  gap: 3px;
  padding: 3px;
  background: var(--color-paper-3);
  border-radius: 11px;
  height: 48px;
}
.seg button {
  flex: 1;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--color-ink-2);
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
  transition: background 120ms var(--ease-out);
}
.seg button.on {
  background: var(--color-surface);
  color: var(--color-ink);
  box-shadow: 0 1px 2px var(--color-shadow);
}


/* 第 3 步:配置回看 + 进度 */
.recap {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.recap-chip {
  padding: 5px 11px;
  border-radius: var(--radius-pill);
  background: var(--color-paper-3);
  font-size: 12.5px;
  color: var(--color-ink-2);
}
.recap-chip b {
  color: var(--color-ink);
  font-weight: 650;
}
.progress-card {
  margin-top: 16px;
  padding: 16px 18px;
  background: var(--color-accent-tint);
  border: 1px solid var(--color-accent-soft-bd);
  border-radius: 12px;
}
.pc-head {
  display: flex;
  align-items: center;
  gap: 9px;
}
.pc-head strong {
  font-size: 14px;
  font-weight: 650;
  color: var(--color-ink);
}
.pulse {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--color-accent);
  animation: pulse 1.3s var(--ease-out) infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.7); }
}
.pc-pct {
  margin-left: auto;
  font-size: 13px;
  font-weight: 700;
  color: var(--color-accent-ink);
  font-variant-numeric: tabular-nums;
}
.pc-track {
  position: relative;
  height: 8px;
  margin-top: 12px;
  border-radius: var(--radius-pill);
  background: var(--color-surface);
  border: 1px solid var(--color-accent-soft-bd);
  overflow: hidden;
}
.pc-fill {
  display: block;
  height: 100%;
  border-radius: var(--radius-pill);
  background-color: var(--color-accent);
  background-image: linear-gradient(135deg, rgba(255, 255, 255, 0.25) 25%, transparent 25%, transparent 50%, rgba(255, 255, 255, 0.25) 50%, rgba(255, 255, 255, 0.25) 75%, transparent 75%, transparent);
  background-size: 18px 18px;
  transition: width 0.5s var(--ease-out);
  animation: stripes 0.7s linear infinite;
}
.pc-fill.indet {
  width: 38%;
  animation: stripes 0.7s linear infinite, indet 1.4s var(--ease-out) infinite;
}
@keyframes stripes {
  from { background-position: 0 0; }
  to { background-position: 18px 0; }
}
@keyframes indet {
  0% { margin-left: -38%; }
  100% { margin-left: 100%; }
}
@media (prefers-reduced-motion: reduce) {
  .pulse, .pc-fill, .pc-fill.indet { animation: none; }
}
.pc-stage {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
  font-size: 12.5px;
}
.pcs-name {
  font-weight: 650;
  color: var(--color-ink);
}
.pcs-msg {
  flex: 1;
  min-width: 0;
  color: var(--color-ink-2);
}
.pcs-elapsed {
  color: var(--color-ink-3);
  font-variant-numeric: tabular-nums;
}
.partial-card {
  margin-top: 12px;
  border: 0.5px solid var(--color-line, #e5e7eb);
  border-radius: 12px;
  padding: 14px 16px;
  background: var(--color-surface, #fff);
}
.pcard-head {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: 10px;
}
.pcard-head strong {
  font-size: 15px;
}
.pcard-sub {
  font-size: 12px;
  color: var(--color-ink-3, #999);
}
.pcard-sum {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 12px;
  color: var(--color-ink-2, #666);
  background: var(--color-bg-2, #f7f8fa);
  border-radius: 8px;
  padding: 8px 12px;
  margin-bottom: 6px;
}
.pcard-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.pcard-list li {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 2px;
  border-top: 0.5px solid var(--color-line, #eee);
  font-size: 13px;
}
.pcard-type {
  flex: 0 0 auto;
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 6px;
  background: var(--color-bg-2, #f0f1f3);
  color: var(--color-ink-2, #666);
}
.pcard-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pcard-cap {
  flex: 0 0 auto;
  font-size: 12px;
  color: var(--color-ink-3, #999);
}
.pcard-cap.ok {
  color: var(--color-accent-ink, #1d9e75);
}
.pcard-more {
  font-size: 12px;
  color: var(--color-ink-3, #999);
  margin: 8px 0 0;
}
.collect-error {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 12px 14px;
  margin-top: 12px;
  border: 1px solid var(--color-danger-bd, #f0b4b4);
  background: var(--color-danger-bg, #fdecec);
  border-radius: 10px;
  font-size: 13px;
}
.collect-error strong {
  color: var(--color-danger, #c0392b);
}
.collect-error span {
  color: var(--color-ink-2);
  word-break: break-word;
}

/* 折叠:链接定向采集 */
.url-collect {
  margin-top: 16px;
  border: 1px solid var(--color-rule);
  border-radius: 12px;
}
.uc-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 13px 16px;
  border: 0;
  background: transparent;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--color-ink);
  cursor: pointer;
  text-align: left;
}
.uc-chevron {
  color: var(--color-ink-3);
  transition: transform 160ms var(--ease-out);
}
.url-collect.open .uc-chevron {
  transform: rotate(90deg);
}
.uc-body {
  padding: 0 16px 16px;
}
.uc-body textarea {
  width: 100%;
  margin: 10px 0;
  padding: 10px 12px;
  border: 1px solid var(--color-field-border);
  border-radius: 10px;
  font-size: 13px;
  font-family: inherit;
  line-height: 1.6;
  resize: vertical;
  box-sizing: border-box;
}

/* 第 4 步:结果 */
.ok-banner {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  background: var(--color-accent-soft);
  border: 1px solid var(--color-accent-soft-bd);
  border-radius: 12px;
  margin-bottom: 16px;
}
.ok-ico {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--color-accent);
  color: #fff;
  flex: 0 0 auto;
}
.ok-banner strong {
  font-size: 15px;
  font-weight: 680;
  color: var(--color-ink);
}
.ok-banner p {
  margin: 3px 0 0;
  font-size: 13px;
  color: var(--color-ink-2);
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 10px;
}
.metric {
  padding: 14px 16px;
  border: 1px solid var(--color-rule);
  border-radius: 12px;
  background: var(--color-surface);
}
.metric span {
  display: block;
  font-size: 12px;
  color: var(--color-ink-3);
  margin-bottom: 6px;
}
.metric b {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-ink);
  font-variant-numeric: tabular-nums;
  line-height: 1;
}
.m--new b {
  color: var(--color-ok);
}
.m--warn b {
  color: var(--color-warn);
}
.m--danger b {
  color: var(--color-danger);
}

/* 采集历史 */
.history {
  margin-top: 18px;
}
.history-head {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 10px;
}
.history-head strong {
  font-size: 14px;
  font-weight: 650;
}
.count {
  padding: 1px 9px;
  border-radius: var(--radius-pill);
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
  font-size: 12px;
  font-weight: 700;
}
.run-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  width: 100%;
  padding: 11px 13px;
  border: 1px solid var(--color-rule);
  border-radius: 10px;
  background: var(--color-surface);
  cursor: pointer;
  text-align: left;
  transition: border-color 120ms var(--ease-out), background 120ms var(--ease-out);
}
.run-row + .run-row {
  margin-top: 8px;
}
.run-row:hover {
  border-color: var(--color-accent-soft-bd);
}
.run-row.sel {
  border-color: var(--color-accent);
  background: var(--color-accent-tint);
}
.run-id {
  font-size: 13px;
  font-weight: 620;
  color: var(--color-ink);
  font-variant-numeric: tabular-nums;
}
.run-meta {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  color: var(--color-ink-3);
}

/* 空态 */
.empty-region.pad {
  padding: 26px 20px;
  text-align: center;
}

/* 底部导航 */
.nav {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 18px;
}
.nav-spacer {
  flex: 1;
}

@media (max-width: 560px) {
  .step-label {
    font-size: 12px;
  }
  .card {
    padding: 18px 16px;
  }
  .card-head {
    flex-direction: column;
  }
}
</style>
