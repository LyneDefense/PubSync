<script setup lang="ts">
defineProps<{ image: { url: string; caption: string } | null }>()
defineEmits<{ (e: 'close'): void }>()
</script>

<template>
  <div v-if="image" class="image-preview-backdrop" role="presentation" @click.self="$emit('close')">
    <figure class="image-preview-panel" role="dialog" aria-modal="true" aria-label="配图预览">
      <button type="button" class="ghost image-preview-close" @click="$emit('close')">关闭</button>
      <img :src="image.url" alt="小红书发布包配图大图预览" />
      <figcaption>{{ image.caption }}</figcaption>
    </figure>
  </div>
</template>
