<script setup lang="ts">
// 全站统一的「实时进度」面板:展示当前正在执行任务的真实事件时间线。
// 在 App.vue 的 workspace 顶部渲染一份,按当前平台/动作自动显隐(isVisibleTaskRunning)。
import { ref, watch, nextTick } from 'vue'
import {
  isVisibleTaskRunning,
  liveHeadline,
  liveStageMessage,
  liveTimeline,
  pendingAction,
  taskCountProgress,
  taskElapsedLabel,
  handleCancelDistillation
} from '../composables/useWorkspaceStore'

// 任务一开始就把进度面板滚动到可见处。手机上动作按钮在页面下方,面板在顶部,
// 不滚动的话用户点完按钮根本看不到进度(block:center 避开吸顶的顶栏遮挡)。
const root = ref<HTMLElement | null>(null)
watch(
  isVisibleTaskRunning,
  (running) => {
    if (running) {
      nextTick(() => root.value?.scrollIntoView({ behavior: 'smooth', block: 'center' }))
    }
  },
  { immediate: true }
)
</script>

<template>
  <section v-if="isVisibleTaskRunning" ref="root" class="live-progress" role="status" aria-live="polite">
    <header class="live-progress__head">
      <span class="live-progress__spinner" aria-hidden="true"></span>
      <div class="live-progress__headline">
        <strong>{{ liveHeadline }}</strong>
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
