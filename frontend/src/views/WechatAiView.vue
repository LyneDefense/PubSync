<script setup lang="ts">
// 公众号·AI 创作面板。
// 状态与方法来自 useWorkspaceStore 单例；本组件仅负责该面板的视图与交互。
import {
  activeMainTab,
  activeWechatTab,
  article
} from '../composables/useWorkspaceStore'
</script>

<template>
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
</template>
