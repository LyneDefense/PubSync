<script setup lang="ts">
// 博主画像(档案主页,已并入原「博主资产」):左选博主,右 = 身份卡 → 数据面板 → 成长轨迹 →
// 创作画像(可展开看蒸馏结果) → 选材快照 + 笔记池(可折叠,含笔记详情弹窗)。
// 设计见 docs/博主档案页_流程设计.md;旧 /assets 路由按别名落到本页。
import { computed } from 'vue'

import DossierAssetsPanel from '../components/dossier/DossierAssetsPanel.vue'
import DossierCompliance from '../components/dossier/DossierCompliance.vue'
import DossierHabits from '../components/dossier/DossierHabits.vue'
import DossierIdentityCard from '../components/dossier/DossierIdentityCard.vue'
import DossierPortraits from '../components/dossier/DossierPortraits.vue'
import DossierStatsPanel from '../components/dossier/DossierStatsPanel.vue'
import DossierTrajectory from '../components/dossier/DossierTrajectory.vue'
import {
  attributionRunning,
  dossier,
  dossierBusy,
  dossierLoading,
  handleBuildDossier,
  handleRunAttribution,
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
  selectedBloggerId,
} from '../composables/useWorkspaceStore'

// 旧「博主资产」tab 并入本页:assets 作为别名仍然渲染这里,老链接/收藏不失效。
const visible = computed(() => isSocialPlatform.value && ['dossier', 'assets'].includes(currentSocialTab.value))
const busy = computed(() => dossierBusy())
const hasPool = computed(() => (dossier.value?.pool.total || 0) > 0)

// 去多画像:重新蒸馏 = 重跑一键建档(重新系统选样 + 覆盖唯一画像),不再走快照。
async function redistill() {
  await handleBuildDossier()
}
</script>

<template>
  <section v-if="visible" class="dossier-view">
    <div class="section-header">
      <div>
        <h2>博主画像</h2>
        <p class="toolbar-subtitle">这个博主的一切:真实数据（身份 / 笔记池）+ 系统分析（数据 / 轨迹 / 创作画像）。</p>
      </div>
    </div>

    <div class="dossier-view__layout">
      <aside class="dossier-view__rail">
        <p v-if="!benchmarkAccounts.length" class="dossier-block__hint">还没有对标博主，先去「找对标博主」添加。</p>
        <button
          v-for="b in benchmarkAccounts"
          :key="b.id"
          type="button"
          class="dossier-view__blogger"
          :class="{ 'dossier-view__blogger--active': b.id === selectedBloggerId }"
          @click="selectBlogger(b.id)"
        >
          <strong>{{ b.display_name }}</strong>
          <span>{{ b.niche || (b.platform === 'douyin' ? '抖音' : '小红书') }} · 样本 {{ b.sample_count }}</span>
        </button>
      </aside>

      <div class="dossier-view__content">
        <p v-if="!selectedBlogger" class="dossier-block__hint">从左侧选择一个博主查看画像。</p>
        <template v-else>
          <DossierIdentityCard :blogger="selectedBlogger" :pool-synced-at="dossier?.pool.synced_at || null">
            <span v-if="dossier?.building" class="dossier-chip dossier-chip--busy">构建中 · {{ dossier.building.message }}</span>
            <div class="dossier-view__id-actions">
              <button type="button" class="ghost" @click="handleToggleBloggerFavorite(selectedBlogger)">{{ selectedBlogger.is_favorite ? '取消标记' : '⭐ 标记' }}</button>
              <button type="button" class="ghost" @click="openEditBloggerModal(selectedBlogger)">编辑</button>
              <button type="button" class="ghost" :disabled="Boolean(pendingAction)" @click="handleRefreshBlogger(selectedBlogger)">刷新资料</button>
              <button type="button" class="ghost" @click="goCollectForBlogger(selectedBlogger.id)">采集笔记 →</button>
              <button type="button" class="ghost dossier-view__danger" @click="handleDeleteBlogger(selectedBlogger)">删除</button>
            </div>
          </DossierIdentityCard>

          <p v-if="dossierLoading && !dossier" class="dossier-block__hint">档案加载中…</p>

          <!-- 空态:未建档 → 一键构建 -->
          <div v-else-if="dossier && !hasPool && !dossier.building" class="dossier-view__empty">
            <h3>还没有这个博主的画像</h3>
            <p>
              一键构建会依次完成：拉取资料 → 全量笔记列表入池 → 数据面板与成长轨迹 →
              最新笔记升级详情（正文 / 转写 / 图文理解）→ 自动蒸馏默认创作画像。
            </p>
            <p class="dossier-view__empty-note">全程约 10–20 分钟，后台执行，可离开本页随时回来看进度。</p>
            <button type="button" class="primary" :disabled="busy" @click="handleBuildDossier">构建博主画像</button>
          </div>

          <template v-else-if="dossier">
            <div v-if="!dossier.building && dossier.pool.list_count === dossier.pool.total && hasPool" class="dossier-view__nudge">
              笔记池目前只有列表级数据（无正文/转写），
              <button type="button" class="link-button" :disabled="busy" @click="handleBuildDossier">一键构建画像</button>
              可升级详情并自动蒸馏。
            </div>
            <DossierStatsPanel v-if="dossier.stats" :stats="dossier.stats" />
            <DossierHabits v-if="dossier.habits" :habits="dossier.habits" />
            <DossierTrajectory
              v-if="dossier.trajectory"
              :trajectory="dossier.trajectory"
              :attribution="dossier.attribution"
              :attribution-running="attributionRunning"
              :reached-end="dossier.pool.reached_end"
              :busy="busy"
              @run-attribution="handleRunAttribution"
            />
            <DossierCompliance v-if="dossier.compliance" :compliance="dossier.compliance" />
            <DossierPortraits :portraits="dossier.portraits" :busy="busy" @redistill="redistill" />
          </template>

          <!-- 选材快照 + 笔记池(原博主资产,含选取/详情/笔记弹窗) -->
          <DossierAssetsPanel :busy="busy" />
          <span class="dossier-view__sync-hint" v-if="dossier && !dossier.pool.reached_end && hasPool">
            提示:列表未翻到底,早期笔记可能缺失,可在笔记池点「全量校准」补齐。
          </span>
        </template>
      </div>
    </div>
  </section>
</template>

<style scoped>
.dossier-view__layout { display: flex; gap: 16px; align-items: flex-start; }
.dossier-view__rail {
  width: 200px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.dossier-view__blogger {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 12px;
  text-align: left;
  border: 1px solid var(--color-rule);
  border-radius: 10px;
  background: var(--color-paper-2);
  cursor: pointer;
}
.dossier-view__blogger span { font-size: 12px; color: var(--color-ink-3); }
.dossier-view__blogger--active { border-color: var(--color-accent); background: var(--color-accent-soft); }
.dossier-view__content { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 12px; }
.dossier-view__id-actions { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
.dossier-view__id-actions .ghost { font-size: 12px; padding: 4px 10px; }
.dossier-view__danger { color: var(--color-danger); }
.dossier-view__empty {
  padding: 36px 24px;
  border: 1px dashed var(--color-rule-strong);
  border-radius: 12px;
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

@media (max-width: 900px) {
  .dossier-view__layout { flex-direction: column; }
  .dossier-view__rail { width: 100%; flex-direction: row; flex-wrap: wrap; }
}
</style>

<style>
/* 档案页区块与徽章:各区共用,全局(仅 dossier- 前缀,避免污染)。 */
.dossier-block {
  padding: 16px 20px;
  background: var(--color-paper-2);
  border: 1px solid var(--color-rule);
  border-radius: 12px;
}
.dossier-block__head { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }
.dossier-block__head h3 { margin: 0; font-size: 15px; }
.dossier-block__head .ghost { margin-left: auto; }
.dossier-block__hint { font-size: 12px; color: var(--color-ink-3); }
.dossier-chip {
  font-size: 11px;
  padding: 2px 9px;
  border-radius: 999px;
  background: var(--color-paper-3);
  color: var(--color-ink-2);
  white-space: nowrap;
}
.dossier-chip--ok { background: var(--color-ok-bg); color: var(--color-ok); }
.dossier-chip--warn { background: #fdf3e0; color: #8a5a12; }
.dossier-chip--busy { background: var(--color-accent-soft); color: var(--color-accent-ink); }
.dossier-chip--burst { background: #fceceb; color: var(--color-danger); }
</style>
