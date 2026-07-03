<script setup lang="ts">
// 社媒·提炼 Skill(蒸馏):主从工作台 —— 左博主列表 + 右(两种入口 / 蒸馏中 / 历史 / 选中结果四态)。
// 纯展示重构:状态/方法全部沿用 useWorkspaceStore;蒸馏中进度复用真实任务事件,不杜撰。
import { computed, ref } from 'vue'
import { sanitizeHtml } from '../utils/sanitize'
import StatusChip from '../components/StatusChip.vue'
import TIcon from '../components/TIcon.vue'
import {
  benchmarkAccounts,
  bloggerRuns,
  bloggerSnapshots,
  currentSocialTab,
  distillRunMeta,
  distillRunOrdinal,
  DISTILL_MIN_SAMPLES,
  DISTILL_RECOMMEND_SAMPLES,
  friendlyTime,
  handleAbandonBloggerRun,
  handleAutoDistill,
  handleConfirmBloggerRun,
  handleDistillFromSnapshot,
  isSocialPlatform,
  liveStage,
  liveStageMessage,
  pendingAction,
  qualityTone,
  selectBlogger,
  selectBloggerRun,
  selectedBlogger,
  selectedBloggerId,
  selectedBloggerRun,
  selectedBloggerRunCount,
  selectedBloggerRunId,
  selectedBloggerSkill,
  setCurrentSocialTab,
  taskCountProgress,
  taskElapsedLabel
} from '../composables/useWorkspaceStore'

const distilling = computed(() => pendingAction.value === 'distill')
const runMeta = computed(() => distillRunMeta(selectedBloggerRun.value))
const isPending = computed(() => selectedBloggerRun.value?.status === 'pending_confirmation')

// 文字头像:名字首字 + 按 id 取柔和底色。
const AVATAR_BG = ['#eaf3ee', '#f0eef7', '#eef4f5', '#eef1f6', '#f6eef2', '#eef3f7']
const AVATAR_INK = ['#2f6b54', '#5a4a86', '#3a6a72', '#44506a', '#8a4a64', '#3a5a86']
function avatarStyle(id: number) {
  const i = (((id || 0) % AVATAR_BG.length) + AVATAR_BG.length) % AVATAR_BG.length
  return { background: AVATAR_BG[i], color: AVATAR_INK[i] }
}

// 复制 Skill:成功后短暂提示「已复制」。
const copied = ref(false)
async function copySkill() {
  const text = selectedBloggerSkill.value?.skill_markdown
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    copied.value = true
    window.setTimeout(() => (copied.value = false), 1600)
  } catch {
    copied.value = false
  }
}

// 「创建快照」跳「博主资产」勾选笔记。
function goCreateSnapshot() {
  setCurrentSocialTab('dossier')
}
</script>

<template>
  <section v-if="isSocialPlatform && currentSocialTab === 'distill'" class="distill">
    <div class="md-grid">
      <!-- 左:博主列表 -->
      <aside class="bl-card" aria-label="博主列表">
        <div class="bl-head">
          <strong>博主</strong>
          <span class="count">{{ benchmarkAccounts.length }} 个</span>
        </div>
        <div v-if="benchmarkAccounts.length" class="bl-list">
          <button
            v-for="blogger in benchmarkAccounts"
            :key="blogger.id"
            type="button"
            class="bl-row"
            :class="{ sel: selectedBloggerId === blogger.id }"
            @click="selectBlogger(blogger.id)"
          >
            <span class="bl-avatar" :style="avatarStyle(blogger.id)">{{ (blogger.display_name || '?').slice(0, 1) }}</span>
            <span class="bl-body">
              <span class="bl-name">{{ blogger.display_name }}</span>
              <span class="bl-sub">{{ blogger.niche || '未设置领域' }} · 样本 {{ blogger.sample_count }}</span>
            </span>
          </button>
        </div>
        <p v-else class="empty-region pad">还没有博主。请先到「博主资产」创建并采集。</p>
      </aside>

      <!-- 右:详情 -->
      <div v-if="selectedBlogger" class="detail">
        <!-- 两种蒸馏入口 -->
        <div class="entry-grid">
          <section class="card entry">
            <div class="entry-head">
              <span class="entry-ico ico-auto" aria-hidden="true">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M13 2L4 14h6l-1 8 9-12h-6l1-8z" /></svg>
              </span>
              <h3>自动蒸馏</h3>
              <span class="entry-tag">高赞优先</span>
            </div>
            <p class="entry-desc">取该博主笔记池里赞藏最高的若干篇，蒸馏出一个 Skill（不用先存快照）。</p>
            <button type="button" class="btn btn--accent block" :disabled="distilling" @click="handleAutoDistill">
              <svg v-if="!distilling" viewBox="0 0 24 24" width="14" height="14" fill="currentColor" aria-hidden="true"><path d="M13 2L4 14h6l-1 8 9-12h-6l1-8z" /></svg>
              {{ distilling ? '蒸馏中…' : '一键自动蒸馏' }}
            </button>
          </section>

          <section class="card entry">
            <div class="entry-head">
              <span class="entry-ico ico-snap" aria-hidden="true"><TIcon name="folder" /></span>
              <h3>用快照蒸馏</h3>
              <span class="entry-tag">{{ bloggerSnapshots.length }} 个</span>
            </div>
            <div v-if="bloggerSnapshots.length" class="snap-list">
              <div v-for="snap in bloggerSnapshots" :key="snap.id" class="snap-row">
                <span class="snap-info">
                  <span class="snap-name">{{ snap.name }}</span>
                  <span class="snap-meta">{{ snap.post_count }} 篇 · {{ friendlyTime(snap.created_at) }}</span>
                </span>
                <button type="button" class="btn btn--ghost slim" :disabled="distilling" @click="handleDistillFromSnapshot(snap.id)">用此快照</button>
              </div>
            </div>
            <button type="button" class="snap-create" @click="goCreateSnapshot">+ 创建快照</button>
            <p class="entry-foot">「创建快照」会跳到「博主资产」勾选笔记保存（需 ≥ {{ DISTILL_MIN_SAMPLES }} 篇，建议 ≥ {{ DISTILL_RECOMMEND_SAMPLES }} 篇）。</p>
          </section>
        </div>

        <!-- 蒸馏中横幅(真实进度) -->
        <section v-if="distilling" class="card progress-card">
          <div class="pc-head">
            <span class="pulse" aria-hidden="true"></span>
            <strong>正在蒸馏…</strong>
            <span class="pc-pct">{{ taskCountProgress.total ? taskCountProgress.pct + '%' : '进行中' }}</span>
          </div>
          <div class="pc-track">
            <span class="pc-fill" :class="{ indet: !taskCountProgress.total }" :style="taskCountProgress.total ? { width: taskCountProgress.pct + '%' } : {}"></span>
          </div>
          <div class="pc-stage">
            <span class="pcs-name">{{ liveStage }}</span>
            <span class="pcs-msg">{{ liveStageMessage }}</span>
            <span class="pcs-elapsed">{{ taskElapsedLabel }}</span>
          </div>
          <p class="pc-note">蒸馏在后台进行，离开本页时顶部会出现一条迷你进度提醒；完成后会生成一条「待确认」结果并自动选中。</p>
        </section>

        <!-- 蒸馏历史 -->
        <section class="card">
          <div class="card-head">
            <div class="ch-l"><h3>蒸馏历史</h3><span class="ch-count">{{ selectedBloggerRunCount }} 次</span></div>
          </div>
          <div v-if="bloggerRuns.length" class="run-list">
            <button
              v-for="run in bloggerRuns"
              :key="run.id"
              type="button"
              class="run-row"
              :class="{ sel: selectedBloggerRunId === run.id, failed: run.status === 'failed' }"
              @click="selectBloggerRun(run.id)"
            >
              <span class="run-top">
                <span class="run-seq">第 {{ distillRunOrdinal(run.id) }} 次蒸馏</span>
                <StatusChip :status="run.status" />
              </span>
              <span class="run-meta">{{ friendlyTime(run.created_at) }} · 样本 {{ run.sample_count }}</span>
              <span v-if="run.status === 'failed'" class="run-error">失败原因：{{ run.error_message || '未记录失败原因' }}</span>
            </button>
          </div>
          <p v-else class="empty-region pad">这个博主还没有蒸馏记录。</p>
        </section>

        <!-- 选中蒸馏结果 -->
        <section v-if="selectedBloggerRun" class="card result" :class="{ 'result--pending': isPending }">
          <div class="result-head">
            <div class="rh-l">
              <div class="rh-title">
                <h3>第 {{ distillRunOrdinal(selectedBloggerRun.id) }} 次蒸馏</h3>
                <StatusChip :status="selectedBloggerRun.status" />
              </div>
              <div class="rh-tags">
                <span class="status-chip status-chip--neutral">{{ runMeta.mode === 'B' ? '诊断我的账号' : '拆解对标博主' }}</span>
                <span v-if="runMeta.qualityScore !== null" class="status-chip" :class="`status-chip--${qualityTone(runMeta.qualityGrade)}`">质量自检 {{ runMeta.qualityScore }} 分 · {{ runMeta.qualityGrade }}</span>
                <span v-if="runMeta.revisions > 0" class="status-chip status-chip--info">已自我修订 {{ runMeta.revisions }} 次</span>
              </div>
            </div>
            <div v-if="isPending" class="rh-actions">
              <button type="button" class="btn btn--accent slim" :disabled="Boolean(pendingAction)" @click="handleConfirmBloggerRun">
                {{ pendingAction === 'distill-confirm' ? '保存中…' : '保存结果' }}
              </button>
              <button type="button" class="btn btn--ghost slim" :disabled="Boolean(pendingAction)" @click="handleAbandonBloggerRun">
                {{ pendingAction === 'distill-abandon' ? '放弃中…' : '放弃' }}
              </button>
            </div>
          </div>

          <p v-if="isPending" class="pending-note">这是一次待确认的蒸馏结果，确认无误后点「保存结果」才会写入；不满意可「放弃」。</p>

          <!-- 失败态 -->
          <div v-if="selectedBloggerRun.status === 'failed'" class="fail-panel">
            <span class="fail-ico" aria-hidden="true">!</span>
            <div>
              <strong>蒸馏失败</strong>
              <p>{{ selectedBloggerRun.error_message || '这次蒸馏没有记录失败原因，请查看任务日志。' }}</p>
            </div>
          </div>

          <!-- 已完成 / 待确认:报告 + Skill -->
          <template v-else>
            <div class="result-block">
              <h4 class="block-title"><TIcon name="folder" /> 蒸馏报告</h4>
              <div v-if="selectedBloggerRun.report_html" class="rep" v-html="sanitizeHtml(selectedBloggerRun.report_html)"></div>
              <p v-else class="empty-region pad">这次蒸馏没有生成报告。</p>
            </div>
            <div class="result-block">
              <div class="block-title-row">
                <h4 class="block-title">Skill 输出</h4>
                <button v-if="selectedBloggerSkill" type="button" class="btn btn--ghost slim" @click="copySkill">{{ copied ? '✓ 已复制' : '复制' }}</button>
              </div>
              <pre v-if="selectedBloggerSkill" class="skill-code">{{ selectedBloggerSkill.skill_markdown }}</pre>
              <p v-else class="empty-region pad">这次蒸馏没有生成 Skill。</p>
            </div>
          </template>
        </section>
      </div>
      <div v-else class="empty-region card pad detail-empty">请选择一个博主开始蒸馏。</div>
    </div>
  </section>
</template>

<style scoped>
.distill {
  max-width: 1080px;
  margin: 0 auto;
}
.md-grid {
  display: grid;
  grid-template-columns: 248px minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}
.card {
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-lg);
}

/* 左栏博主列表 */
.bl-card {
  position: sticky;
  top: 0;
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-lg);
  overflow: hidden;
}
.bl-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--color-paper-3);
}
.bl-head strong {
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
.bl-list {
  display: flex;
  flex-direction: column;
  padding: 8px;
  gap: 2px;
}
.bl-row {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 9px 10px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  cursor: pointer;
  text-align: left;
  transition: background 120ms var(--ease-out);
}
.bl-row:hover {
  background: #fafbfc;
}
.bl-row.sel {
  background: var(--color-accent-soft);
}
.bl-avatar {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  flex: 0 0 auto;
}
.bl-body {
  flex: 1;
  min-width: 0;
}
.bl-name {
  display: block;
  font-size: 13.5px;
  font-weight: 620;
  color: var(--color-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.bl-row.sel .bl-name {
  color: var(--color-accent-ink);
}
.bl-sub {
  display: block;
  margin-top: 2px;
  font-size: 11.5px;
  color: var(--color-ink-3);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 右栏 */
.detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.detail-empty {
  text-align: center;
  padding: 48px 24px;
}

/* 两种入口 */
.entry-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 14px;
}
.entry {
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
}
.entry-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.entry-ico {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  flex: 0 0 auto;
}
.ico-auto {
  background: var(--color-score-warn-bg);
  color: var(--color-warn);
}
.ico-snap {
  background: var(--color-accent-soft);
  color: var(--color-accent);
}
.entry-head h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 680;
}
.entry-tag {
  margin-left: auto;
  padding: 2px 9px;
  border-radius: var(--radius-pill);
  background: var(--color-paper-3);
  color: var(--color-ink-3);
  font-size: 11.5px;
  font-weight: 600;
}
.entry-desc {
  margin: 0 0 14px;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--color-ink-2);
}
.snap-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 10px;
}
.snap-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--color-rule);
  border-radius: 10px;
}
.snap-info {
  min-width: 0;
}
.snap-name {
  display: block;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--color-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.snap-meta {
  display: block;
  margin-top: 2px;
  font-size: 11.5px;
  color: var(--color-ink-3);
}
.snap-create {
  width: 100%;
  padding: 10px;
  border: 1.5px dashed var(--color-accent-soft-bd);
  border-radius: 10px;
  background: var(--color-accent-tint);
  color: var(--color-accent-ink);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 120ms var(--ease-out), border-color 120ms var(--ease-out);
}
.snap-create:hover {
  background: var(--color-accent-soft);
  border-color: var(--color-accent);
}
.entry-foot {
  margin: 10px 0 0;
  font-size: 11.5px;
  line-height: 1.6;
  color: var(--color-ink-3);
}

/* 卡头 */
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px 0;
}
.ch-l {
  display: flex;
  align-items: baseline;
  gap: 9px;
}
.ch-l h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 650;
}
.ch-count {
  font-size: 12.5px;
  color: var(--color-ink-3);
}

/* 蒸馏中进度 */
.progress-card {
  padding: 16px 20px;
  background: var(--color-accent-tint);
  border-color: var(--color-accent-soft-bd);
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
.pc-note {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--color-ink-3);
}

/* 蒸馏历史 */
.run-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 20px 18px;
}
.run-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 11px 13px;
  border: 1px solid var(--color-rule);
  border-radius: 11px;
  background: var(--color-surface);
  cursor: pointer;
  text-align: left;
  transition: border-color 120ms var(--ease-out), background 120ms var(--ease-out);
}
.run-row:hover {
  border-color: var(--color-accent-soft-bd);
}
.run-row.sel {
  border-color: var(--color-accent);
  background: var(--color-accent-tint);
}
.run-row.failed {
  border-color: var(--color-score-danger-bd);
}
.run-top {
  display: flex;
  align-items: center;
  gap: 9px;
}
.run-seq {
  font-size: 13.5px;
  font-weight: 620;
  color: var(--color-ink);
}
.run-meta {
  font-size: 12px;
  color: var(--color-ink-3);
  font-variant-numeric: tabular-nums;
}
.run-error {
  font-size: 12px;
  color: var(--color-danger);
}

/* 选中结果 */
.result {
  padding: 18px 20px;
}
.result--pending {
  border-color: var(--color-warn-card-bd);
  background: var(--color-warn-card-bg);
}
.result-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.rh-title {
  display: flex;
  align-items: center;
  gap: 9px;
}
.rh-title h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 680;
}
.rh-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.rh-actions {
  flex: 0 0 auto;
  display: flex;
  gap: 8px;
}

.pending-note {
  margin: 14px 0 0;
  padding: 10px 13px;
  border: 1px solid var(--color-warn-card-bd);
  border-radius: 10px;
  background: var(--color-surface);
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--color-warn);
}

/* 失败面板 */
.fail-panel {
  display: flex;
  gap: 12px;
  margin-top: 14px;
  padding: 14px 16px;
  border: 1px solid var(--color-score-danger-bd);
  border-radius: 12px;
  background: var(--color-score-danger-bg);
}
.fail-ico {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--color-danger);
  color: #fff;
  font-weight: 800;
  flex: 0 0 auto;
}
.fail-panel strong {
  font-size: 14px;
  font-weight: 680;
  color: var(--color-danger);
}
.fail-panel p {
  margin: 4px 0 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-ink-2);
}

/* 结果分块 */
.result-block {
  margin-top: 18px;
}
.block-title {
  display: flex;
  align-items: center;
  gap: 7px;
  margin: 0 0 10px;
  font-size: 14px;
  font-weight: 650;
  color: var(--color-ink);
}
.block-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.block-title-row .block-title {
  margin: 0;
}

/* 报告富文本 */
.rep {
  font-size: 13.5px;
  line-height: 1.75;
  color: var(--color-ink-2);
}
.rep :deep(h2),
.rep :deep(h3) {
  margin: 18px 0 8px;
  font-size: 14.5px;
  font-weight: 680;
  color: var(--color-ink);
}
.rep :deep(h2:first-child),
.rep :deep(h3:first-child) {
  margin-top: 0;
}
.rep :deep(h4) {
  margin: 14px 0 6px;
  font-size: 13.5px;
  font-weight: 650;
  color: var(--color-ink);
}
.rep :deep(p) {
  margin: 8px 0;
}
.rep :deep(strong) {
  color: var(--color-ink);
  font-weight: 650;
}
.rep :deep(ul),
.rep :deep(ol) {
  margin: 8px 0;
  padding-left: 20px;
}
.rep :deep(li) {
  margin: 4px 0;
}
.rep :deep(blockquote) {
  margin: 10px 0;
  padding: 10px 14px;
  border-left: 3px solid var(--color-accent);
  border-radius: 0 8px 8px 0;
  background: var(--color-accent-tint);
  color: var(--color-ink-2);
}
.rep :deep(code) {
  padding: 1px 5px;
  border-radius: 5px;
  background: var(--color-paper-3);
  font-size: 12.5px;
}

/* Skill 深色代码框 */
.skill-code {
  margin: 0;
  max-height: 460px;
  overflow: auto;
  padding: 16px 18px;
  border-radius: 12px;
  background: var(--color-code-bg);
  color: var(--color-code-ink);
  font-family: 'SFMono-Regular', Menlo, Consolas, monospace;
  font-size: 12.5px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
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
.btn.block {
  width: 100%;
  margin-top: auto;
}
.btn.slim {
  height: 32px;
  padding: 0 13px;
  font-size: 13px;
  border-radius: 9px;
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

.empty-region.pad {
  padding: 24px 20px;
}

@media (max-width: 900px) {
  .md-grid {
    grid-template-columns: 1fr;
  }
  .bl-card {
    position: static;
  }
}
</style>
