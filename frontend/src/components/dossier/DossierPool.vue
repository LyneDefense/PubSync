<script setup lang="ts">
// 档案页·笔记池区:两级详情计数 + 覆盖徽章 + 增量/全量同步入口;明细列表在「博主资产」页看。
import type { DossierPoolInfo } from '../../api/types'
import { friendlyTime } from '../../composables/useWorkspaceStore'

defineProps<{ pool: DossierPoolInfo; busy: boolean }>()
defineEmits<{ (e: 'sync', mode: 'incremental' | 'full'): void; (e: 'open-assets'): void }>()
</script>

<template>
  <section class="dossier-block">
    <header class="dossier-block__head">
      <h3>笔记池</h3>
      <span class="dossier-block__hint">
        共 {{ pool.total }} 篇 · 详情级 {{ pool.full_count }}（含正文/转写/图文理解）· 列表级 {{ pool.list_count }}（仅标题/时间/互动）
        <template v-if="pool.synced_at">· {{ friendlyTime(pool.synced_at) }}同步</template>
      </span>
    </header>
    <div class="dossier-pool__actions">
      <button type="button" class="ghost" :disabled="busy" @click="$emit('sync', 'incremental')">增量更新（拉新笔记、刷新近期互动）</button>
      <button type="button" class="ghost" :disabled="busy" @click="$emit('sync', 'full')">全量校准（重翻整个列表）</button>
      <button type="button" class="ghost" @click="$emit('open-assets')">查看笔记明细 →</button>
    </div>
  </section>
</template>

<style scoped>
.dossier-pool__actions { display: flex; flex-wrap: wrap; gap: 8px; }
</style>
