<script setup lang="ts">
// 社媒·发布包历史：已保存发布包的查看与复制。
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
  copyText,
  currentSocialPlatformName,
  currentSocialTab,
  formatDate,
  isSocialPlatform,
  openImagePreview,
  selectedXhsPackage,
  selectedXhsPackageBloggerName,
  selectedXhsPackageId,
  visibleXhsPackages,
  xhsPackageHashtags,
  xhsPackageImagePlan,
  xhsPackageImageUrls,
  xhsPackageScriptSegments
} from '../composables/useWorkspaceStore'
</script>

<template>
      <section v-if="isSocialPlatform && currentSocialTab === 'history'" class="panel">
        <div class="section-header">
          <div>
            <h2>{{ currentSocialPlatformName }}发布包历史</h2>
            <p class="toolbar-subtitle">这里专门查看、复制和管理历史生成结果，不进入生成流程。</p>
          </div>
          </div>
        <div class="package-browser history-browser">
          <aside class="run-list package-list" aria-label="发布包记录">
            <div class="run-list-header">
              <strong>发布包记录</strong>
              <span>{{ visibleXhsPackages.length }} 条</span>
            </div>
            <button
              v-for="pack in visibleXhsPackages"
              :key="pack.id"
              type="button"
              :class="{ active: selectedXhsPackage?.id === pack.id }"
              @click="selectedXhsPackageId = pack.id"
            >
              <strong>{{ pack.title || pack.topic }}</strong>
              <span>{{ xhsContentTypeLabel(pack.content_type) }} · {{ formatDate(pack.created_at) }}</span>
            </button>
            <p v-if="!visibleXhsPackages.length" class="empty-region">还没有发布包。到“AI 创作”生成后会出现在这里。</p>
          </aside>

          <article v-if="selectedXhsPackage" class="package-preview">
            <div class="inline-card-header">
              <div>
                <span>{{ selectedXhsPackageBloggerName }} · {{ xhsContentTypeLabel(selectedXhsPackage.content_type) }}</span>
                <h3>{{ selectedXhsPackage.title }}</h3>
              </div>
              <button type="button" @click="copyText(xhsPackageCopyText(selectedXhsPackage), '发布文案')">复制发布文案</button>
            </div>
            <div class="workspace-snapshot scoped-snapshot">
              <div>
                <span>主题</span>
                <strong>{{ selectedXhsPackage.topic }}</strong>
              </div>
              <div>
                <span>封面文案</span>
                <strong>{{ selectedXhsPackage.cover_text || '暂无' }}</strong>
              </div>
              <div>
                <span>配图</span>
                <strong>{{ xhsPackageImageUrls.length || xhsPackageImagePlan.length }} 张</strong>
              </div>
            </div>
            <section class="package-copy-block">
              <div class="inline-card-header">
                <h3>正文</h3>
                <button type="button" @click="copyText(selectedXhsPackage.body_text, '正文')">复制正文</button>
              </div>
              <pre>{{ selectedXhsPackage.body_text }}</pre>
            </section>
            <HashtagCloud :tags="xhsPackageHashtags" @copy="copyText($event, '标签')" />
            <section v-if="xhsPackageImageUrls.length || xhsPackageImagePlan.length" class="package-images">
              <div class="inline-card-header">
                <h3>配图</h3>
              </div>
              <ImageOutputGrid
                :urls="xhsPackageImageUrls"
                :plan="xhsPackageImagePlan"
                :alt-text="`${currentSocialPlatformName}发布包配图`"
                @preview="openImagePreview($event.url, $event.caption)"
              />
              <div v-if="!xhsPackageImageUrls.length" class="sample-list">
                <div v-for="item in xhsPackageImagePlan" :key="String(item.slot)">
                  <strong>{{ item.caption || `配图 ${item.slot}` }}</strong>
                  <span>{{ item.purpose }}</span>
                </div>
              </div>
              <p v-if="selectedXhsPackage.error_message" class="run-error">{{ selectedXhsPackage.error_message }}</p>
            </section>
            <section v-if="xhsPackageScriptSegments.length" class="script-timeline">
              <div class="inline-card-header">
                <h3>脚本分段</h3>
                <button type="button" @click="copyText(JSON.stringify(parseJsonObject(selectedXhsPackage.script_json), null, 2), '脚本')">复制脚本</button>
              </div>
              <div v-for="(segment, index) in xhsPackageScriptSegments" :key="index">
                <time>{{ segment.start || `${index * 10}s` }} - {{ segment.end || `${(index + 1) * 10}s` }}</time>
                <strong>{{ segment.voiceover || segment.subtitle }}</strong>
                <span>{{ segment.scene }}</span>
              </div>
            </section>
          </article>
          <p v-else class="empty-region result-placeholder">选择一条发布包记录后，这里会展示可复制的内容。</p>
        </div>
      </section>
</template>
