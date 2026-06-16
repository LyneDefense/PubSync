<script setup lang="ts">
// 公众号·每日早报：新闻抓取、分组、勾选与文章生成入口。
// 状态与方法来自 useWorkspaceStore 单例；本组件仅负责该面板的视图与交互。
import InlineTaskProgress from '../components/InlineTaskProgress.vue'
import {
  activeMainTab,
  activeNews,
  activeNewsTab,
  activeWechatTab,
  article,
  articleStateLabel,
  changeNewsPage,
  formatDate,
  groupLabel,
  handleFetchNews,
  handleToggleNews,
  hasNewsGroups,
  news,
  newsPage,
  newsTotalPages,
  pagedNews,
  pendingAction,
  publicationName,
  setNewsTab,
  taskButtonStyle,
  taskProgress,
  visibleNewsTabs,
  workspaceTitle
} from '../composables/useWorkspaceStore'
</script>

<template>
      <section v-if="activeMainTab === 'wechat' && activeWechatTab === 'brief'" class="panel">
        <div class="workspace-snapshot scoped-snapshot" aria-label="公众号每日早报摘要">
          <div>
            <span>候选内容</span>
            <strong>{{ news.length }}</strong>
          </div>
          <div>
            <span>当前文章</span>
            <strong>{{ articleStateLabel }}</strong>
          </div>
          <div>
            <span>工作区</span>
            <strong>{{ publicationName }}</strong>
          </div>
        </div>
        <div class="section-header">
          <div>
            <h2>{{ workspaceTitle }}每日早报</h2>
            <p class="toolbar-subtitle">新闻采集、候选筛选和早报生成是独立链路，最终进入公众号文章草稿。</p>
          </div>
          <div class="actions">
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
        </div>
        <InlineTaskProgress :active="pendingAction === 'fetch'" title="正在抓取新闻" fallback="正在抓取新闻并做大模型筛选,可能需要一会儿。" />
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
                <span v-if="hasNewsGroups" class="region-pill">
                  {{ groupLabel(item.group_key) }}
                </span>
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
        <p v-else class="empty-region">当前分类还没有候选新闻。</p>
      </section>
</template>
