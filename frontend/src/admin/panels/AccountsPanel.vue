<script setup lang="ts">
// 账号与工作空间:创建账号+工作空间、启停账号、重置密码、查看工作空间列表。
import { onMounted, reactive, ref } from 'vue'
import StatusChip from '../../components/StatusChip.vue'
import {
  createAdminUser,
  disableAdminUser,
  enableAdminUser,
  listAdminTenants,
  listAdminUsers,
  resetAdminUserPassword
} from '../../api'
import type { AdminTenant, AdminUser, AdminUserCreate } from '../../api/types'

const users = ref<AdminUser[]>([])
const tenants = ref<AdminTenant[]>([])
const message = ref('')
const error = ref('')
const busy = ref(false)

const form = reactive<AdminUserCreate>({
  username: '',
  password: '',
  tenant_name: '',
  tenant_slug: '',
  is_admin: false
})

async function reload() {
  try {
    ;[users.value, tenants.value] = await Promise.all([listAdminUsers(), listAdminTenants()])
  } catch (e) {
    error.value = (e as Error).message
  }
}

onMounted(reload)

function formatDate(value: string) {
  return new Date(value).toLocaleString('zh-CN')
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

function onCreate() {
  if (!form.username || !form.password || !form.tenant_name) {
    error.value = '请填写账号、密码和工作空间名'
    return
  }
  run('账号已创建', async () => {
    await createAdminUser({ ...form })
    form.username = ''
    form.password = ''
    form.tenant_name = ''
    form.tenant_slug = ''
    form.is_admin = false
  })
}

function onToggle(user: AdminUser) {
  if (user.status === 'active') run('账号已停用', () => disableAdminUser(user.id))
  else run('账号已启用', () => enableAdminUser(user.id))
}

function onReset(user: AdminUser) {
  const pwd = window.prompt(`为 ${user.username} 设置新密码（至少 6 位）`)
  if (!pwd) return
  if (pwd.length < 6) {
    error.value = '密码至少 6 位'
    return
  }
  run('密码已重置', () => resetAdminUserPassword(user.id, pwd))
}
</script>

<template>
  <section class="panel">
    <div class="section-header">
      <div>
        <h2>账号与工作空间</h2>
        <p class="toolbar-subtitle">创建账号会同时建一个工作空间;普通账号登录后只进入自己的工作空间。</p>
      </div>
      <button type="button" @click="reload">刷新</button>
    </div>

    <p v-if="message" class="admin-flash admin-flash--ok">{{ message }}</p>
    <p v-if="error" class="admin-flash admin-flash--err">{{ error }}</p>

    <div class="accounts-grid">
      <form class="accounts-form" @submit.prevent="onCreate">
        <h3>创建账号</h3>
        <label>账号<input v-model="form.username" type="text" :disabled="busy" /></label>
        <label>初始密码<input v-model="form.password" type="text" :disabled="busy" /></label>
        <label>工作空间名<input v-model="form.tenant_name" type="text" :disabled="busy" /></label>
        <label>工作空间标识(可选)<input v-model="form.tenant_slug" type="text" :disabled="busy" placeholder="留空自动生成" /></label>
        <label class="accounts-form__check"><input v-model="form.is_admin" type="checkbox" :disabled="busy" /> 设为管理员</label>
        <button type="submit" class="primary" :disabled="busy">创建账号</button>
      </form>

      <div class="accounts-list">
        <h3>账号列表（{{ users.length }}）</h3>
        <div v-for="user in users" :key="user.id" class="accounts-item">
          <div>
            <strong>{{ user.username }}</strong>
            <span v-if="user.is_admin" class="status-chip status-chip--info">管理员</span>
            <StatusChip :status="user.status" />
            <small>工作空间 #{{ user.tenant_id ?? '-' }} · {{ formatDate(user.created_at) }}</small>
          </div>
          <div class="accounts-actions">
            <button type="button" :disabled="busy" @click="onToggle(user)">
              {{ user.status === 'active' ? '停用' : '启用' }}
            </button>
            <button type="button" :disabled="busy" @click="onReset(user)">重置密码</button>
          </div>
        </div>

        <h3 class="accounts-tenants-title">工作空间（{{ tenants.length }}）</h3>
        <div v-for="tenant in tenants" :key="tenant.id" class="accounts-item">
          <div>
            <strong>{{ tenant.name }}</strong>
            <code>{{ tenant.slug }}</code>
            <StatusChip :status="tenant.status" />
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.accounts-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr);
  gap: var(--space-lg, 24px);
  align-items: start;
  margin-top: var(--space-md, 16px);
}
.accounts-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.accounts-form label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: var(--text-sm);
}
.accounts-form__check {
  flex-direction: row;
  align-items: center;
  gap: 8px;
}
.accounts-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.accounts-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border: var(--rule-hair);
  border-radius: var(--radius-md, 8px);
  padding: 8px 12px;
}
.accounts-item code {
  font-size: var(--text-xs, 12px);
  color: var(--color-ink-2, inherit);
  margin: 0 6px;
}
.accounts-item small {
  display: block;
  color: var(--color-ink-2, inherit);
  margin-top: 2px;
}
.accounts-actions {
  display: flex;
  gap: 6px;
}
.accounts-tenants-title {
  margin-top: var(--space-md, 16px);
}
.admin-flash {
  padding: 8px 12px;
  border-radius: var(--radius-md, 8px);
  margin: 8px 0;
}
.admin-flash--ok { background: var(--color-success-bg, #ecfdf5); }
.admin-flash--err { background: var(--color-danger-bg, #fef2f2); }
@media (max-width: 900px) {
  .accounts-grid { grid-template-columns: 1fr; }
}
</style>
