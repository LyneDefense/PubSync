<script setup lang="ts">
// 找对标(精确搜索):知道名字/关键词直接搜 → 「采用」加入对标库。
// 泛搜索/找相似已移除——发现交给小红书本身更强,我们做精确查找 + 后续「对标分析」诊断它值不值得学。
import { ref } from 'vue'

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
  <section v-if="isSocialPlatform && currentSocialTab === 'find'" class="panel find-benchmark">
    <div class="section-header">
      <div>
        <h2>找对标博主</h2>
        <p class="toolbar-subtitle">知道名字或关键词直接搜,「采用」即加入{{ currentSocialPlatformName }}对标库;再去「对标分析」诊断它值不值得学。</p>
      </div>
    </div>

    <div class="fb-precise">
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
.fb-search-row { display: flex; gap: 10px; margin-bottom: 12px; }
.fb-search-row input { flex: 1; }
.fb-results { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.fb-results li { display: flex; align-items: center; gap: 10px; border: 1px solid var(--color-field-border, #c8ced4); border-radius: 12px; padding: 10px 12px; }
.fb-results img { width: 40px; height: 40px; border-radius: 50%; object-fit: cover; flex: none; }
.fb-r-body { display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1; }
.fb-r-body small { color: var(--color-ink-2, #6b7280); font-size: 0.8rem; }
</style>
