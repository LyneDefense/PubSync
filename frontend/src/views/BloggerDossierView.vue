<script setup lang="ts">
// 博主画像(档案主页):右上角下拉选择器切博主,内容全宽分两条产线带 ——
// 账号事实(身份卡 / 数据面板 / 成长趋势 / 运营习惯 + 合规)与 创作画像 · 笔记池。
// 设计见 UI-Refactor/design_handoff_dossier_redesign;旧 /assets 路由按别名落到本页。
import { computed } from 'vue'

import DossierAudience from '../components/dossier/DossierAudience.vue'
import DossierBloggerPicker from '../components/dossier/DossierBloggerPicker.vue'
import DossierBuildChecklist from '../components/dossier/DossierBuildChecklist.vue'
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
  handleUpgradeDetail,
  loadDossier
} from '../composables/useDossier'
import {
  benchmarkAccounts,
  currentSocialTab,
  goCollectForBlogger,
  handleDeleteBlogger,
  handleRefreshBlogger,
  handleToggleBloggerFavorite,
  isSocialPlatform,
  openEditBloggerModal,
  pendingAction,
  selectBlogger,
  selectedBlogger,
  selectedBloggerId
} from '../composables/useWorkspaceStore'

// 旧「博主资产」tab 并入本页:assets 作为别名仍然渲染这里,老链接/收藏不失效。
const visible = computed(() => isSocialPlatform.value && ['dossier', 'assets'].includes(currentSocialTab.value))
const busy = computed(() => dossierBusy())
const hasPool = computed(() => (dossier.value?.pool.total || 0) > 0)
const built = computed(() => (dossier.value?.portraits.length || 0) > 0)

// 彻底重建 = 重跑一键建档(重拉全部笔记 + 重升详情 + 重蒸)。信息确认告知耗时,不劝退。
async function rebuild() {
  const ok = window.confirm('彻底重建会重新拉取该博主全部笔记、重升详情并重蒸创作画像,约 10–20 分钟(后台执行,有 TikHub + AI 成本)。确定?')
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
</script>

<template>
  <section v-if="visible" class="dossier-view">
    <div class="dossier-view__header">
      <DossierBloggerPicker v-if="benchmarkAccounts.length" :accounts="benchmarkAccounts" :selected-id="selectedBloggerId" @select="selectBlogger" />
    </div>

    <p v-if="!benchmarkAccounts.length" class="dossier-view__hint">还没有对标博主，先去「找对标博主」添加。</p>
    <p v-else-if="!selectedBlogger" class="dossier-view__hint">从右上角选择器选择一个博主查看画像。</p>

    <div v-else class="dossier-view__content">
      <DossierIdentityCard
        :blogger="selectedBlogger"
        :pool-synced-at="dossier?.pool.synced_at || null"
        :built="built"
        :refreshing="Boolean(pendingAction)"
        :building="dossier?.building?.message || null"
        @toggle-favorite="handleToggleBloggerFavorite(selectedBlogger)"
        @refresh="refreshProfile"
        @collect="goCollectForBlogger(selectedBlogger.id)"
        @edit="openEditBloggerModal(selectedBlogger)"
        @delete="onDelete"
      />

      <p v-if="dossierLoading && !dossier" class="dossier-view__hint">档案加载中…</p>

      <template v-else-if="dossier">
        <!-- 建档状态清单:每步状态 + 就地入口 + 就地进度(不跳 tab) -->
        <DossierBuildChecklist
          :dossier="dossier"
          :blogger="selectedBlogger"
          :busy="busy"
          @build="handleBuildDossier"
          @rebuild="rebuild"
          @redistill="handleRedistill"
          @upgrade="handleUpgradeDetail"
          @sync="handleSyncPool"
          @audience="handleRunAudience"
          @refresh="refreshProfile"
        />

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
.dossier-view__hint { font-size: 13px; color: var(--color-ink-3); }
.dossier-view__content { display: flex; flex-direction: column; gap: 14px; }

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
