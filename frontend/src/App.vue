<script setup lang="ts">
// App.vue 现在只承担「应用外壳」：注册全局状态 store、绑定生命周期、渲染模板。
// 所有业务状态与方法集中在 composables/useWorkspaceStore.ts（单例），模板里直接使用。
import { onMounted, onUnmounted } from 'vue'

import HashtagCloud from './components/HashtagCloud.vue'
import ImageOutputGrid from './components/ImageOutputGrid.vue'
import ImagePreviewModal from './components/ImagePreviewModal.vue'
import LoginView from './components/LoginView.vue'
import { clearAuthToken, clearTenantId } from './api'
import {
  bloggerCommentLabel,
  collectionCostLabel,
  distillationStatusLabel,
  findXhsDraftFromEvents,
  parseEventPayload,
  parseJsonArray,
  parseJsonObject,
  runCostLabel,
  sampledCommentCount,
  wait,
  xhsContentTypeLabel,
  xhsPackageCopyText
} from './utils/format'
import { sanitizeHtml } from './utils/sanitize'
import {
  activeArticleTab,
  activeDouyinTab,
  activeMainTab,
  activeNews,
  activeNewsTab,
  activePlatformLabel,
  activeSettingsTab,
  activeWechatTab,
  activeXhsSkills,
  activeXhsTab,
  addContentGroup,
  adminUserForm,
  adminUsers,
  article,
  articleStateLabel,
  bloggerCollectionRuns,
  bloggerDistillForm,
  bloggerForm,
  bloggerPosts,
  bloggerRuns,
  bloggerSearchKeyword,
  bloggerSearchResults,
  bloggerSkills,
  bloggers,
  canGoNextXhsCollectStep,
  canGoNextXhsCreationStep,
  canGoNextXhsDistillStep,
  canSwitchTenant,
  changeNewsPage,
  closeBloggerModal,
  closeImagePreview,
  collectionDistillationCount,
  compactTaskMessage,
  contentGroupForms,
  contentGroups,
  copyText,
  currentSocialPlatform,
  currentSocialPlatformName,
  currentSocialTab,
  currentTenantName,
  currentUser,
  currentUsername,
  currentXhsDraft,
  editingBlogger,
  editingBloggerId,
  enabledContentGroups,
  eventPayloadSummary,
  form,
  formatDate,
  formatScheduleTime,
  goNextXhsCollectStep,
  goNextXhsCreationStep,
  goNextXhsDistillStep,
  goPreviousXhsCollectStep,
  goPreviousXhsCreationStep,
  goPreviousXhsDistillStep,
  groupLabel,
  handleAbandonBloggerRun,
  handleCancelDistillation,
  handleCollectBlogger,
  handleConfirmBloggerRun,
  handleCreateAdminUser,
  handleCreateBlogger,
  handleCreateXhsPackage,
  handleDeleteBlogger,
  handleDiscardXhsDraft,
  handleDistillBlogger,
  handleFetchNews,
  handleGenerateArticle,
  handleGenerateXhsTopicIdeas,
  handleGlobalKeydown,
  handleLogin,
  handleLogout,
  handleSaveArticle,
  handleSaveConfig,
  handleSaveXhsPackage,
  handleSearchBloggerCandidates,
  handleSendWechat,
  handleTenantChange,
  handleToggleBloggerFavorite,
  handleToggleNews,
  handleXhsCreatorBloggerChange,
  handleXhsCreatorSkillChange,
  hasArticle,
  hasNewsGroups,
  hasTaskEvents,
  isAdmin,
  isAuthenticated,
  isError,
  isLoggingIn,
  isSocialPlatform,
  isTaskRunning,
  isVisibleTaskRunning,
  latestCollectionProgressText,
  latestTaskEvent,
  layoutForm,
  layoutPreviewHeadingStyle,
  layoutPreviewImageStyle,
  layoutPreviewSectionStyle,
  layoutPreviewStyle,
  loadAll,
  loadTenantOptions,
  loginMessage,
  message,
  news,
  newsPage,
  newsTotalPages,
  openCreateBloggerModal,
  openEditBloggerModal,
  openImagePreview,
  pageSize,
  pagedNews,
  parseScheduleTime,
  pendingAction,
  previewImage,
  profile,
  profileForm,
  progressTimers,
  publicationName,
  publishingForm,
  refreshArticle,
  refreshBloggers,
  refreshSelectedBlogger,
  refreshXhsPackages,
  removeContentGroup,
  resetBloggerForm,
  resetBloggerSearch,
  resetFakeProgress,
  resetXhsTopicIdeas,
  resultCollectionFilter,
  resultCollectionFilterId,
  runAction,
  runTaskAction,
  runningTaskId,
  runningTaskName,
  selectBlogger,
  selectBloggerCandidate,
  selectBloggerRun,
  selectCollectionRun,
  selectLatestRunForCollection,
  selectXhsTopicIdea,
  selectedBlogger,
  selectedBloggerCandidate,
  selectedBloggerId,
  selectedBloggerRun,
  selectedBloggerRunCount,
  selectedBloggerRunId,
  selectedBloggerSkill,
  selectedCollectionRun,
  selectedCollectionRunId,
  selectedRunCostLabel,
  selectedTenantId,
  selectedXhsPackage,
  selectedXhsPackageBloggerName,
  selectedXhsPackageId,
  selectedXhsSkill,
  selectedXhsTopicIdea,
  selectedXhsTopicIndex,
  setArticle,
  setCurrentSocialTab,
  setNewsTab,
  setWorkspaceConfig,
  showAllBloggerRuns,
  showBloggerModal,
  showCollectionResults,
  showMessage,
  showTaskEventDetails,
  showUserMenu,
  startFakeProgress,
  statusText,
  stopFakeProgress,
  syncXhsPackageSelection,
  taskButtonStyle,
  taskEvents,
  taskEventsAction,
  taskEventsMainTab,
  taskProgress,
  taskSummaryMessage,
  taskSummaryPayload,
  taskSummaryStatus,
  taskSummaryStep,
  tenants,
  toggleUserMenu,
  usesRegionalGrouping,
  visibleBloggerRunCount,
  visibleBloggerRuns,
  visibleNewsTabs,
  visibleTaskEvents,
  visibleXhsPackages,
  wechatForm,
  workspaceTitle,
  xhsCollectStep,
  xhsCollectStepTitle,
  xhsCreationStep,
  xhsCreationStepTitle,
  xhsCreatorBloggerId,
  xhsCreatorSkillOptions,
  xhsDistillStep,
  xhsDistillStepTitle,
  xhsDraftHashtags,
  xhsDraftImagePlan,
  xhsDraftImageUrls,
  xhsDraftScriptSegments,
  xhsPackageForm,
  xhsPackageHashtags,
  xhsPackageImagePlan,
  xhsPackageImageUrls,
  xhsPackageScriptSegments,
  xhsPackages,
  xhsTopicIdeas
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

    <nav class="main-tabs" role="tablist" aria-label="媒体平台">
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
      <button
        v-if="isAdmin"
        type="button"
        role="tab"
        :aria-selected="activeMainTab === 'admin'"
        :class="{ active: activeMainTab === 'admin' }"
        @click="activeMainTab = 'admin'"
      >
        后台管理
      </button>
    </nav>

    <main class="workspace">
      <div v-if="activeMainTab === 'wechat'" class="module-subnav platform-subnav">
        <div class="tabs" role="tablist" aria-label="公众号模块">
          <button type="button" :class="{ active: activeWechatTab === 'brief' }" @click="activeWechatTab = 'brief'">每日早报</button>
          <button type="button" :class="{ active: activeWechatTab === 'ai' }" @click="activeWechatTab = 'ai'">AI 创作</button>
          <button type="button" :class="{ active: activeWechatTab === 'drafts' }" @click="activeWechatTab = 'drafts'">文章草稿</button>
          <button type="button" :class="{ active: activeWechatTab === 'records' }" @click="activeWechatTab = 'records'">发布记录</button>
          <button type="button" :class="{ active: activeWechatTab === 'settings' }" @click="activeWechatTab = 'settings'">设置</button>
        </div>
      </div>

      <div v-if="isSocialPlatform" class="module-subnav platform-subnav xhs-module-subnav">
        <div class="tabs" role="tablist" :aria-label="`${currentSocialPlatformName}模块`">
          <button
            type="button"
            :class="{ active: ['collect', 'distill', 'assets'].includes(currentSocialTab) }"
            @click="setCurrentSocialTab('collect')"
          >
            博主蒸馏
          </button>
          <button
            type="button"
            :class="{ active: ['packages', 'history'].includes(currentSocialTab) }"
            @click="setCurrentSocialTab('packages')"
          >
            AI 创作
          </button>
          <button type="button" :class="{ active: currentSocialTab === 'records' }" @click="setCurrentSocialTab('records')">发布记录</button>
          <button type="button" :class="{ active: currentSocialTab === 'settings' }" @click="setCurrentSocialTab('settings')">设置</button>
        </div>
        <div v-if="['collect', 'distill', 'assets'].includes(currentSocialTab)" class="tabs sub-tabs" role="tablist" :aria-label="`${currentSocialPlatformName}博主蒸馏子模块`">
          <button type="button" :class="{ active: currentSocialTab === 'collect' }" @click="setCurrentSocialTab('collect')">数据采集</button>
          <button type="button" :class="{ active: currentSocialTab === 'distill' }" @click="setCurrentSocialTab('distill')">蒸馏</button>
          <button type="button" :class="{ active: currentSocialTab === 'assets' }" @click="setCurrentSocialTab('assets')">博主资产</button>
        </div>
        <div v-if="['packages', 'history'].includes(currentSocialTab)" class="tabs sub-tabs" role="tablist" :aria-label="`${currentSocialPlatformName} AI 创作子模块`">
          <button type="button" :class="{ active: currentSocialTab === 'packages' }" @click="setCurrentSocialTab('packages')">创作流程</button>
          <button type="button" :class="{ active: currentSocialTab === 'history' }" @click="setCurrentSocialTab('history')">发布包历史</button>
        </div>
      </div>

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

      <section v-if="activeMainTab === 'wechat' && activeWechatTab === 'brief'" class="panel">
        <div class="workspace-snapshot scoped-snapshot" aria-label="公众号每日早报摘要">
          <div>
            <span>候选内容</span>
            <strong>{{ news.length }}</strong>
          </div>
          <div>
            <span>当前文章</span>
            <strong>{{ articleStateLabel }}</strong>
          </div>
          <div>
            <span>工作区</span>
            <strong>{{ publicationName }}</strong>
          </div>
        </div>
        <div class="section-header">
          <div>
            <h2>{{ workspaceTitle }}每日早报</h2>
            <p class="toolbar-subtitle">新闻采集、候选筛选和早报生成是独立链路，最终进入公众号文章草稿。</p>
          </div>
          <div class="actions">
            <button
              type="button"
              class="task-button"
              :class="{ running: pendingAction === 'fetch' }"
              :style="taskButtonStyle('fetch')"
              :disabled="Boolean(pendingAction)"
              @click="handleFetchNews"
            >
              <span>{{ pendingAction === 'fetch' ? `抓取中 ${Math.round(taskProgress.fetch)}%` : '重新抓取' }}</span>
            </button>
          </div>
        </div>
        <div class="module-subnav">
          <div class="tabs" role="tablist" aria-label="新闻分组">
            <button
              v-for="tab in visibleNewsTabs"
              :key="tab.group_key"
              type="button"
              role="tab"
              :aria-selected="activeNewsTab === tab.group_key"
              :class="{ active: activeNewsTab === tab.group_key }"
              @click="setNewsTab(tab.group_key)"
            >
              {{ tab.name }}
              <span>{{ tab.count }}</span>
            </button>
          </div>
        </div>
        <div v-if="activeNews.length" class="news-list">
          <article v-for="item in pagedNews" :key="item.id" class="news-card">
            <input
              type="checkbox"
              :checked="item.selected"
              :aria-label="`选择 ${item.title}`"
              @change="handleToggleNews(item, ($event.target as HTMLInputElement).checked)"
            />
            <div>
              <h3>{{ item.title }}</h3>
              <div class="meta">
                <span v-if="hasNewsGroups" class="region-pill">
                  {{ groupLabel(item.group_key) }}
                </span>
                {{ item.category }} · {{ item.source }} · {{ formatDate(item.published_at) }}
              </div>
              <p>{{ item.summary }}</p>
              <a :href="item.url" target="_blank" rel="noreferrer">查看来源</a>
            </div>
            <div class="score">{{ item.importance_score }}</div>
          </article>
          <div class="pagination">
            <button type="button" :disabled="newsPage <= 1" @click="changeNewsPage(-1)">上一页</button>
            <span>第 {{ newsPage }} / {{ newsTotalPages }} 页</span>
            <button type="button" :disabled="newsPage >= newsTotalPages" @click="changeNewsPage(1)">下一页</button>
          </div>
        </div>
        <p v-else class="empty-region">当前分类还没有候选新闻。</p>
      </section>

      <section v-if="activeMainTab === 'wechat' && activeWechatTab === 'ai'" class="panel">
        <div class="section-header">
          <div>
            <h2>公众号 AI 创作</h2>
            <p class="toolbar-subtitle">博主风格创作和自主 AI 创作会生成公众号文章，并复用预览与草稿箱发布能力。</p>
          </div>
        </div>
        <div class="feature-grid">
          <article class="feature-card locked">
            <span>博主风格创作</span>
            <h3>公众号博主蒸馏</h3>
            <p>未来流程：采集公众号文章样本，蒸馏风格资产，再应用风格生成公众号文章。</p>
            <strong>暂未开放</strong>
          </article>
          <article class="feature-card locked">
            <span>自主 AI 创作</span>
            <h3>输入主题生成文章</h3>
            <p>未来流程：输入主题、目标读者和内容目标，由 AI 自主规划并生成公众号文章。</p>
            <strong>暂未开放</strong>
          </article>
        </div>
      </section>

      <section v-if="activeMainTab === 'wechat' && activeWechatTab === 'drafts'" class="panel">
        <div class="section-header">
          <div>
            <h2>公众号文章</h2>
            <p class="toolbar-subtitle">当前文章状态：{{ articleStateLabel }}</p>
          </div>
          <div class="actions">
            <button
              type="button"
              class="task-button"
              :class="{ running: pendingAction === 'generate' }"
              :style="taskButtonStyle('generate')"
              :disabled="Boolean(pendingAction)"
              @click="handleGenerateArticle"
            >
              <span>{{ pendingAction === 'generate' ? `生成中 ${Math.round(taskProgress.generate)}%` : '生成文章' }}</span>
            </button>
            <button type="button" class="primary" :disabled="!hasArticle || Boolean(pendingAction)" @click="handleSendWechat">
              {{ pendingAction === 'wechat' ? '发送中' : '发送草稿箱' }}
            </button>
          </div>
        </div>
        <div class="module-subnav">
          <div class="tabs" role="tablist" aria-label="文章草稿">
            <button
              type="button"
              role="tab"
              :aria-selected="activeArticleTab === 'preview'"
              :class="{ active: activeArticleTab === 'preview' }"
              @click="activeArticleTab = 'preview'"
            >
              预览
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeArticleTab === 'edit'"
              :class="{ active: activeArticleTab === 'edit' }"
              @click="activeArticleTab = 'edit'"
            >
              编辑
            </button>
          </div>
        </div>

        <form v-if="activeArticleTab === 'edit'" class="article-form" @submit.prevent="handleSaveArticle">
          <label>
            标题
            <input v-model="form.title" type="text" :disabled="!hasArticle" />
          </label>
          <label>
            导语
            <textarea v-model="form.intro" rows="4" :disabled="!hasArticle"></textarea>
          </label>
          <label>
            封面图 URL
            <input v-model="form.cover_image_url" type="url" :disabled="!hasArticle" />
          </label>
          <label>
            正文 HTML
            <textarea v-model="form.content_html" rows="16" :disabled="!hasArticle"></textarea>
          </label>
          <button type="submit" :disabled="!hasArticle || Boolean(pendingAction)">
            {{ pendingAction === 'save' ? '保存中' : '保存修改' }}
          </button>
        </form>

        <article v-else class="preview-panel">
          <img v-if="form.cover_image_url" class="cover" :src="form.cover_image_url" alt="文章封面预览" />
          <h3>{{ form.title || '尚未生成文章' }}</h3>
          <p class="intro-preview">{{ form.intro }}</p>
          <div v-if="form.content_html" class="article-preview" v-html="sanitizeHtml(form.content_html)"></div>
          <div v-else class="article-preview">
            <p>生成文章后，这里会显示公众号图文预览。</p>
          </div>
        </article>
      </section>

      <section v-if="activeMainTab === 'wechat' && activeWechatTab === 'records'" class="panel">
        <div class="section-header">
          <div>
            <h2>公众号发布记录</h2>
            <p class="toolbar-subtitle">这里会汇总每日早报和 AI 创作文章的草稿箱推送记录。</p>
          </div>
        </div>
        <p class="empty-region">发布记录模块暂未开放。</p>
      </section>

      <section v-if="isSocialPlatform && currentSocialTab === 'collect'" class="panel">
        <div class="section-header">
          <div>
            <h2>{{ currentSocialPlatformName }}数据采集</h2>
            <p class="toolbar-subtitle">先选择博主，再配置采样数量、评论数量和 ASR；采集结果会进入博主资产。</p>
          </div>
        </div>
        <div class="creator-shell">
          <button v-if="xhsCollectStep > 1" type="button" class="creator-arrow previous" aria-label="上一步" @click="goPreviousXhsCollectStep">←</button>
          <div class="creator-main">
            <div class="creator-step-header">
              <h3>{{ xhsCollectStepTitle }}</h3>
              <span>步骤 {{ xhsCollectStep }} / 4</span>
              <div class="creator-progress" aria-hidden="true"><i :style="{ width: `${(xhsCollectStep / 4) * 100}%` }"></i></div>
            </div>

            <section v-if="xhsCollectStep === 1" class="creation-stage-card active">
              <div class="inline-card-header">
                <div><span>01 选择博主</span><h3>选择要采集的博主</h3></div>
                <button type="button" class="primary" @click="openCreateBloggerModal">创建博主</button>
              </div>
              <div v-if="bloggers.length" class="blogger-list compact">
                <button v-for="blogger in bloggers" :key="blogger.id" type="button" :class="{ active: selectedBloggerId === blogger.id }" @click="selectBlogger(blogger.id)">
                  <strong>{{ blogger.display_name }}</strong>
                  <span>{{ blogger.niche || '未设置领域' }} · 样本 {{ blogger.sample_count }} · {{ blogger.last_distilled_at ? formatDate(blogger.last_distilled_at) : '未蒸馏' }}</span>
                </button>
              </div>
              <p v-else class="empty-region">还没有博主档案。点击“创建博主”添加小红书主页。</p>
            </section>

            <section v-if="xhsCollectStep === 2" class="creation-stage-card active">
              <div class="inline-card-header"><div><span>02 配置采集</span><h3>设置样本和评论范围</h3></div></div>
              <div class="config-grid">
                <label>采样笔记数<input v-model.number="bloggerDistillForm.sample_limit" type="number" min="5" max="200" /></label>
                <label>每条评论数<input v-model.number="bloggerDistillForm.comments_per_post" type="number" min="0" max="100" /></label>
              </div>
              <label class="asr-callout">
                <input v-model="bloggerDistillForm.asr_enabled" type="checkbox" />
                <span><strong>启用视频字幕/ASR 分析</strong><small>采集视频笔记时优先提取字幕；没有字幕时尝试转写音频。</small></span>
              </label>
              <p class="form-hint">这些配置只影响本次采集批次，后续可基于不同批次分别蒸馏。</p>
            </section>

            <section v-if="xhsCollectStep === 3" class="creation-stage-card active">
              <div class="inline-card-header">
                <div><span>03 执行采集</span><h3>提交后台采集任务</h3></div>
                <button type="button" class="task-button primary" :class="{ running: pendingAction === 'collect' }" :style="taskButtonStyle('collect')" :disabled="!selectedBloggerId || Boolean(pendingAction)" @click="handleCollectBlogger">
                  <span>{{ pendingAction === 'collect' ? `采集中 ${Math.round(taskProgress.collect)}%` : '开始采集' }}</span>
                </button>
              </div>
              <div v-if="pendingAction === 'collect'" class="inline-progress-card" aria-live="polite">
                <div><strong>正在采集数据</strong><span>系统正在读取公开笔记、互动数据和评论样本。</span></div><i aria-hidden="true"></i>
              </div>
              <p class="form-hint">采集耗时取决于样本数量、评论数量和视频 ASR 开关。</p>
            </section>

            <section v-if="xhsCollectStep === 4" class="creation-stage-card active">
              <div class="inline-card-header">
                <div><span>04 查看结果</span><h3>采集批次和样本预览</h3></div>
                <button type="button" @click="setCurrentSocialTab('assets')">查看博主资产</button>
              </div>
              <div v-if="selectedBlogger" class="stage-result-grid">
                <article class="stage-metric"><span>当前博主</span><strong>{{ selectedBlogger.display_name }}</strong></article>
                <article class="stage-metric"><span>采集批次</span><strong>{{ bloggerCollectionRuns.length }}</strong></article>
              </div>
              <div v-if="selectedBlogger" class="run-list collection-list">
                <div class="run-list-header"><strong>采集历史</strong><span>{{ bloggerCollectionRuns.length }} 次</span></div>
                <button v-for="run in bloggerCollectionRuns" :key="run.id" type="button" :class="{ active: selectedCollectionRunId === run.id }" @click="selectCollectionRun(run.id)">
                  <strong>#{{ run.id }} · {{ formatDate(run.created_at) }}</strong>
                  <span>{{ run.status }} · 样本 {{ run.post_count }} · 评论 {{ run.comment_count }} · ASR {{ run.asr_enabled ? '开启' : '关闭' }}</span>
                </button>
              </div>
              <p v-if="!selectedBlogger" class="empty-region">请先选择博主。</p>
            </section>
          </div>
          <button v-if="xhsCollectStep < 4" type="button" class="creator-arrow next" aria-label="下一步" @click="goNextXhsCollectStep">→</button>
        </div>
      </section>

      <section v-if="isSocialPlatform && currentSocialTab === 'distill'" class="panel">
        <div class="section-header">
          <div>
            <h2>{{ currentSocialPlatformName }}博主蒸馏</h2>
            <p class="toolbar-subtitle">选择博主和采集批次，生成报告与 Skill；保存后才进入 AI 创作可选列表。</p>
          </div>
        </div>
        <div class="creator-shell">
          <button v-if="xhsDistillStep > 1" type="button" class="creator-arrow previous" aria-label="上一步" @click="goPreviousXhsDistillStep">←</button>
          <div class="creator-main">
            <div class="creator-step-header">
              <h3>{{ xhsDistillStepTitle }}</h3>
              <span>步骤 {{ xhsDistillStep }} / 4</span>
              <div class="creator-progress" aria-hidden="true"><i :style="{ width: `${(xhsDistillStep / 4) * 100}%` }"></i></div>
            </div>
            <section v-if="xhsDistillStep === 1" class="creation-stage-card active">
              <div class="inline-card-header"><div><span>01 选择博主</span><h3>选择要蒸馏的博主</h3></div></div>
              <div v-if="bloggers.length" class="blogger-list compact">
                <button v-for="blogger in bloggers" :key="blogger.id" type="button" :class="{ active: selectedBloggerId === blogger.id }" @click="selectBlogger(blogger.id)">
                  <strong>{{ blogger.display_name }}</strong><span>{{ blogger.niche || '未设置领域' }} · 采集批次 {{ bloggerCollectionRuns.length }}</span>
                </button>
              </div>
              <p v-else class="empty-region">还没有博主档案。请先到“数据采集”创建博主。</p>
            </section>
            <section v-if="xhsDistillStep === 2" class="creation-stage-card active">
              <div class="inline-card-header"><div><span>02 选择批次</span><h3>选择一次已完成采集</h3></div></div>
              <div v-if="selectedBlogger" class="run-list collection-list">
                <div class="run-list-header"><strong>可蒸馏批次</strong><span>{{ bloggerCollectionRuns.length }} 次</span></div>
                <button v-for="run in bloggerCollectionRuns" :key="run.id" type="button" :disabled="run.status !== 'succeeded'" :class="{ active: selectedCollectionRunId === run.id }" @click="selectCollectionRun(run.id)">
                  <strong>#{{ run.id }} · {{ formatDate(run.created_at) }}</strong>
                  <span>{{ run.status }} · 样本 {{ run.post_count }} · 已蒸馏 {{ collectionDistillationCount(run.id) }} 次</span>
                </button>
              </div>
              <p v-else class="empty-region">请先选择博主。</p>
            </section>
            <section v-if="xhsDistillStep === 3" class="creation-stage-card active">
              <div class="inline-card-header">
                <div><span>03 执行蒸馏</span><h3>基于采集批次生成 Skill</h3></div>
                <button type="button" class="task-button primary" :class="{ running: pendingAction === 'distill' }" :style="taskButtonStyle('distill')" :disabled="!selectedBloggerId || !selectedCollectionRunId || Boolean(pendingAction)" @click="handleDistillBlogger">
                  <span>{{ pendingAction === 'distill' ? `蒸馏中 ${Math.round(taskProgress.distill)}%` : '开始蒸馏' }}</span>
                </button>
              </div>
              <div v-if="pendingAction === 'distill'" class="inline-progress-card" aria-live="polite">
                <div><strong>正在蒸馏风格</strong><span>大模型正在提炼选题、结构、标题、表达和禁区。</span></div><i aria-hidden="true"></i>
              </div>
              <p class="form-hint">蒸馏完成后会进入结果确认页，保存后 Skill 才会生效。</p>
            </section>
            <section v-if="xhsDistillStep === 4" class="creation-stage-card active">
              <div class="inline-card-header">
                <div><span>04 确认结果</span><h3>预览报告和 Skill</h3></div>
                <div class="actions">
                  <button type="button" class="primary" :disabled="Boolean(pendingAction) || selectedBloggerRun?.status !== 'pending_confirmation'" @click="handleConfirmBloggerRun">{{ pendingAction === 'distill-confirm' ? '保存中' : '保存结果' }}</button>
                  <button type="button" :disabled="Boolean(pendingAction) || selectedBloggerRun?.status !== 'pending_confirmation'" @click="handleAbandonBloggerRun">{{ pendingAction === 'distill-abandon' ? '放弃中' : '放弃本次蒸馏' }}</button>
                </div>
              </div>
              <div v-if="selectedBloggerRun" class="distill-grid compact-result">
                <article class="distill-card"><h3>蒸馏报告</h3><div v-if="selectedBloggerRun.report_html" class="distill-report" v-html="sanitizeHtml(selectedBloggerRun.report_html)"></div><p v-else class="empty-region">暂无报告。</p></article>
                <article class="distill-card"><h3>Skill 输出</h3><textarea v-if="selectedBloggerSkill" :value="selectedBloggerSkill.skill_markdown" readonly rows="18"></textarea><p v-else class="empty-region">暂无 Skill。</p></article>
              </div>
              <p v-else class="empty-region">完成一次蒸馏后，这里会显示待确认结果。</p>
            </section>
          </div>
          <button v-if="xhsDistillStep < 4" type="button" class="creator-arrow next" aria-label="下一步" @click="goNextXhsDistillStep">→</button>
        </div>
      </section>

      <section v-if="isSocialPlatform && currentSocialTab === 'assets'" class="panel">
        <div class="section-header">
          <div>
            <h2>{{ currentSocialPlatformName }}博主资产</h2>
            <p class="toolbar-subtitle">集中查看博主信息、采集历史、蒸馏历史、报告和 Skill。</p>
          </div>
        </div>

        <div class="xhs-assets-browser">
          <aside class="asset-sidebar" aria-label="小红书博主列表">
            <div class="run-list-header">
              <strong>博主</strong>
              <span>{{ bloggers.length }} 个</span>
            </div>
            <button
              v-for="blogger in bloggers"
              :key="blogger.id"
              type="button"
              :class="{ active: selectedBloggerId === blogger.id }"
              @click="selectBlogger(blogger.id)"
            >
              <strong>{{ blogger.display_name }}</strong>
              <span>{{ blogger.is_favorite ? '已标记 · ' : '' }}{{ blogger.niche || '未设置领域' }} · 样本 {{ blogger.sample_count }}</span>
            </button>
            <p v-if="!bloggers.length" class="empty-region">还没有博主档案。请先到“数据采集”创建博主。</p>
          </aside>

          <div v-if="selectedBlogger" class="asset-detail">
            <div class="asset-hero">
              <div>
                <span>{{ selectedBlogger.is_favorite ? '已标记博主' : '博主资产' }}</span>
                <h3>{{ selectedBlogger.display_name }}</h3>
                <p>{{ selectedBlogger.description || selectedBlogger.niche || '暂无备注' }}</p>
              </div>
              <div class="asset-actions">
                <button type="button" @click="handleToggleBloggerFavorite(selectedBlogger)">
                  {{ selectedBlogger.is_favorite ? '取消标记' : '标记博主' }}
                </button>
                <button type="button" @click="openEditBloggerModal(selectedBlogger)">编辑信息</button>
                <button type="button" class="danger" @click="handleDeleteBlogger(selectedBlogger)">删除博主</button>
              </div>
            </div>

            <div class="workspace-snapshot scoped-snapshot">
              <div>
                <span>采集批次</span>
                <strong>{{ bloggerCollectionRuns.length }}</strong>
              </div>
              <div>
                <span>蒸馏记录</span>
                <strong>{{ selectedBloggerRunCount }}</strong>
              </div>
              <div>
                <span>最近蒸馏</span>
                <strong>{{ selectedBlogger.last_distilled_at ? formatDate(selectedBlogger.last_distilled_at) : '暂无' }}</strong>
              </div>
            </div>

            <div class="asset-two-column">
              <section class="asset-panel">
                <div class="run-list-header">
                  <strong>采集历史</strong>
                  <span>{{ bloggerCollectionRuns.length }} 次</span>
                </div>
                <div class="asset-run-list">
                  <button
                    v-for="run in bloggerCollectionRuns"
                    :key="run.id"
                    type="button"
                    :class="{ active: selectedCollectionRunId === run.id }"
                    @click="selectCollectionRun(run.id)"
                  >
                    <strong>#{{ run.id }} · {{ formatDate(run.created_at) }}</strong>
                    <span>{{ run.status }} · 样本 {{ run.post_count }} · 评论 {{ run.comment_count }} · ASR {{ run.asr_enabled ? '开' : '关' }} · 蒸馏 {{ collectionDistillationCount(run.id) }}</span>
                  </button>
                  <p v-if="!bloggerCollectionRuns.length" class="empty-region">这个博主还没有采集批次。</p>
                </div>
              </section>

              <section class="asset-panel">
                <div class="run-list-header">
                  <strong>{{ resultCollectionFilter ? `批次 #${resultCollectionFilter.id} 的蒸馏结果` : '蒸馏历史' }}</strong>
                  <span>{{ resultCollectionFilter ? `${visibleBloggerRunCount} / ${selectedBloggerRunCount}` : `${selectedBloggerRunCount} 次` }}</span>
                </div>
                <div v-if="resultCollectionFilter" class="filter-bar">
                  <span>已按采集批次筛选</span>
                  <button type="button" @click="showAllBloggerRuns">查看全部</button>
                </div>
                <div class="asset-run-list">
                  <button
                    v-for="run in visibleBloggerRuns"
                    :key="run.id"
                    type="button"
                    :class="{ active: selectedBloggerRunId === run.id, failed: run.status === 'failed' }"
                    @click="selectBloggerRun(run.id)"
                  >
                    <strong>{{ formatDate(run.created_at) }}</strong>
                    <span>批次 #{{ run.collection_run_id || '旧数据' }} · {{ distillationStatusLabel(run.status) }} · 样本 {{ run.sample_count }} · {{ runCostLabel(run) }}</span>
                    <em v-if="run.status === 'failed'" class="run-error">失败原因：{{ run.error_message || '未记录失败原因' }}</em>
                  </button>
                  <p v-if="!visibleBloggerRuns.length && resultCollectionFilter" class="empty-region">这个采集批次还没有蒸馏结果。</p>
                  <p v-else-if="!visibleBloggerRuns.length" class="empty-region">这个博主还没有蒸馏记录。</p>
                </div>
              </section>
            </div>

            <section v-if="selectedCollectionRun" class="asset-panel">
              <div class="inline-card-header">
                <div>
                  <span>采集样本</span>
                  <h3>批次 #{{ selectedCollectionRun.id }}</h3>
                </div>
                <button v-if="collectionDistillationCount(selectedCollectionRun.id)" type="button" @click="showCollectionResults(selectedCollectionRun.id)">查看对应蒸馏</button>
              </div>
              <div v-if="bloggerPosts.length" class="sample-list asset-samples">
                <div v-for="post in bloggerPosts.slice(0, 8)" :key="post.id">
                  <strong>{{ post.title }}</strong>
                  <span>
                    {{ post.content_type === 'video' ? '视频' : '图文' }} · 收藏 {{ post.favorite_count }} / 点赞 {{ post.like_count }} / {{ bloggerCommentLabel(post) }}
                    <template v-if="post.content_type === 'video'"> / ASR {{ post.asr_status }}</template>
                  </span>
                </div>
              </div>
              <p v-else class="empty-region">这个采集批次还没有可展示样本。</p>
            </section>

            <section v-if="selectedBloggerRun" class="asset-panel">
              <div class="stage-header">
                <div>
                  <span>{{ distillationStatusLabel(selectedBloggerRun.status) }}</span>
                  <h3>蒸馏结果 #{{ selectedBloggerRun.id }}</h3>
                </div>
                <div v-if="selectedBloggerRun.status === 'pending_confirmation'" class="actions">
                  <button type="button" class="primary" :disabled="Boolean(pendingAction)" @click="handleConfirmBloggerRun">
                    {{ pendingAction === 'distill-confirm' ? '保存中' : '保存结果' }}
                  </button>
                  <button type="button" :disabled="Boolean(pendingAction)" @click="handleAbandonBloggerRun">
                    {{ pendingAction === 'distill-abandon' ? '放弃中' : '放弃本次蒸馏' }}
                  </button>
                </div>
              </div>
              <div class="workspace-snapshot scoped-snapshot">
                <div><span>样本数量</span><strong>{{ selectedBloggerRun.sample_count }}</strong></div>
                <div><span>TikHub 请求</span><strong>{{ selectedBloggerRun.tikhub_request_count }}</strong></div>
                <div><span>本次费用</span><strong>{{ selectedRunCostLabel }}</strong></div>
              </div>
              <div class="distill-grid compact-result">
                <article class="distill-card">
                  <h3>蒸馏报告</h3>
                  <div v-if="selectedBloggerRun.status === 'failed'" class="failure-panel">
                    <strong>蒸馏失败</strong>
                    <p>{{ selectedBloggerRun.error_message || '这次蒸馏没有记录失败原因，请查看任务日志。' }}</p>
                  </div>
                  <div v-else-if="selectedBloggerRun.report_html" class="distill-report" v-html="sanitizeHtml(selectedBloggerRun.report_html)"></div>
                  <p v-else class="empty-region">这次蒸馏没有生成报告。</p>
                </article>

                <article class="distill-card">
                  <h3>Skill 输出</h3>
                  <textarea
                    v-if="selectedBloggerSkill"
                    :value="selectedBloggerSkill.skill_markdown"
                    readonly
                    rows="18"
                  ></textarea>
                  <p v-else-if="selectedBloggerRun.status === 'failed'" class="empty-region">蒸馏失败后不会生成 Skill。</p>
                  <p v-else class="empty-region">这次蒸馏没有生成 Skill。</p>
                </article>
              </div>
            </section>
            <p v-else class="empty-region result-placeholder">请选择一次蒸馏记录查看报告和 Skill。</p>
          </div>
          <p v-else class="empty-region">请选择一个博主查看资产。</p>
        </div>

      </section>

      <section v-if="isSocialPlatform && currentSocialTab === 'packages'" class="panel">
        <div class="section-header">
          <div>
            <h2>{{ currentSocialPlatformName }} AI 创作</h2>
            <p class="toolbar-subtitle">按步骤生成一条新内容；历史结果请到“发布包历史”查看。</p>
          </div>
        </div>
        <div class="creator-shell">
          <button
            v-if="xhsCreationStep > 1"
            type="button"
            class="creator-arrow previous"
            aria-label="上一步"
            @click="goPreviousXhsCreationStep"
          >
            ←
          </button>
          <div class="creator-main">
            <div class="creator-step-header">
              <h3>{{ xhsCreationStepTitle }}</h3>
              <span>步骤 {{ xhsCreationStep }} / 6</span>
              <div class="creator-progress" aria-hidden="true">
                <i :style="{ width: `${(xhsCreationStep / 6) * 100}%` }"></i>
              </div>
            </div>

            <section v-if="xhsCreationStep === 1" class="creation-stage-card active">
              <div class="inline-card-header">
                <div>
                  <span>01 选择博主</span>
                  <h3>选择要借鉴风格的博主</h3>
                </div>
              </div>
              <div v-if="bloggers.length" class="blogger-list compact">
                <button
                  v-for="blogger in bloggers"
                  :key="blogger.id"
                  type="button"
                  :class="{ active: xhsCreatorBloggerId === blogger.id }"
                  @click="xhsCreatorBloggerId = blogger.id; handleXhsCreatorBloggerChange()"
                >
                  <strong>{{ blogger.display_name }}</strong>
                  <span>{{ blogger.niche || '未设置领域' }} · 样本 {{ blogger.sample_count }} · {{ blogger.last_distilled_at ? formatDate(blogger.last_distilled_at) : '未蒸馏' }}</span>
                </button>
              </div>
              <p v-else class="empty-region">还没有可用于创作的博主。请先到“博主蒸馏 / 数据采集”创建博主并完成采集。</p>
            </section>

            <section v-if="xhsCreationStep === 2" class="creation-stage-card active">
              <div class="inline-card-header">
                <div>
                  <span>02 选择 Skill</span>
                  <h3>选择该博主的风格资产</h3>
                </div>
              </div>
              <div v-if="xhsCreatorSkillOptions.length" class="topic-idea-grid">
                <button
                  v-for="skill in xhsCreatorSkillOptions"
                  :key="skill.id"
                  type="button"
                  :class="{ active: xhsPackageForm.skill_id === skill.id }"
                  @click="xhsPackageForm.skill_id = skill.id; handleXhsCreatorSkillChange()"
                >
                  <strong>{{ skill.name }}</strong>
                  <span>{{ skill.description }}</span>
                  <small>{{ formatDate(skill.created_at) }}</small>
                </button>
              </div>
              <p v-else class="empty-region">这个博主还没有可用 Skill。请先到“博主蒸馏”完成一次风格蒸馏。</p>
              <div v-if="selectedXhsSkill" class="skill-mini-card">
                <strong>{{ selectedXhsSkill.name }}</strong>
                <span>{{ selectedXhsSkill.description }}</span>
              </div>
            </section>

            <section v-if="xhsCreationStep === 3" class="creation-stage-card active">
              <div class="inline-card-header">
                <div>
                  <span>03 生成/选择选题</span>
                  <h3>先确定这次要写什么</h3>
                </div>
                <button type="button" class="primary" :disabled="Boolean(pendingAction) || !selectedXhsSkill" @click="handleGenerateXhsTopicIdeas">
                  {{ pendingAction === 'xhs-topic' ? '生成中' : xhsTopicIdeas.length ? '重新生成选题' : '生成选题方案' }}
                </button>
              </div>
              <label>
                种子主题
                <input v-model="xhsPackageForm.topic" type="text" placeholder="可以留空，也可以输入你想写的大方向" />
              </label>
              <div class="config-grid">
                <label>
                  目标人群
                  <input v-model="xhsPackageForm.target_audience" type="text" placeholder="例如：第一次养猫的年轻人" />
                </label>
                <label>
                  内容目的
                  <select v-model="xhsPackageForm.content_goal">
                    <option value="知识分享">知识分享</option>
                    <option value="避坑科普">避坑科普</option>
                    <option value="种草转化">种草转化</option>
                    <option value="观点表达">观点表达</option>
                    <option value="经验复盘">经验复盘</option>
                  </select>
                </label>
              </div>
              <label>
                关键词
                <input v-model="xhsPackageForm.keywords" type="text" placeholder="用逗号分隔，例如：猫粮, 配料表, 蛋白质" />
              </label>
              <div v-if="pendingAction === 'xhs-topic'" class="inline-progress-card" aria-live="polite">
                <div>
                  <strong>正在生成选题</strong>
                  <span>大模型正在结合 Skill、主题和目标人群整理方向。</span>
                </div>
                <i aria-hidden="true"></i>
              </div>
              <div v-if="xhsTopicIdeas.length" class="topic-idea-grid">
                <button
                  v-for="(idea, index) in xhsTopicIdeas"
                  :key="`${idea.title}-${index}`"
                  type="button"
                  :class="{ active: selectedXhsTopicIndex === index }"
                  @click="selectXhsTopicIdea(index)"
                >
                  <strong>{{ idea.title }}</strong>
                  <span>{{ idea.angle }}</span>
                  <small>{{ idea.reason }}</small>
                </button>
              </div>
              <p v-else class="empty-region">生成后，这里会显示多个可选择的选题方案。</p>
            </section>

            <section v-if="xhsCreationStep === 4" class="creation-stage-card active">
              <div class="inline-card-header">
                <div>
                  <span>04 生成正文/脚本</span>
                  <h3>选择内容类型并生成</h3>
                </div>
                <button type="button" class="primary" :disabled="Boolean(pendingAction) || !selectedXhsSkill || !xhsPackageForm.topic.trim()" @click="handleCreateXhsPackage">
                  {{ pendingAction === 'xhs-package' ? '生成中' : currentXhsDraft ? '重新生成' : '开始生成' }}
                </button>
              </div>
              <div v-if="selectedXhsTopicIdea" class="selected-idea-card">
                <span>已选方向</span>
                <strong>{{ selectedXhsTopicIdea.title }}</strong>
                <p>{{ selectedXhsTopicIdea.angle }}</p>
              </div>
              <div class="package-type-grid" role="radiogroup" aria-label="内容类型">
                <label :class="{ active: xhsPackageForm.content_type === 'text_note' }">
                  <input v-model="xhsPackageForm.content_type" type="radio" value="text_note" />
                  <strong>图文笔记</strong>
                  <span>标题、正文、标签、封面文案</span>
                </label>
                <label :class="{ active: xhsPackageForm.content_type === 'image_note' }">
                  <input v-model="xhsPackageForm.content_type" type="radio" value="image_note" />
                  <strong>图文配图</strong>
                  <span>额外规划并生成配图</span>
                </label>
                <label :class="{ active: xhsPackageForm.content_type === 'spoken_script' }">
                  <input v-model="xhsPackageForm.content_type" type="radio" value="spoken_script" />
                  <strong>口播脚本</strong>
                  <span>按时间段输出口播稿</span>
                </label>
                <label :class="{ active: xhsPackageForm.content_type === 'video_script' }">
                  <input v-model="xhsPackageForm.content_type" type="radio" value="video_script" />
                  <strong>视频脚本</strong>
                  <span>分镜、旁白、字幕建议</span>
                </label>
              </div>
              <div v-if="pendingAction === 'xhs-package'" class="inline-progress-card" aria-live="polite">
                <div>
                  <strong>正在生成正文/脚本</strong>
                  <span>会先生成内容结构；如果选择配图，会继续规划并生成图片。</span>
                </div>
                <i aria-hidden="true"></i>
              </div>
              <section v-if="currentXhsDraft" class="package-copy-block">
                <div class="inline-card-header">
                  <h3>{{ currentXhsDraft.title }}</h3>
                  <button type="button" @click="copyText(currentXhsDraft.body_text, '正文')">复制正文</button>
                </div>
                <pre>{{ currentXhsDraft.body_text }}</pre>
              </section>
            </section>

            <section v-if="xhsCreationStep === 5" class="creation-stage-card active">
              <div class="inline-card-header">
                <div>
                  <span>05 封面、配图与标签</span>
                  <h3>检查素材输出</h3>
                </div>
              </div>
              <div v-if="currentXhsDraft" class="asset-output-grid">
                <article>
                  <span>封面文案</span>
                  <strong>{{ currentXhsDraft.cover_text || '暂无' }}</strong>
                </article>
                <article>
                  <span>标签</span>
                  <strong>{{ xhsDraftHashtags.length }} 个</strong>
                </article>
                <article>
                  <span>配图</span>
                  <strong>{{ xhsDraftImageUrls.length || xhsDraftImagePlan.length }} 张</strong>
                </article>
              </div>
              <HashtagCloud :tags="xhsDraftHashtags" @copy="copyText($event, '标签')" />
              <ImageOutputGrid
                v-if="xhsDraftImageUrls.length"
                :urls="xhsDraftImageUrls"
                :plan="xhsDraftImagePlan"
                :alt-text="`${currentSocialPlatformName}发布包配图`"
                @preview="openImagePreview($event.url, $event.caption)"
              />
              <p v-if="!currentXhsDraft" class="empty-region">生成内容后，这里会展示封面、标签和配图输出。</p>
            </section>

            <section v-if="xhsCreationStep === 6" class="creation-stage-card active">
              <div class="inline-card-header">
                <div>
                  <span>06 最终发布包</span>
                  <h3>预览并决定是否保存</h3>
                </div>
                <div class="actions compact-actions">
                  <button type="button" :disabled="!currentXhsDraft" @click="currentXhsDraft && copyText(xhsPackageCopyText(currentXhsDraft), '发布文案')">复制发布文案</button>
                  <button type="button" class="primary" :disabled="Boolean(pendingAction) || !currentXhsDraft" @click="handleSaveXhsPackage">
                    {{ pendingAction === 'xhs-package-save' ? '保存中' : '保存发布包' }}
                  </button>
                  <button type="button" :disabled="!currentXhsDraft" @click="handleDiscardXhsDraft">放弃本次创作</button>
                </div>
              </div>
              <div v-if="pendingAction === 'xhs-package-save'" class="inline-progress-card" aria-live="polite">
                <div>
                  <strong>正在保存发布包</strong>
                  <span>保存后会进入发布包历史，方便后续查看和复制。</span>
                </div>
                <i aria-hidden="true"></i>
              </div>
              <p v-if="!currentXhsDraft" class="empty-region">生成内容后，这里会显示本次创作的最终预览。保存后才会进入发布包历史。</p>
              <div v-else class="package-preview draft-preview">
                <div class="package-preview-head">
                  <div>
                    <span>{{ xhsContentTypeLabel(currentXhsDraft.content_type) }}</span>
                    <h3>{{ currentXhsDraft.title }}</h3>
                  </div>
                </div>
                <div class="package-meta-grid">
                  <article>
                    <span>主题</span>
                    <strong>{{ currentXhsDraft.topic }}</strong>
                  </article>
                  <article>
                    <span>封面文案</span>
                    <strong>{{ currentXhsDraft.cover_text || '暂无' }}</strong>
                  </article>
                  <article>
                    <span>标签</span>
                    <strong>{{ xhsDraftHashtags.length }} 个</strong>
                  </article>
                </div>
                <HashtagCloud :tags="xhsDraftHashtags" @copy="copyText($event, '标签')" />
                <section class="package-copy-block">
                  <div class="inline-card-header">
                    <h3>正文预览</h3>
                    <button type="button" @click="copyText(currentXhsDraft.body_text, '正文')">复制正文</button>
                  </div>
                  <pre>{{ currentXhsDraft.body_text }}</pre>
                </section>
                <ImageOutputGrid
                  v-if="xhsDraftImageUrls.length"
                  :urls="xhsDraftImageUrls"
                  :plan="xhsDraftImagePlan"
                  :alt-text="`${currentSocialPlatformName}发布包配图`"
                  @preview="openImagePreview($event.url, $event.caption)"
                />
                <section v-if="xhsDraftScriptSegments.length" class="script-segments">
                  <div class="inline-card-header">
                    <h3>脚本预览</h3>
                    <button type="button" @click="copyText(JSON.stringify(parseJsonObject(currentXhsDraft.script_json), null, 2), '脚本')">复制脚本</button>
                  </div>
                  <article v-for="(segment, index) in xhsDraftScriptSegments" :key="index">
                    <span>{{ segment.start || `${index * 5}s` }} - {{ segment.end || '' }}</span>
                    <strong>{{ segment.subtitle || segment.scene || '脚本片段' }}</strong>
                    <p>{{ segment.voiceover || segment.scene }}</p>
                  </article>
                </section>
                <p v-if="currentXhsDraft.error_message" class="run-error">{{ currentXhsDraft.error_message }}</p>
              </div>
            </section>
          </div>
          <button
            v-if="xhsCreationStep < 6"
            type="button"
            class="creator-arrow next"
            aria-label="下一步"
            @click="goNextXhsCreationStep"
          >
            →
          </button>
        </div>
      </section>

      <section v-if="isSocialPlatform && currentSocialTab === 'history'" class="panel">
        <div class="section-header">
          <div>
            <h2>{{ currentSocialPlatformName }}发布包历史</h2>
            <p class="toolbar-subtitle">这里专门查看、复制和管理历史生成结果，不进入生成流程。</p>
          </div>
          </div>
        <div class="package-browser history-browser">
          <aside class="run-list package-list" aria-label="发布包记录">
            <div class="run-list-header">
              <strong>发布包记录</strong>
              <span>{{ visibleXhsPackages.length }} 条</span>
            </div>
            <button
              v-for="pack in visibleXhsPackages"
              :key="pack.id"
              type="button"
              :class="{ active: selectedXhsPackage?.id === pack.id }"
              @click="selectedXhsPackageId = pack.id"
            >
              <strong>{{ pack.title || pack.topic }}</strong>
              <span>{{ xhsContentTypeLabel(pack.content_type) }} · {{ formatDate(pack.created_at) }}</span>
            </button>
            <p v-if="!visibleXhsPackages.length" class="empty-region">还没有发布包。到“AI 创作”生成后会出现在这里。</p>
          </aside>

          <article v-if="selectedXhsPackage" class="package-preview">
            <div class="inline-card-header">
              <div>
                <span>{{ selectedXhsPackageBloggerName }} · {{ xhsContentTypeLabel(selectedXhsPackage.content_type) }}</span>
                <h3>{{ selectedXhsPackage.title }}</h3>
              </div>
              <button type="button" @click="copyText(xhsPackageCopyText(selectedXhsPackage), '发布文案')">复制发布文案</button>
            </div>
            <div class="workspace-snapshot scoped-snapshot">
              <div>
                <span>主题</span>
                <strong>{{ selectedXhsPackage.topic }}</strong>
              </div>
              <div>
                <span>封面文案</span>
                <strong>{{ selectedXhsPackage.cover_text || '暂无' }}</strong>
              </div>
              <div>
                <span>配图</span>
                <strong>{{ xhsPackageImageUrls.length || xhsPackageImagePlan.length }} 张</strong>
              </div>
            </div>
            <section class="package-copy-block">
              <div class="inline-card-header">
                <h3>正文</h3>
                <button type="button" @click="copyText(selectedXhsPackage.body_text, '正文')">复制正文</button>
              </div>
              <pre>{{ selectedXhsPackage.body_text }}</pre>
            </section>
            <HashtagCloud :tags="xhsPackageHashtags" @copy="copyText($event, '标签')" />
            <section v-if="xhsPackageImageUrls.length || xhsPackageImagePlan.length" class="package-images">
              <div class="inline-card-header">
                <h3>配图</h3>
              </div>
              <ImageOutputGrid
                :urls="xhsPackageImageUrls"
                :plan="xhsPackageImagePlan"
                :alt-text="`${currentSocialPlatformName}发布包配图`"
                @preview="openImagePreview($event.url, $event.caption)"
              />
              <div v-if="!xhsPackageImageUrls.length" class="sample-list">
                <div v-for="item in xhsPackageImagePlan" :key="String(item.slot)">
                  <strong>{{ item.caption || `配图 ${item.slot}` }}</strong>
                  <span>{{ item.purpose }}</span>
                </div>
              </div>
              <p v-if="selectedXhsPackage.error_message" class="run-error">{{ selectedXhsPackage.error_message }}</p>
            </section>
            <section v-if="xhsPackageScriptSegments.length" class="script-timeline">
              <div class="inline-card-header">
                <h3>脚本分段</h3>
                <button type="button" @click="copyText(JSON.stringify(parseJsonObject(selectedXhsPackage.script_json), null, 2), '脚本')">复制脚本</button>
              </div>
              <div v-for="(segment, index) in xhsPackageScriptSegments" :key="index">
                <time>{{ segment.start || `${index * 10}s` }} - {{ segment.end || `${(index + 1) * 10}s` }}</time>
                <strong>{{ segment.voiceover || segment.subtitle }}</strong>
                <span>{{ segment.scene }}</span>
              </div>
            </section>
          </article>
          <p v-else class="empty-region result-placeholder">选择一条发布包记录后，这里会展示可复制的内容。</p>
        </div>
      </section>

      <section v-if="activeMainTab === 'xhs' && (activeXhsTab === 'records' || activeXhsTab === 'settings')" class="panel">
        <div class="section-header">
          <div>
            <h2>{{ activeXhsTab === 'records' ? '小红书发布记录' : '小红书设置' }}</h2>
            <p class="toolbar-subtitle">发布记录和平台设置能力后续开放。</p>
          </div>
        </div>
        <p class="empty-region">该模块暂未开放。</p>
      </section>

      <section v-if="activeMainTab === 'douyin' && (currentSocialTab === 'records' || currentSocialTab === 'settings')" class="panel">
        <div class="section-header">
          <div>
            <h2>{{ currentSocialTab === 'records' ? '抖音发布记录' : '抖音设置' }}</h2>
            <p class="toolbar-subtitle">发布记录和平台设置能力后续开放。</p>
          </div>
        </div>
        <p class="empty-region">该模块暂未开放。</p>
      </section>

      <section v-if="activeMainTab === 'wechat' && activeWechatTab === 'settings'" class="panel">
        <div class="section-header">
          <div>
            <h2>工作空间配置</h2>
          </div>
          <button type="submit" form="workspace-config-form" class="primary" :disabled="Boolean(pendingAction)">
            {{ pendingAction === 'config' ? '保存中' : '保存配置' }}
          </button>
        </div>
        <div class="module-subnav">
          <div class="tabs" role="tablist" aria-label="设置模块">
            <button
              type="button"
              role="tab"
              :aria-selected="activeSettingsTab === 'general'"
              :class="{ active: activeSettingsTab === 'general' }"
              @click="activeSettingsTab = 'general'"
            >
              通用设置
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeSettingsTab === 'wechat'"
              :class="{ active: activeSettingsTab === 'wechat' }"
              @click="activeSettingsTab = 'wechat'"
            >
              公众号设置
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeSettingsTab === 'automation'"
              :class="{ active: activeSettingsTab === 'automation' }"
              @click="activeSettingsTab = 'automation'"
            >
              自动化设置
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeSettingsTab === 'sources'"
              :class="{ active: activeSettingsTab === 'sources' }"
              @click="activeSettingsTab = 'sources'"
            >
              新闻源设置
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeSettingsTab === 'generation'"
              :class="{ active: activeSettingsTab === 'generation' }"
              @click="activeSettingsTab = 'generation'"
            >
              生成策略
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeSettingsTab === 'layout'"
              :class="{ active: activeSettingsTab === 'layout' }"
              @click="activeSettingsTab = 'layout'"
            >
              排版设置
            </button>
          </div>
        </div>

        <form id="workspace-config-form" class="config-form" @submit.prevent="handleSaveConfig">
          <div v-if="activeSettingsTab === 'general'" class="settings-pane">
            <h3>工作空间与文章标题</h3>
            <div class="config-grid">
              <label>
                公众号/栏目名称
                <input v-model="profileForm.publication_name" type="text" required />
              </label>
              <label>
                工作台标题
                <input v-model="profileForm.workspace_title" type="text" required />
              </label>
              <label>
                文章标题前缀
                <input v-model="profileForm.title_prefix" type="text" required />
              </label>
            </div>
            <label>
              内容领域
              <textarea v-model="profileForm.content_domain" rows="3" readonly></textarea>
            </label>
            <label>
              编辑人设
              <textarea v-model="profileForm.editor_persona" rows="3" readonly></textarea>
            </label>
            <label>
              目标读者
              <textarea v-model="profileForm.audience" rows="3" readonly></textarea>
            </label>
            <label>
              文章风格
              <textarea v-model="profileForm.article_style" rows="3" readonly></textarea>
            </label>
            <label>
              图片风格
              <textarea v-model="profileForm.image_style" rows="3" readonly></textarea>
            </label>
            <label>
              分类 JSON
              <textarea v-model="profileForm.categories_json" rows="3" readonly></textarea>
            </label>
          </div>

          <div v-if="activeSettingsTab === 'wechat'" class="settings-pane">
            <h3>微信草稿箱配置</h3>
            <div class="config-grid">
              <label>
                微信 AppID
                <input v-model="wechatForm.app_id" type="text" autocomplete="off" />
              </label>
              <label>
                微信 AppSecret
                <input
                  v-model="wechatForm.app_secret"
                  type="password"
                  autocomplete="new-password"
                  :placeholder="wechatForm.app_secret_configured ? '已配置，留空则不修改' : '未配置'"
                />
              </label>
            </div>
          </div>

          <div v-if="activeSettingsTab === 'automation'" class="settings-pane">
            <h3>定时发布</h3>
            <div class="config-grid">
              <label class="toggle-row">
                <input v-model="publishingForm.daily_publish_enabled" type="checkbox" />
                启用定时任务
              </label>
              <label class="toggle-row">
                <input v-model="publishingForm.auto_send_wechat_draft" type="checkbox" />
                生成后自动发送草稿箱
              </label>
              <label>
                发布周期
                <select v-model="publishingForm.publish_frequency">
                  <option value="daily">每日</option>
                  <option value="weekly">每周</option>
                  <option value="monthly">每月</option>
                </select>
              </label>
              <label v-if="publishingForm.publish_frequency === 'weekly'">
                每周执行日
                <select v-model.number="publishingForm.publish_weekday">
                  <option :value="1">周一</option>
                  <option :value="2">周二</option>
                  <option :value="3">周三</option>
                  <option :value="4">周四</option>
                  <option :value="5">周五</option>
                  <option :value="6">周六</option>
                  <option :value="7">周日</option>
                </select>
              </label>
              <label v-if="publishingForm.publish_frequency === 'monthly'">
                每月执行日
                <input v-model.number="publishingForm.publish_month_day" type="number" min="1" max="31" />
              </label>
              <label>
                时间点
                <input v-model="publishingForm.publish_time_value" type="time" step="60" />
              </label>
            </div>
          </div>

          <div v-if="activeSettingsTab === 'sources'" class="settings-pane">
            <h3>来源与候选池</h3>
            <div class="config-grid">
              <label>
                每个源最多抓取
                <input v-model.number="publishingForm.news_per_source_limit" type="number" min="1" max="50" />
              </label>
              <label>
                新闻回看小时
                <input v-model.number="publishingForm.news_lookback_hours" type="number" min="1" max="168" />
              </label>
              <label>
                总候选上限
                <input v-model.number="publishingForm.max_news_candidates" type="number" min="1" max="300" />
              </label>
            </div>
            <div class="group-editor">
              <article v-for="(group, index) in contentGroupForms" :key="`${group.group_key}-${index}`" class="group-card">
                <div class="group-card-header">
                  <strong>{{ group.name || `内容分组 ${index + 1}` }}</strong>
                  <button type="button" @click="removeContentGroup(index)">移除</button>
                </div>
                <div class="config-grid">
                  <label>
                    分组 Key
                    <input v-model="group.group_key" type="text" required />
                  </label>
                  <label>
                    分组名称
                    <input v-model="group.name" type="text" required />
                  </label>
                  <label>
                    内容形态
                    <select v-model="group.content_mode">
                      <option value="news">新闻资讯</option>
                      <option value="knowledge">知识分享</option>
                      <option value="analysis">行业观察</option>
                    </select>
                  </label>
                  <label>
                    候选数量
                    <input v-model.number="group.candidate_limit" type="number" min="0" max="300" />
                  </label>
                  <label class="toggle-row">
                    <input v-model="group.enabled" type="checkbox" />
                    启用分组
                  </label>
                  <label>
                    文章最少
                    <input v-model.number="group.article_min" type="number" min="0" max="50" />
                  </label>
                  <label>
                    文章目标
                    <input v-model.number="group.article_target" type="number" min="0" max="50" />
                  </label>
                  <label>
                    文章最多
                    <input v-model.number="group.article_max" type="number" min="0" max="50" />
                  </label>
                </div>
                <label>
                  新闻源
                  <textarea
                    v-model="group.source_urls"
                    rows="3"
                    placeholder="格式：名称|RSS地址,名称|RSS地址"
                  ></textarea>
                </label>
              </article>
              <button type="button" class="secondary" @click="addContentGroup">新增内容分组</button>
            </div>
          </div>

          <div v-if="activeSettingsTab === 'generation'" class="settings-pane">
            <h3>文章、图片与去重</h3>
            <div class="config-grid">
              <label class="toggle-row">
                <input v-model="publishingForm.generate_article_images" type="checkbox" />
                生成正文配图
              </label>
              <label class="toggle-row">
                <input v-model="publishingForm.dedup_enable_llm_review" type="checkbox" />
                启用大模型去重复核
              </label>
              <label>
                最少正文图
                <input v-model.number="publishingForm.min_article_images" type="number" min="0" max="10" />
              </label>
              <label>
                最多正文图
                <input v-model.number="publishingForm.max_article_images" type="number" min="0" max="10" />
              </label>
              <label>
                文章新闻数量
                <input v-model.number="publishingForm.article_news_limit" type="number" min="1" max="50" />
              </label>
              <label>
                文章回看小时
                <input v-model.number="publishingForm.article_news_lookback_hours" type="number" min="1" max="168" />
              </label>
              <label>
                去重回看天数
                <input v-model.number="publishingForm.dedup_lookback_days" type="number" min="1" max="30" />
              </label>
              <label>
                直接判重阈值
                <input v-model="publishingForm.dedup_direct_similarity" type="number" min="0" max="1" step="0.01" />
              </label>
              <label>
                大模型复核阈值
                <input v-model="publishingForm.dedup_review_similarity" type="number" min="0" max="1" step="0.01" />
              </label>
            </div>
          </div>

          <div v-if="activeSettingsTab === 'layout'" class="settings-pane">
            <h3>视觉参数与实时预览</h3>
            <div class="layout-editor">
              <div class="layout-controls">
                <div class="config-grid">
                  <label>
                    版式模板
                    <select v-model="layoutForm.template_name">
                      <option value="clean">清爽资讯</option>
                      <option value="warm">温和科普</option>
                      <option value="compact">紧凑早报</option>
                    </select>
                  </label>
                  <label>
                    主色
                    <input v-model="layoutForm.primary_color" type="color" />
                  </label>
                  <label>
                    强调线颜色
                    <input v-model="layoutForm.accent_color" type="color" />
                  </label>
                  <label>
                    正文字号
                    <input v-model.number="layoutForm.body_font_size" type="number" min="12" max="20" />
                  </label>
                  <label>
                    标题字号
                    <input v-model.number="layoutForm.heading_font_size" type="number" min="14" max="26" />
                  </label>
                  <label>
                    行高
                    <input v-model="layoutForm.line_height" type="number" min="1.4" max="2.2" step="0.05" />
                  </label>
                  <label>
                    段落间距
                    <input v-model.number="layoutForm.section_spacing" type="number" min="12" max="48" />
                  </label>
                  <label>
                    图片圆角
                    <input v-model.number="layoutForm.image_radius" type="number" min="0" max="24" />
                  </label>
                </div>
                <label class="toggle-row">
                  <input v-model="layoutForm.show_group_heading" type="checkbox" />
                  显示分组标题
                </label>
                <label class="toggle-row">
                  <input v-model="layoutForm.show_editor_note" type="checkbox" />
                  显示编辑观察
                </label>
                <label class="toggle-row">
                  <input v-model="layoutForm.show_source" type="checkbox" />
                  显示来源
                </label>
              </div>
              <div class="layout-preview" :style="layoutPreviewStyle" aria-label="排版预览">
                <p class="layout-preview-kicker">公众号预览</p>
                <section v-if="layoutForm.show_group_heading" :style="layoutPreviewSectionStyle">
                  <h3 :style="layoutPreviewHeadingStyle">{{ usesRegionalGrouping ? contentGroupForms[0]?.name || '内容分组' : '精选内容' }}</h3>
                </section>
                <section :style="layoutPreviewSectionStyle">
                  <h2 :style="layoutPreviewHeadingStyle">01｜一条适合当前工作空间的内容标题</h2>
                  <p>这里展示正文段落的字号、行高和整体阅读密度。实际生成文章时，后端会用同一套参数渲染公众号 HTML。</p>
                  <div class="layout-preview-image" :style="layoutPreviewImageStyle"></div>
                  <blockquote v-if="layoutForm.show_editor_note" :style="{ borderLeftColor: layoutForm.accent_color }">
                    编辑观察：这里展示强调块的颜色和间距。
                  </blockquote>
                  <p v-if="layoutForm.show_source">
                    来源：<a :style="{ color: layoutForm.primary_color, borderBottomColor: layoutForm.primary_color }">示例来源</a>
                  </p>
                </section>
              </div>
            </div>
          </div>
        </form>
      </section>

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
                <span>{{ user.is_admin ? '管理员' : '普通用户' }} · 工作空间 ID {{ user.tenant_id || '未绑定' }} · {{ user.status }}</span>
              </div>
            </div>
            <p v-else class="empty-region">暂无账号。</p>
          </article>
        </div>
      </section>

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
</template>

