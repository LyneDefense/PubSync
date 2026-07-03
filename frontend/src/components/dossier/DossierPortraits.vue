<script setup lang="ts">
// 档案页·创作画像区:active 画像列表(可多个,按快照来源并存)+ 过时提示(过时≠失效,照常可用)。
// 重新蒸馏=同快照重蒸(版本覆盖);蒸新画像=去博主资产按快照选材。
import type { DossierPortrait } from '../../api/types'
import { friendlyTime, SUBTYPE_LABELS } from '../../composables/useWorkspaceStore'

defineProps<{ portraits: DossierPortrait[]; busy: boolean }>()
defineEmits<{ (e: 'redistill', portrait: DossierPortrait): void; (e: 'new-portrait'): void }>()

function laneLabel(lanes: string[]): string {
  const items = lanes.filter((l) => l !== '__all__').map((l) => SUBTYPE_LABELS[l] || l)
  return items.length ? items.join(' + ') : '通用'
}
</script>

<template>
  <section class="dossier-block">
    <header class="dossier-block__head">
      <h3>创作画像</h3>
      <span class="dossier-block__hint">从她的笔记里蒸出的可迁移创作方法，创作与选题都用它</span>
      <button type="button" class="ghost" :disabled="busy" @click="$emit('new-portrait')">蒸新画像</button>
    </header>
    <p v-if="!portraits.length" class="dossier-block__hint">尚未蒸馏。构建画像时会自动生成「默认画像 · 最新笔记」，也可去博主资产按快照自选笔记蒸馏。</p>
    <div v-for="p in portraits" :key="p.skill_id" class="dossier-portrait">
      <div class="dossier-portrait__main">
        <strong>{{ p.snapshot_name || p.name }}</strong>
        <span class="dossier-portrait__meta">
          蒸馏于 {{ p.distilled_at ? friendlyTime(p.distilled_at) : '未知' }} · 样本 {{ p.sample_count }} 篇 · 覆盖 {{ laneLabel(p.lanes) }}
        </span>
      </div>
      <span v-if="p.stale" class="dossier-chip dossier-chip--warn" :title="`蒸馏后笔记池新增 ${p.new_posts_since} 篇`">可能过时 · 新增 {{ p.new_posts_since }} 篇未纳入</span>
      <span v-else class="dossier-chip dossier-chip--ok">最新</span>
      <button v-if="p.snapshot_id" type="button" class="ghost" :disabled="busy" @click="$emit('redistill', p)">重新蒸馏</button>
    </div>
  </section>
</template>

<style scoped>
.dossier-portrait {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  border-top: 1px solid var(--color-rule);
}
.dossier-portrait:first-of-type { border-top: none; }
.dossier-portrait__main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.dossier-portrait__meta { font-size: 12px; color: var(--color-ink-2); }
</style>
