<script setup lang="ts">
// 新架构未建成页面的统一占位:面包屑回首页 + 「建设中」。UI·3–UI·8 会逐个替换成真实视图。
import { useRoute, useRouter } from 'vue-router'
const route = useRoute()
const router = useRouter()
</script>

<template>
  <section class="ph">
    <button type="button" class="ph-crumb" @click="router.push({ name: 'home' })">← 首页</button>
    <div class="ph-card">
      <h2>{{ (route.meta.title as string) || '这个页面' }}</h2>
      <p>正在建设中,很快就好。</p>
    </div>
  </section>
</template>

<style scoped>
.ph-crumb {
  border: 0;
  background: none;
  cursor: pointer;
  font-size: 12.5px;
  color: var(--color-ink-3);
  padding: 0 0 14px;
}
.ph-crumb:hover { color: var(--color-accent-ink); }
.ph-card {
  border: 1px dashed var(--color-rule-strong);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  padding: 40px 24px;
  text-align: center;
}
.ph-card h2 { margin: 0 0 6px; font-size: 17px; font-weight: 650; color: var(--color-ink); }
.ph-card p { margin: 0; font-size: 13px; color: var(--color-ink-3); }
</style>
