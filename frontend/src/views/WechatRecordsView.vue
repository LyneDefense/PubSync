<script setup lang="ts">
// 公众号·发布记录（占位）。未来汇总每日早报与 AI 创作文章的草稿箱推送记录。
import ComingSoonPanel from '../components/ComingSoonPanel.vue'
import { activeMainTab, activeWechatTab } from '../composables/useWorkspaceStore'
</script>

<template>
  <ComingSoonPanel
    v-if="activeMainTab === 'wechat' && activeWechatTab === 'records'"
    title="公众号发布记录"
    description="这里会汇总每日早报和 AI 创作文章的草稿箱推送记录。"
  />
</template>
