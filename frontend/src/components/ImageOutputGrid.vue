<script setup lang="ts">
const props = defineProps<{
  urls: unknown[]
  // Image plan items are parsed from JSON (loosely typed); only `caption` is read here.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  plan: any[]
  altText: string
}>()
defineEmits<{ (e: 'preview', payload: { url: unknown; caption: string }): void }>()

function captionFor(index: number): string {
  return props.plan[index]?.caption || `配图 ${index + 1}`
}
</script>

<template>
  <div class="image-output-grid">
    <figure v-for="(url, index) in urls" :key="String(url)">
      <button
        type="button"
        class="image-preview-trigger"
        @click="$emit('preview', { url, caption: captionFor(index) })"
      >
        <img :src="String(url)" :alt="altText" />
      </button>
      <figcaption>{{ captionFor(index) }}</figcaption>
    </figure>
  </div>
</template>
