<script setup lang="ts">
// 内联 SVG 图标(Tabler outline),只内联用到的 16 个 path —— 不引 ~900KB 整套 webfont。
// 用法:<TIcon name="check" />;尺寸随 font-size(1em),颜色随 currentColor。
import { computed } from 'vue'
import { ICON_PATHS } from './icons'

const props = defineProps<{ name: string }>()
const paths = computed(() => ICON_PATHS[props.name] || [])
</script>

<template>
  <svg
    class="t-icon"
    viewBox="0 0 24 24"
    width="1em"
    height="1em"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path v-for="(d, i) in paths" :key="i" :d="d" />
  </svg>
</template>

<style scoped>
.t-icon {
  display: inline-block;
  vertical-align: -0.125em;
  flex: none;
}
</style>
