<script setup lang="ts">
// 全站统一的「敬请期待」占位面板：替换各处零散、措辞不一的空状态。
// 规划中但未实现的功能阶段（公众号的博主蒸馏/AI创作、各平台的自由创作/发布记录/设置）都复用它。
defineProps<{ title: string; description?: string }>()
</script>

<template>
  <section class="panel coming-soon">
    <div class="section-header">
      <div>
        <h2>{{ title }}</h2>
        <p v-if="description" class="toolbar-subtitle">{{ description }}</p>
      </div>
    </div>
    <div class="coming-soon-body">
      <span class="coming-soon-badge">敬请期待</span>
      <p class="empty-region">该模块正在规划中，稍后开放。</p>
    </div>
  </section>
</template>

<style scoped>
.coming-soon-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-sm);
  padding: var(--space-2xl, 48px) var(--space-md);
  text-align: center;
}

.coming-soon-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border: var(--rule-hair);
  border-radius: 999px;
  background: var(--color-surface-2, transparent);
  color: var(--color-ink-3);
  font-size: var(--text-sm);
  letter-spacing: 0.08em;
}
</style>
