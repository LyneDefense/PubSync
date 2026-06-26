<script setup lang="ts">
// 找相似:从对标库挑 1+ 个博主当参照 → 用其存量笔记取关键词找同类号 → 采用进对标库。
import { computed } from 'vue'
import DiscoveryWorkspacePanel from './DiscoveryWorkspacePanel.vue'
import TIcon from '../components/TIcon.vue'
import {
  bloggers,
  currentSocialPlatform,
  discoverySimilarIds,
  discoveryStarting,
  discoveryWorkspace,
  handleDiscoverySimilarStart
} from '../composables/useWorkspaceStore'

const ws = computed(() => discoveryWorkspace.value)
const mine = computed(() => ws.value && ws.value.source === 'similar')
const benchmarks = computed(() =>
  bloggers.value.filter((b) => b.platform === currentSocialPlatform.value && b.account_type === 'benchmark')
)

function toggle(id: number) {
  discoverySimilarIds.value = discoverySimilarIds.value.includes(id)
    ? discoverySimilarIds.value.filter((x) => x !== id)
    : [...discoverySimilarIds.value, id]
}
</script>

<template>
  <DiscoveryWorkspacePanel v-if="mine" />

  <div v-else class="sim-pick">
    <p class="sim-hint">从你已有的对标里挑 1 个或几个当“参照”，系统按它们的内容找更多同类号。</p>
    <ul v-if="benchmarks.length" class="sim-list">
      <li
        v-for="b in benchmarks"
        :key="b.id"
        :class="{ on: discoverySimilarIds.includes(b.id) }"
        @click="toggle(b.id)"
      >
        <img v-if="b.avatar_url" :src="b.avatar_url" alt="" />
        <span class="sim-body">
          <strong>{{ b.display_name }}</strong>
          <small>{{ b.niche || '未填领域' }} · {{ b.follower_count }} 粉</small>
        </span>
        <TIcon :name="discoverySimilarIds.includes(b.id) ? 'checkbox' : 'square'" />
      </li>
    </ul>
    <p v-else class="sim-empty">对标库还没有博主。先用「泛搜索」或「精确搜索」收几个，再来找相似。</p>
    <button
      type="button"
      class="primary"
      :disabled="discoveryStarting || !discoverySimilarIds.length"
      @click="handleDiscoverySimilarStart"
    >
      {{ discoveryStarting ? '准备中…' : `找相似（已选 ${discoverySimilarIds.length} 个参照）` }}
    </button>
  </div>
</template>

<style scoped>
.sim-pick { max-width: 560px; display: flex; flex-direction: column; gap: 12px; }
.sim-hint { font-size: 0.86rem; color: var(--color-ink-2, #6b7280); }
.sim-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.sim-list li { display: flex; align-items: center; gap: 10px; border: 1px solid var(--color-field-border, #c8ced4); border-radius: 12px; padding: 10px 12px; cursor: pointer; }
.sim-list li.on { border-color: var(--color-accent, #2563eb); background: var(--color-paper-3, #eef4ff); }
.sim-list img { width: 40px; height: 40px; border-radius: 50%; object-fit: cover; flex: none; }
.sim-body { display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1; }
.sim-body small { color: var(--color-ink-2, #6b7280); font-size: 0.8rem; }
.sim-list li i { color: var(--color-accent, #2563eb); font-size: 20px; }
.sim-empty { color: var(--color-ink-3, #9aa0a6); font-size: 0.85rem; }
</style>
