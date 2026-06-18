<script setup lang="ts">
// 社媒·博主资产(阶段B)：博主信息 + 笔记池(只读、按类型、点开抽屉) + 快照(新建/详情/改名/重选/删除)。蒸馏在独立「蒸馏」页。
import { computed, ref } from 'vue'
import { bloggerCommentLabel } from '../utils/format'
import {
  activeNotePost,
  benchmarkAccounts,
  bloggerNoteGroups,
  bloggerPosts,
  bloggerSnapshots,
  clearPostSelection,
  closeNote,
  currentSocialPlatformName,
  currentSocialTab,
  delistedNoteCount,
  DISTILL_MIN_SAMPLES,
  DISTILL_RECOMMEND_SAMPLES,
  formatDate,
  friendlyTime,
  handleDeleteBlogger,
  handleDeleteSnapshot,
  handleRefreshBlogger,
  handleSaveSnapshot,
  handleToggleBloggerFavorite,
  handleUpdateSnapshot,
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
  selectBlogger,
  selectedBlogger,
  selectedBloggerId,
  selectedPostCount,
  selectGroupPosts,
  setCurrentSocialTab,
  subtypeLabel,
  togglePostSelection
} from '../composables/useWorkspaceStore'

// 选取弹框(新建/重选共用)。pickerSnapshotId=null 表示新建。
const pickerOpen = ref(false)
const pickerSnapshotId = ref<number | null>(null)
const pickerName = ref('')
// 快照详情弹框。
const detailOpen = ref(false)
const detailSnapshotId = ref<number | null>(null)
const detailName = ref('')

// 视频转写状态的友好文案(避免把"转写失败"误读成"抓取失败")。
function transcriptLabel(post: { asr_status: string }): string {
  switch (post.asr_status) {
    case 'subtitle': return '字幕稿'
    case 'succeeded': return '已转写'
    case 'pending': return '待转写'
    default: return '无转写'
  }
}
function transcriptTone(post: { asr_status: string }): string {
  if (post.asr_status === 'subtitle' || post.asr_status === 'succeeded') return 'ok'
  if (post.asr_status === 'pending') return 'wait'
  return 'none'
}

const enoughSelected = computed(() => selectedPostCount.value >= DISTILL_MIN_SAMPLES)
const detailSnapshot = computed(() => bloggerSnapshots.value.find((s) => s.id === detailSnapshotId.value) || null)
const detailSnapshotPosts = computed(() => {
  const ids = detailSnapshot.value?.post_ids || []
  return ids.map((id) => bloggerPosts.value.find((p) => p.id === id)).filter((p): p is NonNullable<typeof p> => Boolean(p))
})

function openCreatePicker() {
  clearPostSelection()
  pickerName.value = ''
  pickerSnapshotId.value = null
  pickerOpen.value = true
}
function closePicker() {
  pickerOpen.value = false
  clearPostSelection()
}
async function savePicker() {
  if (!enoughSelected.value) return
  if (pickerSnapshotId.value) {
    await handleUpdateSnapshot(pickerSnapshotId.value, { name: pickerName.value, postIds: [...selectedPostsIds()] })
  } else {
    await handleSaveSnapshot(pickerName.value)
  }
  pickerOpen.value = false
  clearPostSelection()
}
function selectedPostsIds(): number[] {
  // 直接从勾选集取(store 的 selectedPostIds 通过 isPostSelected 暴露);这里重建一份。
  return bloggerPosts.value.filter((p) => isPostSelected(p.id)).map((p) => p.id)
}

function openSnapshotDetail(id: number, name: string) {
  detailSnapshotId.value = id
  detailName.value = name
  detailOpen.value = true
}
function editSnapshotNotes() {
  if (!detailSnapshot.value) return
  loadSnapshotIntoSelection(detailSnapshot.value.id)
  pickerName.value = detailSnapshot.value.name
  pickerSnapshotId.value = detailSnapshot.value.id
  detailOpen.value = false
  pickerOpen.value = true
}
async function saveDetailName() {
  if (!detailSnapshotId.value || !detailName.value.trim()) return
  await handleUpdateSnapshot(detailSnapshotId.value, { name: detailName.value })
}
async function deleteDetailSnapshot() {
  if (!detailSnapshot.value) return
  if (window.confirm(`确定删除快照「${detailSnapshot.value.name}」？不可恢复（不影响笔记本身）。`)) {
    await handleDeleteSnapshot(detailSnapshot.value.id)
    detailOpen.value = false
  }
}
</script>

<template>
  <section v-if="isSocialPlatform && currentSocialTab === 'assets'" class="panel">
    <div class="section-header">
      <div>
        <h2>{{ currentSocialPlatformName }}博主资产</h2>
        <p class="toolbar-subtitle">查看博主笔记池（按类型、点开看单篇），把要参考的笔记存成快照，去「蒸馏」页提炼 Skill。</p>
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
            <button type="button" class="primary slim" @click="openCreatePicker">+ 新建快照</button>
          </div>
          <p class="form-hint">新建快照会弹出笔记列表勾选（需 ≥{{ DISTILL_MIN_SAMPLES }} 篇，建议 ≥{{ DISTILL_RECOMMEND_SAMPLES }} 篇），命名后保存；之后到「蒸馏」页选快照提炼 Skill。</p>
          <div v-if="bloggerSnapshots.length" class="asset-run-list">
            <button
              v-for="snap in bloggerSnapshots"
              :key="snap.id"
              type="button"
              @click="openSnapshotDetail(snap.id, snap.name)"
            >
              <span class="asset-run-row"><strong>{{ snap.name }}</strong></span>
              <span class="asset-run-meta">{{ snap.post_count }} 篇 · {{ friendlyTime(snap.created_at) }} · 点击查看/编辑</span>
            </button>
          </div>
          <p v-else class="empty-region">还没有快照。点「+ 新建快照」勾选笔记保存。</p>
        </section>

        <!-- 笔记池：按类型分组(只读，点开看详情) -->
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
              <div class="asset-run-list">
                <button v-for="post in group.posts" :key="post.id" type="button" @click="openNote(post.id)">
                  <span class="asset-run-row"><strong>{{ post.title }}</strong><span v-if="post.content_type === 'video'" class="asr-tag" :class="`asr-tag--${transcriptTone(post)}`">{{ transcriptLabel(post) }}</span></span>
                  <span class="asset-run-meta">收藏 {{ post.favorite_count }} · 点赞 {{ post.like_count }} · {{ bloggerCommentLabel(post) }}</span>
                </button>
              </div>
            </div>
          </div>
          <p v-else class="empty-region">这个博主还没有采集到笔记。请到「数据采集」采集。</p>
        </section>
      </div>
      <p v-else class="empty-region">请选择一个博主查看资产。</p>
    </div>

    <!-- 选取弹框：新建 / 重选笔记 -->
    <div v-if="pickerOpen" class="modal-overlay" @click.self="closePicker">
      <div class="modal-card picker-modal">
        <div class="modal-head">
          <strong>{{ pickerSnapshotId ? '重新选取笔记' : '新建快照' }}</strong>
          <button type="button" class="modal-close" @click="closePicker">✕</button>
        </div>
        <div class="modal-body">
          <label class="modal-field">
            <span>快照名称（可留空，自动按时间命名）</span>
            <input v-model="pickerName" type="text" maxlength="40" placeholder="如：高赞口播 · 搞钱主题" />
          </label>
          <p class="form-hint">
            勾选要参考的笔记：已选 <strong :class="{ 'hint-warn': !enoughSelected }">{{ selectedPostCount }}</strong> 篇
            （需 ≥{{ DISTILL_MIN_SAMPLES }}，建议 ≥{{ DISTILL_RECOMMEND_SAMPLES }}）
          </p>
          <div class="picker-groups">
            <div v-for="group in bloggerNoteGroups" :key="group.subtype" class="note-group">
              <div class="note-group-head">
                <strong>{{ group.label }}（{{ group.posts.length }}）</strong>
                <button type="button" class="link-button" @click="selectGroupPosts(group.subtype)">全选本组</button>
              </div>
              <label v-for="post in group.posts" :key="post.id" class="picker-row" :class="{ selected: isPostSelected(post.id) }">
                <input type="checkbox" :checked="isPostSelected(post.id)" @change="togglePostSelection(post.id)" />
                <span class="picker-row-main">
                  <span class="picker-row-title">{{ post.title }}</span>
                  <span class="picker-row-meta">收藏 {{ post.favorite_count }} · 点赞 {{ post.like_count }}</span>
                </span>
              </label>
            </div>
            <p v-if="!bloggerNoteGroups.length" class="empty-region">还没有笔记可选。</p>
          </div>
        </div>
        <div class="modal-foot">
          <button type="button" @click="closePicker">取消</button>
          <button type="button" class="primary" :disabled="!enoughSelected || Boolean(pendingAction)" @click="savePicker">
            {{ pickerSnapshotId ? '保存修改' : '保存快照' }}（{{ selectedPostCount }} 篇）
          </button>
        </div>
      </div>
    </div>

    <!-- 快照详情弹框 -->
    <div v-if="detailOpen && detailSnapshot" class="modal-overlay" @click.self="detailOpen = false">
      <div class="modal-card snapshot-detail-modal">
        <div class="modal-head">
          <strong>快照详情</strong>
          <button type="button" class="modal-close" @click="detailOpen = false">✕</button>
        </div>
        <div class="modal-body">
          <label class="modal-field">
            <span>快照名称</span>
            <div class="rename-row">
              <input v-model="detailName" type="text" maxlength="40" />
              <button type="button" :disabled="!detailName.trim() || Boolean(pendingAction)" @click="saveDetailName">保存名称</button>
            </div>
          </label>
          <p class="form-hint">包含 {{ detailSnapshot.post_count }} 篇笔记：</p>
          <ul class="snapshot-pick-list">
            <li v-for="post in detailSnapshotPosts" :key="post.id">
              <span class="snapshot-pick-title">{{ post.title }}</span>
              <span class="snapshot-pick-sub">{{ subtypeLabel(post.content_subtype) }}</span>
            </li>
            <li v-if="!detailSnapshotPosts.length" class="empty-region">所选笔记已不在当前笔记池（可能已下架）。</li>
          </ul>
        </div>
        <div class="modal-foot snapshot-detail-foot">
          <button type="button" class="danger" @click="deleteDetailSnapshot">删除快照</button>
          <span class="foot-spacer"></span>
          <button type="button" @click="setCurrentSocialTab('distill')">去蒸馏</button>
          <button type="button" class="primary" @click="editSnapshotNotes">重新选取笔记</button>
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
.run-list-header .slim { min-height: 30px; padding: 0 12px; font-size: 13px; }
.note-groups { display: flex; flex-direction: column; gap: 18px; }
.note-group-head { display: flex; justify-content: space-between; align-items: center; font-size: 13px; font-weight: 600; margin-bottom: 8px; }
.note-group-head span { color: var(--color-ink-soft); font-weight: 400; }
.asr-tag { flex: 0 0 auto; font-size: 11px; padding: 1px 7px; border-radius: 999px; font-weight: 500; }
.asr-tag--ok { background: var(--color-accent-soft); color: var(--color-accent); }
.asr-tag--wait { background: #f1f1f1; color: #888; }
.asr-tag--none { background: #f1f1f1; color: #aaa; }

/* 弹框通用 */
.modal-overlay { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.35); z-index: 1100; display: flex; align-items: center; justify-content: center; }
.modal-card { width: min(560px, 94vw); max-height: 88vh; display: flex; flex-direction: column; background: var(--color-paper); border-radius: var(--radius-md); box-shadow: 0 16px 48px rgba(0, 0, 0, 0.25); }
.modal-head, .modal-foot { display: flex; align-items: center; padding: 14px 18px; gap: 8px; }
.modal-head { justify-content: space-between; border-bottom: var(--rule-hair); }
.modal-foot { justify-content: flex-end; border-top: var(--rule-hair); }
.snapshot-detail-foot { justify-content: flex-start; }
.foot-spacer { flex: 1 1 auto; }
.modal-close { min-height: 0; background: none; border: none; font-size: 18px; cursor: pointer; padding: 0 4px; }
.modal-body { padding: 16px 18px; overflow-y: auto; }
.modal-field { display: flex; flex-direction: column; gap: 4px; margin-bottom: 12px; }
.modal-field > span { font-size: 13px; }
.rename-row { display: flex; gap: 8px; }
.rename-row input { flex: 1 1 auto; min-width: 0; }
.hint-warn { color: #d9822b; }

/* 选取弹框 */
.picker-groups { display: flex; flex-direction: column; gap: 14px; }
.picker-row { display: flex; align-items: center; gap: 10px; padding: 7px 10px; border: var(--rule-hair); border-radius: var(--radius-sm); cursor: pointer; }
.picker-row + .picker-row { margin-top: 4px; }
.picker-row.selected { border-color: var(--color-accent); background: var(--color-accent-soft); }
/* 全局 input{width:100%} 会把复选框撑满整行,这里强制收回原生尺寸,否则标题/数据被挤成竖排。 */
.picker-row > input[type='checkbox'] { flex: 0 0 auto; width: 18px; height: 18px; margin: 0; padding: 0; accent-color: var(--color-accent); }
.picker-row-main { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.picker-row-title { font-size: 13px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.picker-row-meta { font-size: 12px; color: var(--color-ink-soft); }

/* 快照详情笔记清单 */
.snapshot-pick-list { list-style: none; padding: 0; margin: 8px 0 0; display: flex; flex-direction: column; gap: 4px; }
.snapshot-pick-list li { display: flex; align-items: center; gap: 8px; padding: 6px 8px; border: var(--rule-hair); border-radius: var(--radius-sm); }
.snapshot-pick-title { flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; }
.snapshot-pick-sub { flex: 0 0 auto; font-size: 12px; color: var(--color-ink-soft); }

/* 右侧抽屉 */
.note-drawer-overlay { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.35); z-index: 1000; display: flex; justify-content: flex-end; }
.note-drawer { width: min(460px, 92vw); height: 100%; background: var(--color-paper); box-shadow: -8px 0 24px rgba(0, 0, 0, 0.15); display: flex; flex-direction: column; }
.note-drawer-head { display: flex; justify-content: space-between; align-items: center; padding: 14px 18px; border-bottom: var(--rule-hair); }
.note-drawer-close { min-height: 0; background: none; border: none; font-size: 18px; cursor: pointer; padding: 0 4px; }
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
