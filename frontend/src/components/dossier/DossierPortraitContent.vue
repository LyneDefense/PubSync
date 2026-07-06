<script setup lang="ts">
// 画像内容:把该画像对应蒸馏 run 的 report_json.distillation 结构化展示。
// 认知 · 她怎么想(核心信念/观点张力/价值立场)+ 方法 · 她怎么写(选题思路 + 分车道写法)。旧形态(strategy_layer)兜底。
import { computed, ref } from 'vue'
import { bloggerRuns, SUBTYPE_LABELS } from '../../composables/useWorkspaceStore'

const props = defineProps<{ runId: number; compact?: boolean }>()

type Dist = Record<string, unknown>
const distillation = computed<Dist | null>(() => {
  const run = bloggerRuns.value.find((r) => r.id === props.runId)
  if (!run?.report_json) return null
  try {
    const parsed = JSON.parse(run.report_json)
    return (parsed?.distillation as Dist) || null
  } catch {
    return null
  }
})

function list(obj: unknown, key: string): string[] {
  const v = (obj as Record<string, unknown> | null)?.[key]
  return Array.isArray(v) ? v.map(String) : []
}
function text(obj: unknown, key: string): string {
  const v = (obj as Record<string, unknown> | null)?.[key]
  return typeof v === 'string' ? v : ''
}

const cognitive = computed(() => (distillation.value?.cognitive_layer as Dist) || null)
const angle = computed(() => (distillation.value?.angle_layer as Dist) || null)
const strategy = computed(() => (distillation.value?.strategy_layer as Dist) || null)
const voice = computed(() => (distillation.value?.voice as Dist) || null)
const voiceLine = computed(() => {
  if (!voice.value) return ''
  const parts = [text(voice.value, 'self_ref') && `自称「${text(voice.value, 'self_ref')}」`, text(voice.value, 'tone'), list(voice.value, 'catchphrases').slice(0, 4).join('、')]
  return parts.filter(Boolean).join(' · ')
})

const COGNITIVE_KEYS: { key: string; label: string }[] = [
  { key: 'core_beliefs', label: '核心信念' },
  { key: 'opinion_tensions', label: '观点张力 / 反共识' },
  { key: 'value_stance', label: '价值立场' }
]
const cognitiveCards = computed(() =>
  cognitive.value
    ? COGNITIVE_KEYS.map((k) => ({ label: k.label, items: list(cognitive.value, k.key).slice(0, 3) })).filter((c) => c.items.length)
    : []
)

// 分车道写法:每车道抽最有用的若干组;当前车道 tab。
const LANE_KEYS: { key: string; label: string }[] = [
  { key: 'title_formulas', label: '标题公式' },
  { key: 'opening_templates', label: '开头模板' },
  { key: 'cover_text_rules', label: '封面文案' },
  { key: 'visual_layout_patterns', label: '图内编排 / 版式' },
  { key: 'video_script_structures', label: '口播结构' },
  { key: 'language_dna', label: '语言 DNA' }
]
const lanes = computed(() => {
  const raw = (distillation.value?.content_lanes as Record<string, Dist>) || {}
  return Object.entries(raw).map(([lane, content]) => ({
    lane,
    label: SUBTYPE_LABELS[lane] || lane,
    groups: LANE_KEYS.map((k) => ({ label: k.label, items: list(content, k.key).slice(0, 5) })).filter((g) => g.items.length)
  }))
})
const activeLane = ref('')
const currentLane = computed(() => lanes.value.find((l) => l.lane === activeLane.value) || lanes.value[0] || null)

// 旧形态策略层(系列/蹭热点/运营)也做成卡片,和车道写法一致。
const STRATEGY_KEYS: { key: string; label: string }[] = [
  { key: 'series_planning', label: '系列 / 选题规划' },
  { key: 'trend_hijacking', label: '蹭热点 / 借势' },
  { key: 'ops_habits', label: '运营习惯' }
]
const strategyGroups = computed(() =>
  strategy.value ? STRATEGY_KEYS.map((k) => ({ label: k.label, items: list(strategy.value, k.key).slice(0, 6) })).filter((g) => g.items.length) : []
)

const hasTopic = computed(() => angle.value && (list(angle.value, 'topic_method').length || list(angle.value, 'topic_angles').length || list(angle.value, 'trend_hijacking').length))
const hasMethod = computed(() => hasTopic.value || lanes.value.length || strategy.value)

// 精简态看点:各抽 1 条最有代表性的(核心信念 / 选题方法 / 招牌写法)。
const highlights = computed(() => {
  const out: { label: string; text: string }[] = []
  const belief = list(cognitive.value, 'core_beliefs')[0]
  if (belief) out.push({ label: '核心信念', text: belief })
  const method = list(angle.value, 'topic_method')[0] || list(angle.value, 'topic_angles').slice(0, 3).join(' · ')
  if (method) out.push({ label: '选题方法', text: method })
  const firstLane = lanes.value[0]
  const sig = firstLane ? (firstLane.groups.find((g) => g.label === '标题公式')?.items[0] || firstLane.groups[0]?.items[0] || '') : ''
  if (sig) out.push({ label: '招牌写法', text: sig })
  return out.slice(0, 3)
})
// 完整创作方法的条目总数(给精简态的「见详情」提示用)。
const totalMethods = computed(() => {
  let n = cognitiveCards.value.reduce((s, c) => s + c.items.length, 0)
  if (angle.value) n += list(angle.value, 'topic_method').length + list(angle.value, 'topic_angles').length + list(angle.value, 'trend_hijacking').length
  for (const l of lanes.value) for (const g of l.groups) n += g.items.length
  return n
})

// 合规红线(蒸馏 grounding 产出;老 skill 重蒸后才有,空则不显示)。
const watchouts = computed(() => list(distillation.value, 'compliance_watchouts'))
</script>

<template>
  <div v-if="distillation" class="pc" :class="{ 'pc--compact': compact }">
    <blockquote v-if="text(distillation, 'one_glance')" class="pc-glance">{{ text(distillation, 'one_glance') }}</blockquote>
    <p v-if="voiceLine" class="pc-voice"><strong>人设声音</strong>{{ voiceLine }}</p>

    <!-- 精简态:看点 + 见详情提示 -->
    <template v-if="compact">
      <div v-if="highlights.length" class="pc-hl">
        <div v-for="h in highlights" :key="h.label" class="pc-hl-row">
          <span class="pc-hl-tag">{{ h.label }}</span>
          <span class="pc-hl-text">{{ h.text }}</span>
        </div>
      </div>
      <p v-if="totalMethods" class="pc-more">完整创作方法(标题公式 / 开头模板 / 封面 / 图内编排 / 语言 DNA 等,共 {{ totalMethods }} 条)见「查看详情」。</p>
      <p v-if="watchouts.length" class="pc-redline-hint">⚠ 合规红线 {{ watchouts.length }} 条(会限流,学思路别抄词)—— 详情看全部</p>
    </template>

    <!-- 完整态:认知 + 方法 -->
    <template v-if="!compact">
    <!-- 认知 · 她怎么想 -->
    <div v-if="cognitiveCards.length" class="pc-group">
      <p class="pc-group__h">认知 · 她怎么想</p>
      <div class="pc-cards">
        <div v-for="c in cognitiveCards" :key="c.label" class="pc-card">
          <span class="pc-card__tag">{{ c.label }}</span>
          <span class="pc-card__text">
            <template v-for="(item, i) in c.items" :key="i"><span v-if="i" class="pc-card__sep"> · </span>{{ item }}</template>
          </span>
        </div>
      </div>
    </div>

    <!-- 方法 · 她怎么写 -->
    <div v-if="hasMethod" class="pc-group">
      <p class="pc-group__h">方法 · 她怎么写</p>

      <div v-if="hasTopic" class="pc-topic">
        <h5 class="pc-topic__h">选题思路 <span>· 最高杠杆</span></h5>
        <div v-if="list(angle, 'topic_method').length" class="pc-topic__method">
          <span class="pc-topic__tag">方法</span>
          <ul><li v-for="(item, i) in list(angle, 'topic_method').slice(0, 3)" :key="i">{{ item }}</li></ul>
        </div>
        <div class="pc-topic__sub">
          <p v-if="list(angle, 'topic_angles').length"><em>常用角度</em>{{ list(angle, 'topic_angles').slice(0, 5).join(' · ') }}</p>
          <p v-if="list(angle, 'trend_hijacking').length"><em>借势</em>{{ list(angle, 'trend_hijacking').slice(0, 4).join(' · ') }}</p>
        </div>
      </div>
      <!-- 旧形态兜底:策略层(卡片) -->
      <div v-else-if="strategyGroups.length" class="pc-lane">
        <div v-for="g in strategyGroups" :key="g.label" class="pc-lane-card">
          <div class="pc-lane-card__h">{{ g.label }}</div>
          <ul class="pc-lane-card__list"><li v-for="(item, i) in g.items" :key="i">{{ item }}</li></ul>
        </div>
      </div>

      <template v-if="lanes.length">
        <div class="pc-lane-tabs">
          <button
            v-for="l in lanes"
            :key="l.lane"
            type="button"
            :class="{ on: currentLane?.lane === l.lane }"
            @click="activeLane = l.lane"
          >{{ l.label }}写法</button>
        </div>
        <div v-if="currentLane" class="pc-lane">
          <div v-for="group in currentLane.groups" :key="group.label" class="pc-lane-card">
            <div class="pc-lane-card__h">{{ group.label }}</div>
            <ul class="pc-lane-card__list"><li v-for="(item, i) in group.items" :key="i">{{ item }}</li></ul>
          </div>
        </div>
      </template>
    </div>

    <!-- 合规红线(护栏):该博主高频但会限流的写法 -->
    <div v-if="watchouts.length" class="pc-redline">
      <p class="pc-redline__h">⚠ 合规红线（该博主高频、但会限流/违规的写法——学思路，别抄词）</p>
      <ul><li v-for="(w, i) in watchouts" :key="i">{{ w }}</li></ul>
    </div>
    </template>
  </div>
  <p v-else class="pc-missing">该画像的蒸馏详情不可用（记录可能已清理），可重新蒸馏生成。</p>
</template>

<style scoped>
.pc { display: flex; flex-direction: column; gap: 16px; padding: 14px 0 4px; }
.pc-glance {
  margin: 0;
  padding: 10px 14px;
  border-left: 3px solid var(--color-accent);
  background: var(--color-accent-tint, var(--color-accent-soft));
  color: var(--color-ink);
  font-size: 13px;
  line-height: 1.6;
  border-radius: 0 8px 8px 0;
}
.pc-voice { margin: 0; font-size: 12.5px; color: var(--color-ink-2); }
.pc-voice strong { color: var(--color-ink); margin-right: 8px; font-size: 12px; }

/* 精简态:看点 + 提示 */
.pc--compact { gap: 12px; }
.pc-hl { display: flex; flex-direction: column; gap: 7px; }
.pc-hl-row { display: flex; gap: 8px; align-items: baseline; }
.pc-hl-tag { flex: 0 0 auto; font-size: 11px; font-weight: 600; padding: 1px 8px; border-radius: 6px; background: var(--color-accent-soft); color: var(--color-accent-ink); }
.pc-hl-text { font-size: 12.5px; color: var(--color-ink-2); line-height: 1.6; }
.pc-more { margin: 0; font-size: 11.5px; color: var(--color-ink-3); }
.pc-redline-hint { margin: 0; font-size: 11.5px; color: #8a5a12; }

/* 合规红线护栏块 */
.pc-redline { border: 1px solid var(--color-warn-card-bd, #f0e3d2); background: var(--color-warn-card-bg, #fdf9f1); border-radius: 10px; padding: 10px 13px; }
.pc-redline__h { margin: 0 0 6px; font-size: 12px; font-weight: 650; color: #8a5a12; }
.pc-redline ul { margin: 0; padding-left: 16px; display: flex; flex-direction: column; gap: 4px; }
.pc-redline li { font-size: 12.5px; color: var(--color-ink-2); line-height: 1.55; }

.pc-group { display: flex; flex-direction: column; gap: 8px; }
.pc-group__h { margin: 0; font-size: 12px; font-weight: 650; color: var(--color-accent-ink); }

.pc-cards { display: flex; flex-direction: column; gap: 8px; }
.pc-card { display: flex; gap: 10px; align-items: flex-start; padding: 10px 13px; background: var(--color-paper); border: 1px solid var(--color-paper-3); border-radius: 10px; }
.pc-card__tag { flex: 0 0 auto; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 6px; background: #f0eef7; color: #5a4a86; margin-top: 1px; }
.pc-card__text { font-size: 12.5px; color: var(--color-ink-2); line-height: 1.6; }
.pc-card__sep { color: var(--color-ink-3); }

.pc-lane-tabs { display: flex; gap: 6px; flex-wrap: wrap; padding-top: 4px; }
.pc-lane-tabs button {
  border: 1px solid var(--color-rule);
  background: var(--color-surface);
  border-radius: 999px;
  padding: 3px 12px;
  font-size: 12px;
  color: var(--color-ink-2);
  cursor: pointer;
}
.pc-lane-tabs button.on { border-color: var(--color-accent); background: var(--color-accent-soft); color: var(--color-accent-ink); }

/* 方法卡片:每组(标题公式/开头模板/…)一张卡,条目分行、hairline 分隔,不再挤成一坨 */
.pc-lane { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 10px; margin-top: 10px; }
.pc-lane-card { background: var(--color-paper); border: 1px solid var(--color-paper-3); border-radius: 10px; overflow: hidden; }
.pc-lane-card__h { padding: 8px 12px; font-size: 12px; font-weight: 650; color: var(--color-accent-ink); background: var(--color-accent-soft); }
.pc-lane-card__list { margin: 0; padding: 2px 0; list-style: none; }
.pc-lane-card__list li { padding: 8px 12px; font-size: 12.5px; color: var(--color-ink-2); line-height: 1.6; border-top: 1px solid var(--color-paper-3); }
.pc-lane-card__list li:first-child { border-top: 0; }
.pc-missing { margin: 8px 0 0; font-size: 12px; color: var(--color-ink-3); }

/* 选题思路:强调块 */
.pc-topic { border-left: 2px solid var(--color-accent); padding-left: 12px; display: flex; flex-direction: column; gap: 8px; }
.pc-topic__h { margin: 0; font-size: 13px; color: var(--color-accent-ink); font-weight: 600; }
.pc-topic__h span { color: var(--color-ink-3); font-weight: 400; font-size: 11px; }
.pc-topic__method { display: flex; gap: 8px; align-items: flex-start; }
.pc-topic__tag { flex-shrink: 0; font-size: 11px; padding: 1px 7px; border-radius: 5px; background: var(--color-accent-soft); color: var(--color-accent-ink); margin-top: 2px; }
.pc-topic__method ul { margin: 0; padding-left: 16px; display: flex; flex-direction: column; gap: 4px; }
.pc-topic__method li { font-size: 13px; color: var(--color-ink); line-height: 1.6; }
.pc-topic__sub { display: flex; flex-direction: column; gap: 4px; }
.pc-topic__sub p { margin: 0; font-size: 12.5px; color: var(--color-ink-2); line-height: 1.5; }
.pc-topic__sub em { font-style: normal; color: var(--color-ink-3); margin-right: 6px; }
</style>
