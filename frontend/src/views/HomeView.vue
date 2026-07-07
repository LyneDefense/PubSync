<script setup lang="ts">
// 首页 Hub —— UI·1 先放骨架占位,UI·2 填「接下来 + 我的账号/草稿 + 博主档案卡片墙」。
import { useRouter } from 'vue-router'
const router = useRouter()
</script>

<template>
  <section class="home">
    <h1 class="home-title">首页</h1>
    <p class="home-sub">对象驱动工作台 · 从这里选一个「东西」开始。</p>

    <div class="home-grid">
      <button type="button" class="home-tile" @click="router.push({ name: 'find' })">
        <strong>加对标博主</strong><span>搜索并采用一个想学的博主</span>
      </button>
      <button type="button" class="home-tile" @click="router.push({ name: 'drafts' })">
        <strong>发布草稿</strong><span>看历史创作与发布状态</span>
      </button>
      <button type="button" class="home-tile" @click="router.push({ name: 'create' })">
        <strong>开始创作</strong><span>用对标博主的画像写新内容</span>
      </button>
    </div>

    <p class="home-note">「接下来」提示、我的账号/草稿入口、博主档案卡片墙 —— 正在搭建(UI·2)。</p>
  </section>
</template>

<style scoped>
.home-title { margin: 0 0 4px; font-size: 21px; font-weight: 680; letter-spacing: -0.01em; }
.home-sub { margin: 0 0 20px; font-size: 13.5px; color: var(--color-ink-2); }
.home-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 10px;
  margin-bottom: 18px;
}
.home-tile {
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-align: left;
  padding: 15px 16px;
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  cursor: pointer;
  transition: border-color 120ms var(--ease-out);
}
.home-tile:hover { border-color: var(--color-accent-soft-bd); }
.home-tile strong { font-size: 14.5px; font-weight: 650; color: var(--color-ink); }
.home-tile span { font-size: 12.5px; color: var(--color-ink-3); }
.home-note { margin: 0; font-size: 12.5px; color: var(--color-ink-3); }
</style>
