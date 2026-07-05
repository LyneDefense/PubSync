<script setup lang="ts">
// 档案页·合规体检:按博主自身赛道扫全量池的广告法红线。模仿护栏——蒸馏会继承这些写法。
import { computed } from 'vue'
import type { DossierCompliance } from '../../api/types'

const props = defineProps<{ compliance: DossierCompliance }>()

const level = computed(() => {
  const c = props.compliance
  if (c.has_ban) return { cls: 'danger', text: '高风险', icon: '⚠' }
  const hitCount = (c.violations?.length || 0) + (c.hits?.length || 0)
  if (hitCount > 0) return { cls: 'warn', text: '轻微风险', icon: '⚠' }
  return { cls: 'ok', text: '干净', icon: '✓' }
})

// 命中项去重成 chips(规则 + 词),取前若干。
const chips = computed(() => {
  const seen = new Set<string>()
  const out: { word: string; rule: string }[] = []
  for (const h of props.compliance.hits || []) {
    const key = `${h.word}·${h.rule}`
    if (seen.has(key)) continue
    seen.add(key)
    out.push({ word: h.word, rule: h.rule })
    if (out.length >= 6) break
  }
  return out
})

const hitTotal = computed(() => (props.compliance.hits || []).length)
const cov = computed(() => props.compliance.coverage)
</script>

<template>
  <section class="dc">
    <div class="dc__head">
      <h3>合规体检</h3>
      <span class="dc__sub">按赛道扫红线 · 模仿护栏</span>
    </div>

    <div class="dc__grade-row">
      <span class="dc__grade" :class="`dc__grade--${level.cls}`">{{ level.icon }} {{ level.text }}</span>
      <span v-if="hitTotal" class="dc__count">命中 {{ hitTotal }} 处红线</span>
      <span v-else class="dc__count">未命中红线</span>
    </div>

    <div v-if="chips.length" class="dc__chips">
      <span v-for="c in chips" :key="`${c.word}-${c.rule}`" class="dc__chip" :class="`dc__chip--${level.cls}`">{{ c.rule }} · 「{{ c.word }}」</span>
    </div>

    <p class="dc__foot">
      <span v-if="cov">依据已收录 {{ cov.pool }} 篇（标题级全覆盖 · 正文级 {{ cov.full_text }} 篇）。</span>
      <span v-if="hitTotal" class="dc__foot-warn">蒸馏会带上这些写法，创作时注意规避。</span>
    </p>
  </section>
</template>

<style scoped>
.dc { background: var(--color-surface); border: 1px solid var(--color-rule); border-radius: 14px; padding: 20px 22px; }
.dc__head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.dc__head h3 { margin: 0; font-size: 15px; font-weight: 650; }
.dc__sub { font-size: 12px; color: var(--color-ink-3); }
.dc__grade-row { display: flex; align-items: center; gap: 11px; margin-bottom: 12px; }
.dc__grade { display: inline-flex; align-items: center; gap: 5px; padding: 3px 12px; border-radius: 999px; font-size: 13px; font-weight: 600; }
.dc__grade--ok { background: var(--color-ok-bg); color: var(--color-ok); }
.dc__grade--warn { background: #fdf3e0; color: #8a5a12; }
.dc__grade--danger { background: #fceceb; color: var(--color-danger); }
.dc__count { font-size: 12.5px; color: var(--color-ink-2); }
.dc__chips { display: flex; gap: 8px; flex-wrap: wrap; }
.dc__chip { font-size: 12px; padding: 3px 10px; border-radius: 999px; }
.dc__chip--warn { background: #fdf3e0; color: #8a5a12; }
.dc__chip--danger { background: #fceceb; color: var(--color-danger); }
.dc__chip--ok { background: var(--color-paper-3); color: var(--color-ink-2); }
.dc__foot { margin: 12px 0 0; padding-top: 11px; border-top: 1px dashed var(--color-rule); font-size: 12px; color: var(--color-ink-3); line-height: 1.55; }
.dc__foot-warn { color: var(--color-ink-2); margin-left: 4px; }
</style>
