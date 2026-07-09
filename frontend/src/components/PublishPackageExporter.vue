<script setup lang="ts">
// 发布包导出:一键导出全文(复制到剪贴板)+ 导出长图(弹窗预览 → toPng 下载)。全类型通用。
// 图片:截图目标是弹窗内「可见、在流内」的 .ppx-card —— html-to-image 截离屏节点会空白,必须截可见元素。
import { computed, ref } from 'vue'
import { toPng } from 'html-to-image'
import type { XhsPublishPackage, XhsPublishPackageDraft } from '../api/types'
import { buildPackageFullText, parseJsonArray, parseJsonObject, xhsContentTypeLabel } from '../utils/format'
import { copyText, showMessage } from '../composables/useWorkspaceStore'

const props = defineProps<{ pkg: XhsPublishPackage | XhsPublishPackageDraft; bloggerName?: string }>()

const hashtags = computed(() => parseJsonArray(props.pkg.hashtags_json).map((t) => `#${String(t).replace(/^#/, '')}`))
const imagePlan = computed(() => parseJsonArray(props.pkg.image_plan_json))
const script = computed(() => parseJsonObject(props.pkg.script_json))
const segments = computed(() => (Array.isArray(script.value.segments) ? (script.value.segments as Record<string, unknown>[]) : []))
const hook = computed(() => String(script.value.hook || ''))
const pacing = computed(() => String(script.value.pacing || ''))
const shootingNotes = computed(() => (Array.isArray(script.value.shooting_notes) ? (script.value.shooting_notes as unknown[]).map(String) : []))
const isImage = computed(() => props.pkg.content_type === 'image_note')
const isVideo = computed(() => props.pkg.content_type === 'video_script')
const isScript = computed(() => props.pkg.content_type === 'video_script' || props.pkg.content_type === 'spoken_script')
const typeLabel = computed(() => xhsContentTypeLabel(props.pkg.content_type))

function onCopyText() {
  copyText(buildPackageFullText(props.pkg), '发布包全文')
}

const showImg = ref(false)
const cardEl = ref<HTMLElement | null>(null)
const exporting = ref(false)
async function downloadImage() {
  const el = cardEl.value
  if (!el || exporting.value) return
  exporting.value = true
  try {
    const url = await toPng(el, { pixelRatio: 2, backgroundColor: '#ffffff', cacheBust: true })
    const a = document.createElement('a')
    a.href = url
    a.download = `发布包_${(props.pkg.title || 'draft').slice(0, 20)}.png`
    a.click()
    showMessage('已导出发布包长图')
  } catch (err) {
    showMessage(err instanceof Error ? err.message : '导出图片失败,请重试', true)
  } finally {
    exporting.value = false
  }
}
</script>

<template>
  <div class="ppx">
    <button type="button" class="ppx-btn" @click="showImg = true">
      <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="8.5" cy="8.5" r="1.5" /><path d="M21 15l-5-5L5 21" /></svg>
      导出图片
    </button>
    <button type="button" class="ppx-btn" @click="onCopyText">
      <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="12" height="12" rx="2" /><path d="M5 15V5a2 2 0 012-2h10" /></svg>
      导出文字
    </button>
  </div>

  <div v-if="showImg" class="pxm" @click.self="showImg = false">
    <div class="pxm-shell">
      <div class="pxm-head">
        <strong>导出长图</strong>
        <button type="button" class="pxm-x" aria-label="关闭" @click="showImg = false">✕</button>
      </div>
      <div class="pxm-body">
        <!-- 截图目标:可见、在流内、自然全高 -->
        <div ref="cardEl" class="ppx-card">
          <div class="ppx-card-head">
            <strong>{{ pkg.title || '未命名发布包' }}</strong>
            <span>{{ bloggerName ? `对标 ${bloggerName} · ` : '' }}{{ typeLabel }}</span>
          </div>

          <div v-if="pkg.body_text" class="ppx-sec">
            <div class="ppx-lbl">正文</div>
            <p class="ppx-text">{{ pkg.body_text }}</p>
          </div>

          <div v-if="isImage && imagePlan.length" class="ppx-sec">
            <div class="ppx-lbl">配图方案 · {{ imagePlan.length }} 张</div>
            <div v-for="(img, i) in imagePlan" :key="i" class="ppx-img">
              <b>图 {{ img.slot || i + 1 }}<span v-if="img.purpose"> · {{ img.purpose }}</span></b>
              <span v-if="img.caption">图上文案:{{ img.caption }}</span>
              <span v-if="img.format">版式:{{ img.format }}</span>
              <span v-if="img.prompt" class="ppx-dim">生图 prompt:{{ img.prompt }}</span>
            </div>
          </div>

          <div v-if="isScript && (segments.length || hook || pacing)" class="ppx-sec">
            <div class="ppx-lbl">{{ isVideo ? '分镜脚本' : '口播脚本' }}</div>
            <div v-if="hook" class="ppx-meta"><b>开头钩子</b>{{ hook }}</div>
            <div v-if="pacing" class="ppx-meta"><b>整体节奏</b>{{ pacing }}</div>
            <div v-for="(seg, i) in segments" :key="i" class="ppx-seg">
              <div class="ppx-seg-h">镜头 {{ i + 1 }}<span v-if="seg.start"> · {{ seg.start }}<span v-if="seg.end">-{{ seg.end }}</span></span></div>
              <span v-if="seg.shot_type"><i>景别/运镜</i>{{ seg.shot_type }}</span>
              <span v-if="seg.scene"><i>画面</i>{{ seg.scene }}</span>
              <span v-if="seg.voiceover"><i>口播</i>{{ seg.voiceover }}</span>
              <span v-if="seg.subtitle"><i>字幕</i>{{ seg.subtitle }}</span>
            </div>
            <div v-if="shootingNotes.length" class="ppx-meta"><b>拍摄建议</b>{{ shootingNotes.join('；') }}</div>
          </div>

          <div v-if="pkg.cover_text" class="ppx-sec">
            <div class="ppx-lbl">封面文案</div>
            <p class="ppx-text">{{ pkg.cover_text }}</p>
          </div>

          <div v-if="hashtags.length" class="ppx-sec">
            <div class="ppx-lbl">话题标签</div>
            <p class="ppx-tags">{{ hashtags.join('  ') }}</p>
          </div>

          <div class="ppx-foot">由 Cadence 生成 · {{ new Date().toLocaleDateString('zh-CN') }}</div>
        </div>
      </div>
      <div class="pxm-foot">
        <button type="button" class="ppx-btn" @click="showImg = false">关闭</button>
        <button type="button" class="ppx-btn ppx-btn--primary" :disabled="exporting" @click="downloadImage">{{ exporting ? '导出中…' : '下载长图' }}</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ppx { display: inline-flex; gap: 8px; }
.ppx-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 32px;
  min-height: 0;
  padding: 0 12px;
  border: 1px solid var(--color-rule-strong);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  color: var(--color-ink-2);
  font-size: 12.5px;
  font-weight: 550;
  cursor: pointer;
  white-space: nowrap;
}
.ppx-btn:hover { border-color: var(--color-accent-soft-bd); color: var(--color-ink); }
.ppx-btn--primary { border: 0; background: var(--color-accent); color: #fff; }
.ppx-btn--primary:hover { background: var(--color-accent-press); color: #fff; }
.ppx-btn--primary:disabled { opacity: 0.6; cursor: not-allowed; }

/* —— 导出弹窗 —— */
.pxm { position: fixed; inset: 0; z-index: 1200; display: flex; align-items: center; justify-content: center; padding: 20px; background: rgba(20, 24, 28, 0.42); }
.pxm-shell { width: min(600px, 96vw); max-height: 90vh; display: flex; flex-direction: column; background: var(--color-surface); border-radius: 16px; box-shadow: 0 16px 48px rgba(0, 0, 0, 0.25); }
.pxm-head { display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid var(--color-paper-3); }
.pxm-head strong { font-size: 15px; font-weight: 650; }
.pxm-x { display: grid; place-items: center; width: 28px; height: 28px; min-height: 0; padding: 0; border: 0; border-radius: 50%; background: var(--color-paper-3); color: var(--color-ink-2); font-size: 13px; cursor: pointer; }
.pxm-x:hover { background: var(--color-rule); }
.pxm-body { padding: 14px 18px; overflow-y: auto; background: var(--color-paper); }
.pxm-foot { display: flex; align-items: center; justify-content: flex-end; gap: 8px; padding: 12px 18px; border-top: 1px solid var(--color-paper-3); }

/* —— 截图卡(白底、固定宽、自然全高) —— */
.ppx-card { background: #fff; border-radius: 12px; padding: 22px 24px; box-sizing: border-box; }
.ppx-card-head { padding-bottom: 14px; margin-bottom: 4px; border-bottom: 2px solid var(--color-accent); }
.ppx-card-head strong { display: block; font-family: var(--font-display); font-size: 18px; font-weight: 700; color: #1a2320; line-height: 1.4; }
.ppx-card-head span { display: block; margin-top: 4px; font-size: 12px; color: #8a988f; }
.ppx-sec { margin-top: 16px; }
.ppx-lbl { font-family: var(--font-display); font-size: 12px; font-weight: 650; color: var(--color-accent-ink); margin-bottom: 6px; }
.ppx-text { margin: 0; font-size: 13.5px; line-height: 1.7; color: #2a332e; white-space: pre-wrap; word-break: break-word; }
.ppx-tags { margin: 0; font-size: 13px; line-height: 1.7; color: var(--color-accent-ink); word-break: break-word; }
.ppx-img, .ppx-seg { display: flex; flex-direction: column; gap: 2px; padding: 9px 0; border-bottom: 1px solid #eef1ef; font-size: 12.5px; color: #3a443e; line-height: 1.5; }
.ppx-img:last-child, .ppx-seg:last-child { border-bottom: 0; }
.ppx-img b, .ppx-seg-h { font-weight: 650; color: #1a2320; font-size: 13px; }
.ppx-seg-h { margin-bottom: 2px; }
.ppx-seg span i, .ppx-dim { color: #8a988f; font-style: normal; }
.ppx-seg span i { display: inline-block; min-width: 62px; margin-right: 4px; }
.ppx-meta { padding: 7px 0; font-size: 12.5px; color: #3a443e; line-height: 1.55; }
.ppx-meta b { display: inline-block; min-width: 62px; margin-right: 6px; color: var(--color-accent-ink); font-weight: 600; }
.ppx-foot { margin-top: 18px; padding-top: 12px; border-top: 1px solid #eef1ef; font-size: 11px; color: #8a988f; text-align: right; }
</style>
