<script setup lang="ts">
// 档案页·创作画像区(去多画像:一份画像,可展开看蒸馏本体)。
// 查看完整报告→ 主按钮;更新画像=用现有详情池重蒸(便宜);彻底重建=拉最新+重升详情+重蒸(纳入新笔记)。
import { ref } from 'vue'
import type { DossierPortrait } from '../../api/types'
import DossierPortraitContent from './DossierPortraitContent.vue'
import { friendlyTime, SUBTYPE_LABELS, selectedBloggerRunId, setCurrentSocialTab } from '../../composables/useWorkspaceStore'

const props = defineProps<{ portraits: DossierPortrait[]; busy: boolean }>()
defineEmits<{ (e: 'redistill'): void; (e: 'rebuild'): void }>()

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
  <section class="cp">
    <h3 class="cp__title">创作画像</h3>
    <p v-if="!portraits.length" class="cp__empty">尚未蒸馏。「构建博主画像」会自动系统选样并生成画像。</p>

    <div v-for="p in portraits" :key="p.skill_id" class="cp__item">
      <button type="button" class="cp__row" @click="toggle(p.skill_id)">
        <span class="cp__chevron" :class="{ open: expanded.has(p.skill_id) }">›</span>
        <span class="cp__row-main">
          <b>{{ p.snapshot_name || p.name }}</b>
          <span class="cp__row-meta">蒸馏于 {{ p.distilled_at ? friendlyTime(p.distilled_at) : '未知' }} · 样本 {{ p.sample_count }} 篇 · 覆盖 {{ laneLabel(p.lanes) }}</span>
        </span>
        <span v-if="p.stale" class="cp__pill cp__pill--warn" :title="`蒸馏后笔记池新增 ${p.new_posts_since} 篇,彻底重建可纳入`">可能过时 · 新增 {{ p.new_posts_since }} 篇</span>
        <span v-else class="cp__pill cp__pill--ok">最新</span>
      </button>

      <div v-if="expanded.has(p.skill_id)" class="cp__body">
        <DossierPortraitContent :run-id="p.run_id" />
        <div class="cp__actions">
          <button type="button" class="cp__btn cp__btn--accent" @click="openFullReport(p)">查看完整报告 →</button>
          <button type="button" class="cp__btn" :disabled="busy" title="用现有笔记重新蒸馏(便宜)" @click="$emit('redistill')">更新画像</button>
          <button type="button" class="cp__btn" :disabled="busy" title="重新拉取全部笔记 + 重升详情 + 重蒸(纳入新笔记)" @click="$emit('rebuild')">彻底重建</button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.cp { background: var(--color-surface); border: 1px solid var(--color-rule); border-radius: 14px; padding: 20px 22px; }
.cp__title { margin: 0; font-size: 15px; font-weight: 650; }
.cp__empty { margin: 12px 0 0; font-size: 12.5px; color: var(--color-ink-3); }

.cp__item { border-top: 1px solid var(--color-paper-3); margin-top: 12px; }
.cp__item:first-of-type { }
.cp__row {
  display: flex;
  align-items: center;
  gap: 11px;
  width: 100%;
  padding: 14px 0;
  border: 0;
  background: none;
  text-align: left;
  cursor: pointer;
}
.cp__chevron { font-size: 16px; color: var(--color-ink-3); transition: transform 0.15s var(--ease-out); }
.cp__chevron.open { transform: rotate(90deg); }
.cp__row-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.cp__row-main b { font-size: 14px; color: var(--color-ink); }
.cp__row-meta { font-size: 12px; color: var(--color-ink-3); }
.cp__pill { padding: 2px 9px; border-radius: 999px; font-size: 11px; white-space: nowrap; }
.cp__pill--ok { background: #eaf3ee; color: #2f6b54; }
.cp__pill--warn { background: #fdf3e0; color: #8a5a12; }

.cp__body { padding: 0 0 4px 27px; }
.cp__actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }
.cp__btn {
  height: 34px;
  padding: 0 14px;
  border: 1px solid var(--color-rule);
  border-radius: 9px;
  background: var(--color-surface);
  color: var(--color-ink-2);
  font-size: 12.5px;
  font-weight: 550;
  cursor: pointer;
  transition: background 140ms var(--ease-out);
}
.cp__btn:hover { background: var(--color-paper); }
.cp__btn:disabled { opacity: 0.55; cursor: not-allowed; }
.cp__btn--accent { border: 0; background: var(--color-accent); color: #fff; font-weight: 620; }
.cp__btn--accent:hover { background: var(--color-accent-press); }
</style>
