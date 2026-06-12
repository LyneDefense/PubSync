<script setup lang="ts">
// 任务执行日志横幅：展示当前后台任务的实时进度与最近事件。
// 状态与方法来自 useWorkspaceStore 单例；本组件仅负责该面板的视图与交互。
import {
  compactTaskMessage,
  eventPayloadSummary,
  formatDate,
  hasTaskEvents,
  isVisibleTaskRunning,
  latestTaskEvent,
  showTaskEventDetails,
  taskSummaryMessage,
  taskSummaryPayload,
  taskSummaryStatus,
  taskSummaryStep,
  visibleTaskEvents
} from '../composables/useWorkspaceStore'
</script>

<template>
      <section v-if="hasTaskEvents" class="panel task-events" aria-label="任务执行日志">
        <div class="section-header">
          <div>
            <h2>流程执行进度</h2>
          </div>
          <button type="button" class="ghost" @click="showTaskEventDetails = !showTaskEventDetails">
            {{ showTaskEventDetails ? '收起详细日志' : `展开详细日志（${visibleTaskEvents.length}）` }}
          </button>
        </div>
        <div class="task-summary" :class="`event-${taskSummaryStatus}`" aria-live="polite">
          <span>{{ taskSummaryStep }}</span>
          <strong>{{ taskSummaryMessage }}</strong>
          <small v-if="taskSummaryPayload">{{ taskSummaryPayload }}</small>
          <time>{{ latestTaskEvent ? formatDate(latestTaskEvent.created_at) : '同步中' }}</time>
          <strong v-if="isVisibleTaskRunning" class="live-tail" aria-label="流程仍在执行">
            <i aria-hidden="true"></i>
            <i aria-hidden="true"></i>
            <i aria-hidden="true"></i>
            <b aria-hidden="true"></b>
          </strong>
        </div>
        <ol v-if="showTaskEventDetails">
          <li v-for="event in visibleTaskEvents" :key="event.id" :class="`event-${event.status}`">
            <span>{{ event.step_name }}</span>
            <strong>{{ compactTaskMessage(event) }}</strong>
            <small v-if="eventPayloadSummary(event)">{{ eventPayloadSummary(event) }}</small>
            <time>{{ formatDate(event.created_at) }}</time>
          </li>
        </ol>
      </section>
</template>
