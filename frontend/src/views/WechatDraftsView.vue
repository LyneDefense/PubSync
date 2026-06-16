<script setup lang="ts">
// 公众号·文章草稿：标题/导语/封面/正文编辑与发送到公众号草稿箱。
// 状态与方法来自 useWorkspaceStore 单例；本组件仅负责该面板的视图与交互。
import { sanitizeHtml } from '../utils/sanitize'
import {
  activeArticleTab,
  activeMainTab,
  activeWechatTab,
  article,
  articleStateLabel,
  form,
  handleGenerateArticle,
  handleSaveArticle,
  handleSendWechat,
  hasArticle,
  pendingAction,
  taskButtonStyle,
  taskProgress
} from '../composables/useWorkspaceStore'
</script>

<template>
      <section v-if="activeMainTab === 'wechat' && activeWechatTab === 'drafts'" class="panel">
        <div class="section-header">
          <div>
            <h2>公众号文章</h2>
            <p class="toolbar-subtitle">当前文章状态：{{ articleStateLabel }}</p>
          </div>
          <div class="actions">
            <button
              type="button"
              class="task-button"
              :class="{ running: pendingAction === 'generate' }"
              :style="taskButtonStyle('generate')"
              :disabled="Boolean(pendingAction)"
              @click="handleGenerateArticle"
            >
              <span>{{ pendingAction === 'generate' ? `生成中 ${Math.round(taskProgress.generate)}%` : '生成文章' }}</span>
            </button>
            <button type="button" class="primary" :disabled="!hasArticle || Boolean(pendingAction)" @click="handleSendWechat">
              {{ pendingAction === 'wechat' ? '发送中' : '发送草稿箱' }}
            </button>
          </div>
        </div>
        <div class="module-subnav">
          <div class="tabs" role="tablist" aria-label="文章草稿">
            <button
              type="button"
              role="tab"
              :aria-selected="activeArticleTab === 'preview'"
              :class="{ active: activeArticleTab === 'preview' }"
              @click="activeArticleTab = 'preview'"
            >
              预览
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeArticleTab === 'edit'"
              :class="{ active: activeArticleTab === 'edit' }"
              @click="activeArticleTab = 'edit'"
            >
              编辑
            </button>
          </div>
        </div>

        <form v-if="activeArticleTab === 'edit'" class="article-form" @submit.prevent="handleSaveArticle">
          <label>
            标题
            <input v-model="form.title" type="text" :disabled="!hasArticle" />
          </label>
          <label>
            导语
            <textarea v-model="form.intro" rows="4" :disabled="!hasArticle"></textarea>
          </label>
          <label>
            封面图 URL
            <input v-model="form.cover_image_url" type="url" :disabled="!hasArticle" />
          </label>
          <label>
            正文 HTML
            <textarea v-model="form.content_html" rows="16" :disabled="!hasArticle"></textarea>
          </label>
          <button type="submit" :disabled="!hasArticle || Boolean(pendingAction)">
            {{ pendingAction === 'save' ? '保存中' : '保存修改' }}
          </button>
        </form>

        <article v-else class="preview-panel">
          <img v-if="form.cover_image_url" class="cover" :src="form.cover_image_url" alt="文章封面预览" />
          <h3>{{ form.title || '尚未生成文章' }}</h3>
          <p class="intro-preview">{{ form.intro }}</p>
          <div v-if="form.content_html" class="article-preview" v-html="sanitizeHtml(form.content_html)"></div>
          <div v-else class="article-preview">
            <p>生成文章后，这里会显示公众号图文预览。</p>
          </div>
        </article>
      </section>
</template>
