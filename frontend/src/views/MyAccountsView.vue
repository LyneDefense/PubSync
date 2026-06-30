<script setup lang="ts">
// 社媒·我的账号:主从工作台 —— 左栏账号列表,右栏「账号概要卡 + 内容列表卡」。内容缓存,点刷新才重采。
import { computed, ref, watch } from 'vue'
import { statusTone } from '../utils/format'
import {
  accountPosts,
  currentSocialPlatformName,
  currentSocialTab,
  formatDate,
  handleCollectAccount,
  isSocialPlatform,
  loadAccountPosts,
  myAccounts,
  openCreateMyAccountModal,
  pendingAction
} from '../composables/useWorkspaceStore'

const selectedId = ref<number | null>(null)
const selectedAccount = computed(() => myAccounts.value.find((acc) => acc.id === selectedId.value) || null)
const sort = ref<'recent' | 'hot'>('recent')

function pick(id: number) {
  selectedId.value = id
  loadAccountPosts(id)
}

// 进页面/账号列表变化时,默认选中第一个账号并读缓存内容。
watch(
  () => [isSocialPlatform.value && currentSocialTab.value === 'my-accounts', myAccounts.value.length] as const,
  ([active]) => {
    if (active && selectedId.value === null && myAccounts.value.length) {
      pick(myAccounts.value[0].id)
    }
  },
  { immediate: true }
)

// 文字头像:名字首字 + 按 id 取一组柔和底色。
const AVATAR_BG = ['#eaf3ee', '#f0eef7', '#eef4f5', '#eef1f6', '#f6eef2', '#eef3f7']
const AVATAR_INK = ['#2f6b54', '#5a4a86', '#3a6a72', '#44506a', '#8a4a64', '#3a5a86']
function avatarStyle(id: number) {
  const i = (((id || 0) % AVATAR_BG.length) + AVATAR_BG.length) % AVATAR_BG.length
  return { background: AVATAR_BG[i], color: AVATAR_INK[i] }
}

const posts = computed(() => (selectedId.value ? accountPosts[selectedId.value] || [] : []))
function interaction(p: { like_count: number; favorite_count: number; comment_count: number }): number {
  return (p.like_count || 0) + (p.favorite_count || 0) + (p.comment_count || 0)
}
const maxInteraction = computed(() => posts.value.reduce((m, p) => Math.max(m, interaction(p)), 0))
const avgLikes = computed(() =>
  posts.value.length ? Math.round(posts.value.reduce((s, p) => s + (p.like_count || 0), 0) / posts.value.length) : 0
)

// 中文计数:≥1w 用「万」,否则原值。
function formatCount(n: number): string {
  const v = n || 0
  if (v >= 10000) {
    const w = v / 10000
    return `${w >= 100 ? Math.round(w) : Number(w.toFixed(1))}w`
  }
  return String(v)
}

const sortedPosts = computed(() => {
  const arr = [...posts.value]
  if (sort.value === 'hot') return arr.sort((a, b) => interaction(b) - interaction(a))
  return arr.sort((a, b) => (b.published_at || '').localeCompare(a.published_at || ''))
})

// 互动热度(相对本账号最高):0–100 → 色带 + 点亮的格数(信号条样式)。
function heatPct(p: { like_count: number; favorite_count: number; comment_count: number }): number {
  return maxInteraction.value ? Math.round((100 * interaction(p)) / maxInteraction.value) : 0
}
function heatBand(pct: number): string {
  return pct >= 75 ? 's-ok' : pct >= 35 ? 's-warn' : 's-low'
}
function heatLit(pct: number): number {
  return Math.max(1, Math.min(5, Math.round(pct / 20)))
}

// ASR 状态片:复用全站 status-chip 配色,但用转写语境的文案。
const ASR_LABEL: Record<string, string> = { succeeded: '已转写', running: '转写中', failed: '转写失败', not_required: '无需转写' }
function asrLabel(s: string): string {
  return ASR_LABEL[s] || s
}
</script>

<template>
  <section v-if="isSocialPlatform && currentSocialTab === 'my-accounts'" class="my-accounts">
    <header class="page-head">
      <h1>我的{{ currentSocialPlatformName }}账号</h1>
      <button type="button" class="primary" @click="openCreateMyAccountModal">+ 添加我的账号</button>
    </header>

    <div v-if="myAccounts.length" class="md-grid">
      <!-- 左栏:账号列表 -->
      <aside class="acct-card">
        <div class="acct-head">
          <h2>我的账号</h2>
          <span class="count">{{ myAccounts.length }}</span>
        </div>
        <div class="acct-list">
          <button
            v-for="acc in myAccounts"
            :key="acc.id"
            type="button"
            class="acct-row"
            :class="{ sel: selectedId === acc.id }"
            @click="pick(acc.id)"
          >
            <span class="avatar sm" :style="avatarStyle(acc.id)">{{ (acc.display_name || '?').slice(0, 1) }}</span>
            <span class="acct-body">
              <span class="acct-name">{{ acc.display_name }}</span>
              <span class="acct-sub">{{ acc.niche || '未设置领域' }} · 样本 {{ acc.sample_count }}</span>
            </span>
            <span class="chevron">›</span>
          </button>
        </div>
      </aside>

      <!-- 右栏:详情 -->
      <div v-if="selectedAccount" class="detail">
        <!-- 账号概要卡 -->
        <section class="card summary">
          <div class="sum-head">
            <span class="avatar lg" :style="avatarStyle(selectedAccount.id)">{{ (selectedAccount.display_name || '?').slice(0, 1) }}</span>
            <div class="sum-id">
              <div class="sum-name">
                {{ selectedAccount.display_name }}
                <span v-if="selectedAccount.niche" class="niche">{{ selectedAccount.niche }}</span>
              </div>
              <div class="sum-meta">
                <template v-if="selectedAccount.external_id">小红书号 {{ selectedAccount.external_id }} · </template>最近采集 {{ formatDate(selectedAccount.updated_at) }}
              </div>
            </div>
            <button
              type="button"
              class="refresh"
              :disabled="Boolean(pendingAction)"
              @click="handleCollectAccount(selectedAccount.id)"
            >
              {{ pendingAction === 'collect' ? '采集中…' : '↻ 刷新' }}
            </button>
          </div>

          <div class="stat-band">
            <div class="stat"><span>缓存内容</span><b>{{ posts.length }}</b></div>
            <div class="stat"><span>粉丝量</span><b>{{ formatCount(selectedAccount.follower_count) }}</b></div>
            <div class="stat"><span>篇均赞</span><b>{{ formatCount(avgLikes) }}</b></div>
            <div class="stat"><span>样本数</span><b>{{ selectedAccount.sample_count }}</b></div>
          </div>

          <div v-if="selectedAccount.tags?.length" class="tags">
            <span class="tags-label">内容标签</span>
            <span
              v-for="tag in selectedAccount.tags"
              :key="tag.name"
              class="tag-chip"
              :class="tag.source === 'manual' ? 'tag-chip--manual' : 'tag-chip--auto'"
            >{{ tag.name }}</span>
          </div>
        </section>

        <!-- 内容列表卡 -->
        <section class="card content">
          <div class="content-head">
            <div class="ch-l">
              <h2>内容列表</h2>
              <span v-if="posts.length" class="cache-n">缓存 {{ posts.length }} 篇</span>
            </div>
            <div class="seg">
              <button type="button" :class="{ on: sort === 'recent' }" @click="sort = 'recent'">最新</button>
              <button type="button" :class="{ on: sort === 'hot' }" @click="sort = 'hot'">最热</button>
            </div>
          </div>

          <div v-if="sortedPosts.length" class="post-list">
            <article v-for="(post, i) in sortedPosts" :key="post.id" class="post-row">
              <span class="seq">{{ String(i + 1).padStart(2, '0') }}</span>
              <div class="post-main">
                <div class="post-title">
                  {{ post.title || '(无标题)' }}
                  <span v-if="post.status === 'delisted'" class="tag-chip tag-chip--delisted">已下架</span>
                </div>
                <div class="post-meta">
                  赞 {{ formatCount(post.like_count) }} · 藏 {{ formatCount(post.favorite_count) }} · 评 {{ formatCount(post.comment_count) }}<template v-if="post.published_at"> · {{ formatDate(post.published_at) }}</template>
                </div>
              </div>
              <span class="heat" :class="heatBand(heatPct(post))" :title="`热度 ${heatPct(post)}`">
                <i v-for="b in 5" :key="b" :class="{ on: b <= heatLit(heatPct(post)) }"></i>
              </span>
              <span
                v-if="post.asr_status"
                class="status-chip"
                :class="`status-chip--${statusTone(post.asr_status)}`"
              >{{ asrLabel(post.asr_status) }}</span>
            </article>
          </div>
          <p v-else class="empty-region pad">这个账号还没有缓存内容。点「刷新(重新采集)」抓取最新内容。</p>
        </section>
      </div>
    </div>

    <p v-else class="empty-region card pad">还没有我的账号。点「添加我的账号」搜索并保存你的主页。</p>
  </section>
</template>

<style scoped>
.my-accounts {
  max-width: 1080px;
  margin: 0 auto;
}
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 18px;
}
.page-head h1 {
  margin: 0;
  font-size: 21px;
  font-weight: 680;
  letter-spacing: -0.01em;
}

/* 主从布局 */
.md-grid {
  display: grid;
  grid-template-columns: 264px minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}
.card {
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-lg);
}

/* 左栏 */
.acct-card {
  position: sticky;
  top: 0;
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-lg);
  overflow: hidden;
}
.acct-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--color-paper-3);
}
.acct-head h2 {
  margin: 0;
  font-size: 14px;
  font-weight: 650;
}
.count {
  min-width: 22px;
  height: 20px;
  padding: 0 7px;
  display: inline-grid;
  place-items: center;
  border-radius: var(--radius-pill);
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
  font-size: 12px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.acct-list {
  display: flex;
  flex-direction: column;
  padding: 8px;
  gap: 2px;
}
.acct-row {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 9px 10px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  cursor: pointer;
  text-align: left;
  transition: background 120ms var(--ease-out);
}
.acct-row:hover {
  background: #fafbfc;
}
.acct-row.sel {
  background: var(--color-accent-soft);
}
.avatar {
  display: grid;
  place-items: center;
  border-radius: 10px;
  font-weight: 600;
  flex: 0 0 auto;
}
.avatar.sm {
  width: 36px;
  height: 36px;
  font-size: 15px;
}
.avatar.lg {
  width: 52px;
  height: 52px;
  border-radius: 13px;
  font-size: 21px;
}
.acct-body {
  flex: 1;
  min-width: 0;
}
.acct-name {
  display: block;
  font-size: 13.5px;
  font-weight: 620;
  color: var(--color-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.acct-row.sel .acct-name {
  color: var(--color-accent-ink);
}
.acct-sub {
  display: block;
  margin-top: 2px;
  font-size: 11.5px;
  color: var(--color-ink-3);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.chevron {
  flex: 0 0 auto;
  color: var(--color-ink-3);
  font-size: 18px;
  line-height: 1;
}

/* 右栏 */
.detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.summary {
  padding: 20px 22px;
}
.sum-head {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}
.sum-id {
  flex: 1 1 200px;
  min-width: 160px;
}
.sum-name {
  display: flex;
  align-items: center;
  gap: 9px;
  font-size: 17px;
  font-weight: 680;
  color: var(--color-ink);
}
.niche {
  padding: 2px 9px;
  border-radius: var(--radius-pill);
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
  font-size: 12px;
  font-weight: 600;
}
.sum-meta {
  margin-top: 5px;
  font-size: 12.5px;
  color: var(--color-ink-3);
}
.refresh {
  flex: 0 0 auto;
  height: 34px;
  padding: 0 14px;
  border: 0;
  border-radius: 9px;
  background: var(--color-accent);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
  transition: background 140ms var(--ease-out);
}
.refresh:hover {
  background: var(--color-accent-press);
}
.refresh:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

/* 统计带:4 格,用 1px 间隙 + 外层底色模拟分隔 */
.stat-band {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1px;
  margin-top: 18px;
  background: var(--color-rule);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.stat {
  background: var(--color-surface);
  padding: 12px 14px;
  text-align: center;
}
.stat span {
  display: block;
  font-size: 11.5px;
  color: var(--color-ink-2);
  margin-bottom: 5px;
}
.stat b {
  font-size: 21px;
  font-weight: 700;
  color: var(--color-ink);
  font-variant-numeric: tabular-nums;
  line-height: 1;
}

/* 内容标签 */
.tags {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}
.tags-label {
  font-size: 12.5px;
  color: var(--color-ink-3);
  margin-right: 2px;
}

/* 内容列表卡 */
.content {
  padding: 18px 22px 8px;
}
.content-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}
.ch-l {
  display: flex;
  align-items: baseline;
  gap: 9px;
}
.ch-l h2 {
  margin: 0;
  font-size: 15px;
  font-weight: 650;
}
.cache-n {
  font-size: 12.5px;
  color: var(--color-ink-3);
}
.seg {
  display: inline-flex;
  gap: 2px;
  padding: 3px;
  background: var(--color-paper-3);
  border-radius: 9px;
}
.seg button {
  height: 28px;
  padding: 0 13px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--color-ink-2);
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  transition: background 120ms var(--ease-out);
}
.seg button.on {
  background: var(--color-surface);
  color: var(--color-ink);
  box-shadow: 0 1px 2px var(--color-shadow);
}

.post-list {
  display: flex;
  flex-direction: column;
}
.post-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 0;
  border-top: 1px solid var(--color-paper-3);
}
.post-row:first-child {
  border-top: 0;
}
.seq {
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  border-radius: 9px;
  background: var(--color-paper-3);
  color: var(--color-ink-3);
  font-size: 12px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.post-main {
  flex: 1;
  min-width: 0;
}
.post-title {
  font-size: 14px;
  font-weight: 550;
  color: var(--color-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.post-meta {
  margin-top: 3px;
  font-size: 12px;
  color: var(--color-ink-3);
  font-variant-numeric: tabular-nums;
}
/* 互动热度信号条 */
.heat {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: flex-end;
  gap: 2px;
  height: 18px;
}
.heat i {
  width: 3px;
  border-radius: 1px;
  background: var(--color-paper-3);
}
.heat i:nth-child(1) {
  height: 6px;
}
.heat i:nth-child(2) {
  height: 9px;
}
.heat i:nth-child(3) {
  height: 12px;
}
.heat i:nth-child(4) {
  height: 15px;
}
.heat i:nth-child(5) {
  height: 18px;
}
.heat.s-ok i.on {
  background: var(--color-ok);
}
.heat.s-warn i.on {
  background: var(--color-warn);
}
.heat.s-low i.on {
  background: var(--color-rule-strong);
}

.empty-region.pad {
  padding: 28px 20px;
}
.empty-region.card.pad {
  text-align: center;
}

@media (max-width: 900px) {
  .md-grid {
    grid-template-columns: 1fr;
  }
  .acct-card {
    position: static;
  }
}
</style>
