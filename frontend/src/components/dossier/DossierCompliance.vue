<script setup lang="ts">
// 档案页·合规体检:按博主自身赛道扫全量池的广告法红线。模仿护栏——蒸馏会继承这些写法。
// 卡片给概览(等级 + 命中数 + 类别 chips);「查看详情」弹出与诊断报告同款的分级明细。
import { computed, ref } from 'vue'
import type { DossierCompliance } from '../../api/types'

const props = defineProps<{ compliance: DossierCompliance }>()

const violations = computed(() => props.compliance.violations || [])
const advisories = computed(() => props.compliance.advisories || [])
const legacyHits = computed(() => (violations.value.length || advisories.value.length ? [] : props.compliance.hits || []))
const verticalLabels = computed(() => props.compliance.vertical_labels || [])
const coverage = computed(() => props.compliance.coverage)

const hitCount = computed(() => violations.value.length || legacyHits.value.length)
const hasDetail = computed(() => violations.value.length > 0 || advisories.value.length > 0 || legacyHits.value.length > 0)

// 等级药丸:封号级命中 → 高风险;有违规 → 轻微风险;仅提示 → 需留意;都无 → 干净。
const level = computed(() => {
  const c = props.compliance
  if (c.has_ban) return { cls: 'danger', text: '高风险', icon: '⚠' }
  if (violations.value.length || legacyHits.value.length) return { cls: 'warn', text: c.grade || '轻微风险', icon: '⚠' }
  if (advisories.value.length) return { cls: 'notice', text: '需留意', icon: '·' }
  return { cls: 'ok', text: '干净', icon: '✓' }
})

// 概览 chips:取违规类别(退化到扁平命中的类别),去重取前 4。
const chips = computed(() => {
  const seen = new Set<string>()
  const out: string[] = []
  const src = violations.value.length ? violations.value.map((v) => v.category) : legacyHits.value.map((h) => h.category || '')
  for (const c of src) {
    if (!c || seen.has(c)) continue
    seen.add(c)
    out.push(c)
    if (out.length >= 4) break
  }
  return out
})

function sevClass(sev: string): string {
  return sev === '封号级' ? 'sev-ban' : sev === '限流级' ? 'sev-warn' : 'sev-notice'
}

const detailOpen = ref(false)
</script>

<template>
  <section class="dc">
    <div class="dc__head">
      <h3>合规体检</h3>
      <span class="dc__sub">按赛道扫红线 · 模仿护栏</span>
    </div>

    <div class="dc__grade-row">
      <span class="dc__grade" :class="`dc__grade--${level.cls}`">{{ level.icon }} {{ level.text }}</span>
      <span v-if="hitCount" class="dc__count">命中 {{ hitCount }} 类红线</span>
      <span v-else-if="advisories.length" class="dc__count">{{ advisories.length }} 条优化提示</span>
      <span v-else class="dc__count">未命中红线</span>
    </div>

    <p v-if="verticalLabels.length" class="dc__verticals">按「{{ verticalLabels.join(' · ') }} · 通用」规则检测</p>

    <div v-if="chips.length" class="dc__chips">
      <span v-for="c in chips" :key="c" class="dc__chip" :class="`dc__chip--${level.cls}`">{{ c }}</span>
    </div>

    <div class="dc__foot">
      <p class="dc__foot-note">
        <span v-if="coverage">依据已收录 {{ coverage.pool }} 篇（标题级全覆盖 · 正文级 {{ coverage.full_text }} 篇）。</span>
        <span v-if="hitCount" class="dc__foot-warn">蒸馏会带上这些写法，创作时注意规避。</span>
      </p>
      <button v-if="hasDetail" type="button" class="dc__detail-btn" @click="detailOpen = true">查看详情 →</button>
    </div>

    <!-- 详情弹窗:与诊断报告同款分级明细 -->
    <div v-if="detailOpen" class="dc-modal" @click.self="detailOpen = false">
      <div class="dc-modal__card">
        <div class="dc-modal__head">
          <div class="dc-modal__title">
            <strong>合规体检详情</strong>
            <span class="dc__grade" :class="`dc__grade--${level.cls}`">{{ level.icon }} {{ level.text }}</span>
          </div>
          <button type="button" class="dc-modal__close" aria-label="关闭" @click="detailOpen = false">✕</button>
        </div>

        <div class="dc-modal__body">
          <p v-if="verticalLabels.length" class="dc__verticals">按「{{ verticalLabels.join(' · ') }} · 通用」规则检测</p>

          <!-- 违规(需处置) -->
          <template v-if="violations.length">
            <p class="dc-modal__sec">需处置 · {{ violations.length }} 类</p>
            <div v-for="(g, i) in violations" :key="`v${i}`" class="dc-hit" :class="sevClass(g.severity)">
              <span class="dc-sev" :class="sevClass(g.severity)">{{ g.severity }}</span>
              <div class="dc-hit__body">
                <b>{{ g.category }}</b>
                <span v-if="g.coverage && g.coverage.total_notes > 1" class="dc-cover">命中 {{ g.coverage.hit_notes }}/{{ g.coverage.total_notes }} 篇</span>
                <span v-if="g.matched && g.matched.length" class="dc-quote">{{ g.matched.join('、') }}</span>
                <span v-if="g.sample_titles && g.sample_titles.length" class="dc-notes">
                  涉及笔记:<em v-for="(t, ti) in g.sample_titles" :key="ti">《{{ t }}》</em><em v-if="g.coverage && g.coverage.hit_notes > g.sample_titles.length" class="dc-notes-more">等 {{ g.coverage.hit_notes }} 篇</em>
                </span>
                <span v-if="g.hint" class="dc-sugg">→ {{ g.hint }}</span>
                <span v-if="g.basis" class="dc-basis">依据:{{ g.basis }}</span>
              </div>
            </div>
          </template>

          <!-- 兼容:旧扁平命中 -->
          <template v-else-if="legacyHits.length">
            <p class="dc-modal__sec">命中 · {{ legacyHits.length }} 处</p>
            <div v-for="(h, i) in legacyHits" :key="`l${i}`" class="dc-hit" :class="sevClass(h.severity)">
              <span class="dc-sev" :class="sevClass(h.severity)">{{ h.severity }}</span>
              <div class="dc-hit__body">
                <b>{{ h.category }}</b>
                <span v-if="h.matched" class="dc-quote">{{ h.matched }}</span>
                <span v-if="h.quote" class="dc-quote">「{{ h.quote }}」</span>
                <span v-if="h.suggestion" class="dc-sugg">→ {{ h.suggestion }}</span>
              </div>
            </div>
          </template>

          <!-- 优化提示(不计入违规) -->
          <template v-if="advisories.length">
            <p class="dc-modal__sec">优化提示 · {{ advisories.length }} 条<span>(不算违规,酌情调整)</span></p>
            <div v-for="(g, i) in advisories" :key="`a${i}`" class="dc-adv">
              <b>{{ g.category }}</b>
              <span v-if="g.matched && g.matched.length" class="dc-quote">{{ g.matched.join('、') }}</span>
              <span v-if="g.sample_titles && g.sample_titles.length" class="dc-notes">涉及笔记:<em v-for="(t, ti) in g.sample_titles" :key="ti">《{{ t }}》</em></span>
              <span v-if="g.hint" class="dc-sugg">→ {{ g.hint }}</span>
            </div>
          </template>

          <p class="dc-modal__cover">
            <span v-if="coverage">依据已收录 {{ coverage.pool }} 篇（标题级全覆盖 · 正文级 {{ coverage.full_text }} 篇）。</span>
            纯规则扫描,不代表平台判罚;蒸馏会继承这些写法,创作时注意规避。
          </p>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.dc { background: var(--color-surface); border: 1px solid var(--color-rule); border-radius: 14px; padding: 20px 22px; }
.dc__head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.dc__head h3 { margin: 0; font-size: 15px; font-weight: 650; }
.dc__sub { font-size: 12px; color: var(--color-ink-3); }
.dc__grade-row { display: flex; align-items: center; gap: 11px; margin-bottom: 8px; }
.dc__grade { display: inline-flex; align-items: center; gap: 5px; padding: 3px 12px; border-radius: 999px; font-size: 13px; font-weight: 600; }
.dc__grade--ok { background: var(--color-ok-bg); color: var(--color-ok); }
.dc__grade--warn { background: #fdf3e0; color: #8a5a12; }
.dc__grade--notice { background: var(--color-paper-3); color: var(--color-ink-2); }
.dc__grade--danger { background: #fceceb; color: var(--color-danger); }
.dc__count { font-size: 12.5px; color: var(--color-ink-2); }
.dc__verticals { margin: 0 0 8px; font-size: 11.5px; color: var(--color-ink-3); }
.dc__chips { display: flex; gap: 8px; flex-wrap: wrap; }
.dc__chip { font-size: 12px; padding: 3px 10px; border-radius: 999px; }
.dc__chip--warn { background: #fdf3e0; color: #8a5a12; }
.dc__chip--danger { background: #fceceb; color: var(--color-danger); }
.dc__chip--notice, .dc__chip--ok { background: var(--color-paper-3); color: var(--color-ink-2); }

.dc__foot { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; margin-top: 12px; padding-top: 11px; border-top: 1px dashed var(--color-rule); flex-wrap: wrap; }
.dc__foot-note { margin: 0; font-size: 12px; color: var(--color-ink-3); line-height: 1.55; flex: 1; min-width: 180px; }
.dc__foot-warn { color: var(--color-ink-2); margin-left: 4px; }
.dc__detail-btn {
  flex: 0 0 auto;
  height: 30px;
  padding: 0 12px;
  border: 1px solid var(--color-accent-soft-bd);
  border-radius: 8px;
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  transition: background 140ms var(--ease-out);
}
.dc__detail-btn:hover { background: var(--color-accent-soft); filter: brightness(0.97); }

/* —— 详情弹窗 —— */
.dc-modal { position: fixed; inset: 0; z-index: 1100; display: flex; align-items: center; justify-content: center; padding: 20px; background: rgba(20, 24, 28, 0.4); }
.dc-modal__card { width: min(560px, 96vw); max-height: 86vh; display: flex; flex-direction: column; background: var(--color-surface); border-radius: 16px; box-shadow: 0 16px 48px rgba(0, 0, 0, 0.25); }
.dc-modal__head { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 14px 18px; border-bottom: 1px solid var(--color-paper-3); }
.dc-modal__title { display: flex; align-items: center; gap: 10px; }
.dc-modal__title strong { font-size: 15px; font-weight: 650; }
.dc-modal__close { display: grid; place-items: center; width: 28px; height: 28px; border: 0; border-radius: 50%; background: var(--color-paper-3); color: var(--color-ink-2); font-size: 13px; cursor: pointer; }
.dc-modal__close:hover { background: var(--color-rule-strong); }
.dc-modal__body { padding: 14px 18px 18px; overflow-y: auto; }
.dc-modal__sec { margin: 14px 0 8px; font-size: 12.5px; font-weight: 650; color: var(--color-ink-2); }
.dc-modal__sec:first-child { margin-top: 4px; }
.dc-modal__sec span { font-weight: 400; color: var(--color-ink-3); font-size: 11.5px; margin-left: 6px; }
.dc-modal__cover { margin: 16px 0 0; padding-top: 12px; border-top: 1px dashed var(--color-rule); font-size: 11.5px; color: var(--color-ink-3); line-height: 1.6; }

.dc-hit { display: flex; gap: 10px; align-items: flex-start; padding: 10px 0; border-top: 1px solid var(--color-paper-3); }
.dc-hit:first-of-type { border-top: 0; }
.dc-sev { flex: 0 0 auto; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 6px; margin-top: 1px; white-space: nowrap; }
.dc-sev.sev-ban { background: #fceceb; color: var(--color-danger); }
.dc-sev.sev-warn { background: #fdf3e0; color: #8a5a12; }
.dc-sev.sev-notice { background: var(--color-paper-3); color: var(--color-ink-2); }
.dc-hit__body { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.dc-hit__body b { font-size: 13px; color: var(--color-ink); }
.dc-cover { font-size: 11.5px; color: var(--color-ink-3); }
.dc-quote { font-size: 12.5px; color: var(--color-ink-2); }
.dc-sugg { font-size: 12px; color: var(--color-accent-ink); }
.dc-basis { font-size: 11.5px; color: var(--color-ink-3); line-height: 1.5; }
.dc-notes { font-size: 12px; color: var(--color-ink-2); line-height: 1.6; }
.dc-notes em { font-style: normal; color: var(--color-ink); }
.dc-notes-more { color: var(--color-ink-3); margin-left: 2px; }
.dc-adv { display: flex; flex-direction: column; gap: 3px; padding: 8px 0; border-top: 1px solid var(--color-paper-3); }
.dc-adv:first-of-type { border-top: 0; }
.dc-adv b { font-size: 12.5px; color: var(--color-ink); }

@media (prefers-reduced-motion: no-preference) {
  .dc-modal__card { animation: dc-pop 0.14s var(--ease-out); }
}
@keyframes dc-pop { from { transform: translateY(6px); opacity: 0.6; } to { transform: none; opacity: 1; } }
</style>
