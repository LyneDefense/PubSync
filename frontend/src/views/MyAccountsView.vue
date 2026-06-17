<script setup lang="ts">
// 社媒·我的账号:登记我的小红书/抖音账号,采集并缓存其内容,内容列表 + 手动刷新。
import { computed, ref, watch } from 'vue'
import StatusChip from '../components/StatusChip.vue'
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

function pick(id: number) {
  selectedId.value = id
  loadAccountPosts(id)
}

// 进入页面/账号列表变化时,默认选中第一个账号并读缓存内容。
watch(
  () => [isSocialPlatform.value && currentSocialTab.value === 'my-accounts', myAccounts.value.length] as const,
  ([active]) => {
    if (active && selectedId.value === null && myAccounts.value.length) {
      pick(myAccounts.value[0].id)
    }
  },
  { immediate: true }
)
</script>

<template>
  <section v-if="isSocialPlatform && currentSocialTab === 'my-accounts'" class="panel">
    <div class="section-header">
      <div>
        <h2>我的{{ currentSocialPlatformName }}账号</h2>
        <p class="toolbar-subtitle">登记你自己的账号并采集内容(可多个)。内容会缓存,只有点「刷新」才重新采集。</p>
      </div>
      <button type="button" class="primary" @click="openCreateMyAccountModal">添加我的账号</button>
    </div>

    <div class="audit-grid">
      <div>
        <h3>我的账号({{ myAccounts.length }})</h3>
        <div v-if="myAccounts.length" class="blogger-list compact">
          <button
            v-for="acc in myAccounts"
            :key="acc.id"
            type="button"
            :class="{ active: selectedId === acc.id }"
            @click="pick(acc.id)"
          >
            <strong>{{ acc.display_name }}</strong>
            <span>{{ acc.niche || '未设置领域' }} · 样本 {{ acc.sample_count }}</span>
          </button>
        </div>
        <p v-else class="empty-region">还没有我的账号。点「添加我的账号」搜索并保存你的主页。</p>
      </div>

      <div v-if="selectedId">
        <div class="section-header">
          <h3>内容列表</h3>
          <button
            type="button"
            :disabled="Boolean(pendingAction)"
            @click="handleCollectAccount(selectedId)"
          >
            {{ pendingAction === 'collect' ? '采集中…' : '刷新(重新采集)' }}
          </button>
        </div>
        <div v-if="selectedAccount?.tags?.length" class="tag-chips">
          <span
            v-for="tag in selectedAccount.tags"
            :key="tag.name"
            class="tag-chip"
            :class="tag.source === 'manual' ? 'tag-chip--manual' : 'tag-chip--auto'"
          >{{ tag.name }}</span>
        </div>
        <div v-if="(accountPosts[selectedId] || []).length" class="post-list">
          <article v-for="post in accountPosts[selectedId]" :key="post.id" class="post-row">
            <div>
              <strong>{{ post.title || '(无标题)' }}</strong>
              <small>赞{{ post.like_count }} · 藏{{ post.favorite_count }} · 评{{ post.comment_count }}<template v-if="post.published_at"> · {{ formatDate(post.published_at) }}</template></small>
            </div>
            <StatusChip v-if="post.asr_status && post.asr_status !== 'not_required'" :status="post.asr_status" />
          </article>
        </div>
        <p v-else class="empty-region">这个账号还没有缓存内容。点「刷新(重新采集)」抓取最新内容。</p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.audit-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.6fr);
  gap: var(--space-lg, 24px);
  align-items: start;
}
.post-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.post-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border: var(--rule-hair);
  border-radius: var(--radius-md, 8px);
  padding: 8px 12px;
}
.post-row small {
  display: block;
  color: var(--color-ink-3, inherit);
  margin-top: 2px;
}
@media (max-width: 900px) {
  .audit-grid {
    grid-template-columns: 1fr;
  }
}
</style>
