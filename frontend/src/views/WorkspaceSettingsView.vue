<script setup lang="ts">
// 公众号·工作空间设置：内容定位、公众号、自动化、来源、生成、排版。
// 状态与方法来自 useWorkspaceStore 单例；本组件仅负责该面板的视图与交互。
import {
  activeMainTab,
  activeSettingsTab,
  activeWechatTab,
  addContentGroup,
  article,
  contentGroupForms,
  form,
  handleSaveConfig,
  layoutForm,
  layoutPreviewHeadingStyle,
  layoutPreviewImageStyle,
  layoutPreviewSectionStyle,
  layoutPreviewStyle,
  news,
  pendingAction,
  profileForm,
  publishingForm,
  removeContentGroup,
  usesRegionalGrouping,
  wechatForm
} from '../composables/useWorkspaceStore'
</script>

<template>
      <section v-if="activeMainTab === 'wechat' && activeWechatTab === 'settings'" class="panel">
        <div class="section-header">
          <div>
            <h2>工作空间配置</h2>
          </div>
          <button type="submit" form="workspace-config-form" class="primary" :disabled="Boolean(pendingAction)">
            {{ pendingAction === 'config' ? '保存中…' : '保存配置' }}
          </button>
        </div>
        <div class="module-subnav">
          <div class="tabs" role="tablist" aria-label="设置模块">
            <button
              type="button"
              role="tab"
              :aria-selected="activeSettingsTab === 'general'"
              :class="{ active: activeSettingsTab === 'general' }"
              @click="activeSettingsTab = 'general'"
            >
              通用设置
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeSettingsTab === 'wechat'"
              :class="{ active: activeSettingsTab === 'wechat' }"
              @click="activeSettingsTab = 'wechat'"
            >
              公众号设置
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeSettingsTab === 'automation'"
              :class="{ active: activeSettingsTab === 'automation' }"
              @click="activeSettingsTab = 'automation'"
            >
              自动化设置
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeSettingsTab === 'sources'"
              :class="{ active: activeSettingsTab === 'sources' }"
              @click="activeSettingsTab = 'sources'"
            >
              新闻源设置
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeSettingsTab === 'generation'"
              :class="{ active: activeSettingsTab === 'generation' }"
              @click="activeSettingsTab = 'generation'"
            >
              生成策略
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeSettingsTab === 'layout'"
              :class="{ active: activeSettingsTab === 'layout' }"
              @click="activeSettingsTab = 'layout'"
            >
              排版设置
            </button>
          </div>
        </div>

        <form id="workspace-config-form" class="config-form" @submit.prevent="handleSaveConfig">
          <div v-if="activeSettingsTab === 'general'" class="settings-pane">
            <h3>工作空间与文章标题</h3>
            <div class="config-grid">
              <label>
                公众号/栏目名称
                <input v-model="profileForm.publication_name" type="text" required />
              </label>
              <label>
                工作台标题
                <input v-model="profileForm.workspace_title" type="text" required />
              </label>
              <label>
                文章标题前缀
                <input v-model="profileForm.title_prefix" type="text" required />
              </label>
            </div>
            <label>
              内容领域
              <textarea v-model="profileForm.content_domain" rows="3" readonly></textarea>
            </label>
            <label>
              编辑人设
              <textarea v-model="profileForm.editor_persona" rows="3" readonly></textarea>
            </label>
            <label>
              目标读者
              <textarea v-model="profileForm.audience" rows="3" readonly></textarea>
            </label>
            <label>
              文章风格
              <textarea v-model="profileForm.article_style" rows="3" readonly></textarea>
            </label>
            <label>
              图片风格
              <textarea v-model="profileForm.image_style" rows="3" readonly></textarea>
            </label>
            <label>
              分类 JSON
              <textarea v-model="profileForm.categories_json" rows="3" readonly></textarea>
            </label>
          </div>

          <div v-if="activeSettingsTab === 'wechat'" class="settings-pane">
            <h3>微信草稿箱配置</h3>
            <div class="config-grid">
              <label>
                微信 AppID
                <input v-model="wechatForm.app_id" type="text" autocomplete="off" />
              </label>
              <label>
                微信 AppSecret
                <input
                  v-model="wechatForm.app_secret"
                  type="password"
                  autocomplete="new-password"
                  :placeholder="wechatForm.app_secret_configured ? '已配置，留空则不修改' : '未配置'"
                />
              </label>
            </div>
          </div>

          <div v-if="activeSettingsTab === 'automation'" class="settings-pane">
            <h3>定时发布</h3>
            <div class="config-grid">
              <label class="toggle-row">
                <input v-model="publishingForm.daily_publish_enabled" type="checkbox" />
                启用定时任务
              </label>
              <label class="toggle-row">
                <input v-model="publishingForm.auto_send_wechat_draft" type="checkbox" />
                生成后自动发送草稿箱
              </label>
              <label>
                发布周期
                <select v-model="publishingForm.publish_frequency">
                  <option value="daily">每日</option>
                  <option value="weekly">每周</option>
                  <option value="monthly">每月</option>
                </select>
              </label>
              <label v-if="publishingForm.publish_frequency === 'weekly'">
                每周执行日
                <select v-model.number="publishingForm.publish_weekday">
                  <option :value="1">周一</option>
                  <option :value="2">周二</option>
                  <option :value="3">周三</option>
                  <option :value="4">周四</option>
                  <option :value="5">周五</option>
                  <option :value="6">周六</option>
                  <option :value="7">周日</option>
                </select>
              </label>
              <label v-if="publishingForm.publish_frequency === 'monthly'">
                每月执行日
                <input v-model.number="publishingForm.publish_month_day" type="number" min="1" max="31" />
              </label>
              <label>
                时间点
                <input v-model="publishingForm.publish_time_value" type="time" step="60" />
              </label>
            </div>
          </div>

          <div v-if="activeSettingsTab === 'sources'" class="settings-pane">
            <h3>来源与候选池</h3>
            <div class="config-grid">
              <label>
                每个源最多抓取
                <input v-model.number="publishingForm.news_per_source_limit" type="number" min="1" max="50" />
              </label>
              <label>
                新闻回看小时
                <input v-model.number="publishingForm.news_lookback_hours" type="number" min="1" max="168" />
              </label>
              <label>
                总候选上限
                <input v-model.number="publishingForm.max_news_candidates" type="number" min="1" max="300" />
              </label>
            </div>
            <div class="group-editor">
              <article v-for="(group, index) in contentGroupForms" :key="`${group.group_key}-${index}`" class="group-card">
                <div class="group-card-header">
                  <strong>{{ group.name || `内容分组 ${index + 1}` }}</strong>
                  <button type="button" @click="removeContentGroup(index)">移除</button>
                </div>
                <div class="config-grid">
                  <label>
                    分组 Key
                    <input v-model="group.group_key" type="text" required />
                  </label>
                  <label>
                    分组名称
                    <input v-model="group.name" type="text" required />
                  </label>
                  <label>
                    内容形态
                    <select v-model="group.content_mode">
                      <option value="news">新闻资讯</option>
                      <option value="knowledge">知识分享</option>
                      <option value="analysis">行业观察</option>
                    </select>
                  </label>
                  <label>
                    候选数量
                    <input v-model.number="group.candidate_limit" type="number" min="0" max="300" />
                  </label>
                  <label class="toggle-row">
                    <input v-model="group.enabled" type="checkbox" />
                    启用分组
                  </label>
                  <label>
                    文章最少
                    <input v-model.number="group.article_min" type="number" min="0" max="50" />
                  </label>
                  <label>
                    文章目标
                    <input v-model.number="group.article_target" type="number" min="0" max="50" />
                  </label>
                  <label>
                    文章最多
                    <input v-model.number="group.article_max" type="number" min="0" max="50" />
                  </label>
                </div>
                <label>
                  新闻源
                  <textarea
                    v-model="group.source_urls"
                    rows="3"
                    placeholder="格式：名称|RSS地址,名称|RSS地址"
                  ></textarea>
                </label>
              </article>
              <button type="button" class="secondary" @click="addContentGroup">新增内容分组</button>
            </div>
          </div>

          <div v-if="activeSettingsTab === 'generation'" class="settings-pane">
            <h3>文章、图片与去重</h3>
            <div class="config-grid">
              <label class="toggle-row">
                <input v-model="publishingForm.generate_article_images" type="checkbox" />
                生成正文配图
              </label>
              <label class="toggle-row">
                <input v-model="publishingForm.dedup_enable_llm_review" type="checkbox" />
                启用大模型去重复核
              </label>
              <label>
                最少正文图
                <input v-model.number="publishingForm.min_article_images" type="number" min="0" max="10" />
              </label>
              <label>
                最多正文图
                <input v-model.number="publishingForm.max_article_images" type="number" min="0" max="10" />
              </label>
              <label>
                文章新闻数量
                <input v-model.number="publishingForm.article_news_limit" type="number" min="1" max="50" />
              </label>
              <label>
                文章回看小时
                <input v-model.number="publishingForm.article_news_lookback_hours" type="number" min="1" max="168" />
              </label>
              <label>
                去重回看天数
                <input v-model.number="publishingForm.dedup_lookback_days" type="number" min="1" max="30" />
              </label>
              <label>
                直接判重阈值
                <input v-model="publishingForm.dedup_direct_similarity" type="number" min="0" max="1" step="0.01" />
              </label>
              <label>
                大模型复核阈值
                <input v-model="publishingForm.dedup_review_similarity" type="number" min="0" max="1" step="0.01" />
              </label>
            </div>
          </div>

          <div v-if="activeSettingsTab === 'layout'" class="settings-pane">
            <h3>视觉参数与实时预览</h3>
            <div class="layout-editor">
              <div class="layout-controls">
                <div class="config-grid">
                  <label>
                    版式模板
                    <select v-model="layoutForm.template_name">
                      <option value="clean">清爽资讯</option>
                      <option value="warm">温和科普</option>
                      <option value="compact">紧凑早报</option>
                    </select>
                  </label>
                  <label>
                    主色
                    <input v-model="layoutForm.primary_color" type="color" />
                  </label>
                  <label>
                    强调线颜色
                    <input v-model="layoutForm.accent_color" type="color" />
                  </label>
                  <label>
                    正文字号
                    <input v-model.number="layoutForm.body_font_size" type="number" min="12" max="20" />
                  </label>
                  <label>
                    标题字号
                    <input v-model.number="layoutForm.heading_font_size" type="number" min="14" max="26" />
                  </label>
                  <label>
                    行高
                    <input v-model="layoutForm.line_height" type="number" min="1.4" max="2.2" step="0.05" />
                  </label>
                  <label>
                    段落间距
                    <input v-model.number="layoutForm.section_spacing" type="number" min="12" max="48" />
                  </label>
                  <label>
                    图片圆角
                    <input v-model.number="layoutForm.image_radius" type="number" min="0" max="24" />
                  </label>
                </div>
                <label class="toggle-row">
                  <input v-model="layoutForm.show_group_heading" type="checkbox" />
                  显示分组标题
                </label>
                <label class="toggle-row">
                  <input v-model="layoutForm.show_editor_note" type="checkbox" />
                  显示编辑观察
                </label>
                <label class="toggle-row">
                  <input v-model="layoutForm.show_source" type="checkbox" />
                  显示来源
                </label>
              </div>
              <div class="layout-preview" :style="layoutPreviewStyle" aria-label="排版预览">
                <p class="layout-preview-kicker">公众号预览</p>
                <section v-if="layoutForm.show_group_heading" :style="layoutPreviewSectionStyle">
                  <h3 :style="layoutPreviewHeadingStyle">{{ usesRegionalGrouping ? contentGroupForms[0]?.name || '内容分组' : '精选内容' }}</h3>
                </section>
                <section :style="layoutPreviewSectionStyle">
                  <h2 :style="layoutPreviewHeadingStyle">01｜一条适合当前工作空间的内容标题</h2>
                  <p>这里展示正文段落的字号、行高和整体阅读密度。实际生成文章时，后端会用同一套参数渲染公众号 HTML。</p>
                  <div class="layout-preview-image" :style="layoutPreviewImageStyle"></div>
                  <blockquote v-if="layoutForm.show_editor_note" :style="{ borderLeftColor: layoutForm.accent_color }">
                    编辑观察：这里展示强调块的颜色和间距。
                  </blockquote>
                  <p v-if="layoutForm.show_source">
                    来源：<a :style="{ color: layoutForm.primary_color, borderBottomColor: layoutForm.primary_color }">示例来源</a>
                  </p>
                </section>
              </div>
            </div>
          </div>
        </form>
      </section>
</template>
