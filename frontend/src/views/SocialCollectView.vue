<script setup lang="ts">
// 社媒·数据采集：选择博主、配置并执行小红书/抖音样本采集。
// 状态与方法来自 useWorkspaceStore 单例；本组件仅负责该面板的视图与交互。
import { onMounted } from 'vue'
import StatusChip from '../components/StatusChip.vue'
import {
  article,
  bloggerCollectEstimate,
  bloggerCollectionRuns,
  bloggerDistillForm,
  bloggers,
  currentSocialPlatformName,
  currentSocialTab,
  form,
  formatDate,
  goNextXhsCollectStep,
  goPreviousXhsCollectStep,
  handleCollectBlogger,
  isSocialPlatform,
  openCreateBloggerModal,
  pendingAction,
  refreshCollectEstimate,
  selectBlogger,
  selectCollectionRun,
  selectedBlogger,
  selectedBloggerId,
  selectedCollectionRunId,
  setCurrentSocialTab,
  taskButtonStyle,
  taskProgress,
  xhsCollectStep,
  xhsCollectStepLabels
} from '../composables/useWorkspaceStore'

// 进入采集面板时拉一次成本预估；样本/评论数改变时再刷新。
onMounted(refreshCollectEstimate)
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
              <div v-if="bloggers.length" class="blogger-list compact">
                <button v-for="blogger in bloggers" :key="blogger.id" type="button" :class="{ active: selectedBloggerId === blogger.id }" @click="selectBlogger(blogger.id)">
                  <strong>{{ blogger.display_name }}</strong>
                  <span>{{ blogger.niche || '未设置领域' }} · 样本 {{ blogger.sample_count }} · {{ blogger.last_distilled_at ? formatDate(blogger.last_distilled_at) : '未蒸馏' }}</span>
                </button>
              </div>
              <p v-else class="empty-region">还没有博主档案。点击“创建博主”添加小红书主页。</p>
            </section>

            <section v-if="xhsCollectStep === 2" class="creation-stage-card active">
              <div class="inline-card-header"><div><span>02 配置采集</span><h3>设置样本和评论范围</h3></div></div>
              <div class="config-grid">
                <label>采样笔记数<input v-model.number="bloggerDistillForm.sample_limit" type="number" min="5" max="200" @change="refreshCollectEstimate" /></label>
                <label>每条评论数<input v-model.number="bloggerDistillForm.comments_per_post" type="number" min="0" max="100" @change="refreshCollectEstimate" /></label>
              </div>
              <p v-if="bloggerCollectEstimate" class="collect-estimate">
                预计 TikHub 请求约 <strong>{{ bloggerCollectEstimate.request_estimate }}</strong> 次，
                预计费用 <strong>${{ bloggerCollectEstimate.cost_usd.toFixed(3) }}</strong>
                （区间 ${{ bloggerCollectEstimate.cost_usd_min.toFixed(3) }} - ${{ bloggerCollectEstimate.cost_usd_max.toFixed(3) }}）。实际以采集结果为准。
              </p>
              <label class="asr-callout">
                <input v-model="bloggerDistillForm.asr_enabled" type="checkbox" />
                <span><strong>启用视频字幕/ASR 分析</strong><small>采集视频笔记时优先提取字幕；没有字幕时尝试转写音频。</small></span>
              </label>
              <p class="form-hint">这些配置只影响本次采集批次，后续可基于不同批次分别蒸馏。</p>
            </section>

            <section v-if="xhsCollectStep === 3" class="creation-stage-card active">
              <div class="inline-card-header">
                <div><span>03 执行采集</span><h3>提交后台采集任务</h3></div>
                <button type="button" class="task-button primary" :class="{ running: pendingAction === 'collect' }" :style="taskButtonStyle('collect')" :disabled="!selectedBloggerId || Boolean(pendingAction)" @click="handleCollectBlogger">
                  <span>{{ pendingAction === 'collect' ? `采集中 ${Math.round(taskProgress.collect)}%` : '开始采集' }}</span>
                </button>
              </div>
              <p class="form-hint">采集耗时取决于样本数量、评论数量和视频 ASR 开关。</p>
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
