<script setup lang="ts">
// 公众号·每日早报：四步向导（选新闻 → 生成文章 → 预览/编辑 → 发布草稿箱）。
// 合并了原「每日早报」的新闻抓取/勾选和原「文章草稿」的生成/预览/编辑/发送。
// 状态与方法来自 useWorkspaceStore 单例；本组件仅负责该面板的视图与交互。
import { sanitizeHtml } from '../utils/sanitize'
import {
  activeArticleTab,
  activeMainTab,
  activeNews,
  activeNewsTab,
  activeWechatTab,
  articleStateLabel,
  changeNewsPage,
  form,
  formatDate,
  goNextWechatBriefStep,
  goPreviousWechatBriefStep,
  groupLabel,
  handleFetchNews,
  handleGenerateArticle,
  handleSaveArticle,
  handleSendWechat,
  handleToggleNews,
  hasArticle,
  hasNewsGroups,
  newsPage,
  newsTotalPages,
  pagedNews,
  pendingAction,
  publicationName,
  setNewsTab,
  taskButtonStyle,
  taskProgress,
  visibleNewsTabs,
  wechatBriefStep,
  wechatBriefStepLabels,
  workspaceTitle
} from '../composables/useWorkspaceStore'
</script>

<template>
  <section v-if="activeMainTab === 'wechat' && activeWechatTab === 'brief'" class="panel">
    <div class="section-header">
      <div>
        <h2>{{ workspaceTitle }}每日早报</h2>
        <p class="toolbar-subtitle">工作区：{{ publicationName }} · 抓取新闻 → 生成文章 → 预览/编辑 → 发布草稿箱</p>
      </div>
    </div>

    <div class="creator-shell">
      <div class="creator-main">
        <ol class="creator-steps" aria-label="步骤进度">
          <li
            v-for="(label, index) in wechatBriefStepLabels"
            :key="label"
            class="creator-steps__item"
            :class="{ current: wechatBriefStep === index + 1, done: wechatBriefStep > index + 1 }"
          >
            <span class="creator-steps__dot">{{ index + 1 }}</span>
            <span class="creator-steps__label">{{ label }}</span>
          </li>
        </ol>

        <section v-if="wechatBriefStep === 1" class="creation-stage-card active">
          <div class="inline-card-header">
            <div><span>01 选新闻</span><h3>抓取并勾选候选新闻</h3></div>
            <button
              type="button"
              class="task-button"
              :class="{ running: pendingAction === 'fetch' }"
              :style="taskButtonStyle('fetch')"
              :disabled="Boolean(pendingAction)"
              @click="handleFetchNews"
            >
              <span>{{ pendingAction === 'fetch' ? `抓取中 ${Math.round(taskProgress.fetch)}%` : '重新抓取' }}</span>
            </button>
          </div>
          <div class="module-subnav">
            <div class="tabs" role="tablist" aria-label="新闻分组">
              <button
                v-for="tab in visibleNewsTabs"
                :key="tab.group_key"
                type="button"
                role="tab"
                :aria-selected="activeNewsTab === tab.group_key"
                :class="{ active: activeNewsTab === tab.group_key }"
                @click="setNewsTab(tab.group_key)"
              >
                {{ tab.name }}
                <span>{{ tab.count }}</span>
              </button>
            </div>
          </div>
          <div v-if="activeNews.length" class="news-list">
            <article v-for="item in pagedNews" :key="item.id" class="news-card">
              <input
                type="checkbox"
                :checked="item.selected"
                :aria-label="`选择 ${item.title}`"
                @change="handleToggleNews(item, ($event.target as HTMLInputElement).checked)"
              />
              <div>
                <h3>{{ item.title }}</h3>
                <div class="meta">
                  <span v-if="hasNewsGroups" class="region-pill">{{ groupLabel(item.group_key) }}</span>
                  {{ item.category }} · {{ item.source }} · {{ formatDate(item.published_at) }}
                </div>
                <p>{{ item.summary }}</p>
                <a :href="item.url" target="_blank" rel="noreferrer">查看来源</a>
              </div>
              <div class="score">{{ item.importance_score }}</div>
            </article>
            <div class="pagination">
              <button type="button" :disabled="newsPage <= 1" @click="changeNewsPage(-1)">上一页</button>
              <span>第 {{ newsPage }} / {{ newsTotalPages }} 页</span>
              <button type="button" :disabled="newsPage >= newsTotalPages" @click="changeNewsPage(1)">下一页</button>
            </div>
          </div>
          <p v-else class="empty-region">当前分类还没有候选新闻。点「重新抓取」获取最新候选。</p>
        </section>

        <section v-if="wechatBriefStep === 2" class="creation-stage-card active">
          <div class="inline-card-header">
            <div><span>02 生成文章</span><h3>基于已勾选新闻生成文章</h3></div>
            <button
              type="button"
              class="task-button primary"
              :class="{ running: pendingAction === 'generate' }"
              :style="taskButtonStyle('generate')"
              :disabled="Boolean(pendingAction)"
              @click="handleGenerateArticle"
            >
              <span>{{ pendingAction === 'generate' ? `生成中 ${Math.round(taskProgress.generate)}%` : '生成文章' }}</span>
            </button>
          </div>
          <p class="form-hint">当前文章状态：{{ articleStateLabel }}。生成完成后会自动进入「预览/编辑」。</p>
        </section>

        <section v-if="wechatBriefStep === 3" class="creation-stage-card active">
          <div class="inline-card-header">
            <div><span>03 预览/编辑</span><h3>检查并完善文章</h3></div>
          </div>
          <div class="module-subnav">
            <div class="tabs" role="tablist" aria-label="文章草稿">
              <button type="button" role="tab" :aria-selected="activeArticleTab === 'preview'" :class="{ active: activeArticleTab === 'preview' }" @click="activeArticleTab = 'preview'">预览</button>
              <button type="button" role="tab" :aria-selected="activeArticleTab === 'edit'" :class="{ active: activeArticleTab === 'edit' }" @click="activeArticleTab = 'edit'">编辑</button>
            </div>
          </div>
          <form v-if="activeArticleTab === 'edit'" class="article-form" @submit.prevent="handleSaveArticle">
            <label>标题<input v-model="form.title" type="text" :disabled="!hasArticle" /></label>
            <label>导语<textarea v-model="form.intro" rows="4" :disabled="!hasArticle"></textarea></label>
            <label>封面图 URL<input v-model="form.cover_image_url" type="url" :disabled="!hasArticle" /></label>
            <label>正文 HTML<textarea v-model="form.content_html" rows="16" :disabled="!hasArticle"></textarea></label>
            <button type="submit" :disabled="!hasArticle || Boolean(pendingAction)">{{ pendingAction === 'save' ? '保存中' : '保存修改' }}</button>
          </form>
          <article v-else class="preview-panel">
            <img v-if="form.cover_image_url" class="cover" :src="form.cover_image_url" alt="文章封面预览" />
            <h3>{{ form.title || '尚未生成文章' }}</h3>
            <p class="intro-preview">{{ form.intro }}</p>
            <div v-if="form.content_html" class="article-preview" v-html="sanitizeHtml(form.content_html)"></div>
            <div v-else class="article-preview"><p>生成文章后，这里会显示公众号图文预览。</p></div>
          </article>
        </section>

        <section v-if="wechatBriefStep === 4" class="creation-stage-card active">
          <div class="inline-card-header">
            <div><span>04 发布草稿箱</span><h3>推送到公众号草稿箱</h3></div>
            <button type="button" class="primary" :disabled="!hasArticle || Boolean(pendingAction)" @click="handleSendWechat">
              {{ pendingAction === 'wechat' ? '发送中' : '发送草稿箱' }}
            </button>
          </div>
          <p class="form-hint">当前文章状态：{{ articleStateLabel }}。确认无误后推送到公众号草稿箱。</p>
          <article class="preview-panel">
            <img v-if="form.cover_image_url" class="cover" :src="form.cover_image_url" alt="文章封面预览" />
            <h3>{{ form.title || '尚未生成文章' }}</h3>
            <p class="intro-preview">{{ form.intro }}</p>
          </article>
        </section>

        <div class="creator-nav">
          <button v-if="wechatBriefStep > 1" type="button" @click="goPreviousWechatBriefStep">← 上一步</button>
          <button v-if="wechatBriefStep < 4" type="button" class="creator-nav__next primary" @click="goNextWechatBriefStep">下一步 →</button>
        </div>
      </div>
    </div>
  </section>
</template>
