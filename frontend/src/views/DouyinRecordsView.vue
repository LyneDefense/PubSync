<script setup lang="ts">
// 抖音·发布记录/设置（占位）。发布记录与平台设置能力后续开放。
import { computed } from 'vue'
import ComingSoonPanel from '../components/ComingSoonPanel.vue'
import { activeMainTab, currentSocialTab } from '../composables/useWorkspaceStore'

const title = computed(() => (currentSocialTab.value === 'records' ? '抖音发布记录' : '抖音设置'))
</script>

<template>
  <ComingSoonPanel
    v-if="activeMainTab === 'douyin' && (currentSocialTab === 'records' || currentSocialTab === 'settings')"
    :title="title"
    description="发布记录与平台设置能力后续开放。"
  />
</template>
