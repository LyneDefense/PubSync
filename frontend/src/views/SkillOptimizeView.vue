<script setup lang="ts">
// Skill 优化:选对标博主(卡片单选)→ 发起优化(进度就地内嵌)→ 看「像不像本人」相似度标尺 + 改写清单 + 三栏样例 →
// 采纳/放弃(没提升会明确劝退)。纯展示重构:store 字段、runTitle/verdictInfo 等逻辑全部沿用。
import { computed } from 'vue'
import TIcon from '../components/TIcon.vue'
import LiveProgress from '../components/LiveProgress.vue'
import {
  benchmarkAccounts,
  currentSocialPlatform,
  currentSocialTab,
  currentTrainingRun,
  handleConfirmOptimize,
  handleOptimizeSkill,
  isSocialPlatform,
  optimizeBloggerId,
  optimizeConfirming,
  optimizeSkillId,
  optimizeSkillOptions,
  pendingAction,
  selectTrainingRun,
  trainingRuns
} from '../composables/useWorkspaceStore'
import type { SkillTrainingRun } from '../api/types'

const platformBloggers = computed(() => benchmarkAccounts.value.filter((b) => b.platform === currentSocialPlatform.value))
const optimizing = computed(() => pendingAction.value === 'optimize')
const run = currentTrainingRun

// 语气 → Tabler 图标(全站统一图标系统,替代各处散落的 ✅⚠️⛔ emoji)。
const TONE_ICON: Record<string, string> = {
  ok: 'circle-check',
  warn: 'alert-triangle',
  bad: 'circle-x',
  mute: 'circle-dashed'
}

const VERDICT: Record<string, { tone: string; text: string }> = {
  improved: { tone: 'ok', text: '建议采纳:优化后明显更贴近该博主风格。' },
  no_gain: { tone: 'warn', text: '建议不要采纳:本次没有明显提升(变化在噪声范围内),保留原 Skill 即可。' },
  regressed: { tone: 'bad', text: '建议不要采纳:优化后反而更不像,保留原 Skill。' }
}
function verdictInfo(v: string) {
  return VERDICT[v] || { tone: 'warn', text: '请人工判断是否采纳。' }
}

// 历史记录每条的标题:含「建议采纳/不建议采纳/未完成 + 是否已处理 + 时间」。
function runTitle(run: SkillTrainingRun): { tone: string; label: string } {
  if (run.status === 'failed') return { tone: 'bad', label: '未完成（生成失败）' }
  if (run.status === 'succeeded') return { tone: 'ok', label: '已采纳' }
  if (run.status === 'abandoned') return { tone: 'mute', label: '已放弃' }
  if (run.status === 'running') return { tone: 'mute', label: '优化中…' }
  // pending_confirmation:还没处理,显示系统建议
  if (run.recommend_adopt) return { tone: 'ok', label: '建议采纳' }
  if (run.verdict === 'regressed') return { tone: 'bad', label: '不建议采纳' }
  return { tone: 'warn', label: '不建议采纳' }
}

function runTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

// 「像不像本人」标尺定位:把分数映射到可视区间 20→100 的百分比(避免低分挤在左端)。
function pos(v: number): number {
  const p = ((Number(v) - 20) / 80) * 100
  return Math.max(0, Math.min(100, p))
}
function ptStyle(v: number) {
  return { left: pos(v) + '%' }
}
// 提升段:优化前 ↔ 优化后之间高亮(退步则反向、暖色)。
function gainStyle(before: number, after: number) {
  const lo = pos(Math.min(before, after))
  const hi = pos(Math.max(before, after))
  return { left: lo + '%', width: Math.max(0, hi - lo) + '%' }
}

// 文字头像:名字首字 + 按 id 取柔和底色。
const AVATAR_BG = ['#eaf3ee', '#f0eef7', '#eef4f5', '#eef1f6', '#f6eef2', '#eef3f7']
const AVATAR_INK = ['#2f6b54', '#5a4a86', '#3a6a72', '#44506a', '#8a4a64', '#3a5a86']
function avatarStyle(id: number) {
  const i = (((id || 0) % AVATAR_BG.length) + AVATAR_BG.length) % AVATAR_BG.length
  return { background: AVATAR_BG[i], color: AVATAR_INK[i] }
}
</script>

<template>
  <section v-if="isSocialPlatform && currentSocialTab === 'skill-optimize'" class="skill-opt">
    <header class="page-head">
      <h1>Skill 优化</h1>
      <p>用该博主的真实笔记，把它的写作 Skill 练得更像本人。每次优化都给出<b>前后对比</b>和<b>是否采纳</b>的建议 —— 没提升会明确劝退。</p>
    </header>

    <!-- 发起卡:两列(博主卡 / 版本单选) -->
    <section class="card launch">
      <div class="lc-col">
        <span class="col-title">要优化的对标博主</span>
        <div v-if="platformBloggers.length" class="blogger-list">
          <button
            v-for="b in platformBloggers"
            :key="b.id"
            type="button"
            class="bl-card"
            :class="{ sel: optimizeBloggerId === b.id }"
            :disabled="optimizing"
            @click="optimizeBloggerId = b.id"
          >
            <span class="bl-avatar" :style="avatarStyle(b.id)">{{ (b.display_name || '?').slice(0, 1) }}</span>
            <span class="bl-body">
              <span class="bl-name">{{ b.display_name }}</span>
              <span class="bl-sub">已采集 {{ b.sample_count }} 篇<template v-if="optimizeBloggerId === b.id && optimizeSkillOptions.length"> · {{ optimizeSkillOptions.length }} 个 Skill</template></span>
            </span>
            <span class="bl-radio" aria-hidden="true"></span>
          </button>
        </div>
        <p v-else class="empty-region pad">还没有对标博主。请先到「数据采集 / 提炼 Skill」创建博主并蒸馏。</p>
      </div>

      <div class="lc-col">
        <span class="col-title">要优化的 Skill 版本</span>
        <div v-if="optimizeSkillOptions.length" class="ver-list">
          <button
            v-for="s in optimizeSkillOptions"
            :key="s.id"
            type="button"
            class="ver"
            :class="{ sel: optimizeSkillId === s.id }"
            :disabled="optimizing"
            @click="optimizeSkillId = s.id"
          >
            <span class="ver-dot" aria-hidden="true"></span>
            <span class="ver-name">{{ s.name }}</span>
            <span class="ver-tag" :class="{ cur: s.status === 'active' }">{{ s.status === 'active' ? '当前' : '历史' }}</span>
          </button>
        </div>
        <p v-else class="empty-region pad">{{ optimizeBloggerId ? '该博主暂无 Skill,请先到「提炼 Skill」蒸馏一次。' : '先在左侧选择一个博主。' }}</p>

        <button
          type="button"
          class="btn btn--accent block"
          :disabled="optimizing || !optimizeBloggerId || !optimizeSkillId"
          @click="handleOptimizeSkill"
        >
          <span v-if="optimizing" class="spin" aria-hidden="true"></span>
          {{ optimizing ? '优化中…' : '开始优化' }}
        </button>
        <LiveProgress v-if="optimizing" />
        <p class="lc-hint">默认优化该博主当前 Skill，也可选历史版本。需已采集 ≥ 12 篇笔记。</p>
      </div>
    </section>

    <!-- 优化记录:横向滚动卡片 -->
    <section v-if="optimizeBloggerId && trainingRuns.length" class="history">
      <div class="history-head"><h3>优化记录</h3><span>点一条查看详情</span></div>
      <div class="run-strip">
        <button
          v-for="r in trainingRuns"
          :key="r.id"
          type="button"
          class="run-card"
          :class="{ sel: currentTrainingRun && currentTrainingRun.id === r.id }"
          @click="selectTrainingRun(r)"
        >
          <span class="run-badge" :class="`tone-${runTitle(r).tone}`"><TIcon :name="TONE_ICON[runTitle(r).tone]" /> {{ runTitle(r).label }}</span>
          <span v-if="r.status !== 'failed' && r.status !== 'running'" class="run-delta">
            {{ Math.round(r.before_score) }} <i>→</i> {{ Math.round(r.after_score) }}
            <em :class="r.delta > 0 ? 'pos' : r.delta < 0 ? 'neg' : 'noise'">Δ {{ r.delta > 0 ? '+' : '' }}{{ r.delta }}</em>
          </span>
          <span class="run-time">{{ runTime(r.created_at) }}</span>
        </button>
      </div>
    </section>

    <!-- 失败态:不展示误导性的 0→0 -->
    <section v-if="run && run.status === 'failed'" class="card fail">
      <div class="verdict tone-bad">
        <span class="vd-ico" aria-hidden="true"><TIcon name="circle-x" /></span>
        <strong>本次优化未能完成</strong>
      </div>
      <p class="note">{{ run.error_message || '生成失败，请稍后重试。' }}</p>
      <p v-if="run.report.anchors" class="lc-hint">参照:其它博主基线 {{ Math.round(run.report.anchors.floor) }} 分 · 真笔记天花板 {{ Math.round(run.report.anchors.ceiling) }} 分（满分 100，越高越像本人）。</p>
    </section>

    <!-- 结果 -->
    <template v-else-if="run && run.status !== 'running'">
      <!-- 结论横幅 -->
      <section class="card verdict-card">
        <div class="verdict" :class="`tone-${verdictInfo(run.verdict).tone}`">
          <span class="vd-ico" aria-hidden="true"><TIcon :name="TONE_ICON[verdictInfo(run.verdict).tone]" /></span>
          <strong>{{ verdictInfo(run.verdict).text }}</strong>
        </div>
      </section>

      <!-- 「像不像本人」相似度标尺 -->
      <section class="card meter-card">
        <div class="meter-head">
          <div>
            <h3>像不像本人</h3>
            <span class="meter-sub">相似度（满分 100，越高越像）</span>
          </div>
          <div class="meter-nums">
            <span class="mn"><small>优化前</small><b>{{ Math.round(run.before_score) }}</b></span>
            <span class="mn-arrow">→</span>
            <span class="mn"><small>优化后</small><b class="hi">{{ Math.round(run.after_score) }}</b></span>
            <span class="mn-delta" :class="run.delta > 0 ? 'pos' : run.delta < 0 ? 'neg' : 'noise'">Δ {{ run.delta > 0 ? '+' : '' }}{{ run.delta }}</span>
          </div>
        </div>

        <div class="meter">
          <div class="meter-track"></div>
          <template v-if="run.report.anchors">
            <div class="meter-band" :style="gainStyle(run.report.anchors.floor, run.report.anchors.ceiling)"></div>
            <div class="meter-mark floor" :style="ptStyle(run.report.anchors.floor)">
              <i></i><span class="mk-val">{{ Math.round(run.report.anchors.floor) }}</span><span class="mk-lbl">其它博主基线</span>
            </div>
            <div class="meter-mark ceil" :style="ptStyle(run.report.anchors.ceiling)">
              <i></i><span class="mk-val">{{ Math.round(run.report.anchors.ceiling) }}</span><span class="mk-lbl">真笔记天花板</span>
            </div>
          </template>
          <div class="meter-gain" :class="{ down: run.delta < 0 }" :style="gainStyle(run.before_score, run.after_score)"></div>
          <div class="meter-pt before" :style="ptStyle(run.before_score)" :title="`优化前 ${Math.round(run.before_score)}`"></div>
          <div class="meter-pt after" :style="ptStyle(run.after_score)" :title="`优化后 ${Math.round(run.after_score)}`"></div>
        </div>

        <p class="meter-foot">距天花板差距：优化前 {{ run.before_gap }}% <i>→</i> 优化后 <b>{{ run.after_gap }}%</b></p>
      </section>

      <!-- 采纳 / 放弃 -->
      <section v-if="run.status === 'pending_confirmation'" class="card confirm">
        <span class="cf-q">要把优化后的版本设为当前 Skill 吗？</span>
        <div class="cf-actions">
          <button type="button" class="btn btn--accent" :disabled="optimizeConfirming" @click="handleConfirmOptimize(true)">✓ 采纳新版本</button>
          <button type="button" class="btn btn--ghost" :disabled="optimizeConfirming" @click="handleConfirmOptimize(false)">放弃 · 保留原 Skill</button>
        </div>
      </section>
      <section v-else-if="run.status === 'succeeded'" class="done-strip ok">已采纳：优化版已设为当前 Skill。</section>
      <section v-else-if="run.status === 'abandoned'" class="done-strip">已放弃：保留原 Skill。</section>

      <!-- 我们是怎么优化的 -->
      <section class="card">
        <h3 class="block-title">我们是怎么优化的</h3>
        <p class="note">{{ run.report.process_note }}</p>
        <template v-if="run.report.changelog && run.report.changelog.length">
          <p class="sub-label">优化器对 Skill 做的改写</p>
          <ol class="changelog">
            <li v-for="(c, i) in run.report.changelog" :key="i"><span class="cl-num">{{ i + 1 }}</span><span class="cl-text">{{ c }}</span></li>
          </ol>
        </template>
        <p v-else class="lc-hint">本次优化器没有产生被验证集采纳的改写（候选改写都没能超过原 Skill）。</p>
      </section>

      <!-- 同一选题三栏 -->
      <section v-if="run.report.samples && run.report.samples.length" class="card">
        <h3 class="block-title">同一选题：优化前 / 优化后 / 真笔记</h3>
        <div v-for="(s, i) in run.report.samples" :key="i" class="sample">
          <p class="sample-topic">选题：{{ s.topic }}</p>
          <div class="sample-cols">
            <div class="scol">
              <div class="scol-head"><span>优化前</span><b>{{ s.seed_sim }}</b></div>
              <p>{{ s.seed_text }}</p>
            </div>
            <div class="scol best">
              <div class="scol-head"><span>优化后</span><b>{{ s.optimized_sim }}</b></div>
              <p>{{ s.optimized_text }}</p>
            </div>
            <div class="scol real">
              <div class="scol-head"><span>真笔记</span><b>本人</b></div>
              <p>{{ s.real_text }}</p>
            </div>
          </div>
        </div>
      </section>
    </template>
  </section>
</template>

<style scoped>
.skill-opt {
  max-width: 920px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
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
.page-head b {
  color: var(--color-ink);
  font-weight: 650;
}

/* 卡片 */
.card {
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-lg);
  padding: 20px 22px;
}
.block-title {
  margin: 0 0 10px;
  font-size: 15px;
  font-weight: 650;
}
.note {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--color-ink-2);
}
.lc-hint {
  margin: 10px 0 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--color-ink-3);
}

/* 按钮 */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  height: 40px;
  padding: 0 18px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: background 140ms var(--ease-out), border-color 140ms var(--ease-out);
}
.btn.block {
  width: 100%;
  margin-top: 12px;
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
  opacity: 0.5;
  cursor: not-allowed;
}
.spin {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.45);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 发起卡:两列 */
.launch {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}
.col-title {
  display: block;
  margin-bottom: 12px;
  font-size: 13px;
  font-weight: 650;
  color: var(--color-ink);
}
.blogger-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.bl-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 13px;
  border: 1px solid var(--color-rule);
  border-radius: 12px;
  background: var(--color-surface);
  cursor: pointer;
  text-align: left;
  transition: border-color 120ms var(--ease-out), background 120ms var(--ease-out);
}
.bl-card:hover:not(:disabled) {
  border-color: var(--color-accent-soft-bd);
}
.bl-card.sel {
  border-color: var(--color-accent);
  background: var(--color-accent-tint);
  box-shadow: 0 1px 4px var(--color-shadow);
}
.bl-card:disabled {
  cursor: not-allowed;
}
.bl-avatar {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: 11px;
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
  font-size: 14px;
  font-weight: 620;
  color: var(--color-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.bl-sub {
  display: block;
  margin-top: 2px;
  font-size: 11.5px;
  color: var(--color-ink-3);
  font-variant-numeric: tabular-nums;
}
.bl-radio {
  flex: 0 0 auto;
  width: 20px;
  height: 20px;
  border: 1.5px solid var(--color-rule-strong);
  border-radius: 50%;
  position: relative;
}
.bl-card.sel .bl-radio {
  border-color: var(--color-accent);
  background: var(--color-accent);
}
.bl-card.sel .bl-radio::after {
  content: '✓';
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: #fff;
  font-size: 12px;
  font-weight: 800;
}

/* 版本单选 */
.ver-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ver {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 13px;
  border: 1px solid var(--color-rule);
  border-radius: 11px;
  background: var(--color-surface);
  cursor: pointer;
  text-align: left;
  transition: border-color 120ms var(--ease-out), background 120ms var(--ease-out);
}
.ver:hover:not(:disabled) {
  border-color: var(--color-accent-soft-bd);
}
.ver.sel {
  border-color: var(--color-accent);
  background: var(--color-accent-tint);
}
.ver:disabled {
  cursor: not-allowed;
}
.ver-dot {
  flex: 0 0 auto;
  width: 16px;
  height: 16px;
  border: 1.5px solid var(--color-rule-strong);
  border-radius: 50%;
  position: relative;
}
.ver.sel .ver-dot {
  border-color: var(--color-accent);
}
.ver.sel .ver-dot::after {
  content: '';
  position: absolute;
  inset: 3px;
  border-radius: 50%;
  background: var(--color-accent);
}
.ver-name {
  flex: 1;
  min-width: 0;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--color-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ver-tag {
  flex: 0 0 auto;
  padding: 2px 9px;
  border-radius: 6px;
  background: var(--color-paper-3);
  color: var(--color-ink-3);
  font-size: 11.5px;
  font-weight: 600;
}
.ver-tag.cur {
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
}

/* 优化记录:横向滚动 */
.history-head {
  display: flex;
  align-items: baseline;
  gap: 9px;
  margin-bottom: 12px;
}
.history-head h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 650;
}
.history-head span {
  font-size: 12.5px;
  color: var(--color-ink-3);
}
.run-strip {
  display: flex;
  gap: 10px;
  overflow-x: auto;
  padding-bottom: 4px;
}
.run-card {
  flex: 0 0 auto;
  width: 200px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 13px 14px;
  border: 1px solid var(--color-rule);
  border-radius: 12px;
  background: var(--color-surface);
  cursor: pointer;
  text-align: left;
  transition: border-color 120ms var(--ease-out), background 120ms var(--ease-out);
}
.run-card:hover {
  border-color: var(--color-accent-soft-bd);
}
.run-card.sel {
  border-color: var(--color-accent);
  background: var(--color-accent-tint);
  box-shadow: 0 1px 4px var(--color-shadow);
}
.run-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  font-weight: 650;
}
.run-badge i {
  vertical-align: -1px;
}
.run-delta {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 650;
  color: var(--color-ink);
  font-variant-numeric: tabular-nums;
}
.run-delta i {
  color: var(--color-ink-3);
  font-style: normal;
}
.run-delta em {
  font-style: normal;
  font-size: 12px;
  font-weight: 700;
  padding: 1px 7px;
  border-radius: var(--radius-pill);
}
.run-time {
  font-size: 11.5px;
  color: var(--color-ink-3);
  font-variant-numeric: tabular-nums;
}
.tone-ok {
  color: var(--color-ok);
}
.tone-warn {
  color: var(--color-warn);
}
.tone-bad {
  color: var(--color-danger);
}
.tone-mute {
  color: var(--color-ink-3);
}
.pos {
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
}
.neg {
  background: var(--color-score-danger-bg);
  color: var(--color-danger);
}
.noise {
  background: var(--color-paper-3);
  color: var(--color-ink-3);
}

/* 结论横幅 */
.verdict-card {
  padding: 0;
  border: 0;
  background: transparent;
}
.verdict {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 18px;
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-lg);
  font-size: 14px;
  font-weight: 600;
  color: var(--color-ink);
}
.verdict .vd-ico {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  flex: 0 0 auto;
  color: #fff;
}
.verdict.tone-ok {
  border-color: var(--color-accent-soft-bd);
  background: var(--color-accent-soft);
}
.verdict.tone-ok .vd-ico {
  background: var(--color-accent);
}
.verdict.tone-warn {
  border-color: var(--color-warn-card-bd);
  background: var(--color-warn-card-bg);
}
.verdict.tone-warn .vd-ico {
  background: var(--color-warn);
}
.verdict.tone-bad {
  border-color: var(--color-score-danger-bd);
  background: var(--color-score-danger-bg);
}
.verdict.tone-bad .vd-ico {
  background: var(--color-danger);
}
.verdict.tone-ok strong { color: var(--color-accent-ink); }
.verdict.tone-warn strong { color: var(--color-warn); }
.verdict.tone-bad strong { color: var(--color-danger); }

/* 失败卡 */
.fail .verdict {
  border: 0;
  padding: 0;
  background: transparent;
  margin-bottom: 8px;
}

/* 「像不像本人」标尺 */
.meter-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 26px;
}
.meter-head h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 680;
  display: inline;
}
.meter-sub {
  margin-left: 8px;
  font-size: 12px;
  color: var(--color-ink-3);
}
.meter-nums {
  display: flex;
  align-items: flex-end;
  gap: 10px;
}
.mn {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.mn small {
  font-size: 11px;
  color: var(--color-ink-3);
}
.mn b {
  font-size: 24px;
  font-weight: 720;
  line-height: 1.1;
  color: var(--color-ink-2);
  font-variant-numeric: tabular-nums;
}
.mn b.hi {
  color: var(--color-accent);
}
.mn-arrow {
  color: var(--color-ink-3);
  font-size: 16px;
  padding-bottom: 2px;
}
.mn-delta {
  font-size: 13px;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  font-variant-numeric: tabular-nums;
  margin-bottom: 2px;
}

.meter {
  position: relative;
  height: 56px;
  margin: 0 10px;
}
.meter-track {
  position: absolute;
  left: 0;
  right: 0;
  top: 11px;
  height: 6px;
  border-radius: 99px;
  background: var(--color-paper-3);
}
.meter-band {
  position: absolute;
  top: 11px;
  height: 6px;
  border-radius: 99px;
  background: var(--color-accent-soft);
}
.meter-gain {
  position: absolute;
  top: 11px;
  height: 6px;
  border-radius: 99px;
  background: var(--color-accent);
  opacity: 0.55;
}
.meter-gain.down {
  background: var(--color-warn);
}
.meter-mark {
  position: absolute;
  top: 0;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
}
.meter-mark i {
  width: 2px;
  height: 16px;
  border-radius: 2px;
  background: var(--color-rule-strong);
}
.meter-mark.ceil i {
  background: var(--color-ink-3);
}
.mk-val {
  margin-top: 5px;
  font-size: 12px;
  font-weight: 650;
  color: var(--color-ink-2);
  font-variant-numeric: tabular-nums;
}
.mk-lbl {
  font-size: 11px;
  color: var(--color-ink-3);
  white-space: nowrap;
}
.meter-pt {
  position: absolute;
  top: 7px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  transform: translateX(-50%);
  z-index: 2;
}
.meter-pt.before {
  background: var(--color-surface);
  border: 2px solid var(--color-rule-strong);
}
.meter-pt.after {
  background: var(--color-accent);
  border: 2px solid var(--color-surface);
  box-shadow: 0 0 0 1px var(--color-accent);
}
.meter-foot {
  margin: 18px 0 0;
  font-size: 13px;
  color: var(--color-ink-2);
  font-variant-numeric: tabular-nums;
}
.meter-foot i {
  font-style: normal;
  color: var(--color-ink-3);
}
.meter-foot b {
  color: var(--color-accent-ink);
  font-weight: 700;
}

/* 采纳 / 放弃 */
.confirm {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.cf-q {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-ink);
}
.cf-actions {
  display: flex;
  gap: 10px;
}
.done-strip {
  padding: 13px 16px;
  border-radius: var(--radius-lg);
  background: var(--color-paper-3);
  color: var(--color-ink-2);
  font-size: 13.5px;
  font-weight: 600;
}
.done-strip.ok {
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
}

/* 改写清单 */
.sub-label {
  margin: 14px 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-ink);
}
.changelog {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.changelog li {
  display: flex;
  gap: 10px;
  padding: 11px 13px;
  border: 1px solid var(--color-rule);
  border-radius: 10px;
}
.cl-num {
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
  font-size: 12px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.cl-text {
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-ink-2);
}

/* 三栏样例 */
.sample {
  margin-top: 14px;
}
.sample:first-of-type {
  margin-top: 0;
}
.sample-topic {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-ink);
}
.sample-cols {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 10px;
}
.scol {
  border: 1px solid var(--color-rule);
  border-radius: 11px;
  overflow: hidden;
  background: var(--color-surface);
}
.scol.best {
  border-color: var(--color-accent);
}
.scol.real {
  background: #fafbfc;
}
.scol-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 11px;
  background: #fafbfc;
  border-bottom: 1px solid var(--color-paper-3);
  font-size: 12px;
  font-weight: 650;
  color: var(--color-ink-2);
}
.scol.best .scol-head {
  background: var(--color-accent-tint);
  color: var(--color-accent-ink);
}
.scol-head b {
  font-variant-numeric: tabular-nums;
}
.scol.best .scol-head b {
  color: var(--color-accent);
}
.scol p {
  margin: 0;
  padding: 11px;
  font-size: 12.5px;
  line-height: 1.65;
  color: var(--color-ink-2);
  white-space: pre-wrap;
  max-height: 240px;
  overflow-y: auto;
}

.empty-region.pad {
  padding: 22px 16px;
  text-align: center;
}

@media (prefers-reduced-motion: reduce) {
  .spin { animation: none; }
}
@media (max-width: 720px) {
  .launch {
    grid-template-columns: 1fr;
  }
  .sample-cols {
    grid-template-columns: 1fr;
  }
}
</style>
