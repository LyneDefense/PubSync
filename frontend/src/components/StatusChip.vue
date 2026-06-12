<script setup lang="ts">
// 统一的状态语义色片：把后端状态值（succeeded / running / failed …）映射为
// 中文标签 + 语义色调，全站复用，保证状态展示风格一致。
import { computed } from 'vue'
import { statusLabel, statusTone } from '../utils/format'

const props = defineProps<{ status: string | null | undefined }>()

const label = computed(() => statusLabel(props.status))
const tone = computed(() => statusTone(props.status))
</script>

<template>
  <span class="status-chip" :class="`status-chip--${tone}`">{{ label }}</span>
</template>
