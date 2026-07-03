<script setup lang="ts">
// 画像内容:把该画像对应蒸馏 run 的 report_json.distillation 结构化展示(不再只给一张卡)。
// 新形态 = 认知层 + 人设声音 + 角度层 + 分车道写法;旧形态(strategy_layer)兜底渲染。
import { computed, ref } from 'vue'
import { bloggerRuns, SUBTYPE_LABELS } from '../../composables/useWorkspaceStore'

const props = defineProps<{ runId: number }>()

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

// 分车道写法:每车道抽最有用的四组;当前车道 tab。
const LANE_KEYS: { key: string; label: string }[] = [
  { key: 'title_formulas', label: '标题公式' },
  { key: 'opening_templates', label: '开头模板' },
  { key: 'cover_text_rules', label: '封面文案' },
  { key: 'visual_layout_patterns', label: '图内编排 / 版式' },
  { key: 'video_script_structures', label: '口播结构' },
  { key: 'language_dna', label: '语言 DNA' },
]
const lanes = computed(() => {
  const raw = (distillation.value?.content_lanes as Record<string, Dist>) || {}
  return Object.entries(raw).map(([lane, content]) => ({
    lane,
    label: SUBTYPE_LABELS[lane] || lane,
    groups: LANE_KEYS.map((k) => ({ label: k.label, items: list(content, k.key).slice(0, 5) })).filter((g) => g.items.length),
  }))
})
const activeLane = ref('')
const currentLane = computed(() => lanes.value.find((l) => l.lane === activeLane.value) || lanes.value[0] || null)

const COGNITIVE_KEYS: { key: string; label: string }[] = [
  { key: 'core_beliefs', label: '核心信念' },
  { key: 'opinion_tensions', label: '观点张力 / 反共识' },
  { key: 'value_stance', label: '价值立场' },
]
</script>

<template>
  <div v-if="distillation" class="pc">
    <blockquote v-if="text(distillation, 'one_glance')" class="pc-glance">{{ text(distillation, 'one_glance') }}</blockquote>
    <p v-if="voiceLine" class="pc-voice"><strong>人设声音</strong>{{ voiceLine }}</p>

    <div v-if="cognitive" class="pc-cols">
      <div v-for="k in COGNITIVE_KEYS" :key="k.key" class="pc-col">
        <h5>{{ k.label }}</h5>
        <ul><li v-for="(item, i) in list(cognitive, k.key).slice(0, 4)" :key="i">{{ item }}</li></ul>
      </div>
    </div>

    <div v-if="angle && (list(angle, 'topic_angles').length || list(angle, 'trend_hijacking').length)" class="pc-cols">
      <div v-if="list(angle, 'topic_angles').length" class="pc-col">
        <h5>选题角度</h5>
        <ul><li v-for="(item, i) in list(angle, 'topic_angles').slice(0, 4)" :key="i">{{ item }}</li></ul>
      </div>
      <div v-if="list(angle, 'trend_hijacking').length" class="pc-col">
        <h5>蹭热点 / 借势</h5>
        <ul><li v-for="(item, i) in list(angle, 'trend_hijacking').slice(0, 4)" :key="i">{{ item }}</li></ul>
      </div>
    </div>
    <!-- 旧形态兜底:策略层 -->
    <div v-else-if="strategy" class="pc-cols">
      <div v-for="k in ['series_planning', 'trend_hijacking', 'ops_habits']" :key="k" class="pc-col">
        <template v-if="list(strategy, k).length">
          <h5>{{ k === 'series_planning' ? '系列 / 选题规划' : k === 'trend_hijacking' ? '蹭热点 / 借势' : '运营习惯' }}</h5>
          <ul><li v-for="(item, i) in list(strategy, k).slice(0, 3)" :key="i">{{ item }}</li></ul>
        </template>
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
        <div v-for="group in currentLane.groups" :key="group.label" class="pc-lane-group">
          <h5>{{ group.label }}</h5>
          <ul><li v-for="(item, i) in group.items" :key="i">{{ item }}</li></ul>
        </div>
      </div>
    </template>
  </div>
  <p v-else class="pc-missing">该画像的蒸馏详情不可用（记录可能已清理），可重新蒸馏生成。</p>
</template>

<style scoped>
.pc { display: flex; flex-direction: column; gap: 14px; padding: 14px 0 4px; }
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
.pc-cols { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
.pc-col h5, .pc-lane-group h5 { margin: 0 0 6px; font-size: 12px; color: var(--color-ink-3); font-weight: 600; }
.pc-col ul, .pc-lane-group ul { margin: 0; padding-left: 16px; display: flex; flex-direction: column; gap: 4px; }
.pc-col li, .pc-lane-group li { font-size: 12.5px; color: var(--color-ink-2); line-height: 1.55; }
.pc-lane-tabs { display: flex; gap: 6px; flex-wrap: wrap; border-top: 1px dashed var(--color-rule); padding-top: 12px; }
.pc-lane-tabs button {
  border: 1px solid var(--color-rule);
  background: var(--color-paper-2);
  border-radius: 999px;
  padding: 3px 12px;
  font-size: 12px;
  color: var(--color-ink-2);
  cursor: pointer;
}
.pc-lane-tabs button.on { border-color: var(--color-accent); background: var(--color-accent-soft); color: var(--color-accent-ink); }
.pc-lane { display: flex; flex-direction: column; gap: 10px; }
.pc-missing { margin: 8px 0 0; font-size: 12px; color: var(--color-ink-3); }
</style>
