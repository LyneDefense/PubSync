<script setup lang="ts">
// 泛搜索向导:按后端「待办」契约渲染。S1 领域 → S2 确认方向(chips+权重) → S3/S4 候选+下一步 → 入库。
// 流程/选项都由后端定,前端只渲染 + 回传结构化选择。重活(召回)走异步任务,进度在顶部 LiveProgress。
import { reactive, ref } from 'vue'
import {
  discoveryDomains,
  discoveryRecalling,
  discoverySeedAccountId,
  discoveryStarting,
  discoveryTodo,
  handleDiscoveryCheckout,
  handleDiscoveryReview,
  handleDiscoveryStart,
  handleDiscoverySubmitDirections,
  myAccountsOnPlatform,
  resetDiscovery
} from '../composables/useWorkspaceStore'

const domainInput = ref('')
// 本地选择态:勾选采用 / 设种子;方向勾选与权重直接改 todo.directions。
const adopt = reactive<Record<string, boolean>>({})
const seed = reactive<Record<string, boolean>>({})
const refineText = ref('')

function addDomain() {
  const v = domainInput.value.trim()
  if (v && !discoveryDomains.value.includes(v)) discoveryDomains.value.push(v)
  domainInput.value = ''
}
function removeDomain(d: string) {
  discoveryDomains.value = discoveryDomains.value.filter((x) => x !== d)
}

function submitDirections() {
  const dirs = (discoveryTodo.value?.directions || []).map((d) => ({
    label: d.label, weight: d.weight, reason: d.reason, selected: d.selected
  }))
  handleDiscoverySubmitDirections(dirs)
}

function doReview(choice: string) {
  const adoptIds = Object.keys(adopt).filter((k) => adopt[k])
  const seedIds = Object.keys(seed).filter((k) => seed[k])
  handleDiscoveryReview(adoptIds, seedIds, choice, refineText.value.trim())
  for (const k of Object.keys(adopt)) delete adopt[k]
  for (const k of Object.keys(seed)) delete seed[k]
  refineText.value = ''
}
</script>

<template>
  <div class="ds">
    <!-- S1 意图 -->
    <div v-if="!discoveryTodo" class="ds-intent">
      <label>你想做的领域（可多个，回车添加）
        <div class="ds-chips">
          <span v-for="d in discoveryDomains" :key="d" class="ds-chip">{{ d }}<button type="button" @click="removeDomain(d)">×</button></span>
          <input v-model="domainInput" type="text" placeholder="如 香港保险、储蓄险" @keydown.enter.prevent="addDomain" @blur="addDomain" />
        </div>
      </label>
      <label v-if="myAccountsOnPlatform.length">想找“像谁”的号？选个种子账号（可选）
        <select v-model="discoverySeedAccountId">
          <option :value="null">不指定</option>
          <option v-for="a in myAccountsOnPlatform" :key="a.id" :value="a.id">{{ a.display_name }}</option>
        </select>
      </label>
      <button type="button" class="primary" :disabled="discoveryStarting || !discoveryDomains.length" @click="handleDiscoveryStart">
        {{ discoveryStarting ? '准备中…' : '开始找对标' }}
      </button>
    </div>

    <!-- S2 确认方向 -->
    <div v-else-if="discoveryTodo.stage === 'confirm_directions'" class="ds-dirs">
      <p class="ds-msg">{{ discoveryTodo.message }}：勾选要搜的方向，拖动权重（高=搜得更深、更靠前）。</p>
      <ul class="ds-dir-list">
        <li v-for="d in discoveryTodo.directions" :key="d.label" :class="{ off: !d.selected }">
          <label class="ds-dir-check"><input type="checkbox" v-model="d.selected" /> {{ d.label }}</label>
          <input type="range" min="0" max="100" v-model.number="d.weight" :disabled="!d.selected" />
          <span class="ds-dir-w">{{ Math.round(d.weight) }}</span>
          <small v-if="d.reason">{{ d.reason }}</small>
        </li>
      </ul>
      <div class="ds-actions">
        <button type="button" class="primary" :disabled="discoveryRecalling" @click="submitDirections">
          {{ discoveryRecalling ? '搜罗中…' : '按这些方向找' }}
        </button>
        <button type="button" @click="resetDiscovery">重来</button>
      </div>
    </div>

    <!-- S3/S4 候选 + 下一步 -->
    <div v-else-if="discoveryTodo.stage === 'review_candidates'" class="ds-review">
      <p class="ds-msg">{{ discoveryTodo.message }}</p>

      <div v-if="discoveryTodo.basket.length" class="ds-basket">
        已入选 {{ discoveryTodo.basket.length }} 个：{{ discoveryTodo.basket.map((b) => b.display_name).join('、') }}
        <button type="button" class="primary sm" @click="handleDiscoveryCheckout">完成，入对标库</button>
      </div>

      <ul class="ds-cands">
        <li v-for="c in discoveryTodo.candidates" :key="c.external_id" class="ds-cand">
          <img v-if="c.avatar_url" :src="c.avatar_url" alt="" />
          <div class="ds-cand-body">
            <strong>{{ c.display_name }}</strong>
            <span v-if="c.existing_blogger_id" class="ds-tag">已在库</span>
            <small>{{ c.reason }}</small>
          </div>
          <div class="ds-cand-pick">
            <label><input type="checkbox" v-model="adopt[c.external_id]" /> 采用</label>
            <label><input type="checkbox" v-model="seed[c.external_id]" /> 设为种子</label>
          </div>
        </li>
        <li v-if="!discoveryTodo.candidates?.length" class="ds-empty">这一批没有新候选了，换/加方向或换种子试试。</li>
      </ul>

      <label class="ds-refine">补充要求（可选）
        <input v-model="refineText" type="text" :placeholder="discoveryTodo.input?.placeholder || '如 只要个人号'" />
      </label>

      <div class="ds-actions ds-next">
        <button
          v-for="o in discoveryTodo.options"
          :key="o.id"
          type="button"
          :class="{ primary: discoveryTodo.recommended?.option_id === o.id }"
          :disabled="discoveryRecalling"
          @click="doReview(o.id)"
        >{{ o.label }}</button>
      </div>
      <p v-if="discoveryTodo.recommended" class="ds-rec">建议：{{ discoveryTodo.recommended.reason }}</p>
    </div>

    <!-- 完成 -->
    <div v-else-if="discoveryTodo.stage === 'done'" class="ds-done">
      <p>{{ discoveryTodo.message }}</p>
      <button type="button" class="primary" @click="resetDiscovery">再找一批</button>
    </div>
  </div>
</template>

<style scoped>
.ds { max-width: 720px; }
.ds-intent, .ds-dirs, .ds-review { display: flex; flex-direction: column; gap: 14px; }
.ds-intent label, .ds-refine { display: flex; flex-direction: column; gap: 6px; font-size: 0.9rem; }
.ds-chips { display: flex; flex-wrap: wrap; gap: 6px; border: 1px solid var(--color-field-border, #c8ced4); border-radius: 10px; padding: 6px 8px; }
.ds-chips input { border: none; outline: none; flex: 1; min-width: 120px; background: none; }
.ds-chip { display: inline-flex; align-items: center; gap: 4px; background: var(--color-paper-3, #eef0f3); border-radius: 999px; padding: 2px 8px; font-size: 0.85rem; }
.ds-chip button { border: none; background: none; cursor: pointer; color: var(--color-ink-3, #9aa0a6); }
.ds-msg { color: var(--color-ink-2, #6b7280); }
.ds-dir-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.ds-dir-list li { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 10px; }
.ds-dir-list li.off { opacity: 0.5; }
.ds-dir-list li small { grid-column: 1 / -1; color: var(--color-ink-3, #9aa0a6); font-size: 0.78rem; }
.ds-dir-check { display: inline-flex; align-items: center; gap: 6px; font-weight: 600; white-space: nowrap; }
.ds-dir-w { width: 30px; text-align: right; font-variant-numeric: tabular-nums; }
.ds-actions { display: flex; gap: 10px; flex-wrap: wrap; }
.ds-basket { background: #eef4ff; color: #1e40af; border-radius: 10px; padding: 8px 12px; font-size: 0.88rem; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.primary.sm { margin-left: auto; padding: 4px 12px; }
.ds-cands { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.ds-cand { display: flex; align-items: center; gap: 10px; border: 1px solid var(--color-field-border, #c8ced4); border-radius: 12px; padding: 10px 12px; }
.ds-cand img { width: 40px; height: 40px; border-radius: 50%; flex: none; object-fit: cover; }
.ds-cand-body { display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1; }
.ds-cand-body small { color: var(--color-ink-2, #6b7280); font-size: 0.8rem; }
.ds-tag { font-size: 0.7rem; color: var(--color-ok, #2e9e5b); }
.ds-cand-pick { display: flex; flex-direction: column; gap: 4px; font-size: 0.82rem; white-space: nowrap; }
.ds-empty { color: var(--color-ink-3, #9aa0a6); text-align: center; padding: 16px; }
.ds-next button.primary { outline: 2px solid var(--color-accent, #2563eb); }
.ds-rec { font-size: 0.82rem; color: var(--color-accent, #2563eb); }
</style>
