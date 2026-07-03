<script setup lang="ts">
// 档案页·创作画像区:每份画像可展开看蒸馏结果本体(认知/声音/角度/分车道写法),不再只是一张名片。
// 过时≠失效:黄徽章只提示"有更新可纳入"。重新蒸馏=同快照重蒸(覆盖);蒸新画像=下方快照区新建。
import { ref } from 'vue'
import type { DossierPortrait } from '../../api/types'
import DossierPortraitContent from './DossierPortraitContent.vue'
import { friendlyTime, SUBTYPE_LABELS, selectedBloggerRunId, setCurrentSocialTab } from '../../composables/useWorkspaceStore'

const props = defineProps<{ portraits: DossierPortrait[]; busy: boolean }>()
defineEmits<{ (e: 'redistill', portrait: DossierPortrait): void }>()

function laneLabel(lanes: string[]): string {
  const items = lanes.filter((l) => l !== '__all__').map((l) => SUBTYPE_LABELS[l] || l)
  return items.length ? items.join(' + ') : '通用'
}

// 展开态:默认展开第一份(通常是默认画像),让蒸馏结果直接可见。
const expanded = ref<Set<number>>(new Set(props.portraits.length ? [props.portraits[0].skill_id] : []))
function toggle(id: number) {
  const next = new Set(expanded.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expanded.value = next
}

function openFullReport(portrait: DossierPortrait) {
  selectedBloggerRunId.value = portrait.run_id
  setCurrentSocialTab('distill')
}
</script>

<template>
  <section class="dossier-block">
    <header class="dossier-block__head">
      <h3>创作画像</h3>
      <span class="dossier-block__hint">从她的笔记里蒸出的可迁移创作方法 —— 创作与选题的直接原料</span>
    </header>
    <p v-if="!portraits.length" class="dossier-block__hint">
      尚未蒸馏。「构建博主画像」会自动生成默认画像；也可在下方「选材快照」自选笔记后去蒸馏。
    </p>
    <div v-for="p in portraits" :key="p.skill_id" class="portrait" :class="{ 'portrait--open': expanded.has(p.skill_id) }">
      <button type="button" class="portrait__row" @click="toggle(p.skill_id)">
        <span class="portrait__chevron" :class="{ open: expanded.has(p.skill_id) }">›</span>
        <span class="portrait__main">
          <strong>{{ p.snapshot_name || p.name }}</strong>
          <span class="portrait__meta">
            蒸馏于 {{ p.distilled_at ? friendlyTime(p.distilled_at) : '未知' }} · 样本 {{ p.sample_count }} 篇 · 覆盖 {{ laneLabel(p.lanes) }}
          </span>
        </span>
        <span v-if="p.stale" class="dossier-chip dossier-chip--warn" :title="`蒸馏后笔记池新增 ${p.new_posts_since} 篇`">可能过时 · 新增 {{ p.new_posts_since }} 篇</span>
        <span v-else class="dossier-chip dossier-chip--ok">最新</span>
      </button>
      <div v-if="expanded.has(p.skill_id)" class="portrait__body">
        <DossierPortraitContent :run-id="p.run_id" />
        <div class="portrait__actions">
          <button type="button" class="ghost" @click="openFullReport(p)">查看完整报告 →</button>
          <button v-if="p.snapshot_id" type="button" class="ghost" :disabled="busy" @click="$emit('redistill', p)">重新蒸馏（纳入新笔记）</button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.portrait { border-top: 1px solid var(--color-rule); }
.portrait:first-of-type { border-top: none; }
.portrait__row {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 12px 0;
  background: none;
  border: none;
  text-align: left;
  cursor: pointer;
}
.portrait__chevron { font-size: 16px; color: var(--color-ink-3); transition: transform 0.15s ease; }
.portrait__chevron.open { transform: rotate(90deg); }
.portrait__main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.portrait__meta { font-size: 12px; color: var(--color-ink-2); }
.portrait__body { padding: 0 0 14px 26px; }
.portrait__actions { display: flex; gap: 8px; margin-top: 12px; }
</style>
