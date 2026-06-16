<script setup lang="ts">
// 社媒·创作流程（发布包）：选博主→选 Skill→选题→生成正文/脚本→配图→确认。
// 状态与方法来自 useWorkspaceStore 单例；本组件仅负责该面板的视图与交互。
import HashtagCloud from '../components/HashtagCloud.vue'
import ImageOutputGrid from '../components/ImageOutputGrid.vue'
import {
  parseJsonObject,
  xhsContentTypeLabel,
  xhsPackageCopyText
} from '../utils/format'
import {
  article,
  bloggers,
  copyText,
  currentSocialPlatformName,
  currentSocialTab,
  currentXhsDraft,
  formatDate,
  xhsDraftBenchmark,
  xhsDraftCompliance,
  xhsDraftProcess,
  goNextXhsCreationStep,
  goPreviousXhsCreationStep,
  handleCreateXhsPackage,
  handleDiscardXhsDraft,
  handleGenerateXhsTopicIdeas,
  handleSaveXhsPackage,
  handleXhsCreatorBloggerChange,
  handleXhsCreatorSkillChange,
  isSocialPlatform,
  openImagePreview,
  pendingAction,
  selectXhsTopicIdea,
  selectedXhsSkill,
  selectedXhsTopicIdea,
  selectedXhsTopicIndex,
  xhsCreationStep,
  xhsCreationStepLabels,
  xhsCreatorBloggerId,
  xhsCreatorSkillOptions,
  xhsDraftHashtags,
  xhsDraftImagePlan,
  xhsDraftImageUrls,
  xhsDraftScriptSegments,
  xhsPackageForm,
  xhsTopicIdeas
} from '../composables/useWorkspaceStore'
</script>

<template>
      <section v-if="isSocialPlatform && currentSocialTab === 'packages'" class="panel">
        <div class="section-header">
          <div>
            <h2>{{ currentSocialPlatformName }} AI 创作</h2>
            <p class="toolbar-subtitle">按步骤生成一条新内容；历史结果请到“发布包历史”查看。</p>
          </div>
        </div>
        <div class="creator-shell">
          <div class="creator-main">
            <ol class="creator-steps" aria-label="步骤进度">
              <li
                v-for="(label, index) in xhsCreationStepLabels"
                :key="label"
                class="creator-steps__item"
                :class="{ current: xhsCreationStep === index + 1, done: xhsCreationStep > index + 1 }"
              >
                <span class="creator-steps__dot">{{ index + 1 }}</span>
                <span class="creator-steps__label">{{ label }}</span>
              </li>
            </ol>

            <section v-if="xhsCreationStep === 1" class="creation-stage-card active">
              <div class="inline-card-header">
                <div>
                  <span>01 选择博主</span>
                  <h3>选择要借鉴风格的博主</h3>
                </div>
              </div>
              <div v-if="bloggers.length" class="blogger-list compact">
                <button
                  v-for="blogger in bloggers"
                  :key="blogger.id"
                  type="button"
                  :class="{ active: xhsCreatorBloggerId === blogger.id }"
                  @click="xhsCreatorBloggerId = blogger.id; handleXhsCreatorBloggerChange()"
                >
                  <strong>{{ blogger.display_name }}</strong>
                  <span>{{ blogger.niche || '未设置领域' }} · 样本 {{ blogger.sample_count }} · {{ blogger.last_distilled_at ? formatDate(blogger.last_distilled_at) : '未蒸馏' }}</span>
                </button>
              </div>
              <p v-else class="empty-region">还没有可用于创作的博主。请先到“博主蒸馏 / 数据采集”创建博主并完成采集。</p>
            </section>

            <section v-if="xhsCreationStep === 2" class="creation-stage-card active">
              <div class="inline-card-header">
                <div>
                  <span>02 选择 Skill</span>
                  <h3>选择该博主的风格资产</h3>
                </div>
              </div>
              <div v-if="xhsCreatorSkillOptions.length" class="topic-idea-grid">
                <button
                  v-for="skill in xhsCreatorSkillOptions"
                  :key="skill.id"
                  type="button"
                  :class="{ active: xhsPackageForm.skill_id === skill.id }"
                  @click="xhsPackageForm.skill_id = skill.id; handleXhsCreatorSkillChange()"
                >
                  <strong>{{ skill.name }}</strong>
                  <span>{{ skill.description }}</span>
                  <small>{{ formatDate(skill.created_at) }}</small>
                </button>
              </div>
              <p v-else class="empty-region">这个博主还没有可用 Skill。请先到“博主蒸馏”完成一次风格蒸馏。</p>
              <div v-if="selectedXhsSkill" class="skill-mini-card">
                <strong>{{ selectedXhsSkill.name }}</strong>
                <span>{{ selectedXhsSkill.description }}</span>
              </div>
            </section>

            <section v-if="xhsCreationStep === 3" class="creation-stage-card active">
              <div class="inline-card-header">
                <div>
                  <span>03 生成/选择选题</span>
                  <h3>先确定这次要写什么</h3>
                </div>
                <button type="button" class="primary" :disabled="Boolean(pendingAction) || !selectedXhsSkill" :title="!selectedXhsSkill ? '请先在第 2 步选择一个 Skill' : ''" @click="handleGenerateXhsTopicIdeas">
                  {{ pendingAction === 'xhs-topic' ? '生成中' : xhsTopicIdeas.length ? '重新生成选题' : '生成选题方案' }}
                </button>
              </div>
              <label>
                种子主题
                <input v-model="xhsPackageForm.topic" type="text" placeholder="可以留空，也可以输入你想写的大方向" />
              </label>
              <div class="config-grid">
                <label>
                  目标人群
                  <input v-model="xhsPackageForm.target_audience" type="text" placeholder="例如：第一次养猫的年轻人" />
                </label>
                <label>
                  内容目的
                  <select v-model="xhsPackageForm.content_goal">
                    <option value="知识分享">知识分享</option>
                    <option value="避坑科普">避坑科普</option>
                    <option value="种草转化">种草转化</option>
                    <option value="观点表达">观点表达</option>
                    <option value="经验复盘">经验复盘</option>
                  </select>
                </label>
              </div>
              <label>
                关键词
                <input v-model="xhsPackageForm.keywords" type="text" placeholder="用逗号分隔，例如：猫粮, 配料表, 蛋白质" />
              </label>
              <div v-if="xhsTopicIdeas.length" class="topic-idea-grid">
                <button
                  v-for="(idea, index) in xhsTopicIdeas"
                  :key="`${idea.title}-${index}`"
                  type="button"
                  :class="{ active: selectedXhsTopicIndex === index }"
                  @click="selectXhsTopicIdea(index)"
                >
                  <strong>{{ idea.title }}</strong>
                  <span>{{ idea.angle }}</span>
                  <small>{{ idea.reason }}</small>
                </button>
              </div>
              <p v-else class="empty-region">生成后，这里会显示多个可选择的选题方案。</p>
            </section>

            <section v-if="xhsCreationStep === 4" class="creation-stage-card active">
              <div class="inline-card-header">
                <div>
                  <span>04 生成正文/脚本</span>
                  <h3>选择内容类型并生成</h3>
                </div>
                <button type="button" class="primary" :disabled="Boolean(pendingAction) || !selectedXhsSkill || !xhsPackageForm.topic.trim()" :title="!selectedXhsSkill ? '请先选择 Skill' : (!xhsPackageForm.topic.trim() ? '请先在上方选择或填写一个选题' : '')" @click="handleCreateXhsPackage">
                  {{ pendingAction === 'xhs-package' ? '生成中' : currentXhsDraft ? '重新生成' : '开始生成' }}
                </button>
              </div>
              <div v-if="selectedXhsTopicIdea" class="selected-idea-card">
                <span>已选方向</span>
                <strong>{{ selectedXhsTopicIdea.title }}</strong>
                <p>{{ selectedXhsTopicIdea.angle }}</p>
              </div>
              <div class="package-type-grid" role="radiogroup" aria-label="内容类型">
                <label :class="{ active: xhsPackageForm.content_type === 'text_note' }">
                  <input v-model="xhsPackageForm.content_type" type="radio" value="text_note" />
                  <strong>图文笔记</strong>
                  <span>标题、正文、标签、封面文案</span>
                </label>
                <label :class="{ active: xhsPackageForm.content_type === 'image_note' }">
                  <input v-model="xhsPackageForm.content_type" type="radio" value="image_note" />
                  <strong>图文配图</strong>
                  <span>额外规划并生成配图</span>
                </label>
                <label :class="{ active: xhsPackageForm.content_type === 'spoken_script' }">
                  <input v-model="xhsPackageForm.content_type" type="radio" value="spoken_script" />
                  <strong>口播脚本</strong>
                  <span>按时间段输出口播稿</span>
                </label>
                <label :class="{ active: xhsPackageForm.content_type === 'video_script' }">
                  <input v-model="xhsPackageForm.content_type" type="radio" value="video_script" />
                  <strong>视频脚本</strong>
                  <span>分镜、旁白、字幕建议</span>
                </label>
              </div>
              <section v-if="currentXhsDraft" class="package-copy-block">
                <div class="inline-card-header">
                  <h3>{{ currentXhsDraft.title }}</h3>
                  <button type="button" @click="copyText(currentXhsDraft.body_text, '正文')">复制正文</button>
                </div>
                <pre>{{ currentXhsDraft.body_text }}</pre>
              </section>
            </section>

            <section v-if="xhsCreationStep === 5" class="creation-stage-card active">
              <div class="inline-card-header">
                <div>
                  <span>05 封面、配图与标签</span>
                  <h3>检查素材输出</h3>
                </div>
              </div>
              <div v-if="currentXhsDraft" class="asset-output-grid">
                <article>
                  <span>封面文案</span>
                  <strong>{{ currentXhsDraft.cover_text || '暂无' }}</strong>
                </article>
                <article>
                  <span>标签</span>
                  <strong>{{ xhsDraftHashtags.length }} 个</strong>
                </article>
                <article>
                  <span>配图</span>
                  <strong>{{ xhsDraftImageUrls.length || xhsDraftImagePlan.length }} 张</strong>
                </article>
              </div>
              <HashtagCloud :tags="xhsDraftHashtags" @copy="copyText($event, '标签')" />
              <ImageOutputGrid
                v-if="xhsDraftImageUrls.length"
                :urls="xhsDraftImageUrls"
                :plan="xhsDraftImagePlan"
                :alt-text="`${currentSocialPlatformName}发布包配图`"
                @preview="openImagePreview($event.url, $event.caption)"
              />
              <p v-if="!currentXhsDraft" class="empty-region">生成内容后，这里会展示封面、标签和配图输出。</p>
            </section>

            <section v-if="xhsCreationStep === 6" class="creation-stage-card active">
              <div class="inline-card-header">
                <div>
                  <span>06 最终发布包</span>
                  <h3>预览并决定是否保存</h3>
                </div>
                <div class="actions compact-actions">
                  <button type="button" :disabled="!currentXhsDraft" @click="currentXhsDraft && copyText(xhsPackageCopyText(currentXhsDraft), '发布文案')">复制发布文案</button>
                  <button type="button" class="primary" :disabled="Boolean(pendingAction) || !currentXhsDraft" @click="handleSaveXhsPackage">
                    {{ pendingAction === 'xhs-package-save' ? '保存中' : '保存发布包' }}
                  </button>
                  <button type="button" :disabled="!currentXhsDraft" @click="handleDiscardXhsDraft">放弃本次创作</button>
                </div>
              </div>
              <p v-if="!currentXhsDraft" class="empty-region">生成内容后，这里会显示本次创作的最终预览。保存后才会进入发布包历史。</p>
              <div v-else class="package-preview draft-preview">
                <div class="package-preview-head">
                  <div>
                    <span>{{ xhsContentTypeLabel(currentXhsDraft.content_type) }}</span>
                    <h3>{{ currentXhsDraft.title }}</h3>
                  </div>
                </div>
                <div class="package-meta-grid">
                  <article>
                    <span>主题</span>
                    <strong>{{ currentXhsDraft.topic }}</strong>
                  </article>
                  <article>
                    <span>封面文案</span>
                    <strong>{{ currentXhsDraft.cover_text || '暂无' }}</strong>
                  </article>
                  <article>
                    <span>标签</span>
                    <strong>{{ xhsDraftHashtags.length }} 个</strong>
                  </article>
                </div>
                <HashtagCloud :tags="xhsDraftHashtags" @copy="copyText($event, '标签')" />
                <section class="package-copy-block">
                  <div class="inline-card-header">
                    <h3>正文预览</h3>
                    <button type="button" @click="copyText(currentXhsDraft.body_text, '正文')">复制正文</button>
                  </div>
                  <pre>{{ currentXhsDraft.body_text }}</pre>
                </section>
                <ImageOutputGrid
                  v-if="xhsDraftImageUrls.length"
                  :urls="xhsDraftImageUrls"
                  :plan="xhsDraftImagePlan"
                  :alt-text="`${currentSocialPlatformName}发布包配图`"
                  @preview="openImagePreview($event.url, $event.caption)"
                />
                <section v-if="xhsDraftScriptSegments.length" class="script-segments">
                  <div class="inline-card-header">
                    <h3>脚本预览</h3>
                    <button type="button" @click="copyText(JSON.stringify(parseJsonObject(currentXhsDraft.script_json), null, 2), '脚本')">复制脚本</button>
                  </div>
                  <article v-for="(segment, index) in xhsDraftScriptSegments" :key="index">
                    <span>{{ segment.start || `${index * 5}s` }} - {{ segment.end || '' }}</span>
                    <strong>{{ segment.subtitle || segment.scene || '脚本片段' }}</strong>
                    <p>{{ segment.voiceover || segment.scene }}</p>
                  </article>
                </section>
                <section v-if="xhsDraftCompliance && xhsDraftCompliance.enabled !== false" class="compliance-box" :class="{ warn: !xhsDraftCompliance.passed }">
                  <div class="inline-card-header">
                    <h3>平台合规</h3>
                  </div>
                  <p v-if="xhsDraftCompliance.passed" class="compliance-ok">已规避平台限流词 ✓</p>
                  <template v-else>
                    <p class="compliance-warn">还有 {{ xhsDraftCompliance.hits.length }} 个限流词建议手动调整(改掉后更不容易被限流):</p>
                    <ul class="compliance-hits">
                      <li v-for="(hit, i) in xhsDraftCompliance.hits" :key="i">
                        <b>{{ hit.word }}</b><span>{{ hit.category }} · 在{{ hit.field }}</span>
                      </li>
                    </ul>
                  </template>
                </section>
                <section v-if="xhsDraftProcess.length" class="audit-process">
                  <div class="inline-card-header">
                    <h3>创作过程</h3>
                  </div>
                  <ol class="process-timeline">
                    <li v-for="(step, index) in xhsDraftProcess" :key="index">
                      <strong>{{ step.label }}</strong>
                      <span>{{ step.detail }}</span>
                    </li>
                  </ol>
                </section>
                <section v-if="xhsDraftBenchmark" class="audit-benchmark">
                  <div class="inline-card-header">
                    <h3>对标对比</h3>
                  </div>
                  <p v-if="xhsDraftBenchmark.summary" class="benchmark-summary">{{ xhsDraftBenchmark.summary }}</p>
                  <ul class="benchmark-points">
                    <li v-if="xhsDraftBenchmark.title_fit"><b>标题:</b>{{ xhsDraftBenchmark.title_fit }}</li>
                    <li v-if="xhsDraftBenchmark.language_fit"><b>语言:</b>{{ xhsDraftBenchmark.language_fit }}</li>
                    <li v-if="xhsDraftBenchmark.formula_fit"><b>套路:</b>{{ xhsDraftBenchmark.formula_fit }}</li>
                  </ul>
                  <div v-if="xhsDraftBenchmark.gaps && xhsDraftBenchmark.gaps.length" class="benchmark-gaps">
                    <h4>还差哪些</h4>
                    <ul><li v-for="(gap, i) in xhsDraftBenchmark.gaps" :key="i">{{ gap }}</li></ul>
                  </div>
                </section>
                <p v-if="currentXhsDraft.error_message" class="run-error">{{ currentXhsDraft.error_message }}</p>
              </div>
            </section>
            <div class="creator-nav">
              <button v-if="xhsCreationStep > 1" type="button" @click="goPreviousXhsCreationStep">← 上一步</button>
              <button v-if="xhsCreationStep < 6" type="button" class="creator-nav__next primary" @click="goNextXhsCreationStep">下一步 →</button>
            </div>
          </div>
        </div>
      </section>
</template>

<style scoped>
.compliance-box {
  margin-top: var(--space-md, 16px);
  border: var(--rule-hair);
  border-radius: var(--radius-md, 8px);
  padding: var(--space-sm, 12px);
}

.compliance-box.warn {
  border-color: var(--color-warn, #d97706);
}

.compliance-ok {
  color: var(--color-ink-3, inherit);
  font-size: var(--text-sm);
}

.compliance-warn {
  color: var(--color-warn, #b45309);
  font-size: var(--text-sm);
  margin-bottom: 8px;
}

.compliance-hits {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  list-style: none;
  padding: 0;
  margin: 0;
}

.compliance-hits li {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  border: var(--rule-hair);
  border-radius: 999px;
  padding: 2px 10px;
  font-size: var(--text-sm);
}

.compliance-hits li span {
  color: var(--color-ink-3, inherit);
  font-size: var(--text-xs, 12px);
}

.process-timeline {
  list-style: none;
  padding: 0;
  margin: 8px 0 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.process-timeline li {
  display: flex;
  gap: 10px;
  font-size: var(--text-sm);
}

.process-timeline strong {
  flex: 0 0 auto;
  min-width: 64px;
  color: var(--color-ink-2, inherit);
}

.audit-process,
.audit-benchmark {
  margin-top: var(--space-md, 16px);
}

.benchmark-points {
  margin: 6px 0;
  padding-left: 18px;
}

.benchmark-points li {
  font-size: var(--text-sm);
  margin: 2px 0;
}
</style>
