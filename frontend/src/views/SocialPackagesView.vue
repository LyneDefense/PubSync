<script setup lang="ts">
// 社媒·对标博主创作(发布包):五步向导 —— 选对标博主 → 选题 → 生成正文/脚本 → 素材 → 发布包。
// 选博主即自动带出其创作画像(去多画像后一博主一画像),无需再单选 Skill。
// 纯展示重构:状态/方法全部沿用 useWorkspaceStore;第 2/3 步「生成后才出现下一步」;三处进度沿用内嵌进度规范。
import { computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import HashtagCloud from '../components/HashtagCloud.vue'
import ImagePlanList from '../components/ImagePlanList.vue'
import LiveProgress from '../components/LiveProgress.vue'
import { parseJsonObject, xhsContentTypeLabel, xhsPackageCopyText } from '../utils/format'
import {
  bloggers,
  copyText,
  currentSocialPlatformName,
  currentSocialTab,
  currentXhsDraft,
  formatDate,
  goNextXhsCreationStep,
  goPreviousXhsCreationStep,
  handleCreateXhsPackage,
  handleDiscardXhsDraft,
  handleGenerateXhsTopicIdeas,
  handleSaveXhsPackage,
  handleXhsCreatorBloggerChange,
  isSocialPlatform,
  myAccountsOnPlatform,
  pendingAction,
  selectXhsTopicIdea,
  selectedXhsSkill,
  selectedXhsTopicIdea,
  selectedXhsTopicIndex,
  xhsCreationStep,
  xhsCreationStepLabels,
  xhsCreatorBloggerId,
  xhsDraftBenchmark,
  xhsDraftCompliance,
  xhsDraftHashtags,
  xhsDraftImagePlan,
  xhsDraftIsVideoScript,
  xhsDraftProcess,
  xhsDraftScriptMeta,
  xhsDraftScriptSegments,
  xhsPackageForm,
  xhsTopicIdeas
} from '../composables/useWorkspaceStore'

// 嵌入 /create(对象驱动新架构):从博主页「用它创作」进来时,预选该博主并直接跳到第 2 步(选题)。
const props = defineProps<{ embedded?: boolean; bloggerId?: number }>()
const router = useRouter()
watch(
  () => props.bloggerId,
  (id) => {
    if (!props.embedded || !id || xhsCreatorBloggerId.value === id) return
    xhsCreatorBloggerId.value = id
    handleXhsCreatorBloggerChange() // 自动带出创作画像 + 复位到第 1 步
    xhsCreationStep.value = 2 // 博主已定,直接到选题
  },
  { immediate: true }
)

// 第 2/3 步「生成」与「下一步」不并存:必须先生成出结果才显示下一步。
const showNext = computed(() => {
  const s = xhsCreationStep.value
  if (s >= 5) return false
  if (s === 2) return xhsTopicIdeas.value.length > 0
  if (s === 3) return Boolean(currentXhsDraft.value)
  return true
})

// 步骤条:点已完成节点回退(生成中禁止跳转)。
function goToStep(n: number) {
  if (pendingAction.value) return
  if (n < xhsCreationStep.value) xhsCreationStep.value = n
}

function pickBlogger(id: number) {
  xhsCreatorBloggerId.value = id
  handleXhsCreatorBloggerChange()
}

// 文字头像:名字首字 + 按 id 取柔和底色。
const AVATAR_BG = ['#eaf3ee', '#f0eef7', '#eef4f5', '#eef1f6', '#f6eef2', '#eef3f7']
const AVATAR_INK = ['#2f6b54', '#5a4a86', '#3a6a72', '#44506a', '#8a4a64', '#3a5a86']
function avatarStyle(id: number) {
  const i = (((id || 0) % AVATAR_BG.length) + AVATAR_BG.length) % AVATAR_BG.length
  return { background: AVATAR_BG[i], color: AVATAR_INK[i] }
}
</script>

<template>
  <section v-if="embedded || (isSocialPlatform && currentSocialTab === 'packages')" class="packages" :class="{ 'is-embedded': embedded }">
    <button v-if="embedded" type="button" class="pk-crumb" @click="router.push({ name: 'home' })">← 首页 / 创作</button>
    <header v-else class="page-head">
      <h1>{{ currentSocialPlatformName }}对标博主创作</h1>
      <p>借鉴对标博主的创作画像，按步骤生成一条新内容；历史结果请到「发布草稿」查看。</p>
    </header>

    <!-- 步骤条 -->
    <ol class="stepper" aria-label="创作步骤">
      <li
        v-for="(label, index) in xhsCreationStepLabels"
        :key="label"
        class="step"
        :class="{ current: xhsCreationStep === index + 1, done: xhsCreationStep > index + 1 }"
      >
        <button type="button" class="step-dot" @click="goToStep(index + 1)">
          <span v-if="xhsCreationStep > index + 1" aria-hidden="true">✓</span>
          <span v-else>{{ index + 1 }}</span>
        </button>
        <span class="step-label">{{ label }}</span>
      </li>
    </ol>

    <!-- 第 1 步:选对标博主 -->
    <section v-if="xhsCreationStep === 1" class="card">
      <div class="card-head">
        <div><span class="eyebrow">01 选择对标博主</span><h3>选择要借鉴创作画像的对标博主</h3></div>
      </div>
      <div v-if="bloggers.length" class="pick-grid">
        <button
          v-for="blogger in bloggers"
          :key="blogger.id"
          type="button"
          class="pick blogger"
          :class="{ sel: xhsCreatorBloggerId === blogger.id }"
          @click="pickBlogger(blogger.id)"
        >
          <span class="pk-avatar" :style="avatarStyle(blogger.id)">{{ (blogger.display_name || '?').slice(0, 1) }}</span>
          <span class="pk-body">
            <span class="pk-name">{{ blogger.display_name }}</span>
            <span class="pk-sub">{{ blogger.niche || '未设置领域' }} · 样本 {{ blogger.sample_count }} · {{ blogger.last_distilled_at ? formatDate(blogger.last_distilled_at) : '未蒸馏' }}</span>
          </span>
          <span class="pk-radio" aria-hidden="true"></span>
        </button>
      </div>
      <p v-else class="empty-region pad">还没有可用于创作的博主。请先到「博主档案」建档并蒸馏出创作画像。</p>
    </section>

    <!-- 第 2 步:生成 / 选择选题 -->
    <section v-if="xhsCreationStep === 2" class="card">
      <div class="card-head">
        <div><span class="eyebrow">02 生成 / 选择选题</span><h3>先确定这次要写什么</h3></div>
        <button
          type="button"
          class="btn btn--accent"
          :disabled="Boolean(pendingAction) || !selectedXhsSkill"
          :title="!selectedXhsSkill ? '请先在第 1 步选择一个已蒸馏出创作画像的对标博主' : ''"
          @click="handleGenerateXhsTopicIdeas"
        >
          {{ pendingAction === 'xhs-topic' ? '生成中…' : xhsTopicIdeas.length ? '重新生成选题' : '生成选题方案' }}
        </button>
      </div>

      <div class="form">
        <label v-if="myAccountsOnPlatform.length" class="field">
          <span class="field-label">为哪个「我的账号」创作</span>
          <select v-model="xhsPackageForm.my_account_id">
            <option :value="null">暂不指定（只按对标博主的选题方法出选题）</option>
            <option v-for="a in myAccountsOnPlatform" :key="a.id" :value="a.id">{{ a.display_name }}</option>
          </select>
          <span class="field-hint">选定后，选题会结合该账号「读者最关心的问题」——需先在「我的账号 · 体检」跑过受众需求；没跑过则自动降级为只按对标方法出选题。</span>
        </label>
        <label class="field">
          <span class="field-label">种子主题</span>
          <input v-model="xhsPackageForm.topic" type="text" placeholder="可以留空，也可以输入你想写的大方向" />
        </label>
        <div class="cfg-grid">
          <label class="field">
            <span class="field-label">目标人群</span>
            <input v-model="xhsPackageForm.target_audience" type="text" placeholder="例如：第一次养猫的年轻人" />
          </label>
          <label class="field">
            <span class="field-label">内容目的</span>
            <select v-model="xhsPackageForm.content_goal">
              <option value="知识分享">知识分享</option>
              <option value="避坑科普">避坑科普</option>
              <option value="种草转化">种草转化</option>
              <option value="观点表达">观点表达</option>
              <option value="经验复盘">经验复盘</option>
            </select>
          </label>
        </div>
        <label class="field">
          <span class="field-label">关键词</span>
          <input v-model="xhsPackageForm.keywords" type="text" placeholder="用逗号分隔，例如：猫粮, 配料表, 蛋白质" />
        </label>
      </div>

      <LiveProgress v-if="pendingAction === 'xhs-topic'" />

      <div v-if="xhsTopicIdeas.length" class="pick-grid topics">
        <button
          v-for="(idea, index) in xhsTopicIdeas"
          :key="`${idea.title}-${index}`"
          type="button"
          class="pick text-pick"
          :class="{ sel: selectedXhsTopicIndex === index }"
          @click="selectXhsTopicIdea(index)"
        >
          <span class="tp-name">{{ idea.title }}</span>
          <span class="tp-angle">{{ idea.angle }}</span>
          <span class="tp-desc">{{ idea.reason }}</span>
        </button>
      </div>
      <p v-else-if="pendingAction !== 'xhs-topic'" class="empty-region pad">点右上「生成选题方案」，这里会出现多个可选择的选题。</p>
    </section>

    <!-- 第 3 步:生成正文 / 脚本 -->
    <section v-if="xhsCreationStep === 3" class="card">
      <div class="card-head">
        <div><span class="eyebrow">03 生成正文 / 脚本</span><h3>选择内容类型并生成</h3></div>
        <button
          type="button"
          class="btn btn--accent"
          :disabled="Boolean(pendingAction) || !selectedXhsSkill || !xhsPackageForm.topic.trim()"
          :title="!selectedXhsSkill ? '请先选择对标博主' : !xhsPackageForm.topic.trim() ? '请先在上一步选择或填写一个选题' : ''"
          @click="handleCreateXhsPackage"
        >
          {{ pendingAction === 'xhs-package' ? '生成中…' : currentXhsDraft ? '重新生成' : '开始生成' }}
        </button>
      </div>

      <div v-if="selectedXhsTopicIdea" class="recap-card">
        <span class="recap-eyebrow">已选方向</span>
        <strong>{{ selectedXhsTopicIdea.title }}</strong>
        <p>{{ selectedXhsTopicIdea.angle }}</p>
      </div>

      <div class="type-grid" role="radiogroup" aria-label="内容类型">
        <label class="type" :class="{ sel: xhsPackageForm.content_type === 'text_note' }">
          <input v-model="xhsPackageForm.content_type" type="radio" value="text_note" />
          <strong>图文笔记</strong><span>标题、正文、标签、封面文案</span>
        </label>
        <label class="type" :class="{ sel: xhsPackageForm.content_type === 'image_note' }">
          <input v-model="xhsPackageForm.content_type" type="radio" value="image_note" />
          <strong>图文配图</strong><span>额外给出配图方案(含生图 prompt,不代生成图)</span>
        </label>
        <label class="type" :class="{ sel: xhsPackageForm.content_type === 'spoken_script' }">
          <input v-model="xhsPackageForm.content_type" type="radio" value="spoken_script" />
          <strong>口播脚本</strong><span>按时间段输出口播稿</span>
        </label>
        <label class="type" :class="{ sel: xhsPackageForm.content_type === 'video_script' }">
          <input v-model="xhsPackageForm.content_type" type="radio" value="video_script" />
          <strong>视频脚本</strong><span>分镜、旁白、字幕建议</span>
        </label>
      </div>

      <LiveProgress v-if="pendingAction === 'xhs-package'" />

      <section v-if="currentXhsDraft" class="copy-block">
        <div class="cb-head">
          <h4>{{ currentXhsDraft.title }}</h4>
          <button type="button" class="btn btn--ghost slim" @click="copyText(currentXhsDraft.body_text, '正文')">复制正文</button>
        </div>
        <pre>{{ currentXhsDraft.body_text }}</pre>
      </section>
    </section>

    <!-- 第 4 步:封面、配图与标签 -->
    <section v-if="xhsCreationStep === 4" class="card">
      <div class="card-head">
        <div><span class="eyebrow">04 封面、配图与标签</span><h3>检查素材输出</h3></div>
      </div>
      <template v-if="currentXhsDraft">
        <div class="metric-grid">
          <article class="metric"><span>封面文案</span><b class="metric-text">{{ currentXhsDraft.cover_text || '暂无' }}</b></article>
          <article class="metric"><span>标签</span><b>{{ xhsDraftHashtags.length }} 个</b></article>
          <article class="metric"><span>配图方案</span><b>{{ xhsDraftImagePlan.length }} 张</b></article>
        </div>
        <HashtagCloud :tags="xhsDraftHashtags" @copy="copyText($event, '标签')" />
        <ImagePlanList v-if="xhsDraftImagePlan.length" :plan="xhsDraftImagePlan" />
      </template>
      <p v-else class="empty-region pad">生成内容后，这里会展示封面、标签和配图方案。</p>
    </section>

    <!-- 第 5 步:最终发布包 -->
    <section v-if="xhsCreationStep === 5" class="card">
      <div class="card-head">
        <div><span class="eyebrow">05 最终发布包</span><h3>预览并决定是否保存</h3></div>
        <div class="pkg-actions">
          <label v-if="myAccountsOnPlatform.length" class="target-account">
            给哪个账号用
            <select v-model="xhsPackageForm.my_account_id" :disabled="!currentXhsDraft">
              <option :value="null">暂不指定</option>
              <option v-for="a in myAccountsOnPlatform" :key="a.id" :value="a.id">{{ a.display_name }}</option>
            </select>
          </label>
          <button type="button" class="btn btn--ghost" :disabled="!currentXhsDraft" @click="currentXhsDraft && copyText(xhsPackageCopyText(currentXhsDraft), '发布文案')">复制发布文案</button>
          <button type="button" class="btn btn--accent" :disabled="Boolean(pendingAction) || !currentXhsDraft" @click="handleSaveXhsPackage">
            {{ pendingAction === 'xhs-package-save' ? '保存中…' : '保存发布包' }}
          </button>
          <button type="button" class="btn btn--ghost danger" :disabled="!currentXhsDraft" @click="handleDiscardXhsDraft">放弃</button>
        </div>
      </div>

      <!-- 保存进度(短任务,不确定型内联条) -->
      <div v-if="pendingAction === 'xhs-package-save'" class="saving">
        <span class="saving-dot" aria-hidden="true"></span>
        <span>正在保存发布包…</span>
        <span class="saving-track" aria-hidden="true"><i></i></span>
      </div>

      <p v-if="!myAccountsOnPlatform.length && currentXhsDraft" class="card-foot">
        还没有自己的{{ currentSocialPlatformName }}账号？到「我的账号」添加后，保存时可归到该账号。
      </p>
      <p v-if="!currentXhsDraft" class="empty-region pad">生成内容后，这里会显示本次创作的最终预览。保存后才会进入「发布草稿」。</p>

      <div v-else class="preview">
        <div class="pv-head">
          <span class="type-badge">{{ xhsContentTypeLabel(currentXhsDraft.content_type) }}</span>
          <h3>{{ currentXhsDraft.title }}</h3>
        </div>
        <div class="metric-grid">
          <article class="metric"><span>主题</span><b class="metric-text">{{ currentXhsDraft.topic }}</b></article>
          <article class="metric"><span>封面文案</span><b class="metric-text">{{ currentXhsDraft.cover_text || '暂无' }}</b></article>
          <article class="metric"><span>标签</span><b>{{ xhsDraftHashtags.length }} 个</b></article>
        </div>
        <HashtagCloud :tags="xhsDraftHashtags" @copy="copyText($event, '标签')" />

        <section class="copy-block">
          <div class="cb-head"><h4>正文预览</h4><button type="button" class="btn btn--ghost slim" @click="copyText(currentXhsDraft.body_text, '正文')">复制正文</button></div>
          <pre>{{ currentXhsDraft.body_text }}</pre>
        </section>

        <section v-if="xhsDraftImagePlan.length" class="copy-block">
          <div class="cb-head"><h4>配图方案</h4></div>
          <ImagePlanList :plan="xhsDraftImagePlan" />
        </section>

        <section v-if="xhsDraftScriptSegments.length" class="copy-block">
          <div class="cb-head">
            <h4>{{ xhsDraftIsVideoScript ? '分镜脚本' : '口播脚本' }}</h4>
            <button type="button" class="btn btn--ghost slim" @click="copyText(JSON.stringify(parseJsonObject(currentXhsDraft.script_json), null, 2), '脚本')">复制脚本</button>
          </div>

          <!-- 拍法附加:开头 3 秒钩子 + 整体节奏 -->
          <div v-if="xhsDraftScriptMeta.hook || xhsDraftScriptMeta.pacing" class="shot-meta">
            <div v-if="xhsDraftScriptMeta.hook" class="sm-card"><span class="sm-label">开头 3 秒钩子</span><p>{{ xhsDraftScriptMeta.hook }}</p></div>
            <div v-if="xhsDraftScriptMeta.pacing" class="sm-card"><span class="sm-label">整体节奏</span><p>{{ xhsDraftScriptMeta.pacing }}</p></div>
          </div>

          <!-- 视频脚本:可照拍的分镜表(镜头/时长/景别/画面/口播/字幕) -->
          <div v-if="xhsDraftIsVideoScript" class="shot-table-wrap">
            <table class="shot-table">
              <thead>
                <tr><th>#</th><th>时长</th><th>景别 / 运镜</th><th>画面</th><th>口播 / 旁白</th><th>字幕</th></tr>
              </thead>
              <tbody>
                <tr v-for="(segment, index) in xhsDraftScriptSegments" :key="index">
                  <td class="st-idx">{{ index + 1 }}</td>
                  <td class="st-time">{{ segment.start || `${index * 5}s` }}<span v-if="segment.end"> - {{ segment.end }}</span></td>
                  <td>{{ segment.shot_type || '—' }}</td>
                  <td>{{ segment.scene || '—' }}</td>
                  <td>{{ segment.voiceover || '—' }}</td>
                  <td>{{ segment.subtitle || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- 口播脚本:按时间段的口播卡片 -->
          <div v-else class="segments">
            <article v-for="(segment, index) in xhsDraftScriptSegments" :key="index" class="segment">
              <span class="seg-time">{{ segment.start || `${index * 5}s` }} - {{ segment.end || '' }}</span>
              <strong>{{ segment.subtitle || segment.voiceover || '脚本片段' }}</strong>
              <p>{{ segment.voiceover }}</p>
            </article>
          </div>
        </section>

        <!-- 平台合规限流词 -->
        <section v-if="xhsDraftCompliance && xhsDraftCompliance.enabled !== false" class="compliance" :class="{ warn: !xhsDraftCompliance.passed }">
          <h4>平台合规</h4>
          <p v-if="xhsDraftCompliance.passed" class="cp-ok">已规避平台限流词 ✓</p>
          <template v-else>
            <p class="cp-warn">还有 {{ xhsDraftCompliance.hits.length }} 个限流词建议手动调整（改掉后更不容易被限流）：</p>
            <ul class="cp-hits">
              <li v-for="(hit, i) in xhsDraftCompliance.hits" :key="i"><b>{{ hit.word }}</b><span>{{ hit.category }} · 在{{ hit.field }}</span></li>
            </ul>
          </template>
        </section>

        <section v-if="xhsDraftProcess.length" class="sub-block">
          <h4>创作过程</h4>
          <ol class="process">
            <li v-for="(step, index) in xhsDraftProcess" :key="index"><strong>{{ step.label }}</strong><span>{{ step.detail }}</span></li>
          </ol>
        </section>

        <section v-if="xhsDraftBenchmark" class="sub-block">
          <h4>对标对比</h4>
          <p v-if="xhsDraftBenchmark.summary" class="bm-summary">{{ xhsDraftBenchmark.summary }}</p>
          <ul class="bm-points">
            <li v-if="xhsDraftBenchmark.title_fit"><b>标题：</b>{{ xhsDraftBenchmark.title_fit }}</li>
            <li v-if="xhsDraftBenchmark.language_fit"><b>语言：</b>{{ xhsDraftBenchmark.language_fit }}</li>
            <li v-if="xhsDraftBenchmark.formula_fit"><b>套路：</b>{{ xhsDraftBenchmark.formula_fit }}</li>
          </ul>
          <div v-if="xhsDraftBenchmark.gaps && xhsDraftBenchmark.gaps.length" class="bm-gaps">
            <h5>还差哪些</h5>
            <ul><li v-for="(gap, i) in xhsDraftBenchmark.gaps" :key="i">{{ gap }}</li></ul>
          </div>
        </section>

        <p v-if="currentXhsDraft.error_message" class="run-error">{{ currentXhsDraft.error_message }}</p>
      </div>
    </section>

    <!-- 底部导航:第 3/4 步「生成后」才出现「下一步」 -->
    <div class="nav">
      <button v-if="xhsCreationStep > 1" type="button" class="btn btn--ghost" @click="goPreviousXhsCreationStep">← 上一步</button>
      <span class="nav-spacer"></span>
      <button v-if="showNext" type="button" class="btn btn--accent" @click="goNextXhsCreationStep">下一步 →</button>
    </div>
  </section>
</template>

<style scoped>
.packages {
  max-width: 880px;
  margin: 0 auto;
}
/* 嵌入 /create 时:宽度交给对象页容器;顶部用面包屑代替页头。 */
.packages.is-embedded { max-width: none; margin: 0; }
.pk-crumb {
  border: 0;
  background: none;
  cursor: pointer;
  font-size: 12.5px;
  color: var(--color-ink-3);
  padding: 0;
  margin-bottom: 14px;
}
.pk-crumb:hover { color: var(--color-accent-ink); }
.page-head {
  margin-bottom: 18px;
}
.page-head h1 {
  margin: 0 0 6px;
  font-size: 21px;
  font-weight: 680;
  letter-spacing: -0.01em;
}
.page-head p {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.6;
  color: var(--color-ink-2);
}

/* 步骤条 */
.stepper {
  display: flex;
  list-style: none;
  margin: 0 0 18px;
  padding: 16px 8px;
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-lg);
  overflow-x: auto;
}
.step {
  flex: 1;
  min-width: 64px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  position: relative;
}
.step:not(:first-child)::before {
  content: '';
  position: absolute;
  top: 15px;
  right: 50%;
  left: -50%;
  height: 2px;
  background: var(--color-rule);
}
.step.current::before,
.step.done::before {
  background: var(--color-accent-soft-bd);
}
.step-dot {
  position: relative;
  z-index: 1;
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: 50%;
  background: var(--color-paper-3);
  color: var(--color-ink-3);
  font-size: 13px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  cursor: default;
}
.step.current .step-dot {
  background: var(--color-accent);
  color: #fff;
}
.step.done .step-dot {
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
  cursor: pointer;
}
.step-label {
  font-size: 13px;
  color: var(--color-ink-3);
  white-space: nowrap;
}
.step.current .step-label,
.step.done .step-label {
  color: var(--color-ink);
  font-weight: 600;
}

/* 卡片 + 卡头 */
.card {
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-lg);
  padding: 20px 22px;
}
.card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}
.eyebrow {
  display: block;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.03em;
  color: var(--color-accent-ink);
}
.card-head h3 {
  margin: 3px 0 0;
  font-size: 18px;
  font-weight: 680;
}
.card-foot {
  margin: 12px 0 0;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--color-ink-3);
}

/* 按钮 */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 38px;
  padding: 0 16px;
  border-radius: 10px;
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: background 140ms var(--ease-out), border-color 140ms var(--ease-out);
}
.btn--accent {
  border: 0;
  background: var(--color-accent);
  color: #fff;
}
.btn--accent:hover {
  background: var(--color-accent-press);
}
.btn--ghost {
  border: 1px solid var(--color-field-border);
  background: var(--color-surface);
  color: var(--color-ink-2);
}
.btn--ghost:hover {
  background: #f7f8f9;
}
.btn--ghost.danger {
  color: var(--color-danger);
}
.btn.slim {
  height: 30px;
  padding: 0 12px;
  font-size: 12.5px;
  border-radius: 8px;
}
.btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* 选择卡网格(博主 / Skill / 选题 / 类型) */
.pick-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(252px, 1fr));
  gap: 10px;
}
.pick {
  border: 1px solid var(--color-rule);
  border-radius: 12px;
  background: var(--color-surface);
  cursor: pointer;
  text-align: left;
  transition: border-color 120ms var(--ease-out), background 120ms var(--ease-out);
}
.pick:hover {
  border-color: var(--color-accent-soft-bd);
}
.pick.sel {
  border-color: var(--color-accent);
  background: var(--color-accent-tint);
  box-shadow: 0 1px 4px var(--color-shadow);
}
/* 博主卡:头像 + 文 + 单选圈 */
.pick.blogger {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
}
.pk-avatar {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 11px;
  font-size: 16px;
  font-weight: 600;
  flex: 0 0 auto;
}
.pk-body {
  flex: 1;
  min-width: 0;
}
.pk-name {
  display: block;
  font-size: 14px;
  font-weight: 620;
  color: var(--color-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pk-sub {
  display: block;
  margin-top: 2px;
  font-size: 11.5px;
  color: var(--color-ink-3);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pk-radio {
  flex: 0 0 auto;
  width: 20px;
  height: 20px;
  border: 1.5px solid var(--color-rule-strong);
  border-radius: 50%;
  position: relative;
}
.pick.blogger.sel .pk-radio {
  border-color: var(--color-accent);
  background: var(--color-accent);
}
.pick.blogger.sel .pk-radio::after {
  content: '✓';
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: #fff;
  font-size: 12px;
  font-weight: 800;
}
/* 文本选择卡(Skill / 选题) */
.text-pick {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 14px 16px;
}
.tp-name {
  font-size: 14px;
  font-weight: 650;
  color: var(--color-ink);
}
.tp-angle {
  font-size: 12.5px;
  font-weight: 550;
  color: var(--color-accent-ink);
}
.tp-desc {
  font-size: 12.5px;
  line-height: 1.55;
  color: var(--color-ink-3);
}
.tp-date {
  font-size: 11.5px;
  color: var(--color-ink-3);
}
.pick-grid.topics {
  margin-top: 16px;
}

/* 第 3 步表单 */
.form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.cfg-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.field-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-ink);
}
.field-hint {
  font-size: 11.5px;
  line-height: 1.55;
  color: var(--color-ink-3);
}
.field input,
.field select,
.target-account select {
  height: 40px;
  padding: 0 12px;
  border: 1px solid var(--color-field-border);
  border-radius: 10px;
  background: var(--color-field);
  font-size: 13.5px;
  color: var(--color-ink);
  font-family: inherit;
}

/* 已选方向 recap */
.recap-card {
  padding: 14px 16px;
  border: 1px solid var(--color-accent-soft-bd);
  border-radius: 12px;
  background: var(--color-accent-tint);
  margin-bottom: 16px;
}
.recap-eyebrow {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-accent-ink);
}
.recap-card strong {
  display: block;
  margin: 4px 0 4px;
  font-size: 15px;
  font-weight: 650;
  color: var(--color-ink);
}
.recap-card p {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--color-ink-2);
}

/* 内容类型四选一 */
.type-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 10px;
}
.type {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px 16px;
  border: 1px solid var(--color-rule);
  border-radius: 12px;
  cursor: pointer;
  transition: border-color 120ms var(--ease-out), background 120ms var(--ease-out);
}
.type:hover {
  border-color: var(--color-accent-soft-bd);
}
.type.sel {
  border-color: var(--color-accent);
  background: var(--color-accent-tint);
}
.type input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}
.type strong {
  font-size: 14px;
  font-weight: 650;
  color: var(--color-ink);
}
.type span {
  font-size: 12px;
  color: var(--color-ink-3);
}

/* 复制块(正文/脚本预览) */
.copy-block {
  margin-top: 16px;
  border: 1px solid var(--color-rule);
  border-radius: 12px;
  overflow: hidden;
}
.cb-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  background: #fafbfc;
  border-bottom: 1px solid var(--color-paper-3);
}
.cb-head h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 650;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.copy-block pre {
  margin: 0;
  padding: 14px 16px;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.7;
  color: var(--color-ink-2);
  font-family: inherit;
}

/* 指标格(素材 / 发布包 meta) */
.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}
.metric {
  padding: 12px 14px;
  border: 1px solid var(--color-rule);
  border-radius: 12px;
}
.metric span {
  display: block;
  font-size: 11.5px;
  color: var(--color-ink-3);
  margin-bottom: 5px;
}
.metric b {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-ink);
  font-variant-numeric: tabular-nums;
}
.metric b.metric-text {
  display: block;
  font-size: 13.5px;
  font-weight: 600;
  line-height: 1.45;
}

/* 第 6 步:操作区 + 预览 */
.pkg-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 8px;
}
.target-account {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 11.5px;
  color: var(--color-ink-3);
}
.target-account select {
  height: 38px;
}
.saving {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 14px;
  padding: 12px 14px;
  border: 1px solid var(--color-accent-soft-bd);
  border-radius: 10px;
  background: var(--color-accent-tint);
  font-size: 13px;
  color: var(--color-ink);
}
.saving-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--color-accent);
  animation: pulse 1.1s var(--ease-out) infinite;
}
.saving-track {
  flex: 1;
  height: 3px;
  border-radius: 99px;
  background: var(--color-accent-soft-bd);
  overflow: hidden;
}
.saving-track i {
  display: block;
  width: 36%;
  height: 100%;
  background: var(--color-accent);
  animation: indet 1.1s var(--ease-out) infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.7); }
}
@keyframes indet {
  0% { margin-left: -36%; }
  100% { margin-left: 100%; }
}
@media (prefers-reduced-motion: reduce) {
  .saving-dot, .saving-track i { animation: none; }
}

.preview {
  display: flex;
  flex-direction: column;
}
.pv-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}
.type-badge {
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
  font-size: 12px;
  font-weight: 650;
}
.pv-head h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 680;
}

.segments {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 16px;
}
.segment {
  display: grid;
  gap: 2px;
}
.seg-time {
  font-size: 11.5px;
  color: var(--color-ink-3);
  font-variant-numeric: tabular-nums;
}
.segment strong {
  font-size: 13px;
  color: var(--color-ink);
}
.segment p {
  margin: 0;
  font-size: 12.5px;
  color: var(--color-ink-2);
}

/* 拍法附加:开头钩子 + 节奏卡 */
.shot-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 12px 16px 4px;
}
.sm-card {
  flex: 1 1 180px;
  min-width: 0;
  padding: 9px 12px;
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-md, 10px);
  background: var(--color-paper-3);
}
.sm-label {
  display: block;
  font-size: 11px;
  font-weight: 650;
  color: var(--color-accent);
  margin-bottom: 3px;
}
.sm-card p {
  margin: 0;
  font-size: 12.5px;
  color: var(--color-ink);
}

/* 视频分镜表:可照拍的分镜(横向可滚,窄屏不撑破布局) */
.shot-table-wrap {
  padding: 12px 16px 14px;
  overflow-x: auto;
}
.shot-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  min-width: 560px;
}
.shot-table th,
.shot-table td {
  padding: 7px 9px;
  text-align: left;
  vertical-align: top;
  border-bottom: 1px solid var(--color-rule);
}
.shot-table th {
  font-size: 11px;
  font-weight: 650;
  color: var(--color-ink-3);
  background: var(--color-paper-3);
  white-space: nowrap;
}
.shot-table td {
  color: var(--color-ink-2);
  line-height: 1.5;
}
.st-idx {
  font-weight: 650;
  color: var(--color-ink);
  width: 28px;
}
.st-time {
  white-space: nowrap;
  color: var(--color-ink-3);
  font-variant-numeric: tabular-nums;
}

/* 平台合规限流词 */
.compliance {
  margin-top: 16px;
  padding: 14px 16px;
  border: 1px solid var(--color-rule);
  border-radius: 12px;
}
.compliance h4 {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 650;
}
.compliance.warn {
  border-color: var(--color-warn-card-bd);
  background: var(--color-warn-card-bg);
}
.cp-ok {
  margin: 0;
  font-size: 13px;
  color: var(--color-ok);
}
.cp-warn {
  margin: 0 0 8px;
  font-size: 12.5px;
  color: var(--color-warn);
}
.cp-hits {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  list-style: none;
  padding: 0;
  margin: 0;
}
.cp-hits li {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  padding: 3px 11px;
  border: 1px solid var(--color-warn-card-bd);
  border-radius: var(--radius-pill);
  background: var(--color-surface);
  font-size: 12.5px;
}
.cp-hits li b {
  color: var(--color-warn);
}
.cp-hits li span {
  color: var(--color-ink-3);
  font-size: 11.5px;
}

/* 创作过程 / 对标对比 */
.sub-block {
  margin-top: 16px;
}
.sub-block h4 {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 650;
}
.process {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.process li {
  display: flex;
  gap: 10px;
  font-size: 13px;
}
.process strong {
  flex: 0 0 auto;
  min-width: 72px;
  color: var(--color-ink-2);
}
.process span {
  color: var(--color-ink-3);
}
.bm-summary {
  margin: 0 0 8px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-ink-2);
}
.bm-points {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.bm-points li {
  font-size: 13px;
  line-height: 1.55;
  color: var(--color-ink-2);
}
.bm-gaps {
  margin-top: 10px;
}
.bm-gaps h5 {
  margin: 0 0 6px;
  font-size: 12.5px;
  font-weight: 650;
  color: var(--color-ink-2);
}
.bm-gaps ul {
  margin: 0;
  padding-left: 18px;
}
.bm-gaps li {
  font-size: 12.5px;
  line-height: 1.55;
  color: var(--color-ink-3);
}
.run-error {
  margin: 12px 0 0;
  font-size: 12.5px;
  color: var(--color-danger);
}

.empty-region.pad {
  padding: 26px 20px;
  text-align: center;
}

/* 底部导航 */
.nav {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 18px;
}
.nav-spacer {
  flex: 1;
}

@media (max-width: 560px) {
  .step-label {
    font-size: 12px;
  }
  .card {
    padding: 18px 16px;
  }
  .card-head {
    flex-direction: column;
  }
}
</style>
