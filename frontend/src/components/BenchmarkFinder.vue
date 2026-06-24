<script setup lang="ts">
// 找对标博主:顶部公用「你的方向」(打分依据,填一次),下面两个入口 ——
//  · 智能推荐:不知道学谁,按方向找一批候选。
//  · 指定评估:已有目标,填昵称(搜)或粘主页链接(评),定位到这个号再打分。
import { computed, ref } from 'vue'

import type { BloggerSearchResult, CandidateScore } from '../api/types'
import {
  adoptBenchmarkCandidate,
  benchmarkCandidates,
  benchmarkEvaluatingId,
  benchmarkIntent,
  benchmarkLinkResult,
  benchmarkLinkUrl,
  benchmarkMyAccountId,
  benchmarkSearchScores,
  bloggerSearchKeyword,
  bloggerSearchResults,
  currentSocialPlatform,
  currentSocialPlatformName,
  handleEvaluateLink,
  handleEvaluateSearchCandidate,
  handleRecommendBloggers,
  handleSearchBloggerCandidates,
  myAccounts,
  pendingAction
} from '../composables/useWorkspaceStore'

const mode = ref<'recommend' | 'target'>('recommend')
const showMore = ref(false)
const targetInput = ref('')
const myPlatformAccounts = computed(() => myAccounts.value.filter((a) => a.platform === currentSocialPlatform.value))
const recommending = computed(() => pendingAction.value === 'recommend')
const evaluatingLink = computed(() => pendingAction.value === 'benchmark-evaluate')
const searching = computed(() => pendingAction.value === 'blogger-search')

function isUrl(text: string): boolean {
  return /^https?:\/\//i.test(text.trim())
}

// 指定评估:输入是链接→直接评分该号;否则当关键词→搜索出候选,再逐个评估。
function submitTarget() {
  const value = targetInput.value.trim()
  if (!value) return
  if (isUrl(value)) {
    bloggerSearchResults.value = []
    benchmarkLinkUrl.value = value
    handleEvaluateLink()
  } else {
    benchmarkLinkResult.value = null
    bloggerSearchKeyword.value = value
    handleSearchBloggerCandidates()
  }
}
</script>

<template>
  <div class="bf">
    <!-- 公用:你的方向(打分依据) -->
    <div class="bf-intent">
      <div class="bf-intent-head">
        <strong>你的方向</strong>
        <span>用来判断哪些博主值得你学、跟你搭不搭。只填一次,下面两种方式都用它。</span>
      </div>
      <label>
        我做什么领域 *
        <input v-model="benchmarkIntent.niche" type="text" placeholder="保险经纪 / 母婴 / 健身 / AI工具…" />
      </label>
      <button type="button" class="bf-more" @click="showMore = !showMore">{{ showMore ? '收起' : '更多(可选):受众 / 目标 / 形式 / 我的账号' }}</button>
      <template v-if="showMore">
        <div class="bf-intent-row">
          <label>
            给谁看
            <input v-model="benchmarkIntent.audience" type="text" placeholder="宝妈 / 职场新人 / 本地客户" />
          </label>
          <label>
            目标
            <input v-model="benchmarkIntent.goal" type="text" placeholder="涨粉立人设 / 私域获客 / 带货" />
          </label>
        </div>
        <div class="bf-intent-row">
          <label>
            内容形式
            <select v-model="benchmarkIntent.content_form">
              <option value="any">都行</option>
              <option value="image_text">图文为主</option>
              <option value="video">视频为主</option>
            </select>
          </label>
          <label>
            结合我的账号
            <select v-model="benchmarkMyAccountId">
              <option :value="null">不结合(仅按方向)</option>
              <option v-for="acc in myPlatformAccounts" :key="acc.id" :value="acc.id">{{ acc.display_name }}</option>
            </select>
          </label>
        </div>
        <p v-if="benchmarkMyAccountId" class="field-hint">已结合你的账号:方向契合更贴你的现状,并多给一项「可迁移度」。</p>
      </template>
    </div>

    <!-- 两个入口 -->
    <div class="bf-modes" role="tablist">
      <button type="button" role="tab" :class="{ active: mode === 'recommend' }" @click="mode = 'recommend'">
        <strong>不知道学谁</strong><small>按方向帮我找一批</small>
      </button>
      <button type="button" role="tab" :class="{ active: mode === 'target' }" @click="mode = 'target'">
        <strong>已有目标博主</strong><small>填昵称或粘链接来评分</small>
      </button>
    </div>

    <!-- 智能推荐 -->
    <div v-if="mode === 'recommend'" class="bf-pane">
      <button type="button" class="primary" :disabled="recommending" @click="handleRecommendBloggers">
        {{ recommending ? '正在找对标博主…' : '帮我找对标博主' }}
      </button>
      <p v-if="recommending" class="field-hint">平台正在按你的方向搜寻并逐个评估,稍候片刻…</p>
      <div v-if="benchmarkCandidates.length" class="bf-list">
        <article v-for="c in benchmarkCandidates" :key="c.external_id" class="cand">
          <img v-if="c.avatar_url" :src="c.avatar_url" alt="" class="cand-avatar" />
          <div class="cand-body">
            <div class="cand-head">
              <strong>{{ c.display_name }}</strong>
              <span class="cand-overall">综合 {{ Math.round(c.overall) }}</span>
              <span v-if="!c.active" class="cand-flag">不活跃</span>
              <span v-if="c.existing_blogger_id" class="cand-flag in-lib">已在库</span>
            </div>
            <small class="cand-sub">{{ c.follower_count }} 粉丝 · {{ c.description || '暂无简介' }}</small>
            <div class="cand-metrics">
              <span>方向契合 <b>{{ Math.round(c.relevance) }}</b></span>
              <span>可对标 <b>{{ Math.round(c.learnability) }}</b></span>
              <span>火爆度 <b>{{ Math.round(c.popularity) }}</b></span>
              <span v-if="c.transferability !== null">可迁移 <b>{{ Math.round(c.transferability) }}</b></span>
            </div>
            <p v-if="c.reasons?.summary" class="cand-reason">{{ c.reasons.summary }}</p>
            <button type="button" class="cand-adopt" @click="adoptBenchmarkCandidate(c)">采用为对标 →</button>
          </div>
        </article>
      </div>
    </div>

    <!-- 指定评估:昵称(搜)或链接(评)合一 -->
    <div v-else class="bf-pane">
      <div class="search-row">
        <label>
          博主昵称 或 主页链接
          <input v-model="targetInput" type="text" placeholder="输入昵称搜索,或粘贴主页链接" @keydown.enter.prevent="submitTarget" />
        </label>
        <button type="button" class="primary" :disabled="searching || evaluatingLink" @click="submitTarget">
          {{ searching ? '搜索中…' : evaluatingLink ? '评分中…' : '查找 / 评分' }}
        </button>
      </div>

      <!-- 粘了链接:直接出单个评分卡 -->
      <article v-if="benchmarkLinkResult" class="cand">
        <img v-if="benchmarkLinkResult.avatar_url" :src="benchmarkLinkResult.avatar_url" alt="" class="cand-avatar" />
        <div class="cand-body">
          <div class="cand-head">
            <strong>{{ benchmarkLinkResult.display_name }}</strong>
            <span class="cand-overall">综合 {{ Math.round(benchmarkLinkResult.overall) }}</span>
            <span v-if="!benchmarkLinkResult.active" class="cand-flag">不活跃</span>
          </div>
          <small class="cand-sub">{{ benchmarkLinkResult.follower_count }} 粉丝</small>
          <div class="cand-metrics">
            <span>方向契合 <b>{{ Math.round(benchmarkLinkResult.relevance) }}</b></span>
            <span>可对标 <b>{{ Math.round(benchmarkLinkResult.learnability) }}</b></span>
            <span>火爆度 <b>{{ Math.round(benchmarkLinkResult.popularity) }}</b></span>
            <span v-if="benchmarkLinkResult.transferability !== null">可迁移 <b>{{ Math.round(benchmarkLinkResult.transferability) }}</b></span>
          </div>
          <p v-if="benchmarkLinkResult.reasons?.summary" class="cand-reason">{{ benchmarkLinkResult.reasons.summary }}</p>
          <button type="button" class="cand-adopt" @click="adoptBenchmarkCandidate(benchmarkLinkResult)">采用为对标 →</button>
        </div>
      </article>

      <!-- 搜了昵称:列出候选,每条可评估 / 采用 -->
      <div v-if="bloggerSearchResults.length" class="bf-list">
        <article v-for="r in bloggerSearchResults" :key="`${r.platform}-${r.external_id}`" class="cand">
          <img v-if="r.avatar_url" :src="r.avatar_url" alt="" class="cand-avatar" />
          <div class="cand-body">
            <div class="cand-head">
              <strong>{{ r.display_name }}</strong>
              <span class="cand-overall light">火爆度 {{ Math.round(r.quick_popularity || 0) }}</span>
            </div>
            <small class="cand-sub">{{ r.follower_count }} 粉丝 · {{ r.description || '暂无简介' }}</small>
            <template v-if="benchmarkSearchScores[r.external_id]">
              <div class="cand-metrics">
                <span>方向契合 <b>{{ Math.round(benchmarkSearchScores[r.external_id].relevance) }}</b></span>
                <span>可对标 <b>{{ Math.round(benchmarkSearchScores[r.external_id].learnability) }}</b></span>
                <span>火爆度 <b>{{ Math.round(benchmarkSearchScores[r.external_id].popularity) }}</b></span>
                <span v-if="benchmarkSearchScores[r.external_id].transferability !== null">可迁移 <b>{{ Math.round(benchmarkSearchScores[r.external_id].transferability as number) }}</b></span>
              </div>
              <p v-if="benchmarkSearchScores[r.external_id].reasons?.summary" class="cand-reason">{{ benchmarkSearchScores[r.external_id].reasons.summary }}</p>
            </template>
            <div class="cand-actions">
              <button type="button" class="ghost" :disabled="benchmarkEvaluatingId === r.external_id" @click="handleEvaluateSearchCandidate(r)">
                {{ benchmarkEvaluatingId === r.external_id ? '评估中…' : benchmarkSearchScores[r.external_id] ? '重新评估' : '评估这个号' }}
              </button>
              <button type="button" class="cand-adopt" @click="adoptBenchmarkCandidate(benchmarkSearchScores[r.external_id] || r)">采用为对标 →</button>
            </div>
          </div>
        </article>
      </div>
    </div>
  </div>
</template>

<style scoped>
.bf {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm, 12px);
}
.bf-intent {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
  border: 1px solid var(--color-field-border, #c8ced4);
  border-radius: 14px;
  background: var(--color-paper-3, #f7f8fa);
}
.bf-intent-head {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.bf-intent-head strong {
  font-weight: 600;
}
.bf-intent-head span {
  font-size: 0.82rem;
  color: var(--color-ink-2, #6b7280);
}
.bf-more {
  align-self: flex-start;
  border: 0;
  background: transparent;
  color: var(--color-accent, #2563eb);
  font-size: 0.85rem;
  cursor: pointer;
  padding: 2px 0;
}
.bf-intent-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.bf-modes {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.bf-modes button {
  display: flex;
  flex-direction: column;
  gap: 2px;
  align-items: flex-start;
  text-align: left;
  padding: 12px 14px;
  border: 1px solid var(--color-field-border, #c8ced4);
  border-radius: 12px;
  background: var(--color-field, #fff);
  cursor: pointer;
}
.bf-modes button small {
  color: var(--color-ink-2, #6b7280);
  font-size: 0.8rem;
}
.bf-modes button.active {
  border-color: var(--color-accent, #2563eb);
  box-shadow: var(--ring-accent, 0 0 0 3px rgba(37, 99, 235, 0.15));
}
.bf-pane {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.bf-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 46vh;
  overflow-y: auto;
}
.cand {
  display: flex;
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--color-field-border, #c8ced4);
  border-radius: 12px;
  background: var(--color-field, #fff);
}
.cand-avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  object-fit: cover;
  flex: none;
}
.cand-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  flex: 1;
}
.cand-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.cand-overall {
  font-size: 0.78rem;
  font-weight: 700;
  padding: 1px 8px;
  border-radius: 999px;
  background: var(--color-accent, #2563eb);
  color: #fff;
}
.cand-overall.light {
  background: var(--color-paper-3, #eef0f3);
  color: var(--color-ink-2, #6b7280);
}
.cand-flag {
  font-size: 0.72rem;
  padding: 1px 7px;
  border-radius: 999px;
  background: #fdecec;
  color: #c0392b;
}
.cand-flag.in-lib {
  background: #e8f5ec;
  color: #2e9e5b;
}
.cand-sub {
  color: var(--color-ink-2, #6b7280);
}
.cand-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 0.8rem;
  color: var(--color-ink-2, #6b7280);
}
.cand-metrics b {
  color: var(--color-ink-1, #111827);
}
.cand-reason {
  margin: 2px 0 0;
  font-size: 0.85rem;
  line-height: 1.5;
}
.cand-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.cand-adopt {
  align-self: flex-start;
  border: 0;
  background: transparent;
  color: var(--color-accent, #2563eb);
  font-weight: 700;
  cursor: pointer;
  padding: 2px 0;
}
@media (max-width: 640px) {
  .bf-intent-row,
  .bf-modes {
    grid-template-columns: 1fr;
  }
}
</style>
