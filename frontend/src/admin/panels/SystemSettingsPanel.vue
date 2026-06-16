<script setup lang="ts">
// 系统设置:通用 AppSetting 键值编辑(含 compliance_extra_words 限流词扩展)。
import { onMounted, reactive, ref } from 'vue'
import { listAppSettings, upsertAppSetting } from '../../api'
import type { AppSettingRead } from '../../api/types'

const settings = ref<AppSettingRead[]>([])
const drafts = reactive<Record<string, string>>({})
const newKey = ref('')
const newValue = ref('')
const message = ref('')
const error = ref('')
const busy = ref(false)

async function reload() {
  try {
    settings.value = await listAppSettings()
    for (const s of settings.value) drafts[s.key] = s.value
  } catch (e) {
    error.value = (e as Error).message
  }
}

onMounted(reload)

async function save(key: string, value: string) {
  if (!key.trim()) {
    error.value = '请填写配置键'
    return
  }
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    await upsertAppSetting(key, value)
    await reload()
    message.value = `已保存：${key}`
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}

function onCreate() {
  save(newKey.value.trim(), newValue.value).then(() => {
    newKey.value = ''
    newValue.value = ''
  })
}

function presetCompliance() {
  newKey.value = 'compliance_extra_words'
  if (!newValue.value) newValue.value = '["示例词1", "示例词2"]'
}
</script>

<template>
  <section class="panel">
    <div class="section-header">
      <div>
        <h2>系统设置</h2>
        <p class="toolbar-subtitle">通用键值配置。限流词扩展请用键 <code>compliance_extra_words</code>(JSON 数组)。</p>
      </div>
      <button type="button" @click="reload">刷新</button>
    </div>

    <p v-if="message" class="admin-flash admin-flash--ok">{{ message }}</p>
    <p v-if="error" class="admin-flash admin-flash--err">{{ error }}</p>

    <div class="set-create">
      <h3>新增 / 覆盖</h3>
      <div class="set-create__row">
        <input v-model="newKey" type="text" placeholder="配置键，如 compliance_extra_words" />
        <button type="button" @click="presetCompliance">填入限流词模板</button>
      </div>
      <textarea v-model="newValue" rows="3" placeholder="配置值（可为 JSON）"></textarea>
      <button type="button" class="primary" :disabled="busy" @click="onCreate">保存</button>
    </div>

    <h3 class="set-list-title">现有配置（{{ settings.length }}）</h3>
    <p v-if="!settings.length" class="empty-region">还没有任何系统设置。</p>
    <div v-for="s in settings" :key="s.key" class="set-item">
      <div class="set-item__head">
        <code>{{ s.key }}</code>
        <button type="button" class="primary" :disabled="busy" @click="save(s.key, drafts[s.key])">保存</button>
      </div>
      <textarea v-model="drafts[s.key]" rows="2"></textarea>
    </div>
  </section>
</template>

<style scoped>
.set-create {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: var(--space-md, 16px);
}
.set-create__row {
  display: flex;
  gap: 8px;
}
.set-create__row input { flex: 1; }
.set-list-title { margin-top: var(--space-lg, 24px); }
.set-item {
  border: var(--rule-hair);
  border-radius: var(--radius-md, 8px);
  padding: 8px 12px;
  margin-bottom: 8px;
}
.set-item__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
textarea { width: 100%; resize: vertical; }
.admin-flash {
  padding: 8px 12px;
  border-radius: var(--radius-md, 8px);
  margin: 8px 0;
}
.admin-flash--ok { background: var(--color-success-bg, #ecfdf5); }
.admin-flash--err { background: var(--color-danger-bg, #fef2f2); }
</style>
