<script setup lang="ts">
// 找对标博主:三段 tab —— 智能推荐(不知道对标谁)/ 关键词搜索(知道大概搜什么)/ 链接评分(盯上某个号)。
// 三者最终都「采用」一个候选 → 填进创建博主表单(adoptBenchmarkCandidate),用户补领域/备注后保存。
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

const tab = ref<'recommend' | 'search' | 'link'>('recommend')
const myPlatformAccounts = computed(() => myAccounts.value.filter((a) => a.platform === currentSocialPlatform.value))
const recommending = computed(() => pendingAction.value === 'recommend')
const evaluatingLink = computed(() => pendingAction.value === 'benchmark-evaluate')
</script>

<template>
  <div class="bf">
    <div class="bf-tabs" role="tablist">
      <button type="button" role="tab" :class="{ active: tab === 'recommend' }" @click="tab = 'recommend'">智能推荐</button>
      <button type="button" role="tab" :class="{ active: tab === 'search' }" @click="tab = 'search'">关键词搜索</button>
      <button type="button" role="tab" :class="{ active: tab === 'link' }" @click="tab = 'link'">链接评分</button>
    </div>

    <!-- 意图:三段共用(永远必填),搜索/链接 tab 评估时也用它 -->
    <div class="bf-intent">
      <label>
        我做什么领域 *
        <input v-model="benchmarkIntent.niche" type="text" placeholder="保险经纪 / 母婴 / 健身 / AI工具…" />
      </label>
      <div class="bf-intent-row">
        <label>
          给谁看(可选)
          <input v-model="benchmarkIntent.audience" type="text" placeholder="宝妈 / 职场新人 / 本地客户" />
        </label>
        <label>
          目标(可选)
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
          结合我的账号(可选)
          <select v-model="benchmarkMyAccountId">
            <option :value="null">不结合(仅按意图)</option>
            <option v-for="acc in myPlatformAccounts" :key="acc.id" :value="acc.id">{{ acc.display_name }}</option>
          </select>
        </label>
      </div>
      <p v-if="benchmarkMyAccountId" class="field-hint">已结合你的账号:方向契合更贴你的现状,并多给一项「可迁移度」。</p>
    </div>

    <!-- 智能推荐 -->
    <div v-if="tab === 'recommend'" class="bf-pane">
      <button type="button" class="primary" :disabled="recommending" @click="handleRecommendBloggers">
        {{ recommending ? '正在找对标博主…' : '帮我找对标博主' }}
      </button>
      <p v-if="recommending" class="field-hint">平台正在按你的意图搜寻并逐个评估,稍候片刻…</p>
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

    <!-- 关键词搜索 -->
    <div v-else-if="tab === 'search'" class="bf-pane">
      <div class="search-row">
        <label>
          搜索{{ currentSocialPlatformName }}博主
          <input v-model="bloggerSearchKeyword" type="search" placeholder="输入昵称或关键词" @keydown.enter.prevent="handleSearchBloggerCandidates" />
        </label>
        <button type="button" class="primary" :disabled="Boolean(pendingAction)" @click="handleSearchBloggerCandidates">
          {{ pendingAction === 'blogger-search' ? '搜索中' : '搜索' }}
        </button>
      </div>
      <div v-if="bloggerSearchResults.length" class="bf-list">
        <article v-for="r in bloggerSearchResults" :key="`${r.platform}-${r.external_id}`" class="cand">
          <img v-if="r.avatar_url" :src="r.avatar_url" alt="" class="cand-avatar" />
          <div class="cand-body">
            <div class="cand-head">
              <strong>{{ r.display_name }}</strong>
              <span class="cand-overall light">火爆度 {{ Math.round(r.quick_popularity || 0) }}</span>
            </div>
            <small class="cand-sub">{{ r.follower_count }} 粉丝 · {{ r.description || '暂无简介' }}</small>
            <!-- 已评估则展示四项,否则给「评估」按钮(才花 LLM) -->
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

    <!-- 链接评分 -->
    <div v-else class="bf-pane">
      <div class="search-row">
        <label>
          粘贴博主主页链接
          <input v-model="benchmarkLinkUrl" type="url" :placeholder="currentSocialPlatform === 'douyin' ? 'https://www.douyin.com/user/...' : 'https://www.xiaohongshu.com/user/profile/...'" />
        </label>
        <button type="button" class="primary" :disabled="evaluatingLink" @click="handleEvaluateLink">
          {{ evaluatingLink ? '评估中…' : '评分' }}
        </button>
      </div>
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
    </div>
  </div>
</template>

<style scoped>
.bf {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm, 12px);
}
.bf-tabs {
  display: inline-flex;
  border: 1px solid var(--color-field-border, #c8ced4);
  border-radius: var(--radius-pill, 999px);
  overflow: hidden;
  align-self: flex-start;
}
.bf-tabs button {
  border: 0;
  border-radius: 0;
  background: transparent;
  padding: 0 14px;
  min-height: 34px;
  font-weight: 700;
  color: var(--color-ink-2, #6b7280);
  cursor: pointer;
}
.bf-tabs button.active {
  background: var(--color-accent, #2563eb);
  color: #fff;
}
.bf-intent {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border: 1px solid var(--color-field-border, #c8ced4);
  border-radius: 12px;
  background: var(--color-paper-3, #f7f8fa);
}
.bf-intent-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
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
  .bf-intent-row {
    grid-template-columns: 1fr;
  }
}
</style>
