<script setup lang="ts">
// Skill 优化:选对标博主 → 发起优化(进度走顶部 LiveProgress)→ 看完整结果
// (优化前后对比 + 优化器改了什么 + 样例三栏 + 明确建议;没提升就劝退)→ 采纳/放弃。
import { computed } from 'vue'
import TIcon from '../components/TIcon.vue'
import {
  benchmarkAccounts,
  currentSocialPlatform,
  currentSocialPlatformName,
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
</script>

<template>
  <section v-if="isSocialPlatform && currentSocialTab === 'skill-optimize'" class="panel skill-opt">
    <div class="section-header">
      <div>
        <h2>Skill 优化</h2>
        <p class="toolbar-subtitle">用该博主的真实笔记把 Skill 练得更像;每次优化都会给出前后对比和是否采纳的建议(没提升会明确劝退)。</p>
      </div>
    </div>

    <div class="so-launch">
      <label>选择要优化的对标博主
        <select v-model="optimizeBloggerId" :disabled="optimizing">
          <option :value="null">请选择…</option>
          <option v-for="b in platformBloggers" :key="b.id" :value="b.id">{{ b.display_name }}</option>
        </select>
      </label>
      <label>选择要优化的 Skill 版本
        <select v-model="optimizeSkillId" :disabled="optimizing || !optimizeBloggerId || !optimizeSkillOptions.length">
          <option v-if="!optimizeSkillOptions.length" :value="null">该博主暂无 Skill</option>
          <option v-for="s in optimizeSkillOptions" :key="s.id" :value="s.id">
            {{ s.name }}{{ s.status === 'active' ? '（当前）' : '（历史）' }}
          </option>
        </select>
      </label>
      <button type="button" class="primary" :disabled="optimizing || !optimizeBloggerId || !optimizeSkillId" @click="handleOptimizeSkill">
        {{ optimizing ? '优化中…' : '开始优化' }}
      </button>
    </div>
    <p class="field-hint">默认优化该博主当前 Skill;也可选历史版本。需采集了足够笔记(≥12 篇)。优化过程见上方进度条。</p>

    <!-- 历史优化记录 -->
    <div v-if="optimizeBloggerId && trainingRuns.length" class="so-history">
      <h3>优化记录</h3>
      <ul class="so-history-list">
        <li v-for="r in trainingRuns" :key="r.id">
          <button
            type="button"
            class="so-history-item"
            :class="{ active: currentTrainingRun && currentTrainingRun.id === r.id }"
            @click="selectTrainingRun(r)"
          >
            <span class="so-history-badge" :class="`so-history-badge--${runTitle(r).tone}`"><TIcon :name="TONE_ICON[runTitle(r).tone]" /> {{ runTitle(r).label }}</span>
            <span v-if="r.status !== 'failed' && r.status !== 'running'" class="so-history-delta">
              {{ Math.round(r.before_score) }} → {{ Math.round(r.after_score) }}（Δ {{ r.delta > 0 ? '+' : '' }}{{ r.delta }}）
            </span>
            <span class="so-history-time">{{ runTime(r.created_at) }}</span>
          </button>
        </li>
      </ul>
    </div>

    <!-- 失败:生成全部失败时不展示误导性的 0→0,直接说明原因 -->
    <div v-if="run && run.status === 'failed'" class="so-result">
      <div class="so-verdict so-verdict--bad">
        <strong><TIcon name="circle-x" /> 本次优化未能完成</strong>
      </div>
      <p class="so-note">{{ run.error_message || '生成失败，请稍后重试。' }}</p>
      <p class="field-hint" v-if="run.report.anchors">
        参照:其它博主基线 {{ Math.round(run.report.anchors.floor) }} 分 · 真笔记天花板 {{ Math.round(run.report.anchors.ceiling) }} 分(满分100，越高越像本人）。
      </p>
    </div>

    <!-- 结果 -->
    <div v-else-if="run && run.status !== 'running'" class="so-result">
      <!-- 建议横幅 -->
      <div class="so-verdict" :class="`so-verdict--${verdictInfo(run.verdict).tone}`">
        <strong><TIcon :name="TONE_ICON[verdictInfo(run.verdict).tone]" /> {{ verdictInfo(run.verdict).text }}</strong>
      </div>

      <!-- 前后对比 -->
      <div class="so-scores">
        <div class="so-score">
          <span class="so-score-label">优化前</span>
          <span class="so-score-val">{{ Math.round(run.before_score) }}</span>
          <small>gap {{ run.before_gap }}%</small>
        </div>
        <div class="so-arrow">→</div>
        <div class="so-score">
          <span class="so-score-label">优化后</span>
          <span class="so-score-val">{{ Math.round(run.after_score) }}</span>
          <small>gap {{ run.after_gap }}%</small>
        </div>
        <div class="so-delta" :class="run.delta > 0 ? 'pos' : run.delta < 0 ? 'neg' : ''">
          Δ {{ run.delta > 0 ? '+' : '' }}{{ run.delta }}
        </div>
      </div>
      <p class="field-hint" v-if="run.report.anchors">
        参照:其它博主基线 {{ Math.round(run.report.anchors.floor) }} 分 · 真笔记天花板 {{ Math.round(run.report.anchors.ceiling) }} 分(满分100,越高越像本人)。
      </p>

      <!-- 采纳/放弃(仅待确认时) -->
      <div v-if="run.status === 'pending_confirmation'" class="so-actions">
        <button type="button" :class="{ primary: run.recommend_adopt }" :disabled="optimizeConfirming" @click="handleConfirmOptimize(true)">采纳新版本</button>
        <button type="button" :class="{ primary: !run.recommend_adopt }" :disabled="optimizeConfirming" @click="handleConfirmOptimize(false)">放弃 · 保留原 Skill</button>
      </div>
      <p v-else-if="run.status === 'succeeded'" class="so-done so-done--ok">已采纳:优化版已设为当前 Skill。</p>
      <p v-else-if="run.status === 'abandoned'" class="so-done">已放弃:保留原 Skill。</p>

      <!-- 怎么优化的 -->
      <div class="so-block">
        <h3>我们是怎么优化的</h3>
        <p class="so-note">{{ run.report.process_note }}</p>
        <template v-if="run.report.changelog && run.report.changelog.length">
          <p class="so-sub">优化器对 Skill 做的改写:</p>
          <ul class="so-changelog">
            <li v-for="(c, i) in run.report.changelog" :key="i">{{ c }}</li>
          </ul>
        </template>
        <p v-else class="field-hint">本次优化器没有产生被验证集采纳的改写(候选改写都没能超过原 Skill)。</p>
      </div>

      <!-- 样例三栏 -->
      <div v-if="run.report.samples && run.report.samples.length" class="so-block">
        <h3>同一选题:优化前 vs 优化后 vs 真笔记</h3>
        <div v-for="(s, i) in run.report.samples" :key="i" class="so-sample">
          <p class="so-sample-topic">选题:{{ s.topic }}</p>
          <div class="so-sample-cols">
            <div class="so-col">
              <div class="so-col-head">优化前 <span>{{ s.seed_sim }}</span></div>
              <p>{{ s.seed_text }}</p>
            </div>
            <div class="so-col">
              <div class="so-col-head">优化后 <span>{{ s.optimized_sim }}</span></div>
              <p>{{ s.optimized_text }}</p>
            </div>
            <div class="so-col so-col--real">
              <div class="so-col-head">真笔记</div>
              <p>{{ s.real_text }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.skill-opt { max-width: 980px; }
.so-launch { display: flex; gap: 12px; align-items: flex-end; margin-bottom: 6px; }
.so-launch label { display: flex; flex-direction: column; gap: 4px; flex: 1; max-width: 360px; }
.so-history { margin-top: 18px; }
.so-history h3 { margin: 0 0 8px; font-size: 1rem; }
.so-history-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.so-history-item {
  width: 100%; display: flex; align-items: center; gap: 12px; text-align: left;
  padding: 8px 12px; border: 1px solid var(--color-field-border, #c8ced4); border-radius: 10px;
  background: var(--color-field, #fff); cursor: pointer;
}
.so-history-item:hover { border-color: var(--color-accent, #2563eb); }
.so-history-item.active { border-color: var(--color-accent, #2563eb); box-shadow: 0 0 0 1px var(--color-accent, #2563eb) inset; }
.so-history-badge { font-weight: 600; font-size: 0.85rem; white-space: nowrap; }
.so-history-badge--ok { color: var(--color-ok); }
.so-history-badge--warn { color: #9a6a12; }
.so-history-badge--bad { color: #c0392b; }
.so-history-badge--mute { color: var(--color-ink-2, #6b7280); }
.so-history-delta { font-size: 0.85rem; color: var(--color-ink-2, #6b7280); }
.so-history-time { margin-left: auto; font-size: 0.8rem; color: var(--color-ink-3, #9aa0a6); white-space: nowrap; }
.so-result { margin-top: 18px; display: flex; flex-direction: column; gap: 16px; }
.so-verdict { padding: 12px 14px; border-radius: 12px; font-size: 1rem; }
.so-verdict strong i, .so-history-badge i { vertical-align: -1px; }
.so-verdict--ok { background: var(--color-ok-bg, #e8f5ec); color: var(--color-ok); }
.so-verdict--warn { background: #fdf3e2; color: #9a6a12; }
.so-verdict--bad { background: #fdecec; color: #c0392b; }
.so-scores { display: flex; align-items: center; gap: 18px; }
.so-score { display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 10px 18px; border: 1px solid var(--color-field-border, #c8ced4); border-radius: 12px; min-width: 96px; }
.so-score-label { font-size: 0.8rem; color: var(--color-ink-2, #6b7280); }
.so-score-val { font-size: 1.8rem; font-weight: 700; }
.so-score small { color: var(--color-ink-2, #6b7280); font-size: 0.75rem; }
.so-arrow { font-size: 1.4rem; color: var(--color-ink-3, #9aa0a6); }
.so-delta { font-weight: 700; padding: 4px 10px; border-radius: 999px; background: var(--color-paper-3, #eef0f3); }
.so-delta.pos { background: var(--color-ok-bg); color: var(--color-ok); }
.so-delta.neg { background: #fdecec; color: #c0392b; }
.so-actions { display: flex; gap: 10px; }
.so-done { font-weight: 600; }
.so-done--ok { color: var(--color-ok); }
.so-block { border-top: 1px solid var(--color-field-border, #c8ced4); padding-top: 14px; }
.so-block h3 { margin: 0 0 8px; }
.so-note { color: var(--color-ink-2, #6b7280); line-height: 1.6; margin: 0 0 8px; }
.so-sub { font-weight: 600; margin: 8px 0 4px; }
.so-changelog { margin: 0; padding-left: 20px; line-height: 1.7; }
.so-sample { border: 1px solid var(--color-field-border, #c8ced4); border-radius: 12px; padding: 12px; margin-bottom: 12px; }
.so-sample-topic { font-weight: 600; margin: 0 0 8px; }
.so-sample-cols { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; }
.so-col { background: var(--color-field, #fff); border: 1px solid var(--color-field-border, #c8ced4); border-radius: 10px; padding: 8px 10px; }
.so-col--real { background: var(--color-paper-3, #f7f8fa); }
.so-col-head { font-size: 0.8rem; font-weight: 700; color: var(--color-ink-2, #6b7280); margin-bottom: 4px; display: flex; justify-content: space-between; }
.so-col-head span { color: var(--color-accent, #2563eb); }
.so-col p { margin: 0; font-size: 0.85rem; line-height: 1.6; white-space: pre-wrap; max-height: 220px; overflow-y: auto; }
@media (max-width: 720px) {
  .so-sample-cols { grid-template-columns: 1fr; }
}
</style>
