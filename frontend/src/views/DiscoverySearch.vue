<script setup lang="ts">
// 泛搜索三列工作台:候选 / 种子 / 已选。东西只往前流:候选→种子/已选,种子→已选;移出候选不回候选。
// 找候选(按方向/按种子)是异步任务,进度在顶部 LiveProgress;移动/移除/保存是同步即时。
import { computed, ref } from 'vue'
import {
  discoveryDomains,
  discoveryOpPending,
  discoveryRecalling,
  discoverySeedAccountId,
  discoveryStarting,
  discoveryWorkspace,
  handleDiscoveryOp,
  handleDiscoveryRecall,
  handleDiscoverySave,
  handleDiscoveryStart,
  handleDiscoveryUpdateDirections,
  myAccountsOnPlatform,
  resetDiscovery
} from '../composables/useWorkspaceStore'

const domainInput = ref('')
const addDomainInput = ref('')
const showDirections = ref(false)

const ws = computed(() => discoveryWorkspace.value)
const busy = computed(() => discoveryRecalling.value || discoveryOpPending.value)

function addDomain() {
  const v = domainInput.value.trim()
  if (v && !discoveryDomains.value.includes(v)) discoveryDomains.value.push(v)
  domainInput.value = ''
}
function removeDomain(d: string) {
  discoveryDomains.value = discoveryDomains.value.filter((x) => x !== d)
}

function applyDirections() {
  const dirs = (ws.value?.directions || []).map((d) => ({
    label: d.label, weight: d.weight, reason: d.reason, selected: d.selected
  }))
  const adds = addDomainInput.value.split(/[,，\s]+/).map((s) => s.trim()).filter(Boolean)
  handleDiscoveryUpdateDirections(dirs, adds)
  addDomainInput.value = ''
}

function fmtFans(c: { follower_known: boolean; follower_count: number }): string {
  if (!c.follower_known) return '粉丝未知'
  const n = c.follower_count
  return n >= 10000 ? `${(n / 10000).toFixed(1)}万粉` : `${n} 粉`
}
</script>

<template>
  <!-- 入口:填领域 + 可选种子账号 -->
  <div v-if="!ws" class="ds-intro">
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

  <!-- 三列工作台 -->
  <div v-else class="ds-ws">
    <div class="ds-ws-top">
      <button type="button" class="ds-link" @click="showDirections = !showDirections">
        <i class="ti" :class="showDirections ? 'ti-chevron-down' : 'ti-adjustments'"></i> 调方向（{{ (ws.directions || []).filter((d) => d.selected).length }} 个在用）
      </button>
      <span class="ds-msg">{{ ws.message }}</span>
      <button type="button" class="ds-link danger" @click="resetDiscovery">重新开始</button>
    </div>

    <!-- 调方向面板 -->
    <div v-if="showDirections" class="ds-dirs">
      <ul>
        <li v-for="d in ws.directions" :key="d.label" :class="{ off: !d.selected }">
          <label><input type="checkbox" v-model="d.selected" /> {{ d.label }}</label>
          <input type="range" min="0" max="100" step="1" v-model.number="d.weight" :disabled="!d.selected" />
          <span class="ds-w">{{ Math.round(d.weight) }}</span>
        </li>
      </ul>
      <div class="ds-dirs-add">
        <input v-model="addDomainInput" type="text" placeholder="加领域，如 重疾险（可空）" @keydown.enter.prevent="applyDirections" />
        <button type="button" :disabled="discoveryOpPending" @click="applyDirections">应用方向</button>
      </div>
    </div>

    <div class="ds-cols">
      <!-- 候选 -->
      <section class="ds-col">
        <header>
          <span class="ds-col-h"><i class="ti ti-users"></i> 候选 <b>{{ ws.candidates.length }}</b></span>
          <div class="ds-col-acts">
            <button type="button" class="primary sm" :disabled="busy" @click="handleDiscoveryRecall('directions')">
              {{ discoveryRecalling ? '搜罗中…' : '继续找候选' }}
            </button>
            <button v-if="ws.candidates.length" type="button" class="sm" :disabled="busy" @click="handleDiscoveryOp('clear_candidates')">清空</button>
          </div>
        </header>
        <div class="ds-col-body">
          <article v-for="c in ws.candidates" :key="c.external_id" class="ds-card">
            <img v-if="c.avatar_url" :src="c.avatar_url" alt="" />
            <div class="ds-card-main">
              <div class="ds-card-top"><strong>{{ c.display_name }}</strong><span class="ds-score">匹配度 {{ Math.round(c.score) }}</span></div>
              <div class="ds-data">{{ fmtFans(c) }} · <span :class="c.is_personal ? 'ok' : 'muted'">{{ c.is_personal ? '个人号' : '机构号' }}</span><span v-if="c.existing_blogger_id" class="ds-tag">已在库</span></div>
              <div class="ds-reason">{{ c.reason }}</div>
              <div class="ds-card-acts">
                <button type="button" :disabled="busy" @click="handleDiscoveryOp('to_seed', [c.external_id])"><i class="ti ti-seeding"></i> 设为种子</button>
                <button type="button" :disabled="busy" @click="handleDiscoveryOp('to_selected', [c.external_id])"><i class="ti ti-check"></i> 选入</button>
              </div>
            </div>
          </article>
          <p v-if="!ws.candidates.length" class="ds-empty">点「继续找候选」拉一批，或从种子「按种子找候选」。</p>
        </div>
      </section>

      <!-- 种子 -->
      <section class="ds-col">
        <header>
          <span class="ds-col-h"><i class="ti ti-seeding"></i> 种子 <b>{{ ws.seeds.length }}</b></span>
          <div class="ds-col-acts">
            <button type="button" class="sm seed" :disabled="busy || !ws.seeds.length" @click="handleDiscoveryRecall('seed')">
              {{ discoveryRecalling ? '搜罗中…' : '按种子找候选' }}
            </button>
          </div>
        </header>
        <div class="ds-col-body">
          <article v-for="s in ws.seeds" :key="s.external_id" class="ds-card">
            <div class="ds-card-main">
              <div class="ds-card-top"><strong>{{ s.display_name }}</strong><span v-if="s.is_mine" class="ds-tag mine">我的号</span></div>
              <div class="ds-data">{{ fmtFans(s) }}</div>
              <div class="ds-card-acts">
                <button type="button" :disabled="busy" @click="handleDiscoveryOp('seed_to_selected', [s.external_id])"><i class="ti ti-check"></i> 选入</button>
                <button type="button" :disabled="busy" @click="handleDiscoveryOp('remove_seed', [s.external_id])"><i class="ti ti-x"></i> 移除</button>
              </div>
            </div>
          </article>
          <p v-if="!ws.seeds.length" class="ds-empty">从候选「设为种子」，再「按种子找候选」挖同类。</p>
        </div>
      </section>

      <!-- 已选 -->
      <section class="ds-col">
        <header>
          <span class="ds-col-h"><i class="ti ti-star"></i> 已选 <b>{{ ws.selected.length }}</b></span>
          <div class="ds-col-acts">
            <button type="button" class="primary sm save" :disabled="busy || !ws.selected.length" @click="handleDiscoverySave">保存到对标库</button>
          </div>
        </header>
        <div class="ds-col-body">
          <article v-for="b in ws.selected" :key="b.external_id" class="ds-card">
            <div class="ds-card-main">
              <div class="ds-card-top"><strong>{{ b.display_name }}</strong><span v-if="b.existing_blogger_id" class="ds-tag">已在库</span></div>
              <div class="ds-data">{{ fmtFans(b) }} · <span :class="b.is_personal ? 'ok' : 'muted'">{{ b.is_personal ? '个人号' : '机构号' }}</span></div>
              <div class="ds-card-acts">
                <button type="button" :disabled="busy" @click="handleDiscoveryOp('remove_selected', [b.external_id])"><i class="ti ti-x"></i> 移除</button>
              </div>
            </div>
          </article>
          <p v-if="!ws.selected.length" class="ds-empty">把满意的号「选入」这里，最后一键保存。</p>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.ds-intro { display: flex; flex-direction: column; gap: 14px; max-width: 520px; }
.ds-intro label { display: flex; flex-direction: column; gap: 6px; font-size: 0.9rem; }
.ds-chips { display: flex; flex-wrap: wrap; gap: 6px; border: 1px solid var(--color-field-border, #c8ced4); border-radius: 10px; padding: 6px 8px; }
.ds-chips input { border: none; outline: none; flex: 1; min-width: 120px; background: none; }
.ds-chip { display: inline-flex; align-items: center; gap: 4px; background: var(--color-paper-3, #eef0f3); border-radius: 999px; padding: 2px 8px; font-size: 0.85rem; }
.ds-chip button { border: none; background: none; cursor: pointer; color: var(--color-ink-3, #9aa0a6); }

.ds-ws-top { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; flex-wrap: wrap; }
.ds-link { border: none; background: none; cursor: pointer; color: var(--color-accent, #2563eb); font-size: 0.86rem; display: inline-flex; align-items: center; gap: 4px; }
.ds-link.danger { color: var(--color-ink-3, #9aa0a6); margin-left: auto; }
.ds-msg { color: var(--color-ink-2, #6b7280); font-size: 0.86rem; }

.ds-dirs { border: 1px solid var(--color-field-border, #c8ced4); border-radius: 10px; padding: 10px 12px; margin-bottom: 12px; }
.ds-dirs ul { list-style: none; margin: 0 0 8px; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.ds-dirs li { display: grid; grid-template-columns: minmax(110px, auto) 1fr 30px; align-items: center; gap: 10px; }
.ds-dirs li.off { opacity: 0.5; }
.ds-dirs li label { display: inline-flex; align-items: center; gap: 6px; font-size: 0.85rem; white-space: nowrap; }
.ds-w { text-align: right; font-variant-numeric: tabular-nums; font-size: 0.82rem; }
.ds-dirs-add { display: flex; gap: 8px; }
.ds-dirs-add input { flex: 1; }

.ds-cols { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.ds-col { background: var(--color-paper-2, #f7f8fa); border-radius: 12px; padding: 10px; display: flex; flex-direction: column; min-height: 260px; }
.ds-col > header { display: flex; align-items: center; justify-content: space-between; gap: 6px; margin-bottom: 8px; }
.ds-col-h { font-weight: 600; font-size: 0.92rem; display: inline-flex; align-items: center; gap: 5px; }
.ds-col-h b { color: var(--color-ink-2, #6b7280); }
.ds-col-acts { display: flex; gap: 6px; }
.ds-col-body { display: flex; flex-direction: column; gap: 8px; max-height: 480px; overflow-y: auto; }

.ds-card { display: flex; gap: 8px; background: var(--color-field, #fff); border: 1px solid var(--color-field-border, #e2e6ea); border-radius: 10px; padding: 8px 10px; }
.ds-card img { width: 36px; height: 36px; border-radius: 50%; flex: none; object-fit: cover; }
.ds-card-main { flex: 1; min-width: 0; }
.ds-card-top { display: flex; align-items: center; justify-content: space-between; gap: 6px; }
.ds-card-top strong { font-size: 0.88rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ds-score { font-size: 0.72rem; color: var(--color-accent, #2563eb); white-space: nowrap; }
.ds-data { font-size: 0.78rem; color: var(--color-ink-2, #6b7280); margin-top: 2px; }
.ds-data .ok { color: var(--color-ok, #2e9e5b); }
.ds-data .muted { color: var(--color-ink-3, #9aa0a6); }
.ds-reason { font-size: 0.76rem; color: var(--color-ink-3, #9aa0a6); margin-top: 3px; }
.ds-tag { font-size: 0.68rem; color: var(--color-ok, #2e9e5b); margin-left: 6px; }
.ds-tag.mine { color: var(--color-accent, #2563eb); }
.ds-card-acts { display: flex; gap: 6px; margin-top: 6px; }
.ds-card-acts button { font-size: 0.74rem; padding: 3px 8px; border: 1px solid var(--color-field-border, #c8ced4); border-radius: 8px; background: transparent; cursor: pointer; display: inline-flex; align-items: center; gap: 3px; }
.ds-card-acts button:disabled { opacity: 0.5; cursor: default; }
.ds-empty { color: var(--color-ink-3, #9aa0a6); font-size: 0.8rem; text-align: center; padding: 18px 8px; }

button.sm { font-size: 0.76rem; padding: 4px 10px; border-radius: 8px; border: 1px solid var(--color-field-border, #c8ced4); background: var(--color-field, #fff); cursor: pointer; }
button.sm:disabled { opacity: 0.5; cursor: default; }
button.primary.sm { background: var(--color-accent, #2563eb); color: #fff; border-color: var(--color-accent, #2563eb); }
button.sm.seed { border-color: var(--color-accent, #2563eb); color: var(--color-accent, #2563eb); }
button.primary.sm.save { background: var(--color-ok, #2e9e5b); border-color: var(--color-ok, #2e9e5b); }
@media (max-width: 720px) { .ds-cols { grid-template-columns: 1fr; } }
</style>
