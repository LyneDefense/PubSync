<script setup lang="ts">
// 社媒·博主资产:主从工作台 —— 左博主列表 + 右(HERO / 选材快照 / 笔记池) + 三浮层(选取 picker / 快照详情 / 笔记抽屉)。
// 纯展示重构:所有状态/方法沿用 useWorkspaceStore,蒸馏仍在独立「蒸馏」页。
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { bloggerCommentLabel } from '../utils/format'
import TIcon from '../components/TIcon.vue'
import {
  activeNotePost,
  benchmarkAccounts,
  bloggerNoteGroups,
  bloggerPosts,
  bloggerSnapshots,
  clearPostSelection,
  closeNote,
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

// 「加对标」去「找对标博主」页。
const route = useRoute()
const router = useRouter()
function goFind() {
  const platform = route.params.platform as string
  if (platform) router.push({ name: 'workspace', params: { platform, tab: 'find' } })
}

// 选取弹框(新建/重选共用)。pickerSnapshotId=null 表示新建。
const pickerOpen = ref(false)
const pickerSnapshotId = ref<number | null>(null)
const pickerName = ref('')
// 快照详情弹框。
const detailOpen = ref(false)
const detailSnapshotId = ref<number | null>(null)
const detailName = ref('')

// 文字头像 + 笔记组类型图标。
const AVATAR_BG = ['#eaf3ee', '#f0eef7', '#eef4f5', '#eef1f6', '#f6eef2', '#eef3f7']
const AVATAR_INK = ['#2f6b54', '#5a4a86', '#3a6a72', '#44506a', '#8a4a64', '#3a5a86']
function avatarStyle(id: number) {
  const i = (((id || 0) % AVATAR_BG.length) + AVATAR_BG.length) % AVATAR_BG.length
  return { background: AVATAR_BG[i], color: AVATAR_INK[i] }
}
function groupIcon(label: string): { ch: string; cls: string } {
  if (label.includes('口播') || label.includes('视频')) return { ch: '▶', cls: 'ico-oral' }
  if (label.includes('测评') || label.includes('评测')) return { ch: '⚖', cls: 'ico-review' }
  return { ch: '▦', cls: 'ico-image' }
}

// 视频转写状态的友好文案。
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
  <section v-if="isSocialPlatform && currentSocialTab === 'assets'" class="assets">
    <div class="assets-top">
      <button type="button" class="ghost-btn" @click="goFind">去找对标博主 →</button>
    </div>

    <div class="md-grid">
      <!-- 左:博主列表 -->
      <aside class="bl-card" aria-label="博主列表">
        <div class="bl-head">
          <strong>博主</strong>
          <span class="count">{{ benchmarkAccounts.length }} 个</span>
        </div>
        <div v-if="benchmarkAccounts.length" class="bl-list">
          <button
            v-for="b in benchmarkAccounts"
            :key="b.id"
            type="button"
            class="bl-row"
            :class="{ sel: selectedBloggerId === b.id }"
            @click="selectBlogger(b.id)"
          >
            <span class="bl-avatar" :style="avatarStyle(b.id)">
              {{ (b.display_name || '?').slice(0, 1) }}
              <span v-if="b.is_favorite" class="bl-star">⭐</span>
            </span>
            <span class="bl-body">
              <span class="bl-name">{{ b.display_name }}</span>
              <span class="bl-sub">{{ b.is_favorite ? '已标记 · ' : '' }}{{ b.niche || '未设置领域' }} · 样本 {{ b.sample_count }}</span>
            </span>
          </button>
        </div>
        <p v-else class="empty-region pad">还没有对标博主。点上方「去找对标博主」添加。</p>
      </aside>

      <!-- 右:详情 -->
      <div v-if="selectedBlogger" class="detail">
        <!-- HERO -->
        <section class="card hero">
          <span class="hero-avatar" :style="avatarStyle(selectedBlogger.id)">{{ (selectedBlogger.display_name || '?').slice(0, 1) }}</span>
          <div class="hero-info">
            <span v-if="selectedBlogger.is_favorite" class="fav-badge">⭐ 已标记博主</span>
            <h3>{{ selectedBlogger.display_name }}</h3>
            <p class="hero-meta">
              粉丝 {{ selectedBlogger.follower_count.toLocaleString() }} · 笔记总数 {{ selectedBlogger.note_total ?? '—' }} · 已采集 {{ selectedBlogger.sample_count }} 条
            </p>
            <p class="hero-desc">{{ selectedBlogger.description || selectedBlogger.niche || '暂无备注' }}</p>
            <div v-if="selectedBlogger.tags?.length" class="tag-chips">
              <span
                v-for="tag in selectedBlogger.tags"
                :key="tag.name"
                class="tag-chip"
                :class="tag.source === 'manual' ? 'tag-chip--manual' : 'tag-chip--auto'"
              >{{ tag.name }}</span>
            </div>
          </div>
          <div class="hero-actions">
            <button type="button" class="ha-btn" :class="{ on: selectedBlogger.is_favorite }" @click="handleToggleBloggerFavorite(selectedBlogger)">
              {{ selectedBlogger.is_favorite ? '取消标记' : '⭐ 标记博主' }}
            </button>
            <button type="button" class="ha-btn" @click="openEditBloggerModal(selectedBlogger)">编辑信息</button>
            <button type="button" class="ha-btn" :disabled="Boolean(pendingAction)" @click="handleRefreshBlogger(selectedBlogger)">
              {{ pendingAction === 'blogger-refresh' ? '刷新中…' : '↻ 刷新' }}
            </button>
            <button type="button" class="ha-del" @click="handleDeleteBlogger(selectedBlogger)">删除博主</button>
          </div>
        </section>

        <!-- 选材快照 -->
        <section class="card">
          <div class="card-head">
            <div class="ch-l"><h3>选材快照</h3><span class="ch-count">{{ bloggerSnapshots.length }} 个</span></div>
            <button type="button" class="primary slim" @click="openCreatePicker">+ 新建快照</button>
          </div>
          <p class="card-hint">选取博主笔记（需 ≥ {{ DISTILL_MIN_SAMPLES }} 篇，建议 ≥ {{ DISTILL_RECOMMEND_SAMPLES }} 篇），存成快照，方便蒸馏</p>
          <div v-if="bloggerSnapshots.length" class="snap-grid">
            <button
              v-for="snap in bloggerSnapshots"
              :key="snap.id"
              type="button"
              class="snap-card"
              @click="openSnapshotDetail(snap.id, snap.name)"
            >
              <span class="snap-ico"><TIcon name="folder" /></span>
              <span class="snap-body">
                <span class="snap-name">{{ snap.name }}</span>
                <span class="snap-meta">{{ snap.post_count }} 篇 · {{ friendlyTime(snap.created_at) }} · 点击查看/编辑</span>
              </span>
            </button>
          </div>
          <p v-else class="empty-region pad">还没有快照。点「+ 新建快照」勾选笔记保存。</p>
        </section>

        <!-- 笔记池 -->
        <section class="card">
          <div class="card-head">
            <div class="ch-l">
              <h3>笔记池</h3>
              <span class="ch-count">按类型 · {{ selectedBlogger.sample_count }} 条<template v-if="delistedNoteCount"> · {{ delistedNoteCount }} 已下架</template></span>
            </div>
          </div>
          <div v-if="bloggerNoteGroups.length" class="note-groups">
            <div v-for="group in bloggerNoteGroups" :key="group.subtype" class="note-group">
              <div class="ng-head">
                <span class="ng-ico" :class="groupIcon(group.label).cls">{{ groupIcon(group.label).ch }}</span>
                <strong>{{ group.label }}</strong>
                <span class="ng-count">{{ group.posts.length }} 篇</span>
              </div>
              <div class="note-rows">
                <button v-for="post in group.posts" :key="post.id" type="button" class="note-row" @click="openNote(post.id)">
                  <span class="nr-main">
                    <span class="nr-title">
                      {{ post.title || '(无标题)' }}
                      <span v-if="post.content_type === 'video' && transcriptTone(post) !== 'none'" class="asr-pill" :class="`asr-pill--${transcriptTone(post)}`">{{ transcriptLabel(post) }}</span>
                      <span v-if="post.status === 'delisted'" class="delisted">已下架</span>
                    </span>
                    <span class="nr-meta">收藏 {{ post.favorite_count }} · 点赞 {{ post.like_count }} · {{ bloggerCommentLabel(post) }}</span>
                  </span>
                  <span class="nr-chevron">›</span>
                </button>
              </div>
            </div>
          </div>
          <p v-else class="empty-region pad">这个博主还没有采集到笔记。请到「数据采集」采集。</p>
        </section>
      </div>
      <div v-else class="empty-region card pad detail-empty">请选择一个博主查看资产。</div>
    </div>

    <!-- 选取弹框:新建 / 重选笔记 -->
    <div v-if="pickerOpen" class="modal-overlay" @click.self="closePicker">
      <div class="modal-card picker-modal">
        <div class="modal-head">
          <strong>{{ pickerSnapshotId ? '重新选取笔记' : '新建快照' }}</strong>
          <button type="button" class="modal-close" aria-label="关闭" @click="closePicker"><TIcon name="x" /></button>
        </div>
        <div class="modal-body">
          <label class="modal-field">
            <span>快照名称 <em>(可留空,自动按时间命名)</em></span>
            <input v-model="pickerName" type="text" maxlength="40" placeholder="如:高赞口播 · 确定性主题" />
          </label>
          <p class="modal-count">
            勾选要参考的笔记:已选 <strong :class="{ warn: !enoughSelected }">{{ selectedPostCount }}</strong> 篇
            <em>(需 ≥ {{ DISTILL_MIN_SAMPLES }},建议 ≥ {{ DISTILL_RECOMMEND_SAMPLES }})</em>
          </p>
          <div class="picker-groups">
            <div v-for="group in bloggerNoteGroups" :key="group.subtype" class="picker-group">
              <div class="pg-head">
                <strong>{{ group.label }}（{{ group.posts.length }}）</strong>
                <button type="button" class="link-button" @click="selectGroupPosts(group.subtype)">全选本组</button>
              </div>
              <label v-for="post in group.posts" :key="post.id" class="picker-row" :class="{ selected: isPostSelected(post.id) }">
                <input type="checkbox" :checked="isPostSelected(post.id)" @change="togglePostSelection(post.id)" />
                <span class="pr-box" aria-hidden="true"></span>
                <span class="pr-main">
                  <span class="pr-title">{{ post.title || '(无标题)' }}</span>
                  <span class="pr-meta">收藏 {{ post.favorite_count }} · 点赞 {{ post.like_count }}</span>
                </span>
              </label>
            </div>
            <p v-if="!bloggerNoteGroups.length" class="empty-region">还没有笔记可选。</p>
          </div>
        </div>
        <div class="modal-foot">
          <button type="button" class="ghost-btn" @click="closePicker">取消</button>
          <button type="button" class="primary" :disabled="!enoughSelected || Boolean(pendingAction)" @click="savePicker">
            {{ pickerSnapshotId ? '保存修改' : '保存快照' }}（{{ selectedPostCount }} 篇）
          </button>
        </div>
      </div>
    </div>

    <!-- 快照详情弹框 -->
    <div v-if="detailOpen && detailSnapshot" class="modal-overlay" @click.self="detailOpen = false">
      <div class="modal-card">
        <div class="modal-head">
          <strong>快照详情</strong>
          <button type="button" class="modal-close" aria-label="关闭" @click="detailOpen = false"><TIcon name="x" /></button>
        </div>
        <div class="modal-body">
          <label class="modal-field">
            <span>快照名称</span>
            <div class="rename-row">
              <input v-model="detailName" type="text" maxlength="40" />
              <button type="button" class="ghost-btn" :disabled="!detailName.trim() || Boolean(pendingAction)" @click="saveDetailName">保存名称</button>
            </div>
          </label>
          <p class="modal-count">包含 {{ detailSnapshot.post_count }} 篇笔记:</p>
          <ul class="snapshot-pick-list">
            <li v-for="post in detailSnapshotPosts" :key="post.id">
              <span class="spl-title">{{ post.title || '(无标题)' }}</span>
              <span class="spl-sub">{{ subtypeLabel(post.content_subtype) }}</span>
            </li>
            <li v-if="!detailSnapshotPosts.length" class="empty-region">所选笔记已不在当前笔记池（可能已下架）。</li>
          </ul>
        </div>
        <div class="modal-foot snapshot-detail-foot">
          <button type="button" class="ha-del" @click="deleteDetailSnapshot">删除快照</button>
          <span class="foot-spacer"></span>
          <button type="button" class="ghost-btn" @click="setCurrentSocialTab('distill')">去蒸馏</button>
          <button type="button" class="primary" @click="editSnapshotNotes">重新选取笔记</button>
        </div>
      </div>
    </div>

    <!-- 单篇笔记详情:右侧抽屉 -->
    <div v-if="activeNotePost" class="drawer-overlay" @click.self="closeNote">
      <aside class="drawer">
        <div class="drawer-head">
          <strong>笔记详情</strong>
          <button type="button" class="modal-close" aria-label="关闭" @click="closeNote"><TIcon name="x" /></button>
        </div>
        <div class="drawer-body">
          <img v-if="activeNotePost.cover_url" :src="activeNotePost.cover_url" alt="封面" class="drawer-cover" referrerpolicy="no-referrer" />
          <div v-else class="drawer-cover placeholder"></div>
          <h3 class="drawer-title">{{ activeNotePost.title || '(无标题)' }}</h3>
          <p class="drawer-meta">
            {{ subtypeLabel(activeNotePost.content_subtype) }} · 收藏 {{ activeNotePost.favorite_count }} · 点赞 {{ activeNotePost.like_count }} · {{ bloggerCommentLabel(activeNotePost) }}<template v-if="activeNotePost.published_at"> · {{ formatDate(activeNotePost.published_at) }}</template>
          </p>
          <a v-if="activeNotePost.url" :href="activeNotePost.url" target="_blank" rel="noopener noreferrer" class="drawer-link">打开原帖 <TIcon name="external-link" /></a>

          <div class="drawer-section">
            <h4>{{ activeNotePost.transcript_text ? '口播逐字稿' : '正文' }}</h4>
            <p v-if="noteBodyText(activeNotePost)" class="drawer-text">{{ noteBodyText(activeNotePost) }}</p>
            <p v-else class="empty-region">这篇笔记没有可展示的文字内容。</p>
          </div>

          <div v-if="noteHashtags(activeNotePost).length" class="drawer-section">
            <h4>话题标签</h4>
            <div class="tag-chips">
              <span v-for="tag in noteHashtags(activeNotePost)" :key="tag" class="tag-chip tag-chip--auto">#{{ tag }}</span>
            </div>
          </div>

          <div v-if="noteTopComments(activeNotePost).length" class="drawer-section">
            <h4>热门评论 TOP{{ noteTopComments(activeNotePost).length }}</h4>
            <ul class="drawer-comments">
              <li v-for="(c, i) in noteTopComments(activeNotePost)" :key="i">
                <span class="dc-like"><TIcon name="heart" /> {{ c.like_count }}</span>
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
.assets {
  max-width: 1080px;
  margin: 0 auto;
}
.assets-top {
  margin-bottom: 16px;
}
.ghost-btn {
  height: 38px;
  padding: 0 16px;
  background: var(--color-surface);
  border: 1px solid var(--color-field-border);
  border-radius: 10px;
  font-size: 13.5px;
  font-weight: 550;
  color: var(--color-ink-2);
  cursor: pointer;
  transition: background 140ms var(--ease-out);
}
.ghost-btn:hover {
  background: #f7f8f9;
}
.ghost-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.md-grid {
  display: grid;
  grid-template-columns: 248px minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}
.card {
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-lg);
}

/* 左栏博主列表 */
.bl-card {
  position: sticky;
  top: 0;
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-lg);
  overflow: hidden;
}
.bl-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--color-paper-3);
}
.bl-head strong {
  font-size: 14px;
  font-weight: 650;
}
.count {
  padding: 1px 9px;
  border-radius: var(--radius-pill);
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
  font-size: 12px;
  font-weight: 700;
}
.bl-list {
  display: flex;
  flex-direction: column;
  padding: 8px;
  gap: 2px;
}
.bl-row {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 9px 10px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  cursor: pointer;
  text-align: left;
  transition: background 120ms var(--ease-out);
}
.bl-row:hover {
  background: #fafbfc;
}
.bl-row.sel {
  background: var(--color-accent-soft);
}
.bl-avatar {
  position: relative;
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  flex: 0 0 auto;
}
.bl-star {
  position: absolute;
  top: -5px;
  right: -5px;
  font-size: 11px;
}
.bl-body {
  flex: 1;
  min-width: 0;
}
.bl-name {
  display: block;
  font-size: 13.5px;
  font-weight: 620;
  color: var(--color-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.bl-row.sel .bl-name {
  color: var(--color-accent-ink);
}
.bl-sub {
  display: block;
  margin-top: 2px;
  font-size: 11.5px;
  color: var(--color-ink-3);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 右栏 */
.detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.detail-empty {
  text-align: center;
  padding: 48px 24px;
}

/* HERO */
.hero {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  flex-wrap: wrap;
  padding: 20px 22px;
}
.hero-avatar {
  display: grid;
  place-items: center;
  width: 60px;
  height: 60px;
  border-radius: 14px;
  font-size: 24px;
  font-weight: 600;
  flex: 0 0 auto;
}
.hero-info {
  flex: 1 1 240px;
  min-width: 180px;
}
.fav-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  background: var(--color-score-warn-bg);
  color: var(--color-warn);
  font-size: 12px;
  font-weight: 650;
  margin-bottom: 6px;
}
.hero-info h3 {
  margin: 0 0 6px;
  font-size: 19px;
  font-weight: 680;
}
.hero-meta {
  margin: 0 0 8px;
  font-size: 12.5px;
  color: var(--color-ink-3);
  font-variant-numeric: tabular-nums;
}
.hero-desc {
  margin: 0 0 10px;
  font-size: 13.5px;
  line-height: 1.6;
  color: var(--color-ink-2);
}
.hero-actions {
  flex: 0 0 auto;
  display: flex;
  flex-wrap: wrap;
  align-content: flex-start;
  gap: 8px;
}
.ha-btn {
  height: 34px;
  padding: 0 13px;
  border: 1px solid var(--color-field-border);
  border-radius: 9px;
  background: var(--color-surface);
  color: var(--color-ink-2);
  font-size: 13px;
  font-weight: 550;
  white-space: nowrap;
  cursor: pointer;
  transition: background 140ms var(--ease-out), border-color 140ms var(--ease-out);
}
.ha-btn:hover {
  background: #f7f8f9;
}
.ha-btn.on {
  border-color: var(--color-accent-soft-bd);
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
}
.ha-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
/* 删除:弱化的危险动作。平时无边框,hover 才显出红底红框,与上面三个按钮同高同圆角成组。 */
.ha-del {
  height: 34px;
  padding: 0 13px;
  border: 1px solid transparent;
  border-radius: 9px;
  background: transparent;
  color: var(--color-danger);
  font-size: 13px;
  font-weight: 550;
  white-space: nowrap;
  cursor: pointer;
  transition: background 140ms var(--ease-out), border-color 140ms var(--ease-out);
}
.ha-del:hover {
  background: var(--color-score-danger-bg);
  border-color: var(--color-score-danger-bd);
}

/* 卡片头 + 提示 */
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 22px 0;
}
.ch-l {
  display: flex;
  align-items: baseline;
  gap: 9px;
}
.ch-l h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 650;
}
.ch-count {
  font-size: 12.5px;
  color: var(--color-ink-3);
}
.card-hint {
  margin: 6px 22px 0;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--color-ink-3);
}
.primary.slim {
  height: 32px;
  padding: 0 14px;
  font-size: 13px;
  border-radius: 9px;
}

/* 快照网格 */
.snap-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 10px;
  padding: 14px 22px 20px;
}
.snap-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 13px 15px;
  border: 1px solid var(--color-rule);
  border-radius: 12px;
  background: var(--color-surface);
  cursor: pointer;
  text-align: left;
  transition: border-color 120ms var(--ease-out), box-shadow 120ms var(--ease-out);
}
.snap-card:hover {
  border-color: var(--color-accent-soft-bd);
  box-shadow: 0 2px 8px var(--color-shadow);
}
.snap-ico {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: var(--color-accent-soft);
  color: var(--color-accent);
  flex: 0 0 auto;
}
.snap-body {
  min-width: 0;
}
.snap-name {
  display: block;
  font-size: 14px;
  font-weight: 620;
  color: var(--color-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.snap-meta {
  display: block;
  margin-top: 3px;
  font-size: 11.5px;
  color: var(--color-ink-3);
}

/* 笔记池 */
.note-groups {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 14px 22px 20px;
}
.ng-head {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 8px;
}
.ng-ico {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border-radius: 8px;
  font-size: 13px;
  flex: 0 0 auto;
}
.ico-oral {
  background: #fdeee9;
  color: #bd5b34;
}
.ico-image {
  background: var(--color-accent-soft);
  color: #2f6b54;
}
.ico-review {
  background: #eef1f6;
  color: #44506a;
}
.ng-head strong {
  font-size: 13.5px;
  font-weight: 650;
}
.ng-count {
  font-size: 12px;
  color: var(--color-ink-3);
}
.note-rows {
  display: flex;
  flex-direction: column;
}
.note-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 12px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  cursor: pointer;
  text-align: left;
  transition: background 120ms var(--ease-out);
}
.note-row:hover {
  background: #fafbfc;
}
.nr-main {
  flex: 1;
  min-width: 0;
}
.nr-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--color-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.asr-pill {
  flex: 0 0 auto;
  font-size: 11px;
  padding: 1px 8px;
  border-radius: var(--radius-pill);
  font-weight: 500;
}
.asr-pill--ok {
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
}
.asr-pill--wait {
  background: #f1f2f4;
  color: var(--color-ink-3);
}
.delisted {
  flex: 0 0 auto;
  font-size: 11px;
  padding: 1px 8px;
  border-radius: var(--radius-pill);
  background: #fbeae8;
  color: var(--color-danger);
  font-weight: 500;
}
.nr-meta {
  display: block;
  margin-top: 3px;
  font-size: 12px;
  color: var(--color-ink-3);
  font-variant-numeric: tabular-nums;
}
.nr-chevron {
  flex: 0 0 auto;
  color: var(--color-ink-3);
  font-size: 18px;
}
.empty-region.pad {
  padding: 24px 22px;
}

/* —— 弹框 —— */
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1100;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(20, 24, 28, 0.4);
}
.modal-card {
  width: min(560px, 94vw);
  max-height: 86vh;
  display: flex;
  flex-direction: column;
  background: var(--color-surface);
  border-radius: 16px;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.25);
}
.modal-head,
.modal-foot {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 18px;
}
.modal-head {
  justify-content: space-between;
  border-bottom: 1px solid var(--color-paper-3);
}
.modal-head strong {
  font-size: 15px;
  font-weight: 650;
}
.modal-foot {
  justify-content: flex-end;
  border-top: 1px solid var(--color-paper-3);
}
.snapshot-detail-foot {
  justify-content: flex-start;
}
.foot-spacer {
  flex: 1;
}
.modal-close {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: 50%;
  background: var(--color-paper-3);
  color: var(--color-ink-2);
  cursor: pointer;
}
.modal-close:hover {
  background: var(--color-rule-strong);
}
.modal-body {
  padding: 16px 18px;
  overflow-y: auto;
}
.modal-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 14px;
}
.modal-field > span {
  font-size: 13px;
  font-weight: 600;
}
.modal-field em {
  color: var(--color-placeholder);
  font-weight: 400;
  font-style: normal;
}
.modal-field input {
  height: 40px;
  padding: 0 12px;
  border: 1px solid var(--color-field-border);
  border-radius: 10px;
  font-size: 14px;
}
.rename-row {
  display: flex;
  gap: 8px;
}
.rename-row input {
  flex: 1;
  min-width: 0;
}
.modal-count {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--color-ink-2);
}
.modal-count strong {
  font-variant-numeric: tabular-nums;
}
.modal-count strong.warn {
  color: var(--color-warn);
}
.modal-count em {
  color: var(--color-ink-3);
  font-style: normal;
}

/* picker 分组 + 勾选行 */
.picker-groups {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.pg-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
}
.link-button {
  border: 0;
  background: none;
  color: var(--color-accent);
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
}
.picker-row {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 9px 11px;
  border: 1px solid var(--color-rule);
  border-radius: 10px;
  cursor: pointer;
  transition: border-color 110ms var(--ease-out), background 110ms var(--ease-out);
}
.picker-row + .picker-row {
  margin-top: 6px;
}
.picker-row.selected {
  border-color: var(--color-accent);
  background: var(--color-accent-tint);
}
/* 隐藏原生 checkbox,用自定义方框 */
.picker-row > input[type='checkbox'] {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}
.pr-box {
  flex: 0 0 auto;
  width: 18px;
  height: 18px;
  border: 1.5px solid var(--color-rule-strong);
  border-radius: 5px;
  display: grid;
  place-items: center;
  transition: background 110ms var(--ease-out), border-color 110ms var(--ease-out);
}
.picker-row.selected .pr-box {
  border-color: var(--color-accent);
  background: var(--color-accent);
}
.picker-row.selected .pr-box::after {
  content: '✓';
  color: #fff;
  font-size: 12px;
  font-weight: 800;
}
.pr-main {
  flex: 1;
  min-width: 0;
}
.pr-title {
  display: block;
  font-size: 13.5px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pr-meta {
  display: block;
  margin-top: 2px;
  font-size: 12px;
  color: var(--color-ink-3);
}

/* 快照详情笔记清单 */
.snapshot-pick-list {
  list-style: none;
  padding: 0;
  margin: 8px 0 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.snapshot-pick-list li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid var(--color-rule);
  border-radius: 9px;
}
.spl-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}
.spl-sub {
  flex: 0 0 auto;
  font-size: 12px;
  color: var(--color-ink-3);
}

/* —— 右侧抽屉 —— */
.drawer-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  justify-content: flex-end;
  background: rgba(20, 24, 28, 0.4);
  animation: fade 180ms var(--ease-out);
}
.drawer {
  width: min(460px, 92vw);
  height: 100%;
  background: var(--color-surface);
  box-shadow: -8px 0 24px rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  animation: slide-in 220ms var(--ease-out);
}
@keyframes fade {
  from { opacity: 0; }
}
@keyframes slide-in {
  from { transform: translateX(24px); opacity: 0.6; }
}
@media (prefers-reduced-motion: reduce) {
  .drawer-overlay,
  .drawer {
    animation: none;
  }
}
.drawer-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  border-bottom: 1px solid var(--color-paper-3);
}
.drawer-head strong {
  font-size: 15px;
  font-weight: 650;
}
.drawer-body {
  padding: 18px;
  overflow-y: auto;
}
.drawer-cover {
  width: 100%;
  max-height: 240px;
  object-fit: cover;
  border-radius: 12px;
  margin-bottom: 12px;
}
.drawer-cover.placeholder {
  height: 140px;
  background: linear-gradient(135deg, var(--color-paper-3), var(--color-accent-soft));
}
.drawer-title {
  margin: 0 0 6px;
  font-size: 16px;
  font-weight: 650;
}
.drawer-meta {
  margin: 0 0 10px;
  font-size: 12px;
  color: var(--color-ink-3);
  font-variant-numeric: tabular-nums;
}
.drawer-link {
  font-size: 13px;
  color: var(--color-accent);
  font-weight: 600;
}
.drawer-section {
  margin-top: 18px;
}
.drawer-section h4 {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 650;
}
.drawer-text {
  white-space: pre-wrap;
  font-size: 13px;
  line-height: 1.7;
  color: var(--color-ink-2);
}
.drawer-comments {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.drawer-comments li {
  display: flex;
  gap: 8px;
  font-size: 13px;
  line-height: 1.5;
}
.dc-like {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  color: #e0496b;
  font-variant-numeric: tabular-nums;
}

@media (max-width: 900px) {
  .md-grid {
    grid-template-columns: 1fr;
  }
  .bl-card {
    position: static;
  }
}
</style>
