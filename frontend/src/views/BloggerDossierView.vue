<script setup lang="ts">
// 博主画像(档案主页):左选博主,右五区(身份/数据/轨迹/画像/笔记池)。
// 空态 = 一键「构建博主画像」;构建中渐进点亮;缺数据各区诚实降级。设计见 docs/博主档案页_流程设计.md。
import { computed } from 'vue'

import DossierIdentityCard from '../components/dossier/DossierIdentityCard.vue'
import DossierPool from '../components/dossier/DossierPool.vue'
import DossierPortraits from '../components/dossier/DossierPortraits.vue'
import DossierStatsPanel from '../components/dossier/DossierStatsPanel.vue'
import DossierTrajectory from '../components/dossier/DossierTrajectory.vue'
import type { DossierPortrait } from '../api/types'
import {
  attributionRunning,
  dossier,
  dossierBusy,
  dossierLoading,
  handleBuildDossier,
  handleRunAttribution,
  handleSyncPool,
  loadDossier,
} from '../composables/useDossier'
import {
  benchmarkAccounts,
  currentSocialTab,
  handleDistillFromSnapshot,
  isSocialPlatform,
  selectedBloggerId,
  setCurrentSocialTab,
} from '../composables/useWorkspaceStore'

const visible = computed(() => isSocialPlatform.value && currentSocialTab.value === 'dossier')
const selectedBlogger = computed(() => benchmarkAccounts.value.find((b) => b.id === selectedBloggerId.value) || null)
const busy = computed(() => dossierBusy())
const hasPool = computed(() => (dossier.value?.pool.total || 0) > 0)

function pickBlogger(id: number) {
  selectedBloggerId.value = id // watch(useDossier) 会自动 loadDossier
}

async function redistill(portrait: DossierPortrait) {
  if (!portrait.snapshot_id) return
  await handleDistillFromSnapshot(portrait.snapshot_id)
  await loadDossier()
}
</script>

<template>
  <section v-if="visible" class="dossier-view">
    <div class="section-header">
      <div>
        <h2>博主画像</h2>
        <p class="toolbar-subtitle">先把博主的信息建全（物理层），再看系统的分析（数据 / 轨迹 / 画像）。</p>
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
          @click="pickBlogger(b.id)"
        >
          <strong>{{ b.display_name }}</strong>
          <span>{{ b.niche || (b.platform === 'douyin' ? '抖音' : '小红书') }}</span>
        </button>
      </aside>

      <div class="dossier-view__content">
        <p v-if="!selectedBlogger" class="dossier-block__hint">从左侧选择一个博主查看画像。</p>
        <template v-else>
          <DossierIdentityCard :blogger="selectedBlogger" :pool-synced-at="dossier?.pool.synced_at || null">
            <span v-if="dossier?.building" class="dossier-chip dossier-chip--busy">构建中 · {{ dossier.building.message }}</span>
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
            <DossierStatsPanel v-if="dossier.stats" :stats="dossier.stats" />
            <DossierTrajectory
              v-if="dossier.trajectory"
              :trajectory="dossier.trajectory"
              :attribution="dossier.attribution"
              :attribution-running="attributionRunning"
              :reached-end="dossier.pool.reached_end"
              :busy="busy"
              @run-attribution="handleRunAttribution"
            />
            <DossierPortraits
              :portraits="dossier.portraits"
              :busy="busy"
              @redistill="redistill"
              @new-portrait="setCurrentSocialTab('assets')"
            />
            <DossierPool
              :pool="dossier.pool"
              :busy="busy"
              @sync="handleSyncPool"
              @open-assets="setCurrentSocialTab('assets')"
            />
          </template>
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

@media (max-width: 900px) {
  .dossier-view__layout { flex-direction: column; }
  .dossier-view__rail { width: 100%; flex-direction: row; flex-wrap: wrap; }
}
</style>

<style>
/* 档案页区块与徽章:五区共用,故放全局(仅 dossier- 前缀,避免污染)。 */
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
