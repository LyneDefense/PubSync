<script setup lang="ts">
// 工作台主区:承载某个平台下的所有功能视图。每个子视图自行按 store 的平台/页签门控显隐,
// 路由只负责把 URL 同步到 store(见 App.vue),因此这里把全部视图平铺即可。
import ComingSoonPanel from '../components/ComingSoonPanel.vue'
import ImagePreviewModal from '../components/ImagePreviewModal.vue'
import MiniProgressBanner from '../components/MiniProgressBanner.vue'
import OverviewView from './OverviewView.vue'
import FindBenchmarkView from './FindBenchmarkView.vue'
import SkillOptimizeView from './SkillOptimizeView.vue'
import EffectsDashboardView from './EffectsDashboardView.vue'
import WechatBriefView from './WechatBriefView.vue'
import WechatAiView from './WechatAiView.vue'
import WechatRecordsView from './WechatRecordsView.vue'
import BloggerDossierView from './BloggerDossierView.vue'
import SocialCollectView from './SocialCollectView.vue'
import SocialDistillView from './SocialDistillView.vue'
import SocialAssetsView from './SocialAssetsView.vue'
import MyAccountsView from './MyAccountsView.vue'
import SelfDiagnosisView from './SelfDiagnosisView.vue'
import BenchmarkAnalysisView from './BenchmarkAnalysisView.vue'
import SocialPackagesView from './SocialPackagesView.vue'
import SocialHistoryView from './SocialHistoryView.vue'
import XhsRecordsView from './XhsRecordsView.vue'
import DouyinRecordsView from './DouyinRecordsView.vue'
import WorkspaceSettingsView from './WorkspaceSettingsView.vue'

import {
  activeMainTab,
  activeWechatTab,
  bloggerForm,
  bloggerModalAccountType,
  bloggerSearchKeyword,
  bloggerSearchResults,
  closeBloggerModal,
  closeImagePreview,
  currentSocialPlatform,
  currentSocialPlatformName,
  currentSocialTab,
  editingBlogger,
  handleCreateBlogger,
  handleSearchBloggerCandidates,
  isSocialPlatform,
  pendingAction,
  previewImage,
  selectBloggerCandidate,
  selectedBloggerCandidate,
  showBloggerModal
} from '../composables/useWorkspaceStore'
</script>

<template>
  <MiniProgressBanner />

  <OverviewView />

  <FindBenchmarkView />

  <BloggerDossierView />

  <WechatBriefView />

  <ComingSoonPanel
    v-if="activeMainTab === 'wechat' && activeWechatTab === 'distill'"
    title="公众号博主蒸馏"
    description="未来支持采集公众号文章样本、蒸馏风格资产，再应用风格生成公众号文章。"
  />

  <WechatAiView />

  <WechatRecordsView />

  <SocialCollectView />

  <SocialDistillView />

  <SocialAssetsView />

  <MyAccountsView />

  <SelfDiagnosisView />

  <BenchmarkAnalysisView />

  <SocialPackagesView />

  <SocialHistoryView />

  <ComingSoonPanel
    v-if="isSocialPlatform && currentSocialTab === 'freecreate'"
    :title="`${currentSocialPlatformName}自由创作`"
    description="未来支持不依赖对标博主、直接输入主题由 AI 自主创作内容。"
  />

  <EffectsDashboardView />

  <SkillOptimizeView />

  <XhsRecordsView />

  <DouyinRecordsView />

  <WorkspaceSettingsView />

  <div v-if="showBloggerModal" class="modal-backdrop" role="presentation" @click.self="closeBloggerModal">
    <form class="modal-panel" role="dialog" aria-modal="true" :aria-label="`${editingBlogger ? '编辑' : '创建'}${currentSocialPlatformName}博主`" @submit.prevent="handleCreateBlogger">
      <div class="section-header">
        <div>
          <h2>{{ editingBlogger ? '编辑博主信息' : bloggerModalAccountType === 'mine' ? '添加我的账号' : '确认对标博主' }}</h2>
          <p class="toolbar-subtitle">{{ editingBlogger ? '只能编辑基础信息，不会修改已有采集和蒸馏结果。' : bloggerModalAccountType === 'mine' ? '搜索并选择你的账号主页，补充信息后保存。' : '补充领域和备注后保存。' }}</p>
        </div>
        <button type="button" class="ghost" @click="closeBloggerModal">关闭</button>
      </div>
      <!-- 创建对标博主:候选来自「找对标博主」页(采用后弹此框确认);未选则提示去找对标。 -->
      <p v-if="!editingBlogger && bloggerModalAccountType === 'benchmark' && !selectedBloggerCandidate" class="empty-region">
        请先到「找对标博主」找到并「采用」一个博主,再补充资料保存。
      </p>
      <!-- 创建「我的账号」:沿用简单搜索即可。 -->
      <template v-else-if="!editingBlogger && bloggerModalAccountType === 'mine'">
        <div class="search-row">
          <label>
            搜索{{ currentSocialPlatformName }}博主
            <input v-model="bloggerSearchKeyword" type="search" placeholder="输入昵称或关键词" @keydown.enter.prevent="handleSearchBloggerCandidates" />
          </label>
          <button type="button" class="primary" :disabled="Boolean(pendingAction)" @click="handleSearchBloggerCandidates">
            {{ pendingAction === 'blogger-search' ? '搜索中' : '搜索' }}
          </button>
        </div>
        <div v-if="bloggerSearchResults.length" class="candidate-list" aria-label="博主搜索结果">
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
        <p v-else-if="bloggerSearchKeyword" class="empty-region">搜索后会在这里展示候选博主。</p>
      </template>
      <label>
        博主名称
        <input v-model="bloggerForm.display_name" type="text" required readonly />
      </label>
      <label>
        {{ currentSocialPlatformName }}主页链接
        <input
          v-model="bloggerForm.homepage_url"
          type="url"
          required
          readonly
          :placeholder="currentSocialPlatform === 'douyin' ? 'https://www.douyin.com/user/...' : 'https://www.xiaohongshu.com/user/profile/...'"
        />
      </label>
      <div v-if="editingBlogger" class="config-grid">
        <label>
          平台 ID
          <input v-model="bloggerForm.external_id" type="text" readonly />
        </label>
        <label>
          头像 URL
          <input v-model="bloggerForm.avatar_url" type="url" readonly />
        </label>
        <label>
          粉丝数
          <input v-model.number="bloggerForm.follower_count" type="number" readonly />
        </label>
      </div>
      <p v-if="editingBlogger" class="field-hint">昵称 / 主页 / 平台ID / 头像 / 粉丝数 不可手动修改；如需更新,到「博主资产」点「刷新博主」重新拉取。</p>
      <label>
        领域/赛道
        <input v-model="bloggerForm.niche" type="text" placeholder="宠物、母婴、美妆、AI工具…" />
      </label>
      <label v-if="editingBlogger">
        手动标签
        <input v-model="bloggerForm.tags" type="text" placeholder="逗号分隔，如：职场干货，副业，效率工具" />
        <small class="field-hint">手动标签会一直保留；采集时系统会自动追加内容标签（每次重算）。</small>
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
</template>
