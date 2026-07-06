<script setup lang="ts">
// 档案页·受众需求(读者最常问):从读者评论 LLM 归纳,按钮触发。选题输入,受众侧,正交于蒸馏(创作者侧)。
// 取代旧「爆文归因」——不做因果、不装推流/热点。
import type { DossierAudience } from '../../api/types'

defineProps<{ audience: DossierAudience | null; audienceRunning: boolean; busy: boolean }>()
defineEmits<{ (e: 'run-audience'): void }>()
</script>

<template>
  <section class="da">
    <div class="da__head">
      <h3>受众需求 · 读者最常问</h3>
    </div>

    <template v-if="audience">
      <div v-if="audience.questions.length" class="da__list">
        <div v-for="(q, i) in audience.questions" :key="i" class="da__q">
          <span class="da__q-idx">{{ i + 1 }}</span>
          <span class="da__q-body">
            <b>{{ q.theme }}</b>
            <span v-if="q.sample" class="da__q-sample">“{{ q.sample }}”</span>
          </span>
        </div>
      </div>
      <p v-else class="da__empty">没归纳出反复出现的问题(读者评论较分散)。</p>

      <div v-if="audience.focus_points.length" class="da__focus">
        <span class="da__focus-label">高频关注</span>
        <span v-for="(f, i) in audience.focus_points" :key="i" class="da__focus-chip">{{ f }}</span>
      </div>

      <div class="da__foot">
        <span class="da__note">{{ audience.note || `依据 ${audience.comment_count} 条读者评论,非穷举。` }}</span>
        <button type="button" class="da__btn" :disabled="audienceRunning || busy" @click="$emit('run-audience')">
          {{ audienceRunning ? '重新分析中…' : '重新分析' }}
        </button>
      </div>
    </template>

    <div v-else class="da__cta">
      <p class="da__cta-text">从这个博主笔记的<strong>读者评论</strong>里,归纳读者最常问的问题与关注点——直接拿来做选题。</p>
      <button type="button" class="da__btn da__btn--primary" :disabled="audienceRunning || busy" @click="$emit('run-audience')">
        {{ audienceRunning ? '分析中…' : '分析读者需求' }}
      </button>
      <span class="da__cta-hint">依据已采顶层评论(非全量);评论过少会提示先多采一些。</span>
    </div>
  </section>
</template>

<style scoped>
.da { background: var(--color-surface); border: 1px solid var(--color-rule); border-radius: 14px; padding: 20px 22px; }
.da__head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.da__head h3 { margin: 0; font-size: 15px; font-weight: 650; }
.da__hint { font-size: 12px; color: var(--color-ink-3); }

.da__list { display: flex; flex-direction: column; gap: 10px; }
.da__q { display: flex; gap: 10px; align-items: flex-start; }
.da__q-idx {
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  border-radius: 6px;
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
  font-size: 11px;
  font-weight: 700;
  margin-top: 1px;
}
.da__q-body { min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.da__q-body b { font-size: 13.5px; color: var(--color-ink); line-height: 1.5; }
.da__q-sample { font-size: 12px; color: var(--color-ink-3); line-height: 1.5; }
.da__empty { margin: 0; font-size: 12.5px; color: var(--color-ink-3); }

.da__focus { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--color-paper-3); }
.da__focus-label { font-size: 12px; color: var(--color-ink-3); }
.da__focus-chip { font-size: 12px; padding: 2px 10px; border-radius: 999px; background: var(--color-paper); border: 1px solid var(--color-rule); color: var(--color-ink-2); }

.da__foot { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-top: 14px; }
.da__note { font-size: 11.5px; color: var(--color-ink-3); flex: 1; min-width: 0; }
.da__btn {
  height: 32px;
  padding: 0 14px;
  border: 1px solid var(--color-rule);
  border-radius: 9px;
  background: var(--color-surface);
  font-size: 12.5px;
  font-weight: 600;
  color: var(--color-ink-2);
  cursor: pointer;
  white-space: nowrap;
  transition: background 140ms var(--ease-out);
}
.da__btn:hover:not(:disabled) { background: var(--color-paper); }
.da__btn:disabled { opacity: 0.55; cursor: not-allowed; }
.da__btn--primary { border: 0; background: var(--color-accent); color: #fff; }
.da__btn--primary:hover:not(:disabled) { background: var(--color-accent-press); }

.da__cta { display: flex; flex-direction: column; align-items: flex-start; gap: 10px; }
.da__cta-text { margin: 0; font-size: 13px; color: var(--color-ink-2); line-height: 1.6; }
.da__cta-text strong { color: var(--color-ink); }
.da__cta-hint { font-size: 11.5px; color: var(--color-ink-3); }
</style>
