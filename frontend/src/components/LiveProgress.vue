<script setup lang="ts">
// 全站统一的「实时进度」面板:展示当前正在执行任务的真实事件时间线。
// 在 App.vue 的 workspace 顶部渲染一份,按当前平台/动作自动显隐(isVisibleTaskRunning)。
import {
  isVisibleTaskRunning,
  liveStage,
  liveStageMessage,
  liveTimeline,
  pendingAction,
  runningTaskName,
  taskCountProgress,
  taskElapsedLabel,
  handleCancelDistillation
} from '../composables/useWorkspaceStore'
</script>

<template>
  <section v-if="isVisibleTaskRunning" class="live-progress" role="status" aria-live="polite">
    <header class="live-progress__head">
      <span class="live-progress__spinner" aria-hidden="true"></span>
      <div class="live-progress__headline">
        <strong>{{ runningTaskName }} · {{ liveStage }}</strong>
        <p>{{ liveStageMessage }}</p>
      </div>
      <span class="live-progress__elapsed">{{ taskElapsedLabel }}</span>
      <button v-if="pendingAction === 'distill'" type="button" class="ghost live-progress__cancel" @click="handleCancelDistillation">停止</button>
    </header>

    <div v-if="taskCountProgress.total" class="live-progress__count">
      <div class="live-progress__count-head">
        <span>已处理</span><strong>{{ taskCountProgress.current }}/{{ taskCountProgress.total }}</strong>
      </div>
      <div class="live-progress__bar"><i :style="{ width: taskCountProgress.pct + '%' }"></i></div>
    </div>

    <ol v-if="liveTimeline.length" class="live-progress__timeline">
      <li v-for="item in liveTimeline" :key="item.id" :class="`is-${item.status}`">
        <span class="live-progress__step">{{ item.step }}</span>
        <span class="live-progress__msg">{{ item.message }}</span>
        <span class="live-progress__time">{{ item.time }}</span>
      </li>
    </ol>
    <p v-else class="live-progress__pending">任务已提交，正在等待第一条进度…</p>
  </section>
</template>
