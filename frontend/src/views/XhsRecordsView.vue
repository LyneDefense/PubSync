<script setup lang="ts">
// 小红书·发布记录/设置（占位）。发布记录与平台设置能力后续开放。
import { computed } from 'vue'
import ComingSoonPanel from '../components/ComingSoonPanel.vue'
import { activeMainTab, activeXhsTab } from '../composables/useWorkspaceStore'

const title = computed(() => (activeXhsTab.value === 'records' ? '小红书发布记录' : '小红书设置'))
</script>

<template>
  <ComingSoonPanel
    v-if="activeMainTab === 'xhs' && (activeXhsTab === 'records' || activeXhsTab === 'settings')"
    :title="title"
    description="发布记录与平台设置能力后续开放。"
  />
</template>
