<script setup lang="ts">
// 工作台主区:承载某个平台下的所有功能视图。每个子视图自行按 store 的平台/页签门控显隐,
// 路由只负责把 URL 同步到 store(见 App.vue),因此这里把全部视图平铺即可。
import BloggerFormModal from '../components/BloggerFormModal.vue'
import ComingSoonPanel from '../components/ComingSoonPanel.vue'
import ImagePreviewModal from '../components/ImagePreviewModal.vue'
import MiniProgressBanner from '../components/MiniProgressBanner.vue'
import OverviewView from './OverviewView.vue'
import FindBenchmarkView from './FindBenchmarkView.vue'
import WechatBriefView from './WechatBriefView.vue'
import WechatAiView from './WechatAiView.vue'
import WechatRecordsView from './WechatRecordsView.vue'
import BloggerDossierView from './BloggerDossierView.vue'
import BenchmarkAnalysisView from './BenchmarkAnalysisView.vue'
import SocialPackagesView from './SocialPackagesView.vue'
import SocialHistoryView from './SocialHistoryView.vue'
import XhsRecordsView from './XhsRecordsView.vue'
import DouyinRecordsView from './DouyinRecordsView.vue'
import WorkspaceSettingsView from './WorkspaceSettingsView.vue'

import {
  activeMainTab,
  activeWechatTab,
  closeImagePreview,
  currentSocialPlatformName,
  currentSocialTab,
  isSocialPlatform,
  previewImage
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

  <BenchmarkAnalysisView />

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

  <BloggerFormModal />

  <ImagePreviewModal :image="previewImage" @close="closeImagePreview" />
</template>
