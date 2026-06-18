<script setup lang="ts">
// 社媒·博主资产(阶段B 改版)：博主信息 + 笔记池(按类型分组、单篇抽屉) + 自动/自定义蒸馏 + 快照 + 蒸馏历史。
import { computed, ref } from 'vue'
import { sanitizeHtml } from '../utils/sanitize'
import StatusChip from '../components/StatusChip.vue'
import { bloggerCommentLabel } from '../utils/format'
import {
  activeNotePost,
  benchmarkAccounts,
  bloggerNoteGroups,
  bloggerRuns,
  bloggerSnapshots,
  clearPostSelection,
  closeNote,
  currentSocialPlatformName,
  currentSocialTab,
  delistedNoteCount,
  distillRunMeta,
  distillRunOrdinal,
  DISTILL_MIN_SAMPLES,
  DISTILL_RECOMMEND_SAMPLES,
  formatDate,
  friendlyTime,
  handleAbandonBloggerRun,
  handleAutoDistill,
  handleConfirmBloggerRun,
  handleCustomDistill,
  handleDeleteBlogger,
  handleDeleteSnapshot,
  handleDistillFromSnapshot,
  handleRefreshBlogger,
  handleRenameSnapshot,
  handleSaveSnapshot,
  handleToggleBloggerFavorite,
  isPostSelected,
  isSocialPlatform,
  loadSnapshotIntoSelection,
  noteBodyText,
  noteHashtags,
  noteTopComments,
  openCreateBloggerModal,
  openEditBloggerModal,
  openNote,
  pendingAction,
  qualityTone,
  selectBloggerRun,
  selectedBlogger,
  selectedBloggerId,
  selectedBloggerRun,
  selectedBloggerRunCount,
  selectedBloggerRunId,
  selectedBloggerSkill,
  selectedPostCount,
  selectBlogger,
  subtypeLabel,
  taskProgress,
  togglePostSelection
} from '../composables/useWorkspaceStore'

// 本次选材命名(自定义蒸馏 / 存快照共用，可留空)。
const selectionName = ref('')
const distilling = computed(() => pendingAction.value === 'distill')

const selectedRunMeta = computed(() => distillRunMeta(selectedBloggerRun.value))
const selectedSkillScope = computed(() => {
  try {
    const scope = JSON.parse(selectedBloggerSkill.value?.scope_json || '["__all__"]')
    const items = (Array.isArray(scope) ? scope : []).filter((s: string) => s && s !== '__all__')
    return items.length ? items.map((s: string) => subtypeLabel(s)).join(' + ') : '通用（全部模态）'
  } catch {
    return '通用（全部模态）'
  }
})

function onCustomDistill() {
  handleCustomDistill(selectionName.value)
}
function onSaveSnapshot() {
  handleSaveSnapshot(selectionName.value)
}
function onRenameSnapshot(id: number, current: string) {
  const name = window.prompt('快照新名称', current)
  if (name && name.trim()) handleRenameSnapshot(id, name)
}
function onDeleteSnapshot(id: number, name: string) {
  if (window.confirm(`确定删除快照「${name}」？此操作不可恢复（不影响笔记本身）。`)) handleDeleteSnapshot(id)
}
function noteCover(post: { cover_url: string }) {
  return post.cover_url || ''
}
</script>

<template>
  <section v-if="isSocialPlatform && currentSocialTab === 'assets'" class="panel">
    <div class="section-header">
      <div>
        <h2>{{ currentSocialPlatformName }}博主资产</h2>
        <p class="toolbar-subtitle">查看博主笔记池（按类型分类、点开看单篇），一键自动蒸馏或自定义选材蒸馏。</p>
      </div>
      <button type="button" class="primary" @click="openCreateBloggerModal">创建博主</button>
    </div>

    <div class="xhs-assets-browser">
      <aside class="asset-sidebar" aria-label="博主列表">
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
        <p v-if="!benchmarkAccounts.length" class="empty-region">还没有对标博主。点右上角「创建博主」添加。</p>
      </aside>

      <div v-if="selectedBlogger" class="asset-detail">
        <div class="asset-hero">
          <div>
            <span>{{ selectedBlogger.is_favorite ? '已标记博主' : '博主资产' }}</span>
            <h3>{{ selectedBlogger.display_name }}</h3>
            <p class="asset-meta-line">
              粉丝 {{ selectedBlogger.follower_count.toLocaleString() }}
              · 笔记总数 {{ selectedBlogger.note_total ?? '—' }}
              · 已采集 {{ selectedBlogger.sample_count }} 条
            </p>
            <p>{{ selectedBlogger.description || selectedBlogger.niche || '暂无备注' }}</p>
            <div v-if="selectedBlogger.tags?.length" class="tag-chips">
              <span
                v-for="tag in selectedBlogger.tags"
                :key="tag.name"
                class="tag-chip"
                :class="tag.source === 'manual' ? 'tag-chip--manual' : 'tag-chip--auto'"
              >{{ tag.name }}</span>
            </div>
          </div>
          <div class="asset-actions">
            <button type="button" @click="handleToggleBloggerFavorite(selectedBlogger)">
              {{ selectedBlogger.is_favorite ? '取消标记' : '标记博主' }}
            </button>
            <button type="button" @click="openEditBloggerModal(selectedBlogger)">编辑信息</button>
            <button type="button" :disabled="Boolean(pendingAction)" @click="handleRefreshBlogger(selectedBlogger)">
              {{ pendingAction === 'blogger-refresh' ? '刷新中…' : '刷新博主' }}
            </button>
            <button type="button" class="danger" @click="handleDeleteBlogger(selectedBlogger)">删除博主</button>
          </div>
        </div>

        <div class="workspace-snapshot scoped-snapshot">
          <div><span>笔记池</span><strong>{{ selectedBlogger.sample_count }}</strong></div>
          <div><span>蒸馏记录</span><strong>{{ selectedBloggerRunCount }}</strong></div>
          <div><span>最近蒸馏</span><strong>{{ selectedBlogger.last_distilled_at ? formatDate(selectedBlogger.last_distilled_at) : '暂无' }}</strong></div>
        </div>

        <!-- 蒸馏区 -->
        <section class="asset-panel distill-zone">
          <div class="run-list-header">
            <strong>蒸馏</strong>
            <span>已勾选 {{ selectedPostCount }} 篇</span>
          </div>
          <div class="distill-actions">
            <button
              type="button"
              class="primary"
              :disabled="distilling"
              @click="handleAutoDistill"
            >{{ distilling ? `蒸馏中 ${Math.round(taskProgress.distill)}%` : '自动蒸馏（高赞优先）' }}</button>
            <span class="distill-hint">系统自动取赞藏最高的若干篇，一键生成通用 Skill，不占用你的勾选。</span>
          </div>
          <div class="distill-custom">
            <p class="form-hint">
              自定义蒸馏：在下方笔记池勾选要参考的笔记（需 ≥{{ DISTILL_MIN_SAMPLES }} 篇，建议 ≥{{ DISTILL_RECOMMEND_SAMPLES }} 篇，越多越准）。
              <span :class="{ 'hint-warn': selectedPostCount > 0 && selectedPostCount < DISTILL_MIN_SAMPLES }">当前 {{ selectedPostCount }} 篇</span>
            </p>
            <div class="distill-custom-row">
              <input v-model="selectionName" type="text" maxlength="40" placeholder="给本次选材起个名（可选，自动存为快照）" />
              <button type="button" class="primary" :disabled="distilling || selectedPostCount < DISTILL_MIN_SAMPLES" @click="onCustomDistill">用选中的蒸馏</button>
              <button type="button" :disabled="Boolean(pendingAction) || !selectedPostCount" @click="onSaveSnapshot">存为快照</button>
              <button type="button" :disabled="!selectedPostCount" @click="clearPostSelection">清空勾选</button>
            </div>
          </div>
          <div v-if="bloggerSnapshots.length" class="snapshot-list">
            <div class="run-list-header"><strong>快照</strong><span>{{ bloggerSnapshots.length }} 个</span></div>
            <div v-for="snap in bloggerSnapshots" :key="snap.id" class="snapshot-row">
              <div class="snapshot-info">
                <strong>{{ snap.name }}</strong>
                <span>{{ snap.post_count }} 篇 · {{ friendlyTime(snap.created_at) }}</span>
              </div>
              <div class="snapshot-ops">
                <button type="button" :disabled="distilling" @click="handleDistillFromSnapshot(snap.id)">用此快照蒸馏</button>
                <button type="button" @click="loadSnapshotIntoSelection(snap.id)">载入勾选</button>
                <button type="button" @click="onRenameSnapshot(snap.id, snap.name)">改名</button>
                <button type="button" class="danger" @click="onDeleteSnapshot(snap.id, snap.name)">删除</button>
              </div>
            </div>
          </div>
        </section>

        <!-- 笔记池：按类型分组 -->
        <section class="asset-panel">
          <div class="run-list-header">
            <strong>笔记池（按类型）</strong>
            <span>{{ selectedBlogger.sample_count }} 条<template v-if="delistedNoteCount"> · {{ delistedNoteCount }} 已下架</template></span>
          </div>
          <div v-if="bloggerNoteGroups.length" class="note-groups">
            <div v-for="group in bloggerNoteGroups" :key="group.subtype" class="note-group">
              <div class="note-group-head">
                <strong>{{ group.label }}</strong>
                <span>{{ group.posts.length }} 篇</span>
              </div>
              <div class="note-list">
                <div
                  v-for="post in group.posts"
                  :key="post.id"
                  class="note-row"
                  :class="{ selected: isPostSelected(post.id) }"
                >
                  <input type="checkbox" :checked="isPostSelected(post.id)" @change="togglePostSelection(post.id)" />
                  <button type="button" class="note-open" @click="openNote(post.id)">
                    <span class="note-title">{{ post.title }}</span>
                    <span class="note-meta">收藏 {{ post.favorite_count }} / 点赞 {{ post.like_count }} / {{ bloggerCommentLabel(post) }}
                      <template v-if="post.content_type === 'video'"> · ASR <StatusChip :status="post.asr_status" /></template>
                    </span>
                  </button>
                </div>
              </div>
            </div>
          </div>
          <p v-else class="empty-region">这个博主还没有采集到笔记。请到「数据采集」采集。</p>
        </section>

        <!-- 蒸馏历史(按时间) -->
        <section class="asset-panel">
          <div class="run-list-header">
            <strong>蒸馏历史</strong>
            <span>{{ selectedBloggerRunCount }} 次</span>
          </div>
          <div class="asset-run-list">
            <button
              v-for="run in bloggerRuns"
              :key="run.id"
              type="button"
              :class="{ active: selectedBloggerRunId === run.id, failed: run.status === 'failed' }"
              @click="selectBloggerRun(run.id)"
            >
              <span class="asset-run-row"><strong>第 {{ distillRunOrdinal(run.id) }} 次蒸馏</strong><StatusChip :status="run.status" /></span>
              <span class="asset-run-meta">{{ friendlyTime(run.created_at) }} · 样本 {{ run.sample_count }}</span>
              <em v-if="run.status === 'failed'" class="run-error">失败原因：{{ run.error_message || '未记录失败原因' }}</em>
            </button>
            <p v-if="!bloggerRuns.length" class="empty-region">这个博主还没有蒸馏记录。上面点「自动蒸馏」或勾选后「自定义蒸馏」。</p>
          </div>
        </section>

        <!-- 选中蒸馏的报告 / Skill -->
        <section v-if="selectedBloggerRun" class="asset-panel">
          <div class="stage-header">
            <div>
              <span><StatusChip :status="selectedBloggerRun.status" /></span>
              <h3>第 {{ distillRunOrdinal(selectedBloggerRun.id) }} 次蒸馏</h3>
              <p class="distill-result-meta">
                <span class="status-chip status-chip--neutral">{{ selectedRunMeta.mode === 'B' ? '诊断我的账号' : '拆解对标博主' }}</span>
                <span v-if="selectedBloggerSkill" class="status-chip status-chip--info">适用：{{ selectedSkillScope }}</span>
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
              <textarea v-if="selectedBloggerSkill" :value="selectedBloggerSkill.skill_markdown" readonly rows="18"></textarea>
              <p v-else-if="selectedBloggerRun.status === 'failed'" class="empty-region">蒸馏失败后不会生成 Skill。</p>
              <p v-else class="empty-region">这次蒸馏没有生成 Skill。</p>
            </article>
          </div>
        </section>
      </div>
      <p v-else class="empty-region">请选择一个博主查看资产。</p>
    </div>

    <!-- 单篇笔记详情：右侧抽屉 -->
    <div v-if="activeNotePost" class="note-drawer-overlay" @click.self="closeNote">
      <aside class="note-drawer">
        <div class="note-drawer-head">
          <strong>笔记详情</strong>
          <button type="button" class="note-drawer-close" @click="closeNote">✕</button>
        </div>
        <div class="note-drawer-body">
          <img v-if="noteCover(activeNotePost)" :src="noteCover(activeNotePost)" alt="封面" class="note-drawer-cover" referrerpolicy="no-referrer" />
          <h3>{{ activeNotePost.title }}</h3>
          <p class="note-drawer-meta">
            {{ subtypeLabel(activeNotePost.content_subtype) }}
            · 收藏 {{ activeNotePost.favorite_count }} / 点赞 {{ activeNotePost.like_count }} / {{ bloggerCommentLabel(activeNotePost) }}
            <template v-if="activeNotePost.published_at"> · {{ formatDate(activeNotePost.published_at) }}</template>
          </p>
          <a v-if="activeNotePost.url" :href="activeNotePost.url" target="_blank" rel="noopener noreferrer" class="note-drawer-link">打开原帖 ↗</a>

          <div class="note-drawer-section">
            <h4>{{ activeNotePost.transcript_text ? '口播逐字稿' : '正文' }}</h4>
            <p v-if="noteBodyText(activeNotePost)" class="note-drawer-text">{{ noteBodyText(activeNotePost) }}</p>
            <p v-else class="empty-region">这篇笔记没有可展示的文字内容。</p>
          </div>

          <div v-if="noteHashtags(activeNotePost).length" class="note-drawer-section">
            <h4>话题标签</h4>
            <div class="tag-chips">
              <span v-for="tag in noteHashtags(activeNotePost)" :key="tag" class="tag-chip tag-chip--auto">#{{ tag }}</span>
            </div>
          </div>

          <div v-if="noteTopComments(activeNotePost).length" class="note-drawer-section">
            <h4>热门评论 TOP{{ noteTopComments(activeNotePost).length }}</h4>
            <ul class="note-comments">
              <li v-for="(c, i) in noteTopComments(activeNotePost)" :key="i">
                <span class="note-comment-like">♥ {{ c.like_count }}</span>
                <span>{{ c.content }}</span>
              </li>
            </ul>
          </div>
        </div>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.distill-zone .distill-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.distill-hint {
  font-size: 12px;
  color: var(--text-muted, #888);
}
.distill-custom-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  margin-top: 6px;
}
.distill-custom-row input {
  flex: 1 1 220px;
  min-width: 180px;
}
.hint-warn {
  color: #d9822b;
  font-weight: 600;
}
.snapshot-list {
  margin-top: 14px;
  border-top: 1px solid var(--border, #eee);
  padding-top: 10px;
}
.snapshot-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 6px 0;
  flex-wrap: wrap;
}
.snapshot-info {
  display: flex;
  flex-direction: column;
}
.snapshot-info span {
  font-size: 12px;
  color: var(--text-muted, #888);
}
.snapshot-ops {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.snapshot-ops button {
  font-size: 12px;
  padding: 4px 8px;
}
.note-groups {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.note-group-head {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 6px;
}
.note-group-head span {
  color: var(--text-muted, #888);
  font-weight: 400;
}
.note-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.note-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 8px;
  border: 1px solid transparent;
}
.note-row.selected {
  background: var(--accent-soft, #eef4ff);
  border-color: var(--accent, #4b7bec);
}
.note-row input[type='checkbox'] {
  flex: 0 0 auto;
}
.note-open {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  text-align: left;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
}
.note-title {
  font-weight: 500;
}
.note-meta {
  font-size: 12px;
  color: var(--text-muted, #888);
}
.note-drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  z-index: 1000;
  display: flex;
  justify-content: flex-end;
}
.note-drawer {
  width: min(460px, 92vw);
  height: 100%;
  background: var(--surface, #fff);
  box-shadow: -8px 0 24px rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
}
.note-drawer-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border, #eee);
}
.note-drawer-close {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
}
.note-drawer-body {
  padding: 18px;
  overflow-y: auto;
}
.note-drawer-cover {
  width: 100%;
  max-height: 240px;
  object-fit: cover;
  border-radius: 10px;
  margin-bottom: 12px;
}
.note-drawer-meta {
  font-size: 12px;
  color: var(--text-muted, #888);
  margin: 4px 0;
}
.note-drawer-link {
  font-size: 13px;
}
.note-drawer-section {
  margin-top: 16px;
}
.note-drawer-section h4 {
  margin: 0 0 6px;
  font-size: 13px;
}
.note-drawer-text {
  white-space: pre-wrap;
  font-size: 13px;
  line-height: 1.6;
}
.note-comments {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.note-comments li {
  display: flex;
  gap: 8px;
  font-size: 13px;
}
.note-comment-like {
  flex: 0 0 auto;
  color: #e0496b;
}
</style>
