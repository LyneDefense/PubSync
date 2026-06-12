<script setup lang="ts">
// 公众号·发布记录。
// 状态与方法来自 useWorkspaceStore 单例；本组件仅负责该面板的视图与交互。
import {
  activeMainTab,
  activeWechatTab
} from '../composables/useWorkspaceStore'
</script>

<template>
      <section v-if="activeMainTab === 'wechat' && activeWechatTab === 'records'" class="panel">
        <div class="section-header">
          <div>
            <h2>公众号发布记录</h2>
            <p class="toolbar-subtitle">这里会汇总每日早报和 AI 创作文章的草稿箱推送记录。</p>
          </div>
        </div>
        <p class="empty-region">发布记录模块暂未开放。</p>
      </section>
</template>
