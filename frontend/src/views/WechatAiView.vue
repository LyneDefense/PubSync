<script setup lang="ts">
// 公众号·AI 创作（占位）。未来支持博主风格创作与自主 AI 创作，生成公众号文章并复用预览/草稿箱能力。
import ComingSoonPanel from '../components/ComingSoonPanel.vue'
import { activeMainTab, activeWechatTab } from '../composables/useWorkspaceStore'
</script>

<template>
  <ComingSoonPanel
    v-if="activeMainTab === 'wechat' && activeWechatTab === 'ai'"
    title="公众号 AI 创作"
    description="博主风格创作与自主 AI 创作，将生成公众号文章并复用预览、草稿箱发布能力。"
  />
</template>
