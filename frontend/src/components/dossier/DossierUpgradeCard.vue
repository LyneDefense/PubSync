<script setup lang="ts">
// 建档清单④「升详情/采集」弹卡:模式A 批量升(采几篇+图文/视频+成本预估,系统 smart 选片)/
// 模式B 定向补采(粘链接)。自身取估算;确认后 emit,由 view 走 useDossier 跑任务 + 就地进度。
import { computed, onMounted, ref, watch } from 'vue'

import { getCollectEstimate } from '../../api'
import type { CollectEstimate } from '../../api/types'

const props = defineProps<{ bloggerId: number }>()
const emit = defineEmits<{
  (e: 'close'): void
  (e: 'batch', payload: { sampleLimit: number; contentTypes: string[] }): void
  (e: 'urls', urls: string[]): void
}>()

const mode = ref<'batch' | 'urls'>('batch')
const n = ref(80)
const image = ref(true)
const video = ref(true)
const urlsText = ref('')
const estimate = ref<CollectEstimate | null>(null)

const contentTypes = computed(() => [image.value ? 'image' : '', video.value ? 'video' : ''].filter(Boolean))
const urlList = computed(() =>
  urlsText.value
    .split(/[\n\s]+/)
    .map((u) => u.trim())
    .filter((u) => u.startsWith('http'))
)

let timer: ReturnType<typeof setTimeout> | undefined
async function loadEstimate() {
  const limit = Math.max(5, Math.min(200, Math.round(n.value || 0)))
  try {
    estimate.value = await getCollectEstimate(limit, 20, props.bloggerId)
  } catch {
    estimate.value = null
  }
}
watch(n, () => {
  clearTimeout(timer)
  timer = setTimeout(loadEstimate, 400)
})
onMounted(loadEstimate)

function confirmBatch() {
  if (!contentTypes.value.length) return
  emit('batch', { sampleLimit: Math.max(5, Math.min(200, Math.round(n.value || 0))), contentTypes: contentTypes.value })
}
function confirmUrls() {
  if (urlList.value.length) emit('urls', urlList.value)
}
</script>

<template>
  <div class="uc-overlay" @click.self="emit('close')">
    <div class="uc" role="dialog" aria-label="升级详情">
      <div class="uc__head">
        <h3>升级详情 / 采集内容</h3>
        <button type="button" class="uc__x" aria-label="关闭" @click="emit('close')">✕</button>
      </div>

      <div class="uc__tabs">
        <button type="button" :class="{ on: mode === 'batch' }" @click="mode = 'batch'">批量升</button>
        <button type="button" :class="{ on: mode === 'urls' }" @click="mode = 'urls'">定向补采</button>
      </div>

      <!-- 模式 A -->
      <div v-if="mode === 'batch'" class="uc__body">
        <label class="uc__row">
          <span>升级篇数</span>
          <input v-model.number="n" type="number" min="5" max="200" />
        </label>
        <div class="uc__row">
          <span>拉取范围</span>
          <label class="uc__chk"><input v-model="image" type="checkbox" />图文</label>
          <label class="uc__chk"><input v-model="video" type="checkbox" />视频</label>
        </div>
        <p class="uc__hint">系统按「高赞 + 最近优先 + 爆文保底」自动选片;ASR 默认开,每篇采 20 条最高赞评论。</p>
        <p v-if="estimate" class="uc__est">
          预计约 {{ estimate.request_estimate }} 次请求 · ≈ ${{ estimate.cost_usd_min.toFixed(2) }}–${{ estimate.cost_usd_max.toFixed(2) }}
        </p>
        <div class="uc__foot">
          <button type="button" class="uc__cancel" @click="emit('close')">取消</button>
          <button type="button" class="uc__go" :disabled="!contentTypes.length" @click="confirmBatch">开始升级</button>
        </div>
      </div>

      <!-- 模式 B -->
      <div v-else class="uc__body">
        <textarea
          v-model="urlsText"
          rows="4"
          placeholder="粘贴笔记链接,一行一个(复制分享链接即可,需带 xsec_token;短链会自动展开)"
        />
        <p class="uc__hint">用于补漏列表没抓到、或想精确深挖的指定笔记;会校验作者是否为当前博主。</p>
        <div class="uc__foot">
          <button type="button" class="uc__cancel" @click="emit('close')">取消</button>
          <button type="button" class="uc__go" :disabled="!urlList.length" @click="confirmUrls">
            补采 {{ urlList.length }} 条
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.uc-overlay {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(30, 34, 38, 0.42);
}
.uc {
  width: 100%;
  max-width: 440px;
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-lg);
  box-shadow: 0 12px 40px var(--color-shadow);
  padding: 16px 18px 18px;
}
.uc__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.uc__head h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 680;
}
.uc__x {
  border: 0;
  background: transparent;
  color: var(--color-ink-3);
  font-size: 14px;
  cursor: pointer;
}
.uc__tabs {
  display: flex;
  gap: 6px;
  margin: 12px 0;
}
.uc__tabs button {
  flex: 1;
  height: 32px;
  border: 1px solid var(--color-field-border);
  border-radius: 8px;
  background: var(--color-surface);
  color: var(--color-ink-2);
  font-size: 13px;
  cursor: pointer;
}
.uc__tabs button.on {
  border-color: var(--color-accent);
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
  font-weight: 620;
}
.uc__body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.uc__row {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: var(--color-ink-2);
}
.uc__row > span:first-child {
  width: 64px;
  flex: 0 0 auto;
}
.uc__row input[type='number'] {
  width: 90px;
  height: 32px;
  padding: 0 10px;
  border: 1px solid var(--color-field-border);
  border-radius: 8px;
  background: var(--color-field);
  font-size: 13px;
}
.uc__chk {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
}
.uc__body textarea {
  width: 100%;
  border: 1px solid var(--color-field-border);
  border-radius: 9px;
  background: var(--color-field);
  padding: 9px 11px;
  font-size: 13px;
  line-height: 1.5;
  resize: vertical;
}
.uc__hint {
  margin: 0;
  font-size: 12px;
  line-height: 1.55;
  color: var(--color-ink-3);
}
.uc__est {
  margin: 0;
  font-size: 12.5px;
  color: var(--color-ink-2);
  font-variant-numeric: tabular-nums;
}
.uc__foot {
  display: flex;
  justify-content: flex-end;
  gap: 9px;
  margin-top: 4px;
}
.uc__cancel {
  height: 34px;
  padding: 0 14px;
  border: 1px solid var(--color-field-border);
  border-radius: 9px;
  background: var(--color-surface);
  color: var(--color-ink-2);
  font-size: 13px;
  cursor: pointer;
}
.uc__go {
  height: 34px;
  padding: 0 18px;
  border: 0;
  border-radius: 9px;
  background: var(--color-accent);
  color: #fff;
  font-size: 13px;
  font-weight: 620;
  cursor: pointer;
}
.uc__go:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
