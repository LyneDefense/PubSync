<script setup lang="ts">
// 博主对象页 /blogger/:id(对象驱动新架构):面包屑 + 身份行(用它创作)+ 段控「档案 | 对标分析」。
// 档案视图直接复用现有 dossier 子组件 + useDossier 编排(和旧 BloggerDossierView 同一套,只是换成路由 :id 驱动)。
// 对标分析视图留占位,UI·4 接入 BenchmarkAnalysisView。
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import DossierAudience from '../components/dossier/DossierAudience.vue'
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
import BenchmarkAnalysisView from './BenchmarkAnalysisView.vue'
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
  activeMainTab,
  handleDeleteBlogger,
  handleRefreshBlogger,
  handleToggleBloggerFavorite,
  openEditBloggerModal,
  pendingAction,
  refreshSelectedBlogger,
  selectedBlogger,
  selectedBloggerId
} from '../composables/useWorkspaceStore'

const route = useRoute()
const router = useRouter()
const view = ref<'dossier' | 'analysis'>(route.query.view === 'analysis' ? 'analysis' : 'dossier')

const busy = computed(() => dossierBusy())
const built = computed(() => (dossier.value?.portraits.length || 0) > 0)
const hasPool = computed(() => (dossier.value?.pool.total || 0) > 0)
const showUpgrade = ref(false)

// 路由 :id → 选中并加载档案(直接调 loadDossier;useDossier 的自动 watch 仍按旧 tab 门控,新路由下不触发)。
watch(
  () => route.params.id,
  (raw) => {
    const id = Number(raw)
    if (!id) return
    selectedBloggerId.value = id
    showUpgrade.value = false
    void loadDossier()
    void refreshSelectedBlogger() // 笔记池(bloggerPosts)/蒸馏记录靠它加载,漏了列表就空
  },
  { immediate: true }
)
watch(() => route.query.view, (v) => { view.value = v === 'analysis' ? 'analysis' : 'dossier' })
// 新架构无平台门:选中博主后把平台对齐到它,让 currentSocialPlatform 相关调用(蒸馏/分析)指向对的平台。
watch(selectedBlogger, (b) => { if (b) activeMainTab.value = b.platform === 'douyin' ? 'douyin' : 'xhs' }, { immediate: true })

function setView(v: 'dossier' | 'analysis') {
  view.value = v
  router.replace({ query: { ...route.query, view: v } })
}
function createWith() {
  if (selectedBlogger.value) router.push({ name: 'create', query: { blogger: selectedBlogger.value.id } })
}
async function rebuild() {
  const ok = window.confirm('重建画像会重新拉取该博主全部笔记、重升详情并重蒸创作画像,约 10–20 分钟(后台执行,有 TikHub + AI 成本)。确定?')
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
  <section class="bo">
    <div class="bo-top">
      <button type="button" class="bo-crumb" @click="router.push({ name: 'home' })">
        <span aria-hidden="true">←</span> 首页
        <template v-if="selectedBlogger"><span class="bo-crumb-sep">/</span><span class="bo-crumb-cur">{{ selectedBlogger.display_name }}</span></template>
      </button>
      <button v-if="selectedBlogger" type="button" class="bo-create" @click="createWith">
        <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3l2.3 6.6H21l-5.4 4 2 6.4-5.6-4-5.6 4 2-6.4-5.4-4h6.7z" /></svg>
        用它创作
      </button>
    </div>

    <template v-if="selectedBlogger">
      <div class="bo-seg" role="tablist">
        <button type="button" role="tab" :class="{ 'is-on': view === 'dossier' }" @click="setView('dossier')">档案</button>
        <button type="button" role="tab" :class="{ 'is-on': view === 'analysis' }" @click="setView('analysis')">对标分析</button>
      </div>

      <p v-if="dossierLoading && !dossier" class="bo-hint">档案加载中…</p>

      <!-- 档案视图 -->
      <template v-else-if="view === 'dossier' && dossier">
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
          @build="handleBuildDossier"
          @rebuild="rebuild"
          @redistill="handleRedistill"
          @upgrade="showUpgrade = true"
          @sync="handleSyncPool"
          @audience="handleRunAudience"
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

        <span v-if="!dossier.pool.reached_end && hasPool" class="bo-hint">
          提示:列表未翻到底,早期笔记可能缺失,可用清单的「全量校准」补齐。
        </span>
      </template>

      <!-- 对标分析视图:复用 BenchmarkAnalysisView 的嵌入模式(博主已定,跳过选博主步)。 -->
      <BenchmarkAnalysisView v-else-if="view === 'analysis'" embedded :blogger-id="selectedBlogger.id" />
    </template>

    <p v-else class="bo-hint">没找到这个博主(可能不在当前平台;跨平台合并在后续步骤)。<button type="button" class="bo-link" @click="router.push({ name: 'home' })">回首页</button></p>
  </section>
</template>

<style scoped>
.bo { display: flex; flex-direction: column; gap: 14px; }
.bo-top { display: flex; align-items: center; gap: 12px; }
.bo-crumb {
  display: inline-flex; align-items: center; gap: 5px;
  border: 0; background: none; cursor: pointer;
  font-size: 12.5px; color: var(--color-ink-3); padding: 0;
}
.bo-crumb:hover { color: var(--color-accent-ink); }
.bo-crumb-sep { color: var(--color-rule-strong); }
.bo-crumb-cur { color: var(--color-ink-2); }
.bo-create {
  margin-left: auto;
  display: inline-flex; align-items: center; gap: 5px;
  height: 32px; padding: 0 13px; border: 0; border-radius: 8px;
  background: var(--color-accent); color: #fff; font-size: 13px; font-weight: 600; cursor: pointer;
}
.bo-create:hover { background: var(--color-accent-press); }
.bo-seg {
  display: inline-flex; align-self: flex-start; gap: 2px; padding: 3px;
  border: 1px solid var(--color-field-border); border-radius: 10px; background: var(--color-paper-3);
}
.bo-seg button {
  height: 30px; padding: 0 18px; border: 0; border-radius: 7px;
  background: transparent; color: var(--color-ink-2); font-size: 13px; font-weight: 560; cursor: pointer;
}
.bo-seg button.is-on { background: var(--color-surface); color: var(--color-ink); box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06); }
.bo-hint { font-size: 13px; color: var(--color-ink-3); }
.bo-link { border: 0; background: none; color: var(--color-accent-ink); cursor: pointer; font-size: 13px; }
.bo-analysis-ph {
  border: 1px dashed var(--color-rule-strong); border-radius: var(--radius-lg);
  background: var(--color-surface); padding: 36px 24px; text-align: center;
  font-size: 13px; color: var(--color-ink-3);
}
.bo-plat-tag { display: inline-flex; align-items: center; gap: 4px; font-size: 11.5px; color: var(--color-ink-2); background: var(--color-paper-3); border-radius: 999px; padding: 2px 8px; margin-right: 8px; }
.bo-dot { width: 6px; height: 6px; border-radius: 50%; }
</style>
