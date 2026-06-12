<script setup lang="ts">
// 抖音·发布记录/设置（占位面板）。
// 状态与方法来自 useWorkspaceStore 单例；本组件仅负责该面板的视图与交互。
import {
  activeMainTab,
  currentSocialTab
} from '../composables/useWorkspaceStore'
</script>

<template>
      <section v-if="activeMainTab === 'douyin' && (currentSocialTab === 'records' || currentSocialTab === 'settings')" class="panel">
        <div class="section-header">
          <div>
            <h2>{{ currentSocialTab === 'records' ? '抖音发布记录' : '抖音设置' }}</h2>
            <p class="toolbar-subtitle">发布记录和平台设置能力后续开放。</p>
          </div>
        </div>
        <p class="empty-region">该模块暂未开放。</p>
      </section>
</template>
