<script setup lang="ts">
// 步骤内的统一进度卡片:任务运行时显示动画 + 实时「思考过程」消息(来自任务事件)。
// 取代原来分散的 inline-progress-card,并替代被移除的全局「流程执行进度」横幅。
// 有实时事件时显示最新的步骤与友好消息;还没有事件时显示传入的 fallback 文案。
import { latestTaskEvent, taskSummaryMessage, taskSummaryStep } from '../composables/useWorkspaceStore'

defineProps<{ active: boolean; title?: string; fallback?: string }>()
</script>

<template>
  <div v-if="active" class="inline-progress-card" aria-live="polite">
    <div>
      <strong>{{ latestTaskEvent ? taskSummaryStep : (title || '处理中') }}</strong>
      <span>{{ latestTaskEvent ? taskSummaryMessage : (fallback || '正在处理，请稍候…') }}</span>
    </div>
    <i aria-hidden="true"></i>
  </div>
</template>
