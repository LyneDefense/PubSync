<script setup lang="ts">
// 效果看板:A 层工作台总览(租户级,总能看)+ B 层账号成果(按「我的账号」切换;没绑账号给引导)。
// 涨粉只呈现相关性(曲线 + 使用事件打点 + 活跃/沉默对比),不宣称因果。详见 docs/效果看板_方案设计.md。
import { computed, onMounted, watch } from 'vue'
import {
  currentSocialPlatformName,
  currentSocialTab,
  dashboardAccount,
  dashboardAccountId,
  dashboardGrowth,
  dashboardLoading,
  dashboardOverview,
  dashboardRange,
  isSocialPlatform,
  loadDashboard,
  myAccountsOnPlatform,
  selectDashboardAccount,
  setDashboardRange
} from '../composables/useWorkspaceStore'

const active = computed(() => isSocialPlatform.value && currentSocialTab.value === 'effects')

onMounted(() => {
  if (active.value) loadDashboard()
})
watch(active, (on) => {
  if (on) loadDashboard()
})

const RANGES: Array<{ key: '7d' | '30d' | 'all'; label: string }> = [
  { key: '7d', label: '近7天' },
  { key: '30d', label: '近30天' },
  { key: 'all', label: '全部' }
]

function fmtDuration(seconds: number): string {
  if (!seconds) return '—'
  const s = Math.round(seconds)
  if (s < 60) return `${s}秒`
  const m = Math.floor(s / 60)
  const rest = s % 60
  return rest ? `${m}分${rest}秒` : `${m}分`
}

function fmtSavedHours(minutes: number): string {
  if (!minutes) return '0'
  const h = minutes / 60
  return h >= 1 ? h.toFixed(1) : (minutes + ' 分钟')
}

// 结论式总结条
const summary = computed(() => {
  const o = dashboardOverview.value
  if (!o) return ''
  const parts: string[] = []
  const trend = o.similarity_trend
  if (trend.length) {
    const first = trend[0]
    const last = trend[trend.length - 1]
    parts.push(`相似度 ${Math.round(first.before)}→${Math.round(last.after)}（趋近天花板 ${Math.round(last.gap_closed)}%）`)
  }
  if (o.creation.created) parts.push(`本期创作 ${o.creation.created} 篇、发布 ${o.creation.published} 篇`)
  if (o.saved_minutes) parts.push(`约省 ${fmtSavedHours(o.saved_minutes)} 小时`)
  return parts.join(' · ')
})

// 涨粉曲线点 → SVG polyline(粉丝数)
const growthPath = computed(() => {
  const pts = dashboardGrowth.value?.points || []
  if (pts.length < 2) return null
  const xs = pts.map((_, i) => i)
  const ys = pts.map((p) => p.follower_count)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const spanY = maxY - minY || 1
  const W = 560
  const H = 160
  const pad = 8
  const coords = pts.map((p, i) => {
    const x = pad + (xs[i] / (pts.length - 1)) * (W - 2 * pad)
    const y = H - pad - ((p.follower_count - minY) / spanY) * (H - 2 * pad)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })
  return { points: coords.join(' '), W, H, minY, maxY, first: pts[0], last: pts[pts.length - 1] }
})

const modalityEntries = computed(() => {
  const m = dashboardAccount.value?.content.by_modality || {}
  const label: Record<string, string> = { talking_video: '口播视频', image_text: '图文' }
  return Object.entries(m).map(([k, v]) => ({ label: label[k] || k, value: v }))
})
</script>

<template>
  <section v-if="active" class="panel dash">
    <div class="section-header">
      <div>
        <h2>效果看板</h2>
        <p class="toolbar-subtitle">用了 PubSync 帮到了什么——工作台总览 + 分账号成果。</p>
      </div>
      <div class="dash-range">
        <button v-for="r in RANGES" :key="r.key" type="button" :class="{ active: dashboardRange === r.key }" @click="setDashboardRange(r.key)">{{ r.label }}</button>
      </div>
    </div>

    <p v-if="summary" class="dash-summary">{{ summary }}</p>

    <p v-if="dashboardLoading && !dashboardOverview" class="empty-region">加载中…</p>

    <template v-if="dashboardOverview">
      <!-- A 层:工作台总览 -->
      <h3 class="dash-h3">工作台总览</h3>
      <div class="dash-cards">
        <div v-for="a in dashboardOverview.activities" :key="a.key" class="dash-card">
          <span class="dash-card-val">{{ a.count }}</span>
          <span class="dash-card-label">{{ a.label }}次数</span>
          <small>平均耗时 {{ fmtDuration(a.avg_seconds) }}</small>
        </div>
        <div class="dash-card">
          <span class="dash-card-val">{{ dashboardOverview.creation.created }}</span>
          <span class="dash-card-label">AI 创作</span>
          <small>已发布 {{ dashboardOverview.creation.published }} · 转化 {{ Math.round(dashboardOverview.creation.conversion * 100) }}%</small>
        </div>
        <div class="dash-card dash-card--accent">
          <span class="dash-card-val">{{ fmtSavedHours(dashboardOverview.saved_minutes) }}</span>
          <span class="dash-card-label">约省（小时）</span>
          <small>按创作/蒸馏估算</small>
        </div>
        <div class="dash-card">
          <span class="dash-card-val">{{ dashboardOverview.library.benchmark_count }}</span>
          <span class="dash-card-label">对标博主</span>
          <small>{{ dashboardOverview.library.post_count }} 篇真笔记</small>
        </div>
      </div>

      <!-- 相似度趋近 -->
      <div v-if="dashboardOverview.similarity_trend.length" class="dash-block">
        <h3 class="dash-h3">相似度趋近（Skill 越练越像）</h3>
        <ul class="dash-sim">
          <li v-for="(s, i) in dashboardOverview.similarity_trend" :key="i">
            <span class="dash-sim-date">{{ s.date }}</span>
            <span class="dash-sim-bar">
              <span class="dash-sim-fill" :style="{ width: Math.min(100, Math.round(s.gap_closed)) + '%' }"></span>
            </span>
            <span class="dash-sim-val">{{ Math.round(s.before) }}→{{ Math.round(s.after) }}（趋近 {{ Math.round(s.gap_closed) }}%）</span>
          </li>
        </ul>
        <p class="field-hint">趋近 = 与真笔记天花板的接近程度;越高越像本人。</p>
      </div>

      <!-- B 层:账号成果 -->
      <h3 class="dash-h3">账号成果</h3>
      <!-- 没绑账号:引导,不显示空图 -->
      <div v-if="!myAccountsOnPlatform.length" class="dash-empty">
        <p>你还没有添加自己的{{ currentSocialPlatformName }}账号。</p>
        <p class="field-hint">到「我的账号」添加后，这里会显示涨粉趋势、发布转化、分账号省时等成果。</p>
      </div>
      <template v-else>
        <div class="dash-acc-switch">
          <button
            v-for="a in myAccountsOnPlatform"
            :key="a.id"
            type="button"
            :class="{ active: dashboardAccountId === a.id }"
            @click="selectDashboardAccount(a.id)"
          >{{ a.display_name }}</button>
        </div>

        <template v-if="dashboardAccount">
          <div class="dash-cards">
            <div class="dash-card">
              <span class="dash-card-val">{{ dashboardAccount.account.follower_count }}</span>
              <span class="dash-card-label">当前粉丝</span>
            </div>
            <div class="dash-card">
              <span class="dash-card-val">{{ dashboardAccount.creation.created }}</span>
              <span class="dash-card-label">为该账号创作</span>
              <small>已发布 {{ dashboardAccount.creation.published }} · 转化 {{ Math.round(dashboardAccount.creation.conversion * 100) }}%</small>
            </div>
            <div class="dash-card dash-card--accent">
              <span class="dash-card-val">{{ fmtSavedHours(dashboardAccount.saved_minutes) }}</span>
              <span class="dash-card-label">约省（小时）</span>
            </div>
            <div class="dash-card">
              <span class="dash-card-val">{{ Math.round(dashboardAccount.content.viral_rate * 100) }}%</span>
              <span class="dash-card-label">爆款率</span>
              <small>{{ dashboardAccount.content.viral_count }}/{{ dashboardAccount.content.post_count }} 篇 · 均互动 {{ dashboardAccount.content.avg_interactions }}</small>
            </div>
          </div>

          <div v-if="modalityEntries.length" class="dash-modality">
            <span v-for="m in modalityEntries" :key="m.label">{{ m.label }} 篇均互动 {{ m.value }}</span>
          </div>

          <!-- 涨粉曲线 -->
          <div class="dash-block">
            <h3 class="dash-h3">涨粉趋势</h3>
            <div v-if="growthPath">
              <svg :viewBox="`0 0 ${growthPath.W} ${growthPath.H}`" class="dash-chart" preserveAspectRatio="none">
                <polyline :points="growthPath.points" fill="none" stroke="var(--color-accent, #2563eb)" stroke-width="2" />
              </svg>
              <div class="dash-chart-axis">
                <span>{{ growthPath.first.date }} · {{ growthPath.first.follower_count }} 粉</span>
                <span>{{ growthPath.last.date }} · {{ growthPath.last.follower_count }} 粉</span>
              </div>
            </div>
            <p v-else class="field-hint">还在积累数据点（每天拍一次快照），持续使用后曲线会更完整。</p>

            <!-- 活跃 vs 沉默 -->
            <div v-if="dashboardGrowth && (dashboardGrowth.comparison.active_avg_daily !== null || dashboardGrowth.comparison.silent_avg_daily !== null)" class="dash-compare">
              <span>有使用 PubSync 的周：日均涨粉 <strong>{{ dashboardGrowth.comparison.active_avg_daily ?? '—' }}</strong></span>
              <span>没使用的周：日均涨粉 <strong>{{ dashboardGrowth.comparison.silent_avg_daily ?? '—' }}</strong></span>
            </div>
            <p v-if="dashboardGrowth" class="field-hint dash-disclaimer">{{ dashboardGrowth.disclaimer }}</p>
          </div>
        </template>
      </template>
    </template>
  </section>
</template>

<style scoped>
.dash { max-width: 1000px; }
.dash-range { display: flex; gap: 6px; }
.dash-range button { padding: 4px 12px; border: 1px solid var(--color-field-border, #c8ced4); border-radius: 999px; background: var(--color-field, #fff); cursor: pointer; font-size: 0.85rem; }
.dash-range button.active { background: var(--color-accent, #2563eb); color: #fff; border-color: var(--color-accent, #2563eb); }
.dash-summary { background: #eef4ff; color: #1e40af; padding: 10px 14px; border-radius: 10px; font-weight: 600; margin: 4px 0 12px; }
.dash-h3 { margin: 20px 0 10px; font-size: 1rem; }
.dash-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
.dash-card { display: flex; flex-direction: column; gap: 2px; padding: 12px 14px; border: 1px solid var(--color-field-border, #c8ced4); border-radius: 12px; background: var(--color-field, #fff); }
.dash-card--accent { background: #e8f5ec; border-color: #b6e0c4; }
.dash-card-val { font-size: 1.6rem; font-weight: 700; }
.dash-card-label { font-size: 0.8rem; color: var(--color-ink-2, #6b7280); }
.dash-card small { color: var(--color-ink-3, #9aa0a6); font-size: 0.72rem; }
.dash-block { border-top: 1px solid var(--color-field-border, #e3e7ec); padding-top: 12px; margin-top: 16px; }
.dash-sim { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.dash-sim li { display: flex; align-items: center; gap: 10px; font-size: 0.85rem; }
.dash-sim-date { width: 84px; color: var(--color-ink-2, #6b7280); }
.dash-sim-bar { flex: 1; height: 10px; background: var(--color-paper-3, #eef0f3); border-radius: 999px; overflow: hidden; }
.dash-sim-fill { display: block; height: 100%; background: var(--color-accent, #2563eb); }
.dash-sim-val { width: 200px; text-align: right; color: var(--color-ink-2, #6b7280); }
.dash-empty { padding: 20px; border: 1px dashed var(--color-field-border, #c8ced4); border-radius: 12px; text-align: center; }
.dash-acc-switch { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
.dash-acc-switch button { padding: 5px 14px; border: 1px solid var(--color-field-border, #c8ced4); border-radius: 999px; background: var(--color-field, #fff); cursor: pointer; }
.dash-acc-switch button.active { background: var(--color-accent, #2563eb); color: #fff; border-color: var(--color-accent, #2563eb); }
.dash-modality { display: flex; gap: 16px; font-size: 0.85rem; color: var(--color-ink-2, #6b7280); margin: 8px 0; }
.dash-chart { width: 100%; height: 160px; }
.dash-chart-axis { display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--color-ink-3, #9aa0a6); }
.dash-compare { display: flex; gap: 24px; margin-top: 12px; font-size: 0.9rem; }
.dash-disclaimer { margin-top: 8px; font-style: italic; }
</style>
