<script setup lang="ts">
defineProps<{ tags: unknown[] }>()
defineEmits<{ (e: 'copy', text: string): void }>()

function label(tag: unknown): string {
  return String(tag).replace(/^#/, '')
}
</script>

<template>
  <section v-if="tags.length" class="tag-cloud">
    <button v-for="tag in tags" :key="String(tag)" type="button" @click="$emit('copy', `#${label(tag)}`)">
      #{{ label(tag) }}
    </button>
  </section>
</template>
