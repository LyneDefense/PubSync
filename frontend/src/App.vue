<script setup lang="ts">
// App.vue 现在只承担「应用外壳」：注册全局状态 store、绑定生命周期、渲染模板。
// 所有业务状态与方法集中在 composables/useWorkspaceStore.ts（单例），模板里直接使用。
import { onMounted, onUnmounted } from 'vue'

import ComingSoonPanel from './components/ComingSoonPanel.vue'
import HashtagCloud from './components/HashtagCloud.vue'
import InlineTaskProgress from './components/InlineTaskProgress.vue'
import ImageOutputGrid from './components/ImageOutputGrid.vue'
import ImagePreviewModal from './components/ImagePreviewModal.vue'
import LoginView from './components/LoginView.vue'
import WechatBriefView from './views/WechatBriefView.vue'
import WechatAiView from './views/WechatAiView.vue'
import WechatDraftsView from './views/WechatDraftsView.vue'
import WechatRecordsView from './views/WechatRecordsView.vue'
import SocialCollectView from './views/SocialCollectView.vue'
import SocialDistillView from './views/SocialDistillView.vue'
import SocialAssetsView from './views/SocialAssetsView.vue'
import SocialAuditView from './views/SocialAuditView.vue'
import SocialPackagesView from './views/SocialPackagesView.vue'
import SocialHistoryView from './views/SocialHistoryView.vue'
import XhsRecordsView from './views/XhsRecordsView.vue'
import DouyinRecordsView from './views/DouyinRecordsView.vue'
import WorkspaceSettingsView from './views/WorkspaceSettingsView.vue'
import { clearAuthToken, clearTenantId } from './api'

// 管理后台是独立入口(自带登录),仅给管理员一个跳转链接。
const adminConsoleUrl = `${import.meta.env.BASE_URL}admin.html`

import {
  activeMainTab,
  activeWechatTab,
  bloggerForm,
  bloggerSearchKeyword,
  bloggerSearchResults,
  closeBloggerModal,
  closeImagePreview,
  currentSocialPlatform,
  currentSocialPlatformName,
  currentSocialTab,
  currentUsername,
  editingBlogger,
  form,
  handleCreateBlogger,
  handleGlobalKeydown,
  handleLogin,
  handleLogout,
  handleSearchBloggerCandidates,
  isAdmin,
  isProgressTaskRunning,
  isAuthenticated,
  isLoggingIn,
  isSocialPlatform,
  loadAll,
  loadTenantOptions,
  loginMessage,
  message,
  pendingAction,
  previewImage,
  profile,
  progressTimers,
  selectBloggerCandidate,
  selectedBloggerCandidate,
  setCurrentSocialTab,
  showBloggerModal,
  showUserMenu,
  toggleUserMenu
} from './composables/useWorkspaceStore'

// 应用挂载：注册 Esc 全局快捷键；已登录则先加载工作空间选项再拉取全部数据，失败则退回登录态。
onMounted(() => {
  window.addEventListener('keydown', handleGlobalKeydown)
  if (isAuthenticated.value) {
    loadTenantOptions()
      .then(loadAll)
      .catch((error) => {
        clearAuthToken()
        clearTenantId()
        isAuthenticated.value = false
        loginMessage.value = error instanceof Error ? error.message : '登录已失效，请重新登录'
      })
  }
})

// 应用卸载：移除快捷键监听并清理所有伪进度定时器。
onUnmounted(() => {
  window.removeEventListener('keydown', handleGlobalKeydown)
  for (const timer of Object.values(progressTimers)) {
    window.clearInterval(timer)
  }
})
</script>

<template>
  <LoginView v-if="!isAuthenticated" :loading="isLoggingIn" :message="loginMessage" @submit="handleLogin" />

  <div v-else class="app-shell">
    <header class="topbar">
      <h1 class="topbar-title">多平台内容自动化</h1>
      <div class="topbar-controls">
        <div class="platform-switch" role="tablist" aria-label="媒体平台">
          <button
            type="button"
            role="tab"
            :aria-selected="activeMainTab === 'wechat'"
            :class="{ active: activeMainTab === 'wechat' }"
            @click="activeMainTab = 'wechat'"
          >
            公众号
          </button>
          <button
            type="button"
            role="tab"
            :aria-selected="activeMainTab === 'xhs'"
            :class="{ active: activeMainTab === 'xhs' }"
            @click="activeMainTab = 'xhs'"
          >
            小红书
          </button>
          <button
            type="button"
            role="tab"
            :aria-selected="activeMainTab === 'douyin'"
            :class="{ active: activeMainTab === 'douyin' }"
            @click="activeMainTab = 'douyin'"
          >
            抖音
          </button>
        </div>
        <a v-if="isAdmin" class="admin-console-link" :href="adminConsoleUrl">管理后台</a>
        <div class="user-menu" @mouseleave="showUserMenu = false">
          <button
            type="button"
            class="user-menu-trigger"
            :aria-expanded="showUserMenu"
            aria-haspopup="menu"
            @click="toggleUserMenu"
          >
            <strong>{{ currentUsername }}</strong>
          </button>
          <div v-if="showUserMenu" class="user-menu-popover" role="menu">
            <button type="button" role="menuitem" @click="handleLogout">退出登录</button>
          </div>
        </div>
      </div>
    </header>

    <div class="app-body">
      <aside class="side-nav" aria-label="功能导航">
        <template v-if="activeMainTab === 'wechat'">
          <button type="button" :class="{ active: activeWechatTab === 'brief' }" @click="activeWechatTab = 'brief'">每日早报</button>
          <button type="button" :class="{ active: activeWechatTab === 'distill' }" @click="activeWechatTab = 'distill'">博主蒸馏</button>
          <button type="button" :class="{ active: activeWechatTab === 'ai' }" @click="activeWechatTab = 'ai'">AI 创作</button>
          <button type="button" :class="{ active: activeWechatTab === 'drafts' }" @click="activeWechatTab = 'drafts'">文章草稿</button>
          <button type="button" :class="{ active: activeWechatTab === 'records' }" @click="activeWechatTab = 'records'">发布记录</button>
          <button type="button" :class="{ active: activeWechatTab === 'settings' }" @click="activeWechatTab = 'settings'">设置</button>
        </template>
        <template v-else-if="isSocialPlatform">
          <p class="side-group">博主蒸馏</p>
          <button type="button" :class="{ active: currentSocialTab === 'collect' }" @click="setCurrentSocialTab('collect')">数据采集</button>
          <button type="button" :class="{ active: currentSocialTab === 'distill' }" @click="setCurrentSocialTab('distill')">蒸馏</button>
          <button type="button" :class="{ active: currentSocialTab === 'assets' }" @click="setCurrentSocialTab('assets')">博主资产</button>
          <button type="button" :class="{ active: currentSocialTab === 'audit' }" @click="setCurrentSocialTab('audit')">账号对标</button>
          <p class="side-group">AI 创作</p>
          <button type="button" :class="{ active: currentSocialTab === 'packages' }" @click="setCurrentSocialTab('packages')">对标博主创作</button>
          <button type="button" :class="{ active: currentSocialTab === 'history' }" @click="setCurrentSocialTab('history')">发布包历史</button>
          <button type="button" :class="{ active: currentSocialTab === 'freecreate' }" @click="setCurrentSocialTab('freecreate')">自由创作</button>
          <hr class="side-sep" />
          <button type="button" :class="{ active: currentSocialTab === 'records' }" @click="setCurrentSocialTab('records')">发布记录</button>
          <button type="button" :class="{ active: currentSocialTab === 'settings' }" @click="setCurrentSocialTab('settings')">设置</button>
        </template>
      </aside>

      <main class="workspace">
      <InlineTaskProgress :active="isProgressTaskRunning" title="流程执行进度" fallback="正在处理，请稍候…" />

      <WechatBriefView />

      <ComingSoonPanel
        v-if="activeMainTab === 'wechat' && activeWechatTab === 'distill'"
        title="公众号博主蒸馏"
        description="未来支持采集公众号文章样本、蒸馏风格资产，再应用风格生成公众号文章。"
      />

      <WechatAiView />

      <WechatDraftsView />

      <WechatRecordsView />

      <SocialCollectView />

      <SocialDistillView />

      <SocialAssetsView />

      <SocialAuditView />

      <SocialPackagesView />

      <SocialHistoryView />

      <ComingSoonPanel
        v-if="isSocialPlatform && currentSocialTab === 'freecreate'"
        :title="`${currentSocialPlatformName}自由创作`"
        description="未来支持不依赖对标博主、直接输入主题由 AI 自主创作内容。"
      />

      <XhsRecordsView />

      <DouyinRecordsView />

      <WorkspaceSettingsView />

      <div v-if="showBloggerModal" class="modal-backdrop" role="presentation" @click.self="closeBloggerModal">
        <form class="modal-panel" role="dialog" aria-modal="true" :aria-label="`${editingBlogger ? '编辑' : '创建'}${currentSocialPlatformName}博主`" @submit.prevent="handleCreateBlogger">
          <div class="section-header">
            <div>
              <h2>{{ editingBlogger ? '编辑博主信息' : '创建博主' }}</h2>
              <p class="toolbar-subtitle">{{ editingBlogger ? '只能编辑基础信息，不会修改已有采集和蒸馏结果。' : '先搜索并选择博主，再补充领域和备注。' }}</p>
            </div>
            <button type="button" class="ghost" @click="closeBloggerModal">关闭</button>
          </div>
          <div v-if="!editingBlogger" class="search-row">
            <label>
              搜索{{ currentSocialPlatformName }}博主
              <input v-model="bloggerSearchKeyword" type="search" placeholder="输入昵称或关键词" @keydown.enter.prevent="handleSearchBloggerCandidates" />
            </label>
            <button type="button" class="primary" :disabled="Boolean(pendingAction)" @click="handleSearchBloggerCandidates">
              {{ pendingAction === 'blogger-search' ? '搜索中' : '搜索' }}
            </button>
          </div>
          <div v-if="!editingBlogger && bloggerSearchResults.length" class="candidate-list" aria-label="博主搜索结果">
            <button
              v-for="candidate in bloggerSearchResults"
              :key="`${candidate.platform}-${candidate.external_id}`"
              type="button"
              :class="{ active: selectedBloggerCandidate?.external_id === candidate.external_id }"
              @click="selectBloggerCandidate(candidate)"
            >
              <img v-if="candidate.avatar_url" :src="candidate.avatar_url" alt="" />
              <span>
                <strong>{{ candidate.display_name }}</strong>
                <small>{{ candidate.description || '暂无简介' }}</small>
              </span>
              <em>{{ candidate.follower_count ? `${candidate.follower_count} 粉丝` : '粉丝未知' }}</em>
            </button>
          </div>
          <p v-else-if="!editingBlogger && bloggerSearchKeyword" class="empty-region">搜索后会在这里展示候选博主。</p>
          <label>
            博主名称
            <input v-model="bloggerForm.display_name" type="text" required :readonly="!editingBlogger" />
          </label>
          <label>
            {{ currentSocialPlatformName }}主页链接
            <input
              v-model="bloggerForm.homepage_url"
              type="url"
              required
              :readonly="!editingBlogger"
              :placeholder="currentSocialPlatform === 'douyin' ? 'https://www.douyin.com/user/...' : 'https://www.xiaohongshu.com/user/profile/...'"
            />
          </label>
          <div v-if="editingBlogger" class="config-grid">
            <label>
              平台 ID
              <input v-model="bloggerForm.external_id" type="text" />
            </label>
            <label>
              头像 URL
              <input v-model="bloggerForm.avatar_url" type="url" />
            </label>
            <label>
              粉丝数
              <input v-model.number="bloggerForm.follower_count" type="number" min="0" />
            </label>
          </div>
          <label>
            领域/赛道
            <input v-model="bloggerForm.niche" type="text" placeholder="宠物、母婴、美妆、AI工具..." />
          </label>
          <label>
            备注
            <textarea v-model="bloggerForm.description" rows="3"></textarea>
          </label>
          <div class="actions">
            <button type="button" @click="closeBloggerModal">取消</button>
            <button type="submit" class="primary" :disabled="Boolean(pendingAction) || !bloggerForm.homepage_url">
              {{ pendingAction === 'blogger' ? '保存中' : editingBlogger ? '保存修改' : '保存博主' }}
            </button>
          </div>
        </form>
      </div>

      <ImagePreviewModal :image="previewImage" @close="closeImagePreview" />
      </main>
    </div>
  </div>
</template>

