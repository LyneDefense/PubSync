<script setup lang="ts">
// 社媒·博主资产(阶段B)：博主信息 + 笔记池(按类型分组、单篇抽屉) + 勾选存快照。蒸馏在独立「蒸馏」页。
import { ref } from 'vue'
import StatusChip from '../components/StatusChip.vue'
import { bloggerCommentLabel } from '../utils/format'
import {
  activeNotePost,
  benchmarkAccounts,
  bloggerNoteGroups,
  bloggerSnapshots,
  clearPostSelection,
  closeNote,
  currentSocialPlatformName,
  currentSocialTab,
  delistedNoteCount,
  formatDate,
  friendlyTime,
  handleDeleteBlogger,
  handleDeleteSnapshot,
  handleRefreshBlogger,
  handleRenameSnapshot,
  handleSaveSnapshot,
  handleToggleBloggerFavorite,
  isPostSelected,
  isSocialPlatform,
  noteBodyText,
  noteHashtags,
  noteTopComments,
  openCreateBloggerModal,
  openEditBloggerModal,
  openNote,
  pendingAction,
  selectBlogger,
  selectedBlogger,
  selectedBloggerId,
  selectedPostCount,
  selectedPosts,
  setCurrentSocialTab,
  subtypeLabel,
  togglePostSelection
} from '../composables/useWorkspaceStore'

// 存快照弹框：列出已选笔记(可去掉)、命名、保存。
const snapshotModalOpen = ref(false)
const snapshotName = ref('')

function openSnapshotModal() {
  if (!selectedPostCount.value) return
  snapshotName.value = ''
  snapshotModalOpen.value = true
}
async function confirmSaveSnapshot() {
  await handleSaveSnapshot(snapshotName.value)
  snapshotModalOpen.value = false
}
function onRenameSnapshot(id: number, current: string) {
  const name = window.prompt('快照新名称', current)
  if (name && name.trim()) handleRenameSnapshot(id, name)
}
function onDeleteSnapshot(id: number, name: string) {
  if (window.confirm(`确定删除快照「${name}」？此操作不可恢复（不影响笔记本身）。`)) handleDeleteSnapshot(id)
}
</script>

<template>
  <section v-if="isSocialPlatform && currentSocialTab === 'assets'" class="panel">
    <div class="section-header">
      <div>
        <h2>{{ currentSocialPlatformName }}博主资产</h2>
        <p class="toolbar-subtitle">查看博主笔记池（按类型分类、点开看单篇），勾选笔记存成快照，去「蒸馏」页提炼 Skill。</p>
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

        <!-- 快照 -->
        <section class="asset-panel">
          <div class="run-list-header">
            <strong>选材快照</strong>
            <span>{{ bloggerSnapshots.length }} 个</span>
          </div>
          <p class="form-hint">在下面笔记池勾选要参考的笔记，点「存为快照」命名保存；之后到「蒸馏」页选快照提炼 Skill。</p>
          <div v-if="bloggerSnapshots.length" class="snapshot-list">
            <div v-for="snap in bloggerSnapshots" :key="snap.id" class="snapshot-row">
              <div class="snapshot-info">
                <strong>{{ snap.name }}</strong>
                <span>{{ snap.post_count }} 篇 · {{ friendlyTime(snap.created_at) }}</span>
              </div>
              <div class="snapshot-ops">
                <button type="button" @click="setCurrentSocialTab('distill')">去蒸馏</button>
                <button type="button" @click="onRenameSnapshot(snap.id, snap.name)">改名</button>
                <button type="button" class="danger" @click="onDeleteSnapshot(snap.id, snap.name)">删除</button>
              </div>
            </div>
          </div>
          <p v-else class="empty-region">还没有快照。勾选笔记后点「存为快照」。</p>
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
                <label
                  v-for="post in group.posts"
                  :key="post.id"
                  class="note-row"
                  :class="{ selected: isPostSelected(post.id) }"
                >
                  <input type="checkbox" :checked="isPostSelected(post.id)" @change="togglePostSelection(post.id)" />
                  <span class="note-row-main" @click.prevent="openNote(post.id)">
                    <span class="note-title">{{ post.title }}</span>
                    <span class="note-meta">收藏 {{ post.favorite_count }} · 点赞 {{ post.like_count }} · {{ bloggerCommentLabel(post) }}<template v-if="post.content_type === 'video'"> · ASR </template></span>
                  </span>
                  <StatusChip v-if="post.content_type === 'video'" :status="post.asr_status" />
                </label>
              </div>
            </div>
          </div>
          <p v-else class="empty-region">这个博主还没有采集到笔记。请到「数据采集」采集。</p>
        </section>
      </div>
      <p v-else class="empty-region">请选择一个博主查看资产。</p>
    </div>

    <!-- 勾选浮条 -->
    <div v-if="selectedPostCount" class="selection-bar">
      <span>已勾选 <strong>{{ selectedPostCount }}</strong> 篇</span>
      <div class="selection-bar-ops">
        <button type="button" class="primary" @click="openSnapshotModal">存为快照</button>
        <button type="button" @click="clearPostSelection">清空</button>
      </div>
    </div>

    <!-- 存快照弹框 -->
    <div v-if="snapshotModalOpen" class="modal-overlay" @click.self="snapshotModalOpen = false">
      <div class="modal-card snapshot-modal">
        <div class="modal-head">
          <strong>存为快照</strong>
          <button type="button" class="modal-close" @click="snapshotModalOpen = false">✕</button>
        </div>
        <div class="modal-body">
          <label class="modal-field">
            <span>快照名称（可留空，自动按时间命名）</span>
            <input v-model="snapshotName" type="text" maxlength="40" placeholder="如：高赞口播 · 搞钱主题" />
          </label>
          <p class="form-hint">本次包含 {{ selectedPostCount }} 篇（可在下方去掉不要的）：</p>
          <ul class="snapshot-pick-list">
            <li v-for="post in selectedPosts" :key="post.id">
              <span class="snapshot-pick-title">{{ post.title }}</span>
              <button type="button" class="snapshot-pick-remove" @click="togglePostSelection(post.id)">移除</button>
            </li>
          </ul>
        </div>
        <div class="modal-foot">
          <button type="button" @click="snapshotModalOpen = false">取消</button>
          <button type="button" class="primary" :disabled="!selectedPostCount || Boolean(pendingAction)" @click="confirmSaveSnapshot">保存快照</button>
        </div>
      </div>
    </div>

    <!-- 单篇笔记详情：右侧抽屉 -->
    <div v-if="activeNotePost" class="note-drawer-overlay" @click.self="closeNote">
      <aside class="note-drawer">
        <div class="note-drawer-head">
          <strong>笔记详情</strong>
          <button type="button" class="note-drawer-close" @click="closeNote">✕</button>
        </div>
        <div class="note-drawer-body">
          <img v-if="activeNotePost.cover_url" :src="activeNotePost.cover_url" alt="封面" class="note-drawer-cover" referrerpolicy="no-referrer" />
          <h3>{{ activeNotePost.title }}</h3>
          <p class="note-drawer-meta">
            {{ subtypeLabel(activeNotePost.content_subtype) }}
            · 收藏 {{ activeNotePost.favorite_count }} · 点赞 {{ activeNotePost.like_count }} · {{ bloggerCommentLabel(activeNotePost) }}
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
/* 快照列表 */
.snapshot-list { display: flex; flex-direction: column; gap: 6px; }
.snapshot-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 8px 10px;
  border: var(--rule-hair);
  border-radius: var(--radius-sm);
  background: var(--color-paper-2);
}
.snapshot-info { display: flex; flex-direction: column; min-width: 0; }
.snapshot-info span { font-size: 12px; color: var(--color-ink-soft); }
.snapshot-ops { display: flex; gap: 6px; flex-shrink: 0; }
.snapshot-ops button { font-size: 12px; padding: 4px 10px; }

/* 笔记池分组 */
.note-groups { display: flex; flex-direction: column; gap: 18px; }
.note-group-head { display: flex; justify-content: space-between; font-size: 13px; font-weight: 600; margin-bottom: 8px; }
.note-group-head span { color: var(--color-ink-soft); font-weight: 400; }
.note-list { display: flex; flex-direction: column; gap: 6px; }
.note-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border: var(--rule-hair);
  border-radius: var(--radius-sm);
  cursor: pointer;
}
.note-row.selected { border-color: var(--color-accent); background: var(--color-accent-soft); }
.note-row > input[type='checkbox'] { flex: 0 0 auto; margin: 0; }
.note-row-main { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.note-title { font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.note-meta { font-size: 12px; color: var(--color-ink-soft); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.note-row > .status-chip { flex: 0 0 auto; }

/* 勾选浮条 */
.selection-bar {
  position: sticky;
  bottom: 16px;
  margin-top: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 16px;
  border: var(--rule-hair);
  border-radius: var(--radius-md);
  background: var(--color-paper);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.12);
}
.selection-bar-ops { display: flex; gap: 8px; }

/* 通用弹框 */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  z-index: 1100;
  display: flex;
  align-items: center;
  justify-content: center;
}
.modal-card {
  width: min(520px, 92vw);
  max-height: 86vh;
  display: flex;
  flex-direction: column;
  background: var(--color-paper);
  border-radius: var(--radius-md);
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.25);
}
.modal-head, .modal-foot {
  display: flex;
  align-items: center;
  padding: 14px 18px;
}
.modal-head { justify-content: space-between; border-bottom: var(--rule-hair); }
.modal-foot { justify-content: flex-end; gap: 8px; border-top: var(--rule-hair); }
.modal-close { background: none; border: none; font-size: 18px; cursor: pointer; }
.modal-body { padding: 16px 18px; overflow-y: auto; }
.modal-field { display: flex; flex-direction: column; gap: 4px; margin-bottom: 12px; }
.modal-field span { font-size: 13px; }
.snapshot-pick-list { list-style: none; padding: 0; margin: 8px 0 0; display: flex; flex-direction: column; gap: 4px; }
.snapshot-pick-list li { display: flex; align-items: center; gap: 8px; padding: 6px 8px; border: var(--rule-hair); border-radius: var(--radius-sm); }
.snapshot-pick-title { flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; }
.snapshot-pick-remove { flex: 0 0 auto; font-size: 12px; padding: 2px 8px; }

/* 右侧抽屉 */
.note-drawer-overlay { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.35); z-index: 1000; display: flex; justify-content: flex-end; }
.note-drawer { width: min(460px, 92vw); height: 100%; background: var(--color-paper); box-shadow: -8px 0 24px rgba(0, 0, 0, 0.15); display: flex; flex-direction: column; }
.note-drawer-head { display: flex; justify-content: space-between; align-items: center; padding: 14px 18px; border-bottom: var(--rule-hair); }
.note-drawer-close { background: none; border: none; font-size: 18px; cursor: pointer; }
.note-drawer-body { padding: 18px; overflow-y: auto; }
.note-drawer-cover { width: 100%; max-height: 240px; object-fit: cover; border-radius: var(--radius-sm); margin-bottom: 12px; }
.note-drawer-meta { font-size: 12px; color: var(--color-ink-soft); margin: 4px 0; }
.note-drawer-link { font-size: 13px; }
.note-drawer-section { margin-top: 16px; }
.note-drawer-section h4 { margin: 0 0 6px; font-size: 13px; }
.note-drawer-text { white-space: pre-wrap; font-size: 13px; line-height: 1.6; }
.note-comments { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; }
.note-comments li { display: flex; gap: 8px; font-size: 13px; }
.note-comment-like { flex: 0 0 auto; color: #e0496b; }
</style>
