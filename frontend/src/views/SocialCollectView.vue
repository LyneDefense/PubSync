<script setup lang="ts">
// 社媒·数据采集：选择博主、配置并执行小红书/抖音样本采集。
// 状态与方法来自 useWorkspaceStore 单例；本组件仅负责该面板的视图与交互。
import StatusChip from '../components/StatusChip.vue'
import {
  article,
  benchmarkAccounts,
  bloggerCollectionRuns,
  bloggerDistillForm,
  collectContentTypes,
  collectFetchAll,
  collectLatestMessage,
  collectOrder,
  collectProgress,
  collectTimeline,
  currentSocialPlatformName,
  currentSocialTab,
  form,
  formatDate,
  goNextXhsCollectStep,
  goPreviousXhsCollectStep,
  handleCollectBlogger,
  handleCollectByUrls,
  isSocialPlatform,
  lastCollectSummary,
  openCreateBloggerModal,
  pendingAction,
  subtypeLabel,
  selectBlogger,
  selectCollectionRun,
  selectedBlogger,
  selectedBloggerId,
  selectedCollectionRunId,
  setCurrentSocialTab,
  taskButtonStyle,
  taskProgress,
  urlCollectInput,
  xhsCollectStep,
  xhsCollectStepLabels
} from '../composables/useWorkspaceStore'

function toggleContentType(value: string) {
  const index = collectContentTypes.value.indexOf(value)
  if (index >= 0) collectContentTypes.value.splice(index, 1)
  else collectContentTypes.value.push(value)
}
</script>

<template>
      <section v-if="isSocialPlatform && currentSocialTab === 'collect'" class="panel">
        <div class="section-header">
          <div>
            <h2>{{ currentSocialPlatformName }}数据采集</h2>
            <p class="toolbar-subtitle">先选择博主，再配置采样数量、评论数量和 ASR；采集结果会进入博主资产。</p>
          </div>
        </div>
        <div class="creator-shell">
          <div class="creator-main">
            <ol class="creator-steps" aria-label="步骤进度">
              <li
                v-for="(label, index) in xhsCollectStepLabels"
                :key="label"
                class="creator-steps__item"
                :class="{ current: xhsCollectStep === index + 1, done: xhsCollectStep > index + 1 }"
              >
                <span class="creator-steps__dot">{{ index + 1 }}</span>
                <span class="creator-steps__label">{{ label }}</span>
              </li>
            </ol>

            <section v-if="xhsCollectStep === 1" class="creation-stage-card active">
              <div class="inline-card-header">
                <div><span>01 选择博主</span><h3>选择要采集的博主</h3></div>
                <button type="button" class="primary" @click="openCreateBloggerModal">创建博主</button>
              </div>
              <div v-if="benchmarkAccounts.length" class="blogger-list compact">
                <button v-for="blogger in benchmarkAccounts" :key="blogger.id" type="button" :class="{ active: selectedBloggerId === blogger.id }" @click="selectBlogger(blogger.id)">
                  <strong>{{ blogger.display_name }}</strong>
                  <span>{{ blogger.niche || '未设置领域' }} · 样本 {{ blogger.sample_count }} · {{ blogger.last_distilled_at ? formatDate(blogger.last_distilled_at) : '未蒸馏' }}</span>
                </button>
              </div>
              <p v-else class="empty-region">还没有对标博主档案。点击“创建博主”添加对标主页。</p>
            </section>

            <section v-if="xhsCollectStep === 2" class="creation-stage-card active">
              <div class="inline-card-header"><div><span>02 配置采集</span><h3>设置样本和评论范围</h3></div></div>
              <div class="config-grid">
                <label>采样笔记数<input v-model.number="bloggerDistillForm.sample_limit" type="number" min="5" max="200" /></label>
                <label>每条评论数<input v-model.number="bloggerDistillForm.comments_per_post" type="number" min="0" max="100" /></label>
              </div>
              <div class="subtype-picker">
                <p class="form-hint">拉取范围（不勾选视频可省去视频详情与 ASR 开销）：</p>
                <div class="subtype-options">
                  <label class="subtype-option">
                    <input type="checkbox" :checked="collectContentTypes.includes('image')" @change="toggleContentType('image')" /> 图文
                  </label>
                  <label class="subtype-option">
                    <input type="checkbox" :checked="collectContentTypes.includes('video')" @change="toggleContentType('video')" /> 视频
                  </label>
                </div>
              </div>
              <div class="subtype-picker">
                <p class="form-hint">选材排序：</p>
                <div class="seg-group">
                  <button type="button" class="seg-option" :class="{ active: collectOrder === 'top_liked' }" @click="collectOrder = 'top_liked'">高赞优先</button>
                  <button type="button" class="seg-option" :class="{ active: collectOrder === 'latest' }" @click="collectOrder = 'latest'">最新优先</button>
                </div>
              </div>
              <div class="subtype-picker">
                <p class="form-hint">采集数量：</p>
                <div class="seg-group">
                  <button type="button" class="seg-option" :class="{ active: !collectFetchAll }" @click="collectFetchAll = false">{{ bloggerDistillForm.sample_limit }} 条</button>
                  <button type="button" class="seg-option" :class="{ active: collectFetchAll }" @click="collectFetchAll = true">全部</button>
                </div>
              </div>
              <label class="asr-callout">
                <input v-model="bloggerDistillForm.asr_enabled" type="checkbox" />
                <span><strong>启用视频字幕/ASR 分析</strong><small>采集视频笔记时优先提取字幕；没有字幕时尝试转写音频。</small></span>
              </label>
              <p class="form-hint">这些配置只影响本次采集批次，后续可基于不同批次分别蒸馏。</p>
            </section>

            <section v-if="xhsCollectStep === 3" class="creation-stage-card active">
              <div class="inline-card-header">
                <div><span>03 执行采集</span><h3>提交后台采集任务</h3></div>
                <button type="button" class="task-button primary" :class="{ running: pendingAction === 'collect' }" :style="taskButtonStyle('collect')" :disabled="!selectedBloggerId || Boolean(pendingAction)" :title="!selectedBloggerId ? '请先在第 1 步选择或创建博主' : ''" @click="handleCollectBlogger">
                  <span>{{ pendingAction === 'collect' ? `采集中 ${Math.round(taskProgress.collect)}%` : '开始采集' }}</span>
                </button>
              </div>
              <p v-if="!selectedBloggerId" class="form-hint">还没选择博主——请回到第 1 步「选择博主」选择或创建一个博主。</p>
              <p class="form-hint">采集耗时取决于样本数量、评论数量和视频 ASR 开关。重复采集只补新笔记、刷新老笔记，不会重复扣费。</p>
              <details class="url-collect">
                <summary>采不到想要的笔记？粘贴链接定向采集</summary>
                <p class="form-hint">打开小红书 → 进入该笔记 →「分享」→「复制链接」→ 粘到下面（一行一个）；链接需带 <code>xsec_token</code>（复制分享链接即可），短链会自动展开。逐条结果见下方进度。</p>
                <textarea
                  v-model="urlCollectInput"
                  rows="4"
                  placeholder="https://www.xiaohongshu.com/explore/xxxx?xsec_token=...&#10;一行一个，最多 20 条"
                ></textarea>
                <button type="button" :disabled="!selectedBloggerId || Boolean(pendingAction)" @click="handleCollectByUrls">
                  {{ pendingAction === 'collect' ? '采集中…' : '定向采集' }}
                </button>
              </details>

              <div v-if="pendingAction === 'collect' || collectTimeline.length" class="collect-live">
                <div v-if="collectProgress.total" class="collect-progress">
                  <div class="collect-progress__head"><span>正在采集</span><strong>{{ collectProgress.current }}/{{ collectProgress.total }}</strong></div>
                  <div class="collect-progress__bar"><i :style="{ width: collectProgress.pct + '%' }"></i></div>
                  <p v-if="collectLatestMessage" class="form-hint">{{ collectLatestMessage }}</p>
                </div>
                <ol class="collect-timeline">
                  <li v-for="(event, index) in collectTimeline" :key="index" :class="`is-${event.status}`">
                    <span class="collect-timeline__step">{{ event.step_name }}</span>
                    <StatusChip :status="event.status" />
                    <span class="collect-timeline__msg">{{ event.message }}</span>
                  </li>
                </ol>
              </div>
            </section>

            <section v-if="xhsCollectStep === 4" class="creation-stage-card active">
              <div class="inline-card-header">
                <div><span>04 查看结果</span><h3>采集批次和样本预览</h3></div>
                <button type="button" @click="setCurrentSocialTab('assets')">查看博主资产</button>
              </div>
              <div v-if="selectedBlogger" class="stage-result-grid">
                <article class="stage-metric"><span>当前博主</span><strong>{{ selectedBlogger.display_name }}</strong></article>
                <article class="stage-metric"><span>采集批次</span><strong>{{ bloggerCollectionRuns.length }}</strong></article>
              </div>
              <div v-if="lastCollectSummary" class="collect-summary">
                <div class="collect-summary__row">
                  <strong>本批 {{ lastCollectSummary.postCount }} 条</strong>
                  <span v-if="lastCollectSummary.newCount !== null">新增 {{ lastCollectSummary.newCount }}</span>
                  <span v-if="lastCollectSummary.refreshedCount !== null">刷新 {{ lastCollectSummary.refreshedCount }}</span>
                  <span v-if="lastCollectSummary.delistedCount">已下架 {{ lastCollectSummary.delistedCount }}</span>
                  <span>爆款 {{ lastCollectSummary.hotCount }}</span>
                  <span>评论 {{ lastCollectSummary.commentCount }}</span>
                </div>
                <div v-if="Object.keys(lastCollectSummary.subtypeCounts).length" class="tag-chips">
                  <span v-for="(count, key) in lastCollectSummary.subtypeCounts" :key="key" class="tag-chip tag-chip--auto">{{ subtypeLabel(key) }} {{ count }}</span>
                </div>
              </div>
              <div v-if="selectedBlogger" class="run-list collection-list">
                <div class="run-list-header"><strong>采集历史</strong><span>{{ bloggerCollectionRuns.length }} 次</span></div>
                <button v-for="run in bloggerCollectionRuns" :key="run.id" type="button" :class="{ active: selectedCollectionRunId === run.id }" @click="selectCollectionRun(run.id)">
                  <strong>#{{ run.id }} · {{ formatDate(run.created_at) }}</strong>
                  <span><StatusChip :status="run.status" /> 样本 {{ run.post_count }} · 评论 {{ run.comment_count }} · ASR {{ run.asr_enabled ? '开启' : '关闭' }}</span>
                </button>
              </div>
              <p v-if="!selectedBlogger" class="empty-region">请先选择博主。</p>
            </section>
            <div class="creator-nav">
              <button v-if="xhsCollectStep > 1" type="button" @click="goPreviousXhsCollectStep">← 上一步</button>
              <button v-if="xhsCollectStep < 4" type="button" class="creator-nav__next primary" @click="goNextXhsCollectStep">下一步 →</button>
            </div>
          </div>
        </div>
      </section>
</template>
