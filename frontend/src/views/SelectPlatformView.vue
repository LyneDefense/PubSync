<script setup lang="ts">
// 登录后的「选择平台」落地页:选一个平台 → 进入该平台工作台(/{platform}/{默认页签})。
import { useRouter } from 'vue-router'
import { DEFAULT_TAB } from '../router'
import type { PlatformParam } from '../router'

const router = useRouter()

const PLATFORM_CARDS: Array<{
  id: PlatformParam
  name: string
  tagline: string
  desc: string
  badge?: string
  disabled?: boolean
}> = [
  {
    id: 'xhs',
    name: '小红书',
    tagline: '对标蒸馏 · 账号诊断 · AI 创作',
    desc: '选对标博主，蒸馏打法，生成你能日更的图文笔记，并诊断与头部的差距。'
  },
  {
    id: 'douyin',
    name: '抖音',
    tagline: '对标蒸馏 · 账号诊断 · AI 创作',
    desc: '采集对标博主作品，蒸馏脚本风格，生成口播/图文内容与诊断报告。'
  },
  {
    id: 'wechat',
    name: '公众号',
    tagline: '每日早报',
    desc: '面向实体店/本地经营的每日早报与素材，功能逐步完善中。',
    badge: '降级'
  }
]

function enter(card: (typeof PLATFORM_CARDS)[number]) {
  if (card.disabled) return
  router.push({ name: 'workspace', params: { platform: card.id, tab: DEFAULT_TAB[card.id] } })
}
</script>

<template>
  <section class="platform-select">
    <header class="platform-select-head">
      <h1>选择平台</h1>
      <p>每个平台是一个独立工作台。选一个开始，顶栏随时可切换。</p>
    </header>
    <div class="platform-cards">
      <button
        v-for="card in PLATFORM_CARDS"
        :key="card.id"
        type="button"
        class="platform-card"
        :class="{ disabled: card.disabled }"
        @click="enter(card)"
      >
        <div class="platform-card-top">
          <strong>{{ card.name }}</strong>
          <span v-if="card.badge" class="platform-card-badge">{{ card.badge }}</span>
        </div>
        <span class="platform-card-tagline">{{ card.tagline }}</span>
        <p class="platform-card-desc">{{ card.desc }}</p>
        <span class="platform-card-cta">进入 →</span>
      </button>
    </div>
  </section>
</template>

<style scoped>
.platform-select {
  max-width: 960px;
  margin: 0 auto;
  padding: 48px 20px;
}
.platform-select-head h1 {
  margin: 0 0 8px;
  font-size: 1.6rem;
}
.platform-select-head p {
  margin: 0 0 28px;
  color: var(--color-text-muted, #6b7280);
}
.platform-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(260px, 100%), 1fr));
  gap: 16px;
}
.platform-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  text-align: left;
  padding: 20px;
  border: 1px solid var(--color-field-border, #c8ced4);
  border-radius: 14px;
  background: var(--color-field, #fff);
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s, transform 0.1s;
}
.platform-card:hover {
  border-color: var(--color-accent, #2563eb);
  box-shadow: var(--ring-accent, 0 0 0 3px rgba(37, 99, 235, 0.15));
}
.platform-card:active {
  transform: translateY(1px);
}
.platform-card.disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.platform-card-top {
  display: flex;
  align-items: center;
  gap: 8px;
}
.platform-card-top strong {
  font-size: 1.2rem;
}
.platform-card-badge {
  font-size: 0.72rem;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--color-soft, #f1f3f5);
  color: var(--color-text-muted, #6b7280);
}
.platform-card-tagline {
  font-size: 0.85rem;
  color: var(--color-accent, #2563eb);
}
.platform-card-desc {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.5;
  color: var(--color-text-muted, #6b7280);
}
.platform-card-cta {
  margin-top: auto;
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--color-text, #111827);
}
</style>
