<script setup lang="ts">
// 找对标博主:独立页面,承载三段 tab(智能推荐/关键词搜索/链接评分)。采用候选→弹确认框保存。
import BenchmarkFinder from '../components/BenchmarkFinder.vue'
import { currentSocialPlatformName, currentSocialTab, isSocialPlatform } from '../composables/useWorkspaceStore'
</script>

<template>
  <section v-if="isSocialPlatform && currentSocialTab === 'find'" class="panel find-benchmark">
    <div class="section-header">
      <div>
        <h2>找对标博主</h2>
        <p class="toolbar-subtitle">不知道学谁就用「智能推荐」；知道大概搜什么用「关键词搜索」；盯上某个号用「链接评分」。选中后采用，即可加入你的{{ currentSocialPlatformName }}对标库。</p>
      </div>
    </div>
    <BenchmarkFinder />
  </section>
</template>

<style scoped>
.find-benchmark {
  max-width: 820px;
}
</style>
