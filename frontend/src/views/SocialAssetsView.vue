<script setup lang="ts">
// 社媒·博主资产：博主、采集批次、蒸馏结果与样本展示。
// 状态与方法来自 useWorkspaceStore 单例；本组件仅负责该面板的视图与交互。
import { computed } from 'vue'
import { sanitizeHtml } from '../utils/sanitize'
import StatusChip from '../components/StatusChip.vue'
import { bloggerCommentLabel } from '../utils/format'
import {
  article,
  benchmarkAccounts,
  bloggerCollectionRuns,
  bloggerPosts,
  collectionDistillationCount,
  currentSocialPlatformName,
  currentSocialTab,
  distillRunMeta,
  formatDate,
  handleAbandonBloggerRun,
  handleConfirmBloggerRun,
  handleDeleteBlogger,
  handleToggleBloggerFavorite,
  isSocialPlatform,
  openEditBloggerModal,
  pendingAction,
  qualityTone,
  resultCollectionFilter,
  selectBlogger,
  selectBloggerRun,
  selectCollectionRun,
  selectedBlogger,
  selectedBloggerId,
  selectedBloggerRun,
  selectedBloggerRunCount,
  selectedBloggerRunId,
  selectedBloggerSkill,
  selectedCollectionRun,
  selectedCollectionRunId,
  showAllBloggerRuns,
  showCollectionResults,
  visibleBloggerRunCount,
  visibleBloggerRuns
} from '../composables/useWorkspaceStore'

// 当前蒸馏结果的模式与质量分（解析自 report_json）。
const selectedRunMeta = computed(() => distillRunMeta(selectedBloggerRun.value))
</script>

<template>
      <section v-if="isSocialPlatform && currentSocialTab === 'assets'" class="panel">
        <div class="section-header">
          <div>
            <h2>{{ currentSocialPlatformName }}博主资产</h2>
            <p class="toolbar-subtitle">集中查看博主信息、采集历史、蒸馏历史、报告和 Skill。</p>
          </div>
        </div>

        <div class="xhs-assets-browser">
          <aside class="asset-sidebar" aria-label="小红书博主列表">
            <div class="run-list-header">
              <strong>博主</strong>
              <span>{{ benchmarkAccounts.length }} 个</span>
            </div>
            <button
              v-for="blogger in benchmarkAccounts"
              :key="blogger.id"
              type="button"
              :class="{ active: selectedBloggerId === blogger.id }"
              @click="selectBlogger(blogger.id)"
            >
              <strong>{{ blogger.display_name }}</strong>
              <span>{{ blogger.is_favorite ? '已标记 · ' : '' }}{{ blogger.niche || '未设置领域' }} · 样本 {{ blogger.sample_count }}</span>
            </button>
            <p v-if="!benchmarkAccounts.length" class="empty-region">还没有对标博主。请先到“数据采集”创建博主。</p>
          </aside>

          <div v-if="selectedBlogger" class="asset-detail">
            <div class="asset-hero">
              <div>
                <span>{{ selectedBlogger.is_favorite ? '已标记博主' : '博主资产' }}</span>
                <h3>{{ selectedBlogger.display_name }}</h3>
                <p>{{ selectedBlogger.description || selectedBlogger.niche || '暂无备注' }}</p>
              </div>
              <div class="asset-actions">
                <button type="button" @click="handleToggleBloggerFavorite(selectedBlogger)">
                  {{ selectedBlogger.is_favorite ? '取消标记' : '标记博主' }}
                </button>
                <button type="button" @click="openEditBloggerModal(selectedBlogger)">编辑信息</button>
                <button type="button" class="danger" @click="handleDeleteBlogger(selectedBlogger)">删除博主</button>
              </div>
            </div>

            <div class="workspace-snapshot scoped-snapshot">
              <div>
                <span>采集批次</span>
                <strong>{{ bloggerCollectionRuns.length }}</strong>
              </div>
              <div>
                <span>蒸馏记录</span>
                <strong>{{ selectedBloggerRunCount }}</strong>
              </div>
              <div>
                <span>最近蒸馏</span>
                <strong>{{ selectedBlogger.last_distilled_at ? formatDate(selectedBlogger.last_distilled_at) : '暂无' }}</strong>
              </div>
            </div>

            <div class="asset-two-column">
              <section class="asset-panel">
                <div class="run-list-header">
                  <strong>采集历史</strong>
                  <span>{{ bloggerCollectionRuns.length }} 次</span>
                </div>
                <div class="asset-run-list">
                  <button
                    v-for="run in bloggerCollectionRuns"
                    :key="run.id"
                    type="button"
                    :class="{ active: selectedCollectionRunId === run.id }"
                    @click="selectCollectionRun(run.id)"
                  >
                    <span class="asset-run-row"><strong>#{{ run.id }} · {{ formatDate(run.created_at) }}</strong><StatusChip :status="run.status" /></span>
                    <span class="asset-run-meta">样本 {{ run.post_count }} · 评论 {{ run.comment_count }} · ASR {{ run.asr_enabled ? '开' : '关' }} · 蒸馏 {{ collectionDistillationCount(run.id) }} 次</span>
                  </button>
                  <p v-if="!bloggerCollectionRuns.length" class="empty-region">这个博主还没有采集批次。</p>
                </div>
              </section>

              <section class="asset-panel">
                <div class="run-list-header">
                  <strong>{{ resultCollectionFilter ? `批次 #${resultCollectionFilter.id} 的蒸馏结果` : '蒸馏历史' }}</strong>
                  <span>{{ resultCollectionFilter ? `${visibleBloggerRunCount} / ${selectedBloggerRunCount}` : `${selectedBloggerRunCount} 次` }}</span>
                </div>
                <div v-if="resultCollectionFilter" class="filter-bar">
                  <span>已按采集批次筛选</span>
                  <button type="button" @click="showAllBloggerRuns">查看全部</button>
                </div>
                <div class="asset-run-list">
                  <button
                    v-for="run in visibleBloggerRuns"
                    :key="run.id"
                    type="button"
                    :class="{ active: selectedBloggerRunId === run.id, failed: run.status === 'failed' }"
                    @click="selectBloggerRun(run.id)"
                  >
                    <span class="asset-run-row"><strong>{{ formatDate(run.created_at) }}</strong><StatusChip :status="run.status" /></span>
                    <span class="asset-run-meta">批次 #{{ run.collection_run_id || '旧数据' }} · 样本 {{ run.sample_count }}</span>
                    <em v-if="run.status === 'failed'" class="run-error">失败原因：{{ run.error_message || '未记录失败原因' }}</em>
                  </button>
                  <p v-if="!visibleBloggerRuns.length && resultCollectionFilter" class="empty-region">这个采集批次还没有蒸馏结果。</p>
                  <p v-else-if="!visibleBloggerRuns.length" class="empty-region">这个博主还没有蒸馏记录。</p>
                </div>
              </section>
            </div>

            <section v-if="selectedCollectionRun" class="asset-panel">
              <div class="inline-card-header">
                <div>
                  <span>采集样本</span>
                  <h3>批次 #{{ selectedCollectionRun.id }}</h3>
                </div>
                <button v-if="collectionDistillationCount(selectedCollectionRun.id)" type="button" @click="showCollectionResults(selectedCollectionRun.id)">查看对应蒸馏</button>
              </div>
              <div v-if="bloggerPosts.length" class="sample-list asset-samples">
                <div v-for="post in bloggerPosts.slice(0, 8)" :key="post.id">
                  <strong>{{ post.title }}</strong>
                  <span>
                    {{ post.content_type === 'video' ? '视频' : '图文' }} · 收藏 {{ post.favorite_count }} / 点赞 {{ post.like_count }} / {{ bloggerCommentLabel(post) }}
                    <template v-if="post.content_type === 'video'"> / ASR <StatusChip :status="post.asr_status" /></template>
                  </span>
                </div>
              </div>
              <p v-else class="empty-region">这个采集批次还没有可展示样本。</p>
            </section>

            <section v-if="selectedBloggerRun" class="asset-panel">
              <div class="stage-header">
                <div>
                  <span><StatusChip :status="selectedBloggerRun.status" /></span>
                  <h3>蒸馏结果 #{{ selectedBloggerRun.id }}</h3>
                  <p class="distill-result-meta">
                    <span class="status-chip status-chip--neutral">{{ selectedRunMeta.mode === 'B' ? '诊断我的账号' : '拆解对标博主' }}</span>
                    <span v-if="selectedRunMeta.qualityScore !== null" class="status-chip" :class="`status-chip--${qualityTone(selectedRunMeta.qualityGrade)}`">质量自检 {{ selectedRunMeta.qualityScore }} 分 · {{ selectedRunMeta.qualityGrade }}</span>
                    <span v-if="selectedRunMeta.revisions > 0" class="status-chip status-chip--info">已自我修订 {{ selectedRunMeta.revisions }} 次</span>
                  </p>
                </div>
                <div v-if="selectedBloggerRun.status === 'pending_confirmation'" class="actions">
                  <button type="button" class="primary" :disabled="Boolean(pendingAction)" @click="handleConfirmBloggerRun">
                    {{ pendingAction === 'distill-confirm' ? '保存中' : '保存结果' }}
                  </button>
                  <button type="button" :disabled="Boolean(pendingAction)" @click="handleAbandonBloggerRun">
                    {{ pendingAction === 'distill-abandon' ? '放弃中' : '放弃本次蒸馏' }}
                  </button>
                </div>
              </div>
              <div class="workspace-snapshot scoped-snapshot">
                <div><span>样本数量</span><strong>{{ selectedBloggerRun.sample_count }}</strong></div>
              </div>
              <div class="distill-grid compact-result">
                <article class="distill-card">
                  <h3>蒸馏报告</h3>
                  <div v-if="selectedBloggerRun.status === 'failed'" class="failure-panel">
                    <strong>蒸馏失败</strong>
                    <p>{{ selectedBloggerRun.error_message || '这次蒸馏没有记录失败原因，请查看任务日志。' }}</p>
                  </div>
                  <div v-else-if="selectedBloggerRun.report_html" class="distill-report" v-html="sanitizeHtml(selectedBloggerRun.report_html)"></div>
                  <p v-else class="empty-region">这次蒸馏没有生成报告。</p>
                </article>

                <article class="distill-card">
                  <h3>Skill 输出</h3>
                  <textarea
                    v-if="selectedBloggerSkill"
                    :value="selectedBloggerSkill.skill_markdown"
                    readonly
                    rows="18"
                  ></textarea>
                  <p v-else-if="selectedBloggerRun.status === 'failed'" class="empty-region">蒸馏失败后不会生成 Skill。</p>
                  <p v-else class="empty-region">这次蒸馏没有生成 Skill。</p>
                </article>
              </div>
            </section>
            <p v-else class="empty-region result-placeholder">请选择一次蒸馏记录查看报告和 Skill。</p>
          </div>
          <p v-else class="empty-region">请选择一个博主查看资产。</p>
        </div>

      </section>
</template>
