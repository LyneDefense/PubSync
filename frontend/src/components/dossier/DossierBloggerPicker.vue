<script setup lang="ts">
// 档案页·博主选择器:右上角下拉 + 搜索(替代旧左侧分栏)。触发按钮显示当前博主头像/名称/副标题,
// 展开浮层可按名称/赛道过滤,选中即切换并关闭。点击外部遮罩关闭。
import { computed, nextTick, ref, watch } from 'vue'
import type { BloggerProfile } from '../../api/types'
import { avatarColor } from '../../utils/format'

const props = defineProps<{ accounts: BloggerProfile[]; selectedId: number | null }>()
const emit = defineEmits<{ (e: 'select', id: number): void }>()

const open = ref(false)
const query = ref('')
const searchEl = ref<HTMLInputElement | null>(null)

const selected = computed(() => props.accounts.find((b) => b.id === props.selectedId) || null)

function platformLabel(b: BloggerProfile): string {
  return b.platform === 'douyin' ? '抖音' : '小红书'
}
function subLine(b: BloggerProfile): string {
  return `${b.niche || platformLabel(b)} · 样本 ${b.sample_count}`
}
function initials(name: string): string {
  return (name || '?').slice(0, 1)
}

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return props.accounts
  return props.accounts.filter(
    (b) => b.display_name.toLowerCase().includes(q) || (b.niche || '').toLowerCase().includes(q)
  )
})

function toggle() {
  open.value = !open.value
  if (open.value) nextTick(() => searchEl.value?.focus())
}
function close() {
  open.value = false
}
function pick(id: number) {
  emit('select', id)
  open.value = false
  query.value = ''
}
// 切换博主(外部驱动)后收起浮层。
watch(() => props.selectedId, close)
</script>

<template>
  <div class="dbp">
    <div v-if="open" class="dbp__mask" @click="close"></div>

    <button type="button" class="dbp__trigger" :class="{ 'dbp__trigger--open': open }" @click="toggle">
      <span v-if="selected?.avatar_url" class="dbp__avatar">
        <img :src="selected.avatar_url" alt="" />
      </span>
      <span
        v-else-if="selected"
        class="dbp__avatar dbp__avatar--fallback"
        :style="{ background: avatarColor(selected.id).bg, color: avatarColor(selected.id).ink }"
      >{{ initials(selected.display_name) }}</span>
      <span v-else class="dbp__avatar dbp__avatar--empty">?</span>

      <span class="dbp__label">
        <span class="dbp__name">{{ selected?.display_name || '选择对标博主' }}</span>
        <span class="dbp__sub">{{ selected ? subLine(selected) : `共 ${accounts.length} 个` }}</span>
      </span>
      <svg class="dbp__chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6" /></svg>
    </button>

    <div v-if="open" class="dbp__menu">
      <div class="dbp__menu-head">对标博主 · {{ accounts.length }} 个</div>
      <input ref="searchEl" v-model="query" type="text" class="dbp__search" placeholder="搜索博主 / 赛道…" />
      <div class="dbp__list">
        <button
          v-for="b in filtered"
          :key="b.id"
          type="button"
          class="dbp__row"
          :class="{ 'dbp__row--sel': b.id === selectedId }"
          @click="pick(b.id)"
        >
          <span v-if="b.avatar_url" class="dbp__avatar dbp__avatar--sm"><img :src="b.avatar_url" alt="" /></span>
          <span
            v-else
            class="dbp__avatar dbp__avatar--sm dbp__avatar--fallback"
            :style="{ background: avatarColor(b.id).bg, color: avatarColor(b.id).ink }"
          >{{ initials(b.display_name) }}</span>
          <span class="dbp__label">
            <span class="dbp__name">{{ b.display_name }}</span>
            <span class="dbp__sub">{{ subLine(b) }}</span>
          </span>
          <span class="dbp__check" aria-hidden="true">✓</span>
        </button>
        <p v-if="!filtered.length" class="dbp__empty">没有匹配的博主</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dbp { position: relative; width: 300px; max-width: 100%; }
.dbp__mask { position: fixed; inset: 0; z-index: 25; }

.dbp__trigger {
  position: relative;
  z-index: 26;
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 7px 12px;
  border: 1px solid var(--color-rule);
  border-radius: 11px;
  background: var(--color-surface);
  cursor: pointer;
  text-align: left;
  transition: border-color 140ms var(--ease-out);
}
.dbp__trigger:hover,
.dbp__trigger--open { border-color: var(--color-accent); }

.dbp__avatar {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 9px;
  font-size: 14px;
  font-weight: 600;
  flex: 0 0 auto;
  overflow: hidden;
}
.dbp__avatar img { width: 100%; height: 100%; object-fit: cover; }
.dbp__avatar--empty { background: var(--color-paper-3); color: var(--color-ink-3); }
.dbp__avatar--sm { width: 30px; height: 30px; border-radius: 8px; font-size: 13px; }

.dbp__label { flex: 1; min-width: 0; line-height: 1.3; }
.dbp__name {
  display: block;
  font-size: 13.5px;
  font-weight: 620;
  color: var(--color-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dbp__sub {
  display: block;
  font-size: 11.5px;
  color: var(--color-ink-3);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dbp__chevron { flex: 0 0 auto; color: var(--color-ink-3); transition: transform 0.15s var(--ease-out); }
.dbp__trigger--open .dbp__chevron { transform: rotate(180deg); }

.dbp__menu {
  position: absolute;
  z-index: 30;
  top: calc(100% + 6px);
  left: 0;
  right: 0;
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: 13px;
  box-shadow: 0 14px 36px -10px rgba(0, 0, 0, 0.24);
  padding: 9px;
}
.dbp__menu-head {
  padding: 0 4px 8px;
  font-size: 11.5px;
  font-weight: 650;
  color: var(--color-ink-3);
  letter-spacing: 0.03em;
}
.dbp__search {
  width: 100%;
  height: 36px;
  padding: 0 12px;
  border: 1px solid var(--color-rule);
  border-radius: 9px;
  background: var(--color-paper);
  font-size: 13px;
  color: var(--color-ink);
}
.dbp__search:focus { outline: none; border-color: var(--color-accent); }
.dbp__list {
  max-height: 280px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 8px;
}
.dbp__row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 9px;
  border: 0;
  border-radius: 9px;
  background: transparent;
  cursor: pointer;
  text-align: left;
  transition: background 120ms var(--ease-out);
}
.dbp__row:hover { background: var(--color-paper); }
.dbp__row--sel { background: var(--color-accent-tint); }
.dbp__row--sel .dbp__name { color: var(--color-accent-ink); }
.dbp__check { flex: 0 0 auto; font-size: 13px; font-weight: 800; color: transparent; }
.dbp__row--sel .dbp__check { color: var(--color-accent); }
.dbp__empty { margin: 0; padding: 16px 8px; text-align: center; font-size: 12.5px; color: var(--color-ink-3); }
</style>
