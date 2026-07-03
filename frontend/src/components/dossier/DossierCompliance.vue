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

// 命中项去重成 chips(词 + 规则),取前若干。
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
  <section class="dossier-block">
    <header class="dossier-block__head">
      <h3>合规体检</h3>
      <span class="dossier-block__hint">按博主赛道扫红线 · 模仿护栏</span>
    </header>

    <div class="dc-head">
      <span class="dc-grade" :class="`dc-grade--${level.cls}`">{{ level.icon }} {{ level.text }}</span>
      <span v-if="hitTotal" class="dc-count">命中 {{ hitTotal }} 处红线</span>
      <span v-else class="dc-count">未命中红线</span>
    </div>

    <div v-if="chips.length" class="dc-chips">
      <span v-for="c in chips" :key="`${c.word}-${c.rule}`" class="dc-chip" :class="`dc-chip--${level.cls}`">{{ c.rule }} · 「{{ c.word }}」</span>
    </div>

    <p class="dc-foot">
      <span v-if="cov">依据已收录 {{ cov.pool }} 篇（标题级全覆盖 · 正文级 {{ cov.full_text }} 篇）。</span>
      <span v-if="hitTotal" class="dc-warn-note">蒸馏会带上这些写法，创作时注意规避。</span>
    </p>
  </section>
</template>

<style scoped>
.dc-head { display: flex; align-items: center; gap: 11px; margin-bottom: 10px; }
.dc-grade { display: inline-flex; align-items: center; gap: 5px; padding: 3px 11px; border-radius: 999px; font-size: 13px; font-weight: 600; }
.dc-grade--ok { background: var(--color-ok-bg); color: var(--color-ok); }
.dc-grade--warn { background: #fdf3e0; color: #8a5a12; }
.dc-grade--danger { background: #fceceb; color: var(--color-danger); }
.dc-count { font-size: 12.5px; color: var(--color-ink-2); }
.dc-chips { display: flex; gap: 8px; flex-wrap: wrap; }
.dc-chip { font-size: 12px; padding: 2px 9px; border-radius: 999px; }
.dc-chip--warn { background: #fdf3e0; color: #8a5a12; }
.dc-chip--danger { background: #fceceb; color: var(--color-danger); }
.dc-chip--ok { background: var(--color-paper-3); color: var(--color-ink-2); }
.dc-foot { margin: 11px 0 0; padding-top: 10px; border-top: 1px dashed var(--color-rule); font-size: 12px; color: var(--color-ink-3); line-height: 1.55; }
.dc-warn-note { color: var(--color-ink-2); margin-left: 4px; }
</style>
