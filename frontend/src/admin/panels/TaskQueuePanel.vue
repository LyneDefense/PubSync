<script setup lang="ts">
// 任务队列管理:跨租户列任务、筛选、看事件时间线、取消、重试,以及队列健康。
import { onMounted, ref } from 'vue'
import StatusChip from '../../components/StatusChip.vue'
import {
  cancelAdminTask,
  getAdminQueueHealth,
  getAdminTaskEvents,
  listAdminTasks,
  retryAdminTask
} from '../../api'
import type { AdminTask, OperationTaskEvent, QueueHealth } from '../../api/types'

const tasks = ref<AdminTask[]>([])
const health = ref<QueueHealth | null>(null)
const statusFilter = ref('')
const typeFilter = ref('')
const expandedId = ref('')
const events = ref<OperationTaskEvent[]>([])
const message = ref('')
const error = ref('')
const busy = ref(false)

const STATUSES = ['', 'queued', 'running', 'succeeded', 'failed', 'cancelled', 'cancel_requested']

async function reload() {
  busy.value = true
  error.value = ''
  try {
    ;[tasks.value, health.value] = await Promise.all([
      listAdminTasks({ status: statusFilter.value || undefined, task_type: typeFilter.value || undefined, limit: 100 }),
      getAdminQueueHealth()
    ])
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}

onMounted(reload)

function formatDate(value: string) {
  return new Date(value).toLocaleString('zh-CN')
}

async function toggleEvents(task: AdminTask) {
  if (expandedId.value === task.id) {
    expandedId.value = ''
    return
  }
  expandedId.value = task.id
  events.value = []
  try {
    events.value = await getAdminTaskEvents(task.id)
  } catch (e) {
    error.value = (e as Error).message
  }
}

async function run(label: string, fn: () => Promise<unknown>) {
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    await fn()
    await reload()
    message.value = label
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="panel">
    <div class="section-header">
      <div>
        <h2>任务队列</h2>
        <p class="toolbar-subtitle">跨工作空间查看后台任务、追踪步骤事件,并对卡住/失败的任务做取消或重试。</p>
      </div>
      <button type="button" :disabled="busy" @click="reload">刷新</button>
    </div>

    <div class="queue-health" :class="{ 'queue-health--off': !health?.use_task_queue }">
      <template v-if="health">
        <strong>{{ health.use_task_queue ? `持久化队列：${health.queue_name}` : '进程内执行（未启用持久化队列）' }}</strong>
        <span v-if="health.use_task_queue && health.queued != null">排队 {{ health.queued }} · 失败 {{ health.failed }}</span>
        <span v-if="health.note">{{ health.note }}</span>
      </template>
    </div>

    <div class="queue-filters">
      <label>状态
        <select v-model="statusFilter" @change="reload">
          <option v-for="s in STATUSES" :key="s" :value="s">{{ s || '全部' }}</option>
        </select>
      </label>
      <label>类型<input v-model="typeFilter" type="text" placeholder="如 news_fetch" @keyup.enter="reload" /></label>
    </div>

    <p v-if="message" class="admin-flash admin-flash--ok">{{ message }}</p>
    <p v-if="error" class="admin-flash admin-flash--err">{{ error }}</p>

    <div class="queue-list">
      <p v-if="!tasks.length" class="empty-region">没有匹配的任务。</p>
      <div v-for="task in tasks" :key="task.id" class="queue-item">
        <div class="queue-item__row">
          <div class="queue-item__main">
            <StatusChip :status="task.status" />
            <strong>{{ task.task_type }}</strong>
            <small>#{{ task.tenant_id }} · {{ formatDate(task.created_at) }}</small>
            <span class="queue-item__msg">{{ task.message }}</span>
          </div>
          <div class="queue-item__actions">
            <button type="button" @click="toggleEvents(task)">{{ expandedId === task.id ? '收起' : '事件' }}</button>
            <button
              type="button"
              :disabled="busy || ['succeeded', 'failed', 'cancelled'].includes(task.status)"
              @click="run('已请求取消', () => cancelAdminTask(task.id))"
            >
              取消
            </button>
            <button type="button" :disabled="busy" @click="run('已重新入队', () => retryAdminTask(task.id))">重试</button>
          </div>
        </div>
        <p v-if="task.error_message" class="queue-item__err">{{ task.error_message }}</p>
        <div v-if="expandedId === task.id" class="queue-events">
          <p v-if="!events.length" class="empty-region">暂无事件。</p>
          <div v-for="ev in events" :key="ev.id" class="queue-event">
            <StatusChip :status="ev.status" />
            <strong>{{ ev.step_name }}</strong>
            <span>{{ ev.message }}</span>
            <small>{{ formatDate(ev.created_at) }}</small>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.queue-health {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: baseline;
  border: var(--rule-hair);
  border-radius: var(--radius-md, 8px);
  padding: 8px 12px;
  margin: var(--space-sm, 12px) 0;
}
.queue-health--off { color: var(--color-ink-2, inherit); }
.queue-filters {
  display: flex;
  gap: 16px;
  align-items: flex-end;
  flex-wrap: wrap;
}
.queue-filters label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: var(--text-sm);
}
.queue-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: var(--space-sm, 12px);
}
.queue-item {
  border: var(--rule-hair);
  border-radius: var(--radius-md, 8px);
  padding: 8px 12px;
}
.queue-item__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.queue-item__main {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  min-width: 0;
}
.queue-item__msg {
  color: var(--color-ink-2, inherit);
  font-size: var(--text-sm);
}
.queue-item__actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}
.queue-item__err {
  color: var(--color-danger, #b91c1c);
  font-size: var(--text-sm);
  margin: 6px 0 0;
}
.queue-events {
  margin-top: 8px;
  border-top: var(--rule-hair);
  padding-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.queue-event {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: var(--text-sm);
}
.queue-event small { color: var(--color-ink-2, inherit); }
.admin-flash {
  padding: 8px 12px;
  border-radius: var(--radius-md, 8px);
  margin: 8px 0;
}
.admin-flash--ok { background: var(--color-success-bg, #ecfdf5); }
.admin-flash--err { background: var(--color-danger-bg, #fef2f2); }
</style>
