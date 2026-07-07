<script setup lang="ts">
// 找对标(精确搜索):知道名字/关键词直接搜 → 「采用」加入对标库 → 去「对标分析」诊断值不值得学。
// 搜索 Hero + 试试建议 + 结果卡 + 采用态 + idle/nomatch 空态。逻辑沿用 searchBloggers / adoptBenchmarkCandidate。
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
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

// embedded = 对象驱动新架构下的 /find(无平台门,自带平台切换);默认沿用当前平台。
const props = defineProps<{ embedded?: boolean }>()
const router = useRouter()
const platform = ref<'xhs' | 'douyin'>(currentSocialPlatform.value)
const activePlatform = computed(() => (props.embedded ? platform.value : currentSocialPlatform.value))
const activePlatformName = computed(() => (activePlatform.value === 'douyin' ? '抖音' : '小红书'))

const keyword = ref('')
const searching = ref(false)
const searched = ref(false)
const lastKeyword = ref('')
const results = ref<BloggerSearchResult[]>([])
const adopted = ref<string[]>([])

// 名字首字头像兜底:按 external_id 取一组柔和底色。
const AVATAR_BG = ['#eaf3ee', '#f0eef7', '#eef4f5', '#eef1f6', '#f6eef2', '#eef3f7']
const AVATAR_INK = ['#2f6b54', '#5a4a86', '#3a6a72', '#44506a', '#8a4a64', '#3a5a86']
function avatarStyle(key: string) {
  const h = [...(key || '?')].reduce((a, c) => a + c.charCodeAt(0), 0)
  const i = h % AVATAR_BG.length
  return { background: AVATAR_BG[i], color: AVATAR_INK[i] }
}

// 粉丝数:数字 ≥1w 用「万」;已是字符串(如 "12.4w")则原样。
function formatFans(v: number | string): string {
  const n = typeof v === 'number' ? v : Number(v)
  if (!Number.isFinite(n)) return String(v)
  if (n >= 10000) {
    const w = n / 10000
    return `${w >= 100 ? Math.round(w) : Number(w.toFixed(1))}w`
  }
  return String(n)
}

async function doSearch() {
  const kw = keyword.value.trim()
  if (!kw) {
    showMessage('请输入博主名称或关键词', true)
    return
  }
  searching.value = true
  try {
    results.value = await searchBloggers(activePlatform.value, kw)
    lastKeyword.value = kw
    searched.value = true
  } catch (error) {
    showMessage(error instanceof Error ? error.message : '搜索失败', true)
  } finally {
    searching.value = false
  }
}
function adopt(r: BloggerSearchResult) {
  adoptBenchmarkCandidate(r)
  if (!adopted.value.includes(r.external_id)) adopted.value.push(r.external_id)
}
</script>

<template>
  <section v-if="embedded || (isSocialPlatform && currentSocialTab === 'find')" class="find-benchmark" :class="{ 'is-embedded': embedded }">
    <!-- 新架构 /find:面包屑 + 平台切换(无平台门,搜哪个平台自己选)。 -->
    <div v-if="embedded" class="fb-crumbrow">
      <button type="button" class="fb-crumb" @click="router.push({ name: 'home' })">← 首页 / 加对标博主</button>
      <div class="fb-plat" role="tablist" aria-label="选择平台">
        <button type="button" role="tab" :class="{ 'is-on': platform === 'xhs' }" @click="platform = 'xhs'">小红书</button>
        <button type="button" role="tab" :class="{ 'is-on': platform === 'douyin' }" @click="platform = 'douyin'">抖音</button>
      </div>
    </div>
    <header v-else class="fb-head">
      <h1>查找博主</h1>
      <p>知道名字或关键词直接搜,「采用」即加入{{ currentSocialPlatformName }}对标库;再去「对标分析」诊断它值不值得学。</p>
    </header>

    <!-- 搜索 Hero -->
    <div class="search-hero">
      <div class="search-row">
        <div class="search-box">
          <svg class="s-ico" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></svg>
          <input
            v-model="keyword"
            type="search"
            placeholder="输入博主名称或关键词"
            @keydown.enter.prevent="doSearch"
          />
          <button v-if="keyword" type="button" class="clear" aria-label="清空" @click="keyword = ''">✕</button>
        </div>
        <button type="button" class="search-btn" :disabled="!keyword.trim() || searching" @click="doSearch">
          {{ searching ? '搜索中' : '搜索' }}
        </button>
      </div>
      <p class="search-hint">如果找不到博主,可以点开博主主页复制 Ta 的{{ activePlatformName }}号进行精确搜索喔。</p>
    </div>

    <!-- 结果 / 空态 -->
    <template v-if="searched">
      <template v-if="results.length">
        <div class="result-count">
          找到 <b>{{ results.length }}</b> 个匹配「{{ lastKeyword }}」的博主
          <span class="rc-note">已采用的会进入「博主资产」</span>
        </div>
        <div class="result-list">
          <article v-for="r in results" :key="r.external_id" class="result-card">
            <img v-if="r.avatar_url" :src="r.avatar_url" class="r-avatar" alt="" referrerpolicy="no-referrer" />
            <span v-else class="r-avatar fallback" :style="avatarStyle(r.external_id)">{{ (r.display_name || '?').slice(0, 1) }}</span>
            <div class="r-body">
              <div class="r-name">
                {{ r.display_name }}
                <span class="r-fans">{{ formatFans(r.follower_count) }} 粉丝</span>
              </div>
              <div class="r-desc">{{ r.description || '暂无简介' }}</div>
            </div>
            <button v-if="adopted.includes(r.external_id)" type="button" class="r-adopt adopted" disabled>✓ 已采用</button>
            <button v-else type="button" class="r-adopt" @click="adopt(r)">采用 →</button>
          </article>
        </div>
      </template>
      <div v-else class="empty-card">
        <span class="empty-ico"><svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></svg></span>
        <p class="empty-title">没搜到「{{ lastKeyword }}」</p>
        <p class="empty-sub">换个名字或更宽泛的关键词试试。</p>
      </div>
    </template>
    <div v-else class="empty-card">
      <span class="empty-ico"><svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></svg></span>
      <p class="empty-title">搜一个博主开始</p>
      <p class="empty-sub">输入名字或关键词,采用后去「对标分析」诊断它值不值得学。</p>
    </div>
  </section>
</template>

<style scoped>
.find-benchmark {
  max-width: 760px;
  margin: 0 auto;
}
/* 嵌入 /find 时:宽度交给外壳容器,顶部换面包屑 + 平台切换。 */
.find-benchmark.is-embedded { max-width: none; margin: 0; }
.fb-crumbrow {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}
.fb-crumb { border: 0; background: none; cursor: pointer; font-size: 12.5px; color: var(--color-ink-3); padding: 0; }
.fb-crumb:hover { color: var(--color-accent-ink); }
.fb-plat {
  display: inline-flex; gap: 2px; padding: 3px;
  border: 1px solid var(--color-field-border); border-radius: 10px; background: var(--color-paper-3);
}
.fb-plat button {
  height: 28px; padding: 0 14px; border: 0; border-radius: 7px;
  background: transparent; color: var(--color-ink-2); font-size: 12.5px; font-weight: 560; cursor: pointer;
}
.fb-plat button.is-on { background: var(--color-surface); color: var(--color-ink); box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06); }
.fb-head {
  margin-bottom: 18px;
}
.fb-head h1 {
  margin: 0 0 6px;
  font-size: 21px;
  font-weight: 680;
  letter-spacing: -0.01em;
}
.fb-head p {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.6;
  color: var(--color-ink-2);
}

/* 搜索 Hero */
.search-hero {
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-lg);
  padding: 18px 20px;
  margin-bottom: 18px;
}
.search-row {
  display: flex;
  gap: 10px;
}
.search-box {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 9px;
  height: 46px;
  padding: 0 14px;
  border: 1px solid var(--color-field-border);
  border-radius: 11px;
  background: var(--color-field);
  transition: border-color 140ms var(--ease-out);
}
.search-box:focus-within {
  border-color: var(--color-accent);
}
.s-ico {
  flex: 0 0 auto;
  color: var(--color-ink-3);
}
.search-box input {
  flex: 1;
  min-width: 0;
  height: 100%;
  border: 0;
  background: transparent;
  font-size: 15px;
  color: var(--color-ink);
  outline: none;
  padding: 0;
}
.search-box input::-webkit-search-cancel-button {
  display: none;
}
/* 干掉全局 input:focus 的柔光环——这里描边已经由外层 .search-box:focus-within 接管。 */
.search-box input:focus {
  box-shadow: none;
  border: 0;
}
.clear {
  flex: 0 0 auto;
  width: 22px;
  height: 22px;
  border: 0;
  border-radius: 50%;
  background: var(--color-paper-3);
  color: var(--color-ink-3);
  font-size: 11px;
  cursor: pointer;
  line-height: 1;
}
.clear:hover {
  background: var(--color-rule-strong);
}
.search-btn {
  flex: 0 0 auto;
  height: 46px;
  padding: 0 22px;
  border: 0;
  border-radius: 11px;
  background: var(--color-accent);
  color: #fff;
  font-size: 15px;
  font-weight: 620;
  cursor: pointer;
  transition: background 140ms var(--ease-out);
}
.search-btn:hover {
  background: var(--color-accent-press);
}
.search-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* 搜不到时的提示 */
.search-hint {
  margin: 12px 0 0;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--color-ink-3);
}

/* 结果计数 */
.result-count {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 13.5px;
  color: var(--color-ink-2);
}
.result-count b {
  color: var(--color-ink);
  font-variant-numeric: tabular-nums;
}
.rc-note {
  margin-left: auto;
  font-size: 12.5px;
  color: var(--color-ink-3);
}

/* 结果卡 */
.result-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.result-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: 13px;
  transition: box-shadow 140ms var(--ease-out);
}
.result-card:hover {
  box-shadow: 0 4px 14px var(--color-shadow);
}
.r-avatar {
  flex: 0 0 auto;
  width: 46px;
  height: 46px;
  border-radius: 50%;
  object-fit: cover;
}
.r-avatar.fallback {
  display: grid;
  place-items: center;
  font-size: 18px;
  font-weight: 600;
}
.r-body {
  flex: 1;
  min-width: 0;
}
.r-name {
  display: flex;
  align-items: center;
  gap: 9px;
  font-size: 15px;
  font-weight: 650;
  color: var(--color-ink);
}
.r-fans {
  flex: 0 0 auto;
  padding: 2px 9px;
  border-radius: var(--radius-pill);
  background: var(--color-paper-3);
  color: var(--color-ink-2);
  font-size: 11.5px;
  font-weight: 550;
  font-variant-numeric: tabular-nums;
}
.r-desc {
  margin-top: 4px;
  font-size: 12.5px;
  color: var(--color-ink-3);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-adopt {
  flex: 0 0 auto;
  height: 36px;
  padding: 0 16px;
  border: 1px solid var(--color-accent);
  border-radius: 10px;
  background: var(--color-surface);
  color: var(--color-accent-ink);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition:
    background 140ms var(--ease-out),
    color 140ms var(--ease-out);
}
.r-adopt:hover {
  background: var(--color-accent);
  color: #fff;
}
.r-adopt.adopted {
  border-color: transparent;
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
  cursor: default;
}

/* 空态卡 */
.empty-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 48px 24px;
  border: 1px dashed var(--color-rule-strong);
  border-radius: var(--radius-lg);
  text-align: center;
}
.empty-ico {
  display: grid;
  place-items: center;
  width: 56px;
  height: 56px;
  margin-bottom: 8px;
  border-radius: 50%;
  background: var(--color-accent-soft);
  color: var(--color-accent);
}
.empty-title {
  margin: 0;
  font-size: 15px;
  font-weight: 650;
  color: var(--color-ink);
}
.empty-sub {
  margin: 0;
  font-size: 12.5px;
  color: var(--color-ink-3);
}

@media (max-width: 560px) {
  .search-row {
    flex-wrap: wrap;
  }
  .search-btn {
    flex: 1 0 100%;
  }
}
</style>
