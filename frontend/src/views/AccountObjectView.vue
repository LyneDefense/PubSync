<script setup lang="ts">
// 我的账号对象页 /account/:id:与博主页同构,段控换成「档案 | 体检」。
// 档案视图复用 dossier 子组件;体检视图复用 DossierAudit(账号硬实力 + 受众需求)。没有「用它创作」(创作用的是别人的画像)。
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import DossierAudience from '../components/dossier/DossierAudience.vue'
import DossierAudit from '../components/dossier/DossierAudit.vue'
import DossierBuildChecklist from '../components/dossier/DossierBuildChecklist.vue'
import DossierCompliance from '../components/dossier/DossierCompliance.vue'
import DossierHabits from '../components/dossier/DossierHabits.vue'
import DossierIdentityCard from '../components/dossier/DossierIdentityCard.vue'
import DossierNotePool from '../components/dossier/DossierNotePool.vue'
import DossierPortraits from '../components/dossier/DossierPortraits.vue'
import DossierStatsPanel from '../components/dossier/DossierStatsPanel.vue'
import DossierTrajectory from '../components/dossier/DossierTrajectory.vue'
import DossierUpgradeCard from '../components/dossier/DossierUpgradeCard.vue'
import LiveProgress from '../components/LiveProgress.vue'
import {
  audienceRunning,
  dossier,
  dossierBusy,
  dossierLoading,
  handleBuildDossier,
  handleRedistill,
  handleRunAudience,
  handleSyncPool,
  handleUpgradeByUrls,
  handleUpgradeDetail,
  loadDossier
} from '../composables/useDossier'
import {
  formatDate,
  handleDeleteBlogger,
  handleRefreshBlogger,
  handleToggleBloggerFavorite,
  openEditBloggerModal,
  parseAppraisalReport,
  pendingAction,
  refreshSelfAppraisalHistory,
  selectedBlogger,
  selectedBloggerId,
  selfAppraisalHistory
} from '../composables/useWorkspaceStore'

const route = useRoute()
const router = useRouter()
const view = ref<'dossier' | 'audit'>(route.query.view === 'audit' ? 'audit' : 'dossier')

const busy = computed(() => dossierBusy())
const built = computed(() => (dossier.value?.portraits.length || 0) > 0)
const hasPool = computed(() => (dossier.value?.pool.total || 0) > 0)
const showUpgrade = ref(false)

// 本账号最近一次体检 → 喂给建档清单第⑥步的状态(硬实力分 + 时间)。
const latestAudit = computed(() =>
  selectedBlogger.value
    ? (selfAppraisalHistory.value.find((r) => r.my_blogger_id === selectedBlogger.value!.id && parseAppraisalReport(r)) ?? null)
    : null
)
const auditScore = computed(() => parseAppraisalReport(latestAudit.value)?.hard_score ?? null)
const auditAt = computed(() => (latestAudit.value ? formatDate(latestAudit.value.created_at) : null))

// 路由 :id → 选中并加载档案 + 体检历史(useDossier 自动 watch 按旧 tab 门控,新路由下不触发,故手动)。
watch(
  () => route.params.id,
  (raw) => {
    const id = Number(raw)
    if (!id) return
    selectedBloggerId.value = id
    showUpgrade.value = false
    view.value = route.query.view === 'audit' ? 'audit' : 'dossier'
    void loadDossier()
    void refreshSelfAppraisalHistory()
  },
  { immediate: true }
)
watch(() => route.query.view, (v) => { view.value = v === 'audit' ? 'audit' : 'dossier' })

function setView(v: 'dossier' | 'audit') {
  view.value = v
  router.replace({ query: { ...route.query, view: v } })
}
async function rebuild() {
  const ok = window.confirm('重建画像会重新拉取该账号全部笔记、重升详情并重蒸创作画像,约 10–20 分钟(后台执行,有 TikHub + AI 成本)。确定?')
  if (!ok) return
  await handleBuildDossier()
}
async function refreshProfile() {
  if (!selectedBlogger.value) return
  await handleRefreshBlogger(selectedBlogger.value)
  await loadDossier()
}
async function onDelete() {
  if (!selectedBlogger.value) return
  await handleDeleteBlogger(selectedBlogger.value)
  router.push({ name: 'home' })
}
function onUpgradeBatch(payload: { sampleLimit: number; contentTypes: string[] }) {
  showUpgrade.value = false
  void handleUpgradeDetail(payload.sampleLimit, payload.contentTypes)
}
function onUpgradeUrls(urls: string[]) {
  showUpgrade.value = false
  void handleUpgradeByUrls(urls)
}
</script>

<template>
  <section class="ao">
    <div class="ao-top">
      <button type="button" class="ao-crumb" @click="router.push({ name: 'home' })">
        <span aria-hidden="true">←</span> 首页
        <template v-if="selectedBlogger"><span class="ao-crumb-sep">/</span><span class="ao-crumb-cur">{{ selectedBlogger.display_name }}</span></template>
      </button>
      <span v-if="selectedBlogger" class="ao-tag">我的账号</span>
    </div>

    <template v-if="selectedBlogger">
      <div class="ao-seg" role="tablist">
        <button type="button" role="tab" :class="{ 'is-on': view === 'dossier' }" @click="setView('dossier')">档案</button>
        <button type="button" role="tab" :class="{ 'is-on': view === 'audit' }" @click="setView('audit')">体检</button>
      </div>

      <p v-if="dossierLoading && !dossier" class="ao-hint">档案加载中…</p>

      <template v-else-if="dossier">
        <!-- 体检视图 -->
        <DossierAudit v-if="view === 'audit'" :blogger="selectedBlogger" :pool-total="dossier.pool.total" :busy="busy" />

        <!-- 档案视图 -->
        <template v-else>
          <DossierIdentityCard
            :blogger="selectedBlogger"
            :pool-synced-at="dossier.pool.synced_at || null"
            :built="built"
            :refreshing="Boolean(pendingAction)"
            :building="dossier.building?.message || null"
            @toggle-favorite="handleToggleBloggerFavorite(selectedBlogger)"
            @refresh="refreshProfile"
            @collect="showUpgrade = true"
            @edit="openEditBloggerModal(selectedBlogger)"
            @delete="onDelete"
          />

          <DossierUpgradeCard
            v-if="showUpgrade"
            :blogger-id="selectedBlogger.id"
            @close="showUpgrade = false"
            @batch="onUpgradeBatch"
            @urls="onUpgradeUrls"
          />

          <DossierBuildChecklist
            :dossier="dossier"
            :blogger="selectedBlogger"
            :busy="busy"
            :show-audit="true"
            :audit-score="auditScore"
            :audit-at="auditAt"
            @build="handleBuildDossier"
            @rebuild="rebuild"
            @redistill="handleRedistill"
            @upgrade="showUpgrade = true"
            @sync="handleSyncPool"
            @audience="handleRunAudience"
            @diagnose="setView('audit')"
            @refresh="refreshProfile"
          />

          <LiveProgress v-if="pendingAction === 'dossier' || pendingAction === 'pool-sync'" />

          <DossierStatsPanel v-if="dossier.stats" :stats="dossier.stats" />
          <DossierTrajectory v-if="dossier.trajectory" :trajectory="dossier.trajectory" :reached-end="dossier.pool.reached_end" />
          <DossierAudience :audience="dossier.audience" :audience-running="audienceRunning" :busy="busy" @run-audience="handleRunAudience" />
          <DossierHabits v-if="dossier.habits" :habits="dossier.habits" />
          <DossierCompliance v-if="dossier.compliance" :compliance="dossier.compliance" />
          <DossierPortraits :portraits="dossier.portraits" :busy="busy" @redistill="handleRedistill" @rebuild="rebuild" />
          <DossierNotePool />

          <span v-if="!dossier.pool.reached_end && hasPool" class="ao-hint">
            提示:列表未翻到底,早期笔记可能缺失,可用清单的「全量校准」补齐。
          </span>
        </template>
      </template>
    </template>

    <p v-else class="ao-hint">没找到这个账号(可能不在当前平台;跨平台合并在后续步骤)。<button type="button" class="ao-link" @click="router.push({ name: 'home' })">回首页</button></p>
  </section>
</template>

<style scoped>
.ao { display: flex; flex-direction: column; gap: 14px; }
.ao-top { display: flex; align-items: center; gap: 10px; }
.ao-crumb {
  display: inline-flex; align-items: center; gap: 5px;
  border: 0; background: none; cursor: pointer;
  font-size: 12.5px; color: var(--color-ink-3); padding: 0;
}
.ao-crumb:hover { color: var(--color-accent-ink); }
.ao-crumb-sep { color: var(--color-rule-strong); }
.ao-crumb-cur { color: var(--color-ink-2); }
.ao-tag { font-size: 11px; color: var(--color-accent-ink); background: var(--color-accent-soft); border-radius: 999px; padding: 2px 9px; }
.ao-seg {
  display: inline-flex; align-self: flex-start; gap: 2px; padding: 3px;
  border: 1px solid var(--color-field-border); border-radius: 10px; background: var(--color-paper-3);
}
.ao-seg button {
  height: 30px; padding: 0 18px; border: 0; border-radius: 7px;
  background: transparent; color: var(--color-ink-2); font-size: 13px; font-weight: 560; cursor: pointer;
}
.ao-seg button.is-on { background: var(--color-surface); color: var(--color-ink); box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06); }
.ao-hint { font-size: 13px; color: var(--color-ink-3); }
.ao-link { border: 0; background: none; color: var(--color-accent-ink); cursor: pointer; font-size: 13px; }
</style>
