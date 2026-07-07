<script setup lang="ts">
// 配图方案(不代生成图):每张给 版式/画幅 · 用途 · 图上文案 · 可直接拿去 AI 工具生图的中文 prompt(可复制)。
import { copyText } from '../composables/useWorkspaceStore'

defineProps<{
  // image_plan 从 JSON 解析,松散类型;这里读 slot/purpose/caption/format/prompt。
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  plan: any[]
}>()

function field(item: Record<string, unknown>, key: string): string {
  return String(item?.[key] ?? '').trim()
}
</script>

<template>
  <div class="ipl">
    <p class="ipl__hint">配图方案 · 共 {{ plan.length }} 张 —— 我们不代生成图,把每张的 prompt 拿去你的 AI 绘图工具生成即可。</p>
    <ol class="ipl__list">
      <li v-for="(item, index) in plan" :key="index" class="ipl__card">
        <div class="ipl__head">
          <span class="ipl__slot">第 {{ field(item, 'slot') || index + 1 }} 张</span>
          <span v-if="field(item, 'format')" class="ipl__format">{{ field(item, 'format') }}</span>
        </div>
        <p v-if="field(item, 'purpose')" class="ipl__row"><em>用途</em>{{ field(item, 'purpose') }}</p>
        <p v-if="field(item, 'caption')" class="ipl__row"><em>图上文案</em>{{ field(item, 'caption') }}</p>
        <div v-if="field(item, 'prompt')" class="ipl__prompt">
          <div class="ipl__prompt-head">
            <span>生图 prompt(中文)</span>
            <button type="button" class="ipl__copy" @click="copyText(field(item, 'prompt'), '生图 prompt')">复制</button>
          </div>
          <code>{{ field(item, 'prompt') }}</code>
        </div>
      </li>
    </ol>
  </div>
</template>

<style scoped>
.ipl { display: flex; flex-direction: column; gap: 10px; }
.ipl__hint { margin: 0; font-size: 12.5px; color: var(--color-ink-3); }
.ipl__list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
.ipl__card {
  border: 1px solid var(--color-rule);
  border-radius: 11px;
  background: var(--color-surface);
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.ipl__head { display: flex; align-items: center; gap: 10px; }
.ipl__slot { font-size: 13px; font-weight: 640; color: var(--color-ink); }
.ipl__format {
  font-size: 11.5px;
  padding: 2px 9px;
  border-radius: 999px;
  background: var(--color-paper-3);
  color: var(--color-ink-2);
}
.ipl__row { margin: 0; font-size: 12.5px; color: var(--color-ink-2); line-height: 1.55; }
.ipl__row em { font-style: normal; color: var(--color-ink-3); margin-right: 8px; }
.ipl__prompt {
  margin-top: 2px;
  border: 1px solid var(--color-field-border);
  border-radius: 9px;
  background: var(--color-paper-3);
  padding: 8px 10px;
}
.ipl__prompt-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px; }
.ipl__prompt-head span { font-size: 11.5px; color: var(--color-ink-3); }
.ipl__copy {
  border: 1px solid var(--color-field-border);
  border-radius: 7px;
  background: var(--color-surface);
  color: var(--color-ink-2);
  font-size: 11.5px;
  padding: 2px 10px;
  cursor: pointer;
}
.ipl__copy:hover { border-color: var(--color-accent); color: var(--color-accent-ink); }
.ipl__prompt code {
  display: block;
  font-size: 12px;
  line-height: 1.5;
  color: var(--color-ink);
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
