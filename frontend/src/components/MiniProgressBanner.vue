<script setup lang="ts">
// 任务在跑、但用户已切到别的页面时,workspace 顶部显示的一条迷你进度条:
// 任务图标 +「{任务}进行中 · 当前步骤」+ 百分比/耗时 +「查看 →」+ 底部细进度条。
// 点「查看」跳回发起任务的那个页签,展开就地的完整进度面板。逻辑沿用 store,不新增状态。
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  isMiniTaskRunning,
  miniTaskStep,
  pendingAction,
  runningTaskName,
  taskCountProgress,
  taskElapsedLabel,
  taskEventsMainTab,
  taskEventsSubTab
} from '../composables/useWorkspaceStore'

const router = useRouter()

function goToTaskHome() {
  const platform = taskEventsMainTab.value
  const tab = taskEventsSubTab.value
  if (!platform || !tab) return
  router.push({ name: 'workspace', params: { platform, tab } })
}

// 任务类型图标(白底圆角小图标,按 pendingAction 一眼识别)。线性 SVG path。
const TASK_ICONS: Record<string, string[]> = {
  collect: ['M12 3v11', 'M8 10l4 4 4-4', 'M5 20h14'],
  fetch: ['M20 11a8 8 0 10-2.3 5.7', 'M20 5v5h-5'],
  distill: ['M4 5h16l-6 7v6l-4-2v-4z'],
  generate: ['M12 3l1.7 4.3L18 9l-4.3 1.7L12 15l-1.7-4.3L6 9l4.3-1.7z'],
  'xhs-topic': ['M12 3a6 6 0 00-3.5 10.9c.3.2.5.6.5 1V16h6v-1.1c0-.4.2-.8.5-1A6 6 0 0012 3z', 'M9.5 20h5'],
  'xhs-package': ['M4 19l11-11', 'M13.5 5.5l3 3', 'M14 21h6'],
  'xhs-package-save': ['M5 4h12l3 3v13H5z', 'M9 4v5h6'],
  audit: ['M3 12h4l2 6 4-15 2 9h6'],
  optimize: ['M12 20V5', 'M6 11l6-6 6 6']
}
const taskPaths = computed(() => TASK_ICONS[pendingAction.value || ''] || ['M12 7v5l3 2', 'M12 3a9 9 0 100 18 9 9 0 000-18z'])
const hasCount = computed(() => taskCountProgress.value.total > 0)
</script>

<template>
  <button v-if="isMiniTaskRunning" type="button" class="mini-progress" @click="goToTaskHome">
    <span class="mp-bar-accent" aria-hidden="true"></span>
    <span class="mp-icon" aria-hidden="true">
      <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path v-for="(d, i) in taskPaths" :key="i" :d="d" />
      </svg>
    </span>
    <span class="mp-text">
      <strong>{{ runningTaskName }}进行中</strong>
      <span class="mp-step">· {{ miniTaskStep }}</span>
    </span>
    <span v-if="hasCount" class="mp-pct">{{ taskCountProgress.pct }}%</span>
    <span class="mp-elapsed">
      <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg>
      {{ taskElapsedLabel }}
    </span>
    <span class="mp-cta">查看 →</span>
    <span class="mp-track" aria-hidden="true">
      <i class="mp-fill" :class="{ 'mp-fill--indet': !hasCount }" :style="hasCount ? { width: taskCountProgress.pct + '%' } : {}"></i>
    </span>
  </button>
</template>

<style scoped>
.mini-progress {
  position: relative;
  width: 100%;
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 10px 16px 13px;
  margin-bottom: 14px;
  border: 1px solid var(--color-accent-soft-bd);
  border-radius: 12px;
  background: var(--color-accent-tint);
  color: var(--color-accent-ink);
  cursor: pointer;
  text-align: left;
  font-size: 13.5px;
  overflow: hidden;
}
.mini-progress:hover {
  background: var(--color-accent-soft);
}
/* 左侧 3px accent 竖条 */
.mp-bar-accent {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--color-accent);
}
.mp-icon {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  flex: 0 0 auto;
  border-radius: 8px;
  background: var(--color-surface);
  color: var(--color-accent);
}
.mp-text {
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
}
.mp-text strong {
  font-weight: 650;
  white-space: nowrap;
}
.mp-step {
  color: var(--color-accent-ink);
  opacity: 0.85;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mp-pct {
  flex: 0 0 auto;
  margin-left: auto;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.mp-elapsed {
  flex: 0 0 auto;
  margin-left: auto; /* 没有百分比时,耗时块自己靠右 */
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--color-ink-3);
  font-variant-numeric: tabular-nums;
}
/* 有百分比时,靠右交给 .mp-pct,耗时只跟一个小间距 */
.mp-pct + .mp-elapsed {
  margin-left: 10px;
}
.mp-cta {
  flex: 0 0 auto;
  height: 28px;
  padding: 0 12px;
  display: inline-flex;
  align-items: center;
  border-radius: 8px;
  background: var(--color-accent);
  color: #fff;
  font-weight: 600;
  font-size: 12.5px;
}
/* 底部细进度条(3px) */
.mp-track {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 3px;
  background: var(--color-accent-soft-bd);
  overflow: hidden;
}
.mp-fill {
  display: block;
  height: 100%;
  background: var(--color-accent);
  transition: width 0.5s var(--ease-out);
}
.mp-fill--indet {
  width: 36%;
  animation: indet 1.1s var(--ease-out) infinite;
}
@keyframes indet {
  0% { margin-left: -36%; }
  100% { margin-left: 100%; }
}
@media (prefers-reduced-motion: reduce) {
  .mp-fill--indet { animation: none; }
}
</style>
