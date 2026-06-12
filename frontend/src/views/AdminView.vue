<script setup lang="ts">
// 后台·用户与工作空间管理（仅管理员可见）。
// 状态与方法来自 useWorkspaceStore 单例；本组件仅负责该面板的视图与交互。
import StatusChip from '../components/StatusChip.vue'
import {
  activeMainTab,
  adminUserForm,
  adminUsers,
  article,
  form,
  handleCreateAdminUser,
  isAdmin,
  pendingAction
} from '../composables/useWorkspaceStore'
</script>

<template>
      <section v-if="activeMainTab === 'admin' && isAdmin" class="panel">
        <div class="section-header">
          <div>
            <h2>后台管理</h2>
            <p class="toolbar-subtitle">管理员创建账号和工作空间；普通账号登录后只进入自己的工作空间。</p>
          </div>
        </div>
        <div class="distill-grid">
          <form class="distill-card" @submit.prevent="handleCreateAdminUser">
            <h3>创建账号</h3>
            <div class="config-grid">
              <label>
                用户名
                <input v-model="adminUserForm.username" type="text" autocomplete="off" required />
              </label>
              <label>
                初始密码
                <input v-model="adminUserForm.password" type="password" autocomplete="new-password" required />
              </label>
              <label>
                工作空间名称
                <input v-model="adminUserForm.tenant_name" type="text" required />
              </label>
              <label>
                工作空间标识
                <input v-model="adminUserForm.tenant_slug" type="text" placeholder="留空则使用用户名" />
              </label>
            </div>
            <label class="toggle-row">
              <input v-model="adminUserForm.is_admin" type="checkbox" />
              创建为管理员账号
            </label>
            <button type="submit" class="primary" :disabled="Boolean(pendingAction)">
              {{ pendingAction === 'admin-user' ? '创建中' : '创建账号' }}
            </button>
          </form>

          <article class="distill-card">
            <h3>账号列表</h3>
            <div v-if="adminUsers.length" class="admin-user-list">
              <div v-for="user in adminUsers" :key="user.id">
                <strong>{{ user.username }}</strong>
                <span>{{ user.is_admin ? '管理员' : '普通用户' }} · 工作空间 ID {{ user.tenant_id || '未绑定' }} · <StatusChip :status="user.status" /></span>
              </div>
            </div>
            <p v-else class="empty-region">暂无账号。</p>
          </article>
        </div>
      </section>
</template>
