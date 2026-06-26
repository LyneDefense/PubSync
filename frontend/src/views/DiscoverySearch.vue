<script setup lang="ts">
// 泛搜索:领域 → agent 推细分角度(选/排除/再推,建议选 X 个)→ 候选工作台。
import { computed, ref } from 'vue'
import DiscoveryWorkspacePanel from './DiscoveryWorkspacePanel.vue'
import TIcon from '../components/TIcon.vue'
import {
  discoveryDomains,
  discoveryOpPending,
  discoveryStarting,
  discoveryWorkspace,
  handleDiscoveryAngle,
  handleDiscoveryStart,
  resetDiscovery
} from '../composables/useWorkspaceStore'

const domainInput = ref('')
const proposing = ref(false)   // 「再推几个」专用 loading(推角度要调 LLM,约 15s)
const ws = computed(() => discoveryWorkspace.value)
// 本 tab 只在「没有会话」或「会话是 broad」时接管;similar 会话归找相似 tab。
const mine = computed(() => ws.value && ws.value.source === 'broad')
const choosing = computed(() => mine.value && ws.value!.stage === 'choose_angles')

function addDomain() {
  const v = domainInput.value.trim()
  if (v && !discoveryDomains.value.includes(v)) discoveryDomains.value.push(v)
  domainInput.value = ''
}
function removeDomain(d: string) {
  discoveryDomains.value = discoveryDomains.value.filter((x) => x !== d)
}
async function propose() {
  proposing.value = true
  try {
    await handleDiscoveryAngle('propose')
  } finally {
    proposing.value = false
  }
}
</script>

<template>
  <!-- 入口:填领域 -->
  <div v-if="!mine" class="ds-intro">
    <label>你想做的领域（可多个，回车添加）
      <div class="ds-chips">
        <span v-for="d in discoveryDomains" :key="d" class="ds-chip">{{ d }}<button type="button" @click="removeDomain(d)">×</button></span>
        <input v-model="domainInput" type="text" placeholder="如 香港保险、储蓄险" @keydown.enter.prevent="addDomain" @blur="addDomain" />
      </div>
    </label>
    <button type="button" class="primary" :disabled="discoveryStarting || !discoveryDomains.length" @click="handleDiscoveryStart">
      {{ discoveryStarting ? 'AI 想角度中…' : '下一步：选细分角度' }}
    </button>
    <p class="ds-hint">不知道学谁？先选你想做的领域，下一步系统帮你把方向收窄到几个细分角度，再照着找号。</p>
  </div>

  <!-- 选细分角度(收窄) -->
  <div v-else-if="choosing" class="ds-angles">
    <p class="ds-msg">{{ ws!.message }}（建议选 {{ ws!.angle_target }} 个左右，已选 <b :class="{ over: ws!.selected_angles > ws!.angle_target }">{{ ws!.selected_angles }}</b>）</p>
    <div class="ds-angle-list">
      <button
        v-for="a in ws!.angles"
        :key="a.label"
        type="button"
        class="ds-angle"
        :class="{ on: a.selected }"
        :disabled="discoveryOpPending"
        @click="handleDiscoveryAngle('toggle', [a.label])"
        :title="a.reason"
      >
        <TIcon :name="a.selected ? 'check' : 'plus'" /> {{ a.label }}
        <span class="ds-x" :title="'不想要这个方向'" @click.stop="handleDiscoveryAngle('reject', [a.label])">×</span>
      </button>
    </div>
    <div class="ds-angle-acts">
      <button type="button" :disabled="discoveryOpPending" @click="propose">
        <TIcon name="refresh" /> {{ proposing ? 'AI 想角度中…' : '再推几个' }}
      </button>
      <button type="button" class="primary" :disabled="discoveryOpPending || !ws!.selected_angles" @click="handleDiscoveryAngle('begin')">
        就用选中的开始找 →
      </button>
      <button type="button" class="ghost" @click="resetDiscovery">换领域</button>
    </div>
    <p v-if="ws!.selected_angles > ws!.angle_target" class="ds-warn">选多了（{{ ws!.selected_angles }} 个），搜出来可能比较杂，但仍可继续。</p>
  </div>

  <!-- 候选工作台 -->
  <DiscoveryWorkspacePanel v-else />
</template>

<style scoped>
.ds-intro { display: flex; flex-direction: column; gap: 14px; max-width: 520px; }
.ds-intro label { display: flex; flex-direction: column; gap: 6px; font-size: 0.9rem; }
.ds-chips { display: flex; flex-wrap: wrap; gap: 6px; border: 1px solid var(--color-field-border, #c8ced4); border-radius: 10px; padding: 6px 8px; }
.ds-chips input { border: none; outline: none; flex: 1; min-width: 120px; background: none; }
.ds-chip { display: inline-flex; align-items: center; gap: 4px; background: var(--color-paper-3, #eef0f3); border-radius: 999px; padding: 2px 8px; font-size: 0.85rem; }
.ds-chip button { border: none; background: none; cursor: pointer; color: var(--color-ink-3, #9aa0a6); }
.ds-hint { font-size: 0.8rem; color: var(--color-ink-3, #9aa0a6); }

.ds-angles { max-width: 640px; display: flex; flex-direction: column; gap: 12px; }
.ds-msg { color: var(--color-ink-2, #6b7280); font-size: 0.9rem; }
.ds-msg b { color: var(--color-accent, #2563eb); }
.ds-msg b.over { color: var(--color-warn, #d98a00); }
.ds-angle-list { display: flex; flex-wrap: wrap; gap: 8px; }
.ds-angle { display: inline-flex; align-items: center; gap: 5px; padding: 6px 10px; border: 1px solid var(--color-field-border, #c8ced4); border-radius: 999px; background: var(--color-field, #fff); cursor: pointer; font-size: 0.86rem; }
.ds-angle.on { background: var(--color-accent, #2563eb); color: #fff; border-color: var(--color-accent, #2563eb); }
.ds-angle .ds-x { margin-left: 2px; opacity: 0.55; padding: 0 2px; }
.ds-angle .ds-x:hover { opacity: 1; color: var(--color-danger, #d14343); }
.ds-angle-acts { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.ds-angle-acts .ghost { margin-left: auto; border: none; background: none; color: var(--color-ink-3, #9aa0a6); cursor: pointer; font-size: 0.84rem; }
.ds-warn { font-size: 0.8rem; color: var(--color-warn, #d98a00); }
</style>
