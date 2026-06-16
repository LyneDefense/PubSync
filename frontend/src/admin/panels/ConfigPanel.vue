<script setup lang="ts">
// 通用运行时配置面板:渲染 /admin/config 的若干分组,逐项编辑/保存/清除。
// 密钥字段只显示「已配置/未配置」,输入新值才会替换,绝不回显明文。
import { computed, onMounted, reactive, ref } from 'vue'
import {
  clearAdminConfig,
  getAdminConfig,
  updateAdminConfig
} from '../../api'
import type { ConfigFieldView, ConfigGroupView, ConfigView } from '../../api/types'

const props = defineProps<{ title: string; subtitle?: string; groupKeys: string[] }>()

const config = ref<ConfigView | null>(null)
const drafts = reactive<Record<string, string>>({})
const busyKey = ref('')
const message = ref('')
const error = ref('')
const loading = ref(true)

const groups = computed<ConfigGroupView[]>(() =>
  (config.value?.groups || []).filter((g) => props.groupKeys.includes(g.key))
)

function seedDrafts(view: ConfigView) {
  for (const group of view.groups) {
    for (const field of group.fields) {
      // 密钥不回显:草稿留空;非密钥用当前生效值预填。
      drafts[field.key] = field.is_secret ? '' : String(field.value ?? '')
    }
  }
}

async function reload() {
  loading.value = true
  try {
    const view = await getAdminConfig()
    config.value = view
    seedDrafts(view)
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

onMounted(reload)

async function save(field: ConfigFieldView) {
  error.value = ''
  message.value = ''
  let value = drafts[field.key] ?? ''
  if (field.type === 'bool') value = value === 'true' ? 'true' : 'false'
  if (field.is_secret && !value.trim()) {
    error.value = `${field.label}:请输入新值再保存`
    return
  }
  busyKey.value = field.key
  try {
    const view = await updateAdminConfig(field.key, value)
    config.value = view
    seedDrafts(view)
    message.value = `已保存：${field.label}`
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busyKey.value = ''
  }
}

async function clear(field: ConfigFieldView) {
  error.value = ''
  message.value = ''
  busyKey.value = field.key
  try {
    const view = await clearAdminConfig(field.key)
    config.value = view
    seedDrafts(view)
    message.value = `已清除（回落 .env）：${field.label}`
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busyKey.value = ''
  }
}

function sourceLabel(field: ConfigFieldView) {
  if (field.source === 'db') return '后台覆盖'
  if (field.source === 'unset') return '未设置'
  return '.env 默认'
}
</script>

<template>
  <section class="panel">
    <div class="section-header">
      <div>
        <h2>{{ title }}</h2>
        <p class="toolbar-subtitle">{{ subtitle || '修改即时生效,无需改 .env 或重启;密钥加密保存、不回显明文。' }}</p>
      </div>
      <button type="button" @click="reload">刷新</button>
    </div>

    <p v-if="message" class="admin-flash admin-flash--ok">{{ message }}</p>
    <p v-if="error" class="admin-flash admin-flash--err">{{ error }}</p>
    <p v-if="loading" class="empty-region">加载中…</p>

    <div v-for="group in groups" :key="group.key" class="config-group">
      <h3>{{ group.label }}</h3>
      <div class="config-rows">
        <div v-for="field in group.fields" :key="field.key" class="config-row">
          <div class="config-row__meta">
            <strong>{{ field.label }}</strong>
            <code>{{ field.key }}</code>
            <span class="config-source" :class="`config-source--${field.source}`">{{ sourceLabel(field) }}</span>
            <span v-if="field.is_secret" class="config-secret">
              {{ field.configured ? '🔒 已配置' : '未配置' }}
            </span>
          </div>
          <div class="config-row__control">
            <select v-if="field.type === 'bool'" v-model="drafts[field.key]">
              <option value="true">开启</option>
              <option value="false">关闭</option>
            </select>
            <input
              v-else-if="field.is_secret"
              v-model="drafts[field.key]"
              type="password"
              autocomplete="off"
              :placeholder="field.configured ? '已配置(留空则不变)' : '输入密钥'"
            />
            <input
              v-else
              v-model="drafts[field.key]"
              :type="field.type === 'int' || field.type === 'float' ? 'number' : 'text'"
            />
            <button type="button" class="primary" :disabled="busyKey === field.key" @click="save(field)">保存</button>
            <button
              v-if="field.source === 'db'"
              type="button"
              :disabled="busyKey === field.key"
              @click="clear(field)"
            >
              清除
            </button>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.config-group {
  margin-top: var(--space-md, 16px);
}
.config-group h3 {
  margin: 0 0 8px;
}
.config-rows {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.config-row {
  border: var(--rule-hair);
  border-radius: var(--radius-md, 8px);
  padding: 10px 12px;
}
.config-row__meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 6px;
}
.config-row__meta code {
  font-size: var(--text-xs, 12px);
  color: var(--color-ink-2, inherit);
}
.config-row__control {
  display: flex;
  gap: 8px;
}
.config-row__control input,
.config-row__control select {
  flex: 1;
  min-width: 0;
}
.config-source {
  font-size: var(--text-xs, 12px);
  padding: 1px 6px;
  border-radius: 999px;
  border: var(--rule-hair);
}
.config-source--db {
  color: var(--color-accent, inherit);
}
.config-secret {
  font-size: var(--text-xs, 12px);
  color: var(--color-ink-2, inherit);
}
.admin-flash {
  padding: 8px 12px;
  border-radius: var(--radius-md, 8px);
  margin: 8px 0;
}
.admin-flash--ok {
  background: var(--color-success-bg, #ecfdf5);
}
.admin-flash--err {
  background: var(--color-danger-bg, #fef2f2);
}
</style>
