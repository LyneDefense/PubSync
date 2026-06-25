<script setup lang="ts">
// 任务在跑、但用户已切到别的页面时,顶部显示的一条迷你进度条:
// 「xx 任务进行中 · 当前步骤」+「查看」。点查看跳回发起任务的那个页签,展开完整进度。
import { useRouter } from 'vue-router'
import {
  isMiniTaskRunning,
  miniTaskStep,
  runningTaskName,
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
</script>

<template>
  <button v-if="isMiniTaskRunning" type="button" class="mini-progress" @click="goToTaskHome">
    <span class="mini-progress__spinner" aria-hidden="true"></span>
    <span class="mini-progress__text">
      <strong>{{ runningTaskName }}进行中</strong>
      <span class="mini-progress__step">· {{ miniTaskStep }}</span>
    </span>
    <span class="mini-progress__elapsed">{{ taskElapsedLabel }}</span>
    <span class="mini-progress__cta">查看 →</span>
  </button>
</template>

<style scoped>
.mini-progress {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  margin-bottom: 12px;
  border: 1px solid var(--color-accent, #2563eb);
  border-radius: 10px;
  background: #eef4ff;
  color: #1e40af;
  cursor: pointer;
  text-align: left;
  font-size: 0.88rem;
}
.mini-progress:hover { background: #e0ebff; }
.mini-progress__spinner {
  width: 14px; height: 14px; flex: 0 0 auto;
  border: 2px solid #b9ccf5; border-top-color: var(--color-accent, #2563eb);
  border-radius: 50%; animation: mini-spin 0.8s linear infinite;
}
@keyframes mini-spin { to { transform: rotate(360deg); } }
.mini-progress__text { display: flex; gap: 6px; align-items: baseline; min-width: 0; }
.mini-progress__step { color: #3b5ba5; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mini-progress__elapsed { margin-left: auto; color: #3b5ba5; font-variant-numeric: tabular-nums; }
.mini-progress__cta { flex: 0 0 auto; font-weight: 600; }
</style>
