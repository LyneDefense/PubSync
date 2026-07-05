<script setup lang="ts">
// 档案页·身份卡(她是谁):头像/昵称/赛道/建档状态 + 粉丝·笔记·平台号 + 简介 + 人设标签;
// 右侧 = 档案更新时间 + 主操作(标记/刷新资料/采集笔记→)+「⋯」更多(编辑/删除)。动作 emit 给父级接 store。
import { computed, ref, watch } from 'vue'
import type { BloggerProfile } from '../../api/types'
import { avatarColor } from '../../utils/format'
import { friendlyTime } from '../../composables/useWorkspaceStore'

const props = defineProps<{
  blogger: BloggerProfile
  poolSyncedAt: string | null
  built: boolean
  refreshing: boolean
  building: string | null
}>()
const emit = defineEmits<{
  (e: 'toggle-favorite'): void
  (e: 'refresh'): void
  (e: 'collect'): void
  (e: 'edit'): void
  (e: 'delete'): void
}>()

const initials = computed(() => (props.blogger.display_name || '?').slice(0, 1))
const avatar = computed(() => avatarColor(props.blogger.id))
const tagNames = computed(() => (props.blogger.tags || []).map((t) => t.name).slice(0, 6))
const platformIdLabel = computed(() => (props.blogger.platform === 'douyin' ? '抖音号' : '小红书号'))

function fmtCount(v: number): string {
  return v >= 10000 ? `${(v / 10000).toFixed(1)}w` : v.toLocaleString()
}

const moreOpen = ref(false)
watch(() => props.blogger.id, () => { moreOpen.value = false })
function fireMore(action: 'edit' | 'delete') {
  moreOpen.value = false
  if (action === 'edit') emit('edit')
  else emit('delete')
}
</script>

<template>
  <section class="di">
    <div class="di__avatar">
      <img v-if="blogger.avatar_url" :src="blogger.avatar_url" alt="" />
      <span v-else class="di__avatar-ch" :style="{ background: avatar.bg, color: avatar.ink }">{{ initials }}</span>
    </div>

    <div class="di__main">
      <div class="di__title-row">
        <h2>{{ blogger.display_name }}</h2>
        <span v-if="blogger.niche" class="di__niche">{{ blogger.niche }}</span>
        <span v-if="built" class="di__status di__status--built"><i></i>已建档</span>
        <span v-else class="di__status di__status--todo">待建档</span>
        <span v-if="building" class="dossier-chip dossier-chip--busy">构建中 · {{ building }}</span>
      </div>
      <p class="di__meta">
        粉丝 {{ fmtCount(blogger.follower_count) }}
        <template v-if="blogger.note_total != null"> · 笔记 {{ blogger.note_total }}</template>
        <template v-if="blogger.external_id"> · {{ platformIdLabel }} {{ blogger.external_id }}</template>
      </p>
      <p v-if="blogger.signature" class="di__sig" :title="blogger.signature">{{ blogger.signature }}</p>
      <div v-if="tagNames.length" class="di__tags">
        <span v-for="tag in tagNames" :key="tag">{{ tag }}</span>
      </div>
    </div>

    <div class="di__side">
      <span v-if="poolSyncedAt" class="di__synced">档案 {{ friendlyTime(poolSyncedAt) }}更新</span>
      <div class="di__actions">
        <button type="button" class="di__btn" @click="emit('toggle-favorite')">{{ blogger.is_favorite ? '取消标记' : '⭐ 标记' }}</button>
        <button type="button" class="di__btn" :disabled="refreshing" @click="emit('refresh')">刷新资料</button>
        <button type="button" class="di__btn di__btn--accent" @click="emit('collect')">采集笔记 →</button>
        <div class="di__more">
          <button type="button" class="di__btn di__btn--icon" :class="{ 'di__btn--on': moreOpen }" aria-label="更多操作" @click="moreOpen = !moreOpen">⋯</button>
          <template v-if="moreOpen">
            <div class="di__more-mask" @click="moreOpen = false"></div>
            <div class="di__more-menu">
              <button type="button" @click="fireMore('edit')">编辑资料</button>
              <button type="button" class="di__more-danger" @click="fireMore('delete')">删除博主</button>
            </div>
          </template>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.di {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  flex-wrap: wrap;
  padding: 20px 22px;
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: 14px;
}
.di__avatar {
  width: 58px;
  height: 58px;
  border-radius: 15px;
  overflow: hidden;
  flex: 0 0 auto;
}
.di__avatar img { width: 100%; height: 100%; object-fit: cover; }
.di__avatar-ch { display: grid; place-items: center; width: 100%; height: 100%; font-size: 23px; font-weight: 600; }

.di__main { flex: 1 1 260px; min-width: 0; }
.di__title-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 5px; }
.di__title-row h2 { margin: 0; font-size: 19px; font-weight: 680; letter-spacing: -0.01em; }
.di__niche { padding: 2px 9px; border-radius: 6px; font-size: 11.5px; font-weight: 600; background: #eaf3ee; color: #2f6b54; }
.di__status { display: inline-flex; align-items: center; gap: 5px; padding: 2px 9px; border-radius: 999px; font-size: 11.5px; font-weight: 600; }
.di__status--built { background: var(--color-accent-soft); color: var(--color-accent-ink); }
.di__status--built i { width: 5px; height: 5px; border-radius: 50%; background: var(--color-accent); }
.di__status--todo { background: var(--color-paper-3); color: var(--color-ink-3); }
.di__meta { margin: 0 0 8px; font-size: 12.5px; color: var(--color-ink-3); font-variant-numeric: tabular-nums; }
.di__sig {
  margin: 0 0 10px;
  font-size: 13.5px;
  line-height: 1.6;
  color: var(--color-ink-2);
  max-width: 560px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.di__tags { display: flex; gap: 7px; flex-wrap: wrap; }
.di__tags span { padding: 3px 10px; border-radius: 7px; font-size: 11.5px; font-weight: 500; background: var(--color-paper); color: var(--color-ink-2); }

.di__side { display: flex; flex-direction: column; align-items: flex-end; gap: 10px; flex: 0 0 auto; }
.di__synced { font-size: 11.5px; color: var(--color-ink-3); }
.di__actions { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; max-width: 300px; }
.di__btn {
  height: 32px;
  padding: 0 12px;
  border: 1px solid var(--color-rule);
  border-radius: 9px;
  background: var(--color-surface);
  font-size: 12.5px;
  font-weight: 550;
  color: var(--color-ink-2);
  white-space: nowrap;
  cursor: pointer;
  transition: background 140ms var(--ease-out), border-color 140ms var(--ease-out);
}
.di__btn:hover { background: var(--color-paper); }
.di__btn:disabled { opacity: 0.55; cursor: not-allowed; }
.di__btn--accent { border-color: var(--color-accent-soft-bd); background: var(--color-accent-soft); color: var(--color-accent-ink); font-weight: 600; }
.di__btn--accent:hover { background: var(--color-accent-soft); }
.di__btn--icon { width: 32px; padding: 0; font-size: 16px; line-height: 1; }
.di__btn--on { border-color: var(--color-accent); }

.di__more { position: relative; }
.di__more-mask { position: fixed; inset: 0; z-index: 25; }
.di__more-menu {
  position: absolute;
  z-index: 30;
  top: calc(100% + 6px);
  right: 0;
  min-width: 132px;
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: 10px;
  box-shadow: 0 14px 36px -10px rgba(0, 0, 0, 0.24);
  padding: 5px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.di__more-menu button {
  height: 32px;
  padding: 0 10px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  font-size: 12.5px;
  color: var(--color-ink-2);
  text-align: left;
  cursor: pointer;
}
.di__more-menu button:hover { background: var(--color-paper); }
.di__more-danger { color: var(--color-danger); }
.di__more-danger:hover { background: var(--color-score-danger-bg); }
</style>
