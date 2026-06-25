<script setup lang="ts">
// 找对标:两个入口 —— 泛搜索(帮你扒出合适的号,多步向导)/ 精确搜索(知道名字/关键词直接搜)。
// 评分搬去了对标库;这里只负责"找到 + 采用进库"。
import { ref } from 'vue'

import DiscoverySearch from './DiscoverySearch.vue'
import { searchBloggers } from '../api'
import type { BloggerSearchResult } from '../api/types'
import {
  adoptBenchmarkCandidate,
  currentSocialPlatform,
  currentSocialPlatformName,
  currentSocialTab,
  isSocialPlatform,
  showMessage
} from '../composables/useWorkspaceStore'

const entry = ref<'discovery' | 'precise'>('discovery')

// 精确搜索:关键词/姓名 → 平台搜索 → 采用(不评分)。
const keyword = ref('')
const searching = ref(false)
const results = ref<BloggerSearchResult[]>([])

async function doSearch() {
  const kw = keyword.value.trim()
  if (!kw) {
    showMessage('请输入博主名称或关键词', true)
    return
  }
  searching.value = true
  try {
    results.value = await searchBloggers(currentSocialPlatform.value, kw)
    if (!results.value.length) showMessage('没搜到匹配的博主，换个词试试', true)
  } catch (error) {
    showMessage(error instanceof Error ? error.message : '搜索失败', true)
  } finally {
    searching.value = false
  }
}
</script>

<template>
  <section v-if="isSocialPlatform && currentSocialTab === 'find'" class="panel find-benchmark" :class="{ wide: entry === 'discovery' }">
    <div class="section-header">
      <div>
        <h2>选对标</h2>
        <p class="toolbar-subtitle">不知道学谁用「泛搜索」帮你扒；知道名字用「精确搜索」直接找。选中采用，即加入{{ currentSocialPlatformName }}对标库。</p>
      </div>
    </div>

    <div class="fb-entries" role="tablist">
      <button type="button" role="tab" :class="{ active: entry === 'discovery' }" @click="entry = 'discovery'">泛搜索</button>
      <button type="button" role="tab" :class="{ active: entry === 'precise' }" @click="entry = 'precise'">精确搜索</button>
    </div>

    <DiscoverySearch v-if="entry === 'discovery'" />

    <div v-else class="fb-precise">
      <div class="fb-search-row">
        <input v-model="keyword" type="search" placeholder="输入博主名称或关键词" @keydown.enter.prevent="doSearch" />
        <button type="button" class="primary" :disabled="searching" @click="doSearch">{{ searching ? '搜索中' : '搜索' }}</button>
      </div>
      <ul v-if="results.length" class="fb-results">
        <li v-for="r in results" :key="r.external_id">
          <img v-if="r.avatar_url" :src="r.avatar_url" alt="" />
          <span class="fb-r-body">
            <strong>{{ r.display_name }}</strong>
            <small>{{ r.follower_count }} 粉丝 · {{ r.description || '暂无简介' }}</small>
          </span>
          <button type="button" @click="adoptBenchmarkCandidate(r)">采用 →</button>
        </li>
      </ul>
      <p v-else class="empty-region">搜索后在这里展示结果，点「采用」加入对标库。</p>
    </div>
  </section>
</template>

<style scoped>
.find-benchmark { max-width: 820px; }
.find-benchmark.wide { max-width: 1120px; }
.fb-entries { display: flex; gap: 8px; margin-bottom: 16px; }
.fb-entries button { padding: 6px 16px; border: 1px solid var(--color-field-border, #c8ced4); border-radius: 999px; background: var(--color-field, #fff); cursor: pointer; }
.fb-entries button.active { background: var(--color-accent, #2563eb); color: #fff; border-color: var(--color-accent, #2563eb); }
.fb-search-row { display: flex; gap: 10px; margin-bottom: 12px; }
.fb-search-row input { flex: 1; }
.fb-results { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.fb-results li { display: flex; align-items: center; gap: 10px; border: 1px solid var(--color-field-border, #c8ced4); border-radius: 12px; padding: 10px 12px; }
.fb-results img { width: 40px; height: 40px; border-radius: 50%; object-fit: cover; flex: none; }
.fb-r-body { display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1; }
.fb-r-body small { color: var(--color-ink-2, #6b7280); font-size: 0.8rem; }
</style>
