<script setup lang="ts">
// 档案页·创作画像区(去多画像:一份画像,可展开看蒸馏本体)。
// 查看完整报告→ 主按钮;更新画像=用现有详情池重蒸(便宜);重建画像=拉最新+重升详情+重蒸(纳入新笔记)。
import { ref } from 'vue'
import { toPng } from 'html-to-image'
import type { DossierPortrait } from '../../api/types'
import DossierPortraitContent from './DossierPortraitContent.vue'
import { friendlyTime, SUBTYPE_LABELS, selectedBlogger, selectedBloggerRunId, setCurrentSocialTab, showMessage } from '../../composables/useWorkspaceStore'

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

// 「查看详情」弹窗:展开完整创作方法(认知/方法/分车道),避免卡片内堆太密。
const detailPortrait = ref<DossierPortrait | null>(null)

// 导出长图:截离屏节点(白底、固定宽、全量画像)成一张 PNG,含头部署名。
const exportEl = ref<HTMLElement | null>(null)
const exporting = ref(false)
async function exportImage() {
  const el = exportEl.value
  if (!el || exporting.value) return
  exporting.value = true
  try {
    const url = await toPng(el, { pixelRatio: 2, backgroundColor: '#fff', cacheBust: true })
    const a = document.createElement('a')
    a.href = url
    a.download = `创作画像_${selectedBlogger.value?.display_name || 'portrait'}.png`
    a.click()
    showMessage('已导出创作画像长图')
  } catch (err) {
    showMessage(err instanceof Error ? err.message : '导出图片失败,请重试', true)
  } finally {
    exporting.value = false
  }
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
        <span v-if="p.stale" class="cp__pill cp__pill--warn" :title="`蒸馏后笔记池新增 ${p.new_posts_since} 篇,重建画像可纳入`">可能过时 · 新增 {{ p.new_posts_since }} 篇</span>
        <span v-else class="cp__pill cp__pill--ok">最新</span>
      </button>

      <div v-if="expanded.has(p.skill_id)" class="cp__body">
        <DossierPortraitContent :run-id="p.run_id" compact />
        <div class="cp__actions">
          <button type="button" class="cp__btn cp__btn--accent" @click="detailPortrait = p">查看详情</button>
          <button type="button" class="cp__btn" :disabled="busy" title="用现有笔记重新蒸馏(便宜)" @click="$emit('redistill')">更新画像</button>
          <button type="button" class="cp__btn" :disabled="busy" title="重新拉取全部笔记 + 重升详情 + 重蒸(纳入新笔记)" @click="$emit('rebuild')">重建画像</button>
        </div>
      </div>
    </div>

    <!-- 创作画像详情弹窗:完整创作方法 -->
    <div v-if="detailPortrait" class="cp-modal" @click.self="detailPortrait = null">
      <div class="cp-modal__card">
        <div class="cp-modal__head">
          <strong>{{ detailPortrait.snapshot_name || detailPortrait.name }} · 创作画像</strong>
          <button type="button" class="cp-modal__close" aria-label="关闭" @click="detailPortrait = null">✕</button>
        </div>
        <!-- 弹窗正文即导出目标:可见、在流内、自然全高(不受滚动裁剪),html-to-image 截它才不空白。 -->
        <div class="cp-modal__body">
          <div ref="exportEl" class="cp-export">
            <div class="cp-export__head">
              <strong>{{ selectedBlogger?.display_name || detailPortrait.snapshot_name || detailPortrait.name }} · 创作画像</strong>
              <span>蒸馏于 {{ detailPortrait.distilled_at ? friendlyTime(detailPortrait.distilled_at) : '未知' }} · 样本 {{ detailPortrait.sample_count }} 篇 · 覆盖 {{ laneLabel(detailPortrait.lanes) }}</span>
            </div>
            <DossierPortraitContent :run-id="detailPortrait.run_id" flat />
            <div class="cp-export__foot">由 Cadence 生成 · {{ new Date().toLocaleDateString('zh-CN') }}</div>
          </div>
        </div>
        <div class="cp-modal__foot">
          <button type="button" class="cp__btn" @click="openFullReport(detailPortrait)">查看完整报告 →</button>
          <button type="button" class="cp__btn" :disabled="exporting" @click="exportImage">{{ exporting ? '导出中…' : '导出长图' }}</button>
          <button type="button" class="cp__btn cp__btn--accent" @click="detailPortrait = null">关闭</button>
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

/* —— 详情弹窗 —— */
.cp-modal { position: fixed; inset: 0; z-index: 1100; display: flex; align-items: center; justify-content: center; padding: 20px; background: rgba(20, 24, 28, 0.4); }
.cp-modal__card { width: min(640px, 96vw); max-height: 88vh; display: flex; flex-direction: column; background: var(--color-surface); border-radius: 16px; box-shadow: 0 16px 48px rgba(0, 0, 0, 0.25); }
.cp-modal__head { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 14px 18px; border-bottom: 1px solid var(--color-paper-3); }
.cp-modal__head strong { font-size: 15px; font-weight: 650; }
.cp-modal__close { display: grid; place-items: center; width: 28px; height: 28px; border: 0; border-radius: 50%; background: var(--color-paper-3); color: var(--color-ink-2); font-size: 13px; cursor: pointer; }
.cp-modal__close:hover { background: var(--color-rule-strong); }
.cp-modal__body { padding: 4px 18px 8px; overflow-y: auto; }
.cp-modal__foot { display: flex; align-items: center; justify-content: flex-end; gap: 8px; padding: 12px 18px; border-top: 1px solid var(--color-paper-3); }

/* 导出目标:弹窗内可见、白底(在流内自然全高;html-to-image 截可见元素才不空白)。 */
.cp-export { background: #fff; padding: 2px; box-sizing: border-box; }
.cp-export__head { display: flex; flex-direction: column; gap: 4px; padding-bottom: 12px; margin-bottom: 4px; border-bottom: 2px solid var(--color-accent); }
.cp-export__head strong { font-size: 17px; font-weight: 700; color: var(--color-ink); }
.cp-export__head span { font-size: 12px; color: var(--color-ink-3); }
.cp-export__foot { margin-top: 14px; padding-top: 10px; border-top: 1px solid var(--color-paper-3); font-size: 11px; color: var(--color-ink-3); text-align: right; }</style>
