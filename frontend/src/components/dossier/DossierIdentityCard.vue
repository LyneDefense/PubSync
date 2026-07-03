<script setup lang="ts">
// 档案页·身份卡:她是谁(头像/昵称/粉丝/平台笔记总数/赛道/标签)+ 池同步时间。展示型,动作由父级传入插槽。
import { computed } from 'vue'
import type { BloggerProfile } from '../../api/types'
import { friendlyTime } from '../../composables/useWorkspaceStore'

const props = defineProps<{ blogger: BloggerProfile; poolSyncedAt: string | null }>()

const initials = computed(() => (props.blogger.display_name || '?').slice(0, 1))
const tagNames = computed(() => (props.blogger.tags || []).map((t) => t.name).slice(0, 6))
</script>

<template>
  <div class="dossier-identity">
    <img v-if="blogger.avatar_url" :src="blogger.avatar_url" alt="" class="dossier-identity__avatar" />
    <div v-else class="dossier-identity__avatar dossier-identity__avatar--fallback">{{ initials }}</div>
    <div class="dossier-identity__main">
      <h2>{{ blogger.display_name }}</h2>
      <p class="dossier-identity__meta">
        {{ blogger.platform === 'douyin' ? '抖音' : '小红书' }}
        <template v-if="blogger.niche">· {{ blogger.niche }}</template>
        · 粉丝 {{ blogger.follower_count.toLocaleString() }}
        <template v-if="blogger.note_total != null">· 平台笔记 {{ blogger.note_total }}</template>
      </p>
      <p v-if="blogger.signature" class="dossier-identity__sig" :title="blogger.signature">{{ blogger.signature }}</p>
      <div v-if="tagNames.length" class="dossier-identity__tags">
        <span v-for="tag in tagNames" :key="tag">{{ tag }}</span>
      </div>
    </div>
    <div class="dossier-identity__side">
      <span v-if="poolSyncedAt" class="dossier-identity__synced">档案 {{ friendlyTime(poolSyncedAt) }}更新</span>
      <slot />
    </div>
  </div>
</template>

<style scoped>
.dossier-identity {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 20px;
  background: var(--color-paper-2);
  border: 1px solid var(--color-rule);
  border-radius: 12px;
}
.dossier-identity__avatar {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
}
.dossier-identity__avatar--fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
  font-size: 20px;
  font-weight: 600;
}
.dossier-identity__main { flex: 1; min-width: 0; }
.dossier-identity__main h2 { margin: 0; font-size: 17px; }
.dossier-identity__meta { margin: 4px 0 0; font-size: 13px; color: var(--color-ink-2); }
.dossier-identity__sig {
  margin: 6px 0 0;
  font-size: 12.5px;
  color: var(--color-ink-3);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.dossier-identity__tags { display: flex; gap: 6px; margin-top: 6px; flex-wrap: wrap; }
.dossier-identity__tags span {
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 999px;
  background: var(--color-paper-3);
  color: var(--color-ink-2);
}
.dossier-identity__side { display: flex; flex-direction: column; align-items: flex-end; gap: 8px; }
.dossier-identity__synced { font-size: 12px; color: var(--color-ink-3); }
</style>
