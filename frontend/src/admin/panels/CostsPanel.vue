<script setup lang="ts">
// 后台费用记录:总览 + 分渠道 + 按工作空间汇总 + 明细列表 + 模型单价编辑。
import { computed, onMounted, ref } from 'vue'
import { getAdminCostSummary, getAdminCosts, getModelPrices, putModelPrices } from '../../api'
import type { CostEvent, CostSummary, ModelPrices } from '../../api/types'

const summary = ref<CostSummary | null>(null)
const events = ref<CostEvent[]>([])
const prices = ref<ModelPrices | null>(null)
const days = ref(30)
const providerFilter = ref('')
const showPrices = ref(false)
const message = ref('')
const error = ref('')
const busy = ref(false)

const PROVIDERS = ['', 'tikhub', 'openai', 'minimax']

const llmTotal = computed(() => {
  if (!summary.value) return 0
  return summary.value.by_provider
    .filter((p) => p.key !== 'tikhub')
    .reduce((sum, p) => sum + p.cost_usd, 0)
})
const tikhubTotal = computed(() => summary.value?.by_provider.find((p) => p.key === 'tikhub')?.cost_usd || 0)

function usd(n: number) {
  return `$${n.toFixed(4)}`
}
function formatDate(value: string) {
  return new Date(value).toLocaleString('zh-CN')
}

async function reload() {
  busy.value = true
  error.value = ''
  try {
    ;[summary.value, events.value] = await Promise.all([
      getAdminCostSummary(days.value),
      getAdminCosts({ provider: providerFilter.value || undefined, days: days.value, limit: 200 })
    ])
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}

onMounted(reload)

async function togglePrices() {
  showPrices.value = !showPrices.value
  if (showPrices.value && !prices.value) {
    try {
      prices.value = await getModelPrices()
    } catch (e) {
      error.value = (e as Error).message
    }
  }
}

async function savePrices() {
  if (!prices.value) return
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    prices.value = await putModelPrices(prices.value)
    message.value = '模型单价已保存'
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="panel">
    <div class="section-header">
      <div>
        <h2>费用记录</h2>
        <p class="toolbar-subtitle">TikHub 为真实请求费用;大模型按内置/可编辑单价 × token/图 估算。</p>
      </div>
      <div class="actions">
        <select v-model.number="days" @change="reload">
          <option :value="7">近 7 天</option>
          <option :value="30">近 30 天</option>
          <option :value="90">近 90 天</option>
        </select>
        <button type="button" @click="togglePrices">模型单价</button>
        <button type="button" :disabled="busy" @click="reload">刷新</button>
      </div>
    </div>

    <p v-if="message" class="admin-flash admin-flash--ok">{{ message }}</p>
    <p v-if="error" class="admin-flash admin-flash--err">{{ error }}</p>

    <div v-if="summary" class="cost-cards">
      <div class="cost-card"><span>总费用</span><strong>{{ usd(summary.total_usd) }}</strong><small>{{ summary.event_count }} 条记录</small></div>
      <div class="cost-card"><span>TikHub</span><strong>{{ usd(tikhubTotal) }}</strong></div>
      <div class="cost-card"><span>大模型</span><strong>{{ usd(llmTotal) }}</strong></div>
    </div>

    <div v-if="showPrices && prices" class="price-editor">
      <h3>模型单价(USD)</h3>
      <div class="price-grid">
        <div class="price-row price-row--head"><span>文本模型</span><span>每 1K 输入</span><span>每 1K 输出</span></div>
        <div v-for="(v, model) in prices.text" :key="`t-${model}`" class="price-row">
          <span>{{ model }}</span>
          <input v-model.number="v.input_per_1k" type="number" step="0.0001" min="0" />
          <input v-model.number="v.output_per_1k" type="number" step="0.0001" min="0" />
        </div>
        <div class="price-row price-row--head"><span>图像模型</span><span>每张</span><span></span></div>
        <div v-for="(_v, model) in prices.image" :key="`i-${model}`" class="price-row">
          <span>{{ model }}</span>
          <input v-model.number="prices.image[model]" type="number" step="0.001" min="0" />
          <span></span>
        </div>
      </div>
      <button type="button" class="primary" :disabled="busy" @click="savePrices">保存单价</button>
    </div>

    <div class="cost-grid">
      <div class="cost-by">
        <h3>按工作空间</h3>
        <div v-if="summary && summary.by_tenant.length" class="cost-by-list">
          <div v-for="row in summary.by_tenant" :key="row.key" class="cost-by-row">
            <span>{{ row.label }}</span>
            <em>{{ usd(row.cost_usd) }}</em>
          </div>
        </div>
        <p v-else class="empty-region">暂无数据。</p>
      </div>
      <div class="cost-by">
        <h3>按渠道</h3>
        <div v-if="summary && summary.by_provider.length" class="cost-by-list">
          <div v-for="row in summary.by_provider" :key="row.key" class="cost-by-row">
            <span>{{ row.label }}<small> · {{ row.count }} 次</small></span>
            <em>{{ usd(row.cost_usd) }}</em>
          </div>
        </div>
        <p v-else class="empty-region">暂无数据。</p>
      </div>
    </div>

    <div class="section-header" style="margin-top: var(--space-md, 16px)">
      <h3>明细</h3>
      <select v-model="providerFilter" @change="reload">
        <option v-for="p in PROVIDERS" :key="p" :value="p">{{ p || '全部渠道' }}</option>
      </select>
    </div>
    <p v-if="!events.length" class="empty-region">暂无费用记录。</p>
    <div v-else class="cost-events">
      <div v-for="ev in events" :key="ev.id" class="cost-event">
        <span class="cost-event__time">{{ formatDate(ev.created_at) }}</span>
        <span class="cost-event__prov">{{ ev.provider }}</span>
        <span class="cost-event__model">{{ ev.model || ev.kind }}</span>
        <span class="cost-event__qty">{{ ev.quantity }} {{ ev.unit }}</span>
        <span class="cost-event__tenant">{{ ev.tenant_name || (ev.tenant_id ? `#${ev.tenant_id}` : '未归属') }}</span>
        <em class="cost-event__cost">{{ usd(ev.cost_usd) }}</em>
      </div>
    </div>
  </section>
</template>

<style scoped>
.cost-cards {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin: var(--space-sm, 12px) 0;
}
.cost-card {
  border: var(--rule-hair);
  border-radius: var(--radius-md, 8px);
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.cost-card strong {
  font-size: var(--text-lg, 18px);
}
.cost-card small {
  color: var(--color-ink-3, inherit);
  font-size: var(--text-xs, 12px);
}
.price-editor {
  border: var(--rule-hair);
  border-radius: var(--radius-md, 8px);
  padding: 12px;
  margin-bottom: var(--space-sm, 12px);
}
.price-grid {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 10px;
}
.price-row {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr) minmax(0, 1fr);
  gap: 8px;
  align-items: center;
}
.price-row--head {
  font-size: var(--text-xs, 12px);
  color: var(--color-ink-3, inherit);
}
.cost-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-md, 16px);
}
.cost-by-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.cost-by-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 4px 0;
  border-bottom: var(--rule-hair);
}
.cost-events {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.cost-event {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) 0.7fr minmax(0, 1.2fr) 0.9fr minmax(0, 1fr) 0.8fr;
  gap: 8px;
  align-items: center;
  padding: 6px 0;
  border-bottom: var(--rule-hair);
  font-size: var(--text-sm);
}
.cost-event__cost {
  text-align: right;
  font-style: normal;
  font-weight: 600;
}
.cost-event__time,
.cost-event__tenant {
  color: var(--color-ink-3, inherit);
}
.admin-flash {
  padding: 8px 12px;
  border-radius: var(--radius-md, 8px);
  margin: 8px 0;
}
.admin-flash--ok { background: var(--color-success-bg, #ecfdf5); }
.admin-flash--err { background: var(--color-danger-bg, #fef2f2); }
@media (max-width: 760px) {
  .cost-grid { grid-template-columns: 1fr; }
  .cost-cards { grid-template-columns: 1fr; }
}
</style>
