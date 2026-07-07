<script setup lang="ts">
// 博主画像(档案主页):右上角下拉选择器切博主,内容全宽分两条产线带 ——
// 账号事实(身份卡 / 数据面板 / 成长趋势 / 运营习惯 + 合规)与 创作画像 · 笔记池。
// 设计见 UI-Refactor/design_handoff_dossier_redesign;旧 /assets 路由按别名落到本页。
import { computed, ref, watch } from 'vue'

import DossierAudience from '../components/dossier/DossierAudience.vue'
import DossierAudit from '../components/dossier/DossierAudit.vue'
import DossierBloggerPicker from '../components/dossier/DossierBloggerPicker.vue'
import DossierBuildChecklist from '../components/dossier/DossierBuildChecklist.vue'
import DossierUpgradeCard from '../components/dossier/DossierUpgradeCard.vue'
import LiveProgress from '../components/LiveProgress.vue'
import DossierCompliance from '../components/dossier/DossierCompliance.vue'
import DossierHabits from '../components/dossier/DossierHabits.vue'
import DossierIdentityCard from '../components/dossier/DossierIdentityCard.vue'
import DossierNotePool from '../components/dossier/DossierNotePool.vue'
import DossierPortraits from '../components/dossier/DossierPortraits.vue'
import DossierStatsPanel from '../components/dossier/DossierStatsPanel.vue'
import DossierTrajectory from '../components/dossier/DossierTrajectory.vue'
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
  benchmarkAccounts,
  currentSocialTab,
  formatDate,
  handleDeleteBlogger,
  handleRefreshBlogger,
  handleToggleBloggerFavorite,
  isSocialPlatform,
  myAccountsOnPlatform,
  openCreateMyAccountModal,
  openEditBloggerModal,
  parseAppraisalReport,
  pendingAction,
  refreshSelfAppraisalHistory,
  selectBlogger,
  selectedBlogger,
  selectedBloggerId,
  selfAppraisalHistory
} from '../composables/useWorkspaceStore'

// 旧「博主资产」tab 并入本页:assets 作为别名仍然渲染这里,老链接/收藏不失效。
const visible = computed(() => isSocialPlatform.value && ['dossier', 'assets', 'my-accounts'].includes(currentSocialTab.value))
const busy = computed(() => dossierBusy())
const hasPool = computed(() => (dossier.value?.pool.total || 0) > 0)
const built = computed(() => (dossier.value?.portraits.length || 0) > 0)

// mine(我的账号)/ benchmark(对标博主)同一套档案组件,只按 account_type 换账号列表。
const mode = computed<'mine' | 'benchmark'>(() => (currentSocialTab.value === 'my-accounts' ? 'mine' : 'benchmark'))
const accounts = computed(() => (mode.value === 'mine' ? myAccountsOnPlatform.value : benchmarkAccounts.value))

// 我的账号页:档案(事实)| 体检(评分)段控;对标博主页只有档案。
const view = ref<'dossier' | 'audit'>('dossier')
// 本账号最近一次体检 → 喂给清单第⑥步的状态(实力分 + 时间)。
const latestAudit = computed(() =>
  mode.value === 'mine' && selectedBlogger.value
    ? (selfAppraisalHistory.value.find((r) => r.my_blogger_id === selectedBlogger.value!.id && parseAppraisalReport(r)) ?? null)
    : null
)
const auditScore = computed(() => parseAppraisalReport(latestAudit.value)?.hard_score ?? null)
const auditAt = computed(() => (latestAudit.value ? formatDate(latestAudit.value.created_at) : null))
// 切账号 / 换 tab:回到档案视图;进我的账号则拉体检历史(喂清单状态 + 体检视图)。
watch(
  [mode, selectedBloggerId],
  () => {
    view.value = 'dossier'
    if (mode.value === 'mine') void refreshSelfAppraisalHistory()
  },
  { immediate: true }
)

// 选中态始终对齐当前 tab 的账号类型(两类共用 selectedBloggerId):失效则自动选第一个。
watch(
  [currentSocialTab, accounts],
  () => {
    if (!visible.value) return
    if (!selectedBloggerId.value || !accounts.value.some((a) => a.id === selectedBloggerId.value)) {
      selectedBloggerId.value = accounts.value[0]?.id ?? null
    }
  },
  { immediate: true }
)

// 重建画像 = 重跑一键建档(重拉全部笔记 + 重升详情 + 重蒸)。信息确认告知耗时,不劝退。
async function rebuild() {
  const ok = window.confirm('重建画像会重新拉取该博主全部笔记、重升详情并重蒸创作画像,约 10–20 分钟(后台执行,有 TikHub + AI 成本)。确定?')
  if (!ok) return
  await handleBuildDossier()
}

// 刷新资料后要重载档案聚合(数据面板的 note_total/获赞收藏来自聚合接口,不重拉不更新)。
async function refreshProfile() {
  if (!selectedBlogger.value) return
  await handleRefreshBlogger(selectedBlogger.value)
  await loadDossier()
}
function onDelete() {
  if (selectedBlogger.value) handleDeleteBlogger(selectedBlogger.value)
}

// 建档清单④ 升详情弹卡:批量升 / 定向补采,确认后走 useDossier 跑任务(就地进度)。
const showUpgrade = ref(false)
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
  <section v-if="visible" class="dossier-view">
    <div class="dossier-view__header">
      <DossierBloggerPicker v-if="accounts.length" :accounts="accounts" :selected-id="selectedBloggerId" @select="selectBlogger" />
      <button v-if="mode === 'mine'" type="button" class="dossier-view__add" @click="openCreateMyAccountModal">+ 添加我的账号</button>
    </div>

    <p v-if="!accounts.length" class="dossier-view__hint">
      <template v-if="mode === 'mine'">还没有我的账号，点右上角「+ 添加我的账号」。</template>
      <template v-else>还没有对标博主，先去「查找博主」添加。</template>
    </p>
    <p v-else-if="!selectedBlogger" class="dossier-view__hint">从上方选择器选择一个账号查看档案。</p>

    <div v-else class="dossier-view__content">
      <DossierIdentityCard
        :blogger="selectedBlogger"
        :pool-synced-at="dossier?.pool.synced_at || null"
        :built="built"
        :refreshing="Boolean(pendingAction)"
        :building="dossier?.building?.message || null"
        @toggle-favorite="handleToggleBloggerFavorite(selectedBlogger)"
        @refresh="refreshProfile"
        @collect="showUpgrade = true"
        @edit="openEditBloggerModal(selectedBlogger)"
        @delete="onDelete"
      />

      <!-- 我的账号:档案(事实)| 体检(评分)段控;对标博主页无此段控。 -->
      <div v-if="mode === 'mine' && dossier" class="dossier-view__seg" role="tablist">
        <button type="button" role="tab" :class="{ 'is-on': view === 'dossier' }" @click="view = 'dossier'">档案</button>
        <button type="button" role="tab" :class="{ 'is-on': view === 'audit' }" @click="view = 'audit'">体检</button>
      </div>

      <!-- 升详情弹卡:档案/体检两视图都可触发,放段控外。 -->
      <DossierUpgradeCard
        v-if="showUpgrade && selectedBlogger"
        :blogger-id="selectedBlogger.id"
        @close="showUpgrade = false"
        @batch="onUpgradeBatch"
        @urls="onUpgradeUrls"
      />

      <p v-if="dossierLoading && !dossier" class="dossier-view__hint">档案加载中…</p>

      <template v-else-if="dossier">
        <!-- 体检视图(仅我的账号) -->
        <DossierAudit
          v-if="view === 'audit' && mode === 'mine'"
          :blogger="selectedBlogger"
          :pool-total="dossier.pool.total"
          :busy="busy"
        />

        <!-- 档案视图 -->
        <template v-else>
          <!-- 建档状态清单:每步状态 + 就地入口 + 就地进度(不跳 tab);我的账号多一步「账号体检」 -->
          <DossierBuildChecklist
            :dossier="dossier"
            :blogger="selectedBlogger"
            :busy="busy"
            :show-audit="mode === 'mine'"
            :audit-score="auditScore"
            :audit-at="auditAt"
            @build="handleBuildDossier"
            @rebuild="rebuild"
            @redistill="handleRedistill"
            @upgrade="showUpgrade = true"
            @sync="handleSyncPool"
            @audience="handleRunAudience"
            @diagnose="view = 'audit'"
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

          <span v-if="!dossier.pool.reached_end && hasPool" class="dossier-view__sync-hint">
            提示:列表未翻到底,早期笔记可能缺失,可用上方清单的「全量校准」补齐。
          </span>
        </template>
      </template>
    </div>
  </section>
</template>

<style scoped>
.dossier-view { max-width: 940px; margin: 0 auto; }
.dossier-view__header {
  display: flex;
  align-items: flex-end;
  justify-content: flex-end;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.dossier-view__add {
  height: 34px; padding: 0 14px; border: 1px solid var(--color-field-border); border-radius: 9px;
  background: var(--color-surface); color: var(--color-ink-2); font-size: 13px; cursor: pointer;
}
.dossier-view__add:hover { border-color: var(--color-accent); color: var(--color-accent-ink); }
.dossier-view__hint { font-size: 13px; color: var(--color-ink-3); }
.dossier-view__content { display: flex; flex-direction: column; gap: 14px; }

/* 档案 | 体检 段控 */
.dossier-view__seg {
  display: inline-flex;
  align-self: flex-start;
  gap: 2px;
  padding: 3px;
  border: 1px solid var(--color-field-border);
  border-radius: 10px;
  background: var(--color-paper-3);
}
.dossier-view__seg button {
  height: 30px;
  padding: 0 18px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--color-ink-2);
  font-size: 13px;
  font-weight: 560;
  cursor: pointer;
}
.dossier-view__seg button.is-on {
  background: var(--color-surface);
  color: var(--color-ink);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}

.dossier-view__two-col { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 14px; }

.dossier-view__empty {
  padding: 36px 24px;
  border: 1px dashed var(--color-rule-strong);
  border-radius: 14px;
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
}
.dossier-view__empty h3 { margin: 0; }
.dossier-view__empty p { margin: 0; font-size: 13px; color: var(--color-ink-2); max-width: 520px; }
.dossier-view__empty-note { font-size: 12px; color: var(--color-ink-3); }
.dossier-view__nudge {
  padding: 10px 14px;
  border-radius: 10px;
  background: #fdf3e0;
  color: #8a5a12;
  font-size: 12.5px;
}
.dossier-view__sync-hint { font-size: 12px; color: var(--color-ink-3); }
</style>

<style>
/* 档案页徽章:身份卡「构建中」chip 用(子组件内引用,需全局)。 */
.dossier-chip {
  font-size: 11px;
  padding: 2px 9px;
  border-radius: 999px;
  background: var(--color-paper-3);
  color: var(--color-ink-2);
  white-space: nowrap;
}
.dossier-chip--busy { background: var(--color-accent-soft); color: var(--color-accent-ink); }
</style>
