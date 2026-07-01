<script setup lang="ts">
// 侧栏导航用的轻量内联 SVG 图标(零依赖、不触 CSP)。stroke 用 currentColor,跟随文字色。
defineProps<{ name: string }>()

// 每个图标的内部 path/shape 片段,统一 24x24 视图、线性描边风格。
const PATHS: Record<string, string> = {
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M18.4 5.6L17 7M7 17l-1.4 1.4"/>',
  download: '<path d="M12 4v10"/><path d="M8 10l4 4 4-4"/><path d="M5 19h14"/>',
  funnel: '<path d="M4 5h16l-6 8v6l-4-2v-4z"/>',
  folder: '<path d="M4 7a2 2 0 0 1 2-2h3l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z"/>',
  target: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none"/>',
  sparkles: '<path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8z"/><path d="M18 14l.7 1.8L20.5 16.5l-1.8.7L18 19l-.7-1.8L15.5 16.5l1.8-.7z"/>',
  history: '<circle cx="12" cy="12" r="8"/><path d="M12 8v4l3 2"/>',
  edit: '<path d="M4 20h4L18 10l-4-4L4 16z"/><path d="M13 7l4 4"/>',
  file: '<path d="M7 3h7l5 5v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M14 3v5h5"/>',
  list: '<path d="M9 6h11M9 12h11M9 18h11"/><path d="M4 5.5l1.2 1.2L7.5 4.5M4 11.5l1.2 1.2 2.3-2.2M4 17.5l1.2 1.2 2.3-2.2"/>',
  settings: '<path d="M4 8h8M18 8h2M4 16h2M12 16h8"/><circle cx="15" cy="8" r="2.2"/><circle cx="9" cy="16" r="2.2"/>',
  send: '<path d="M21 4L3 11l6 2.5L11 20l3.5-6L21 4z"/><path d="M9 13.5L21 4"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M5 20c0-3.3 3.1-6 7-6s7 2.7 7 6"/>',
  pulse: '<path d="M3 12h4l2 6 4-14 2 8h6"/>',
  search: '<circle cx="11" cy="11" r="6"/><path d="M20 20l-3.6-3.6"/>',
  chart: '<path d="M4 5v14h16"/><path d="M8 15l3-4 3 2 4-6"/>',
  'arrow-up': '<path d="M12 19V6"/><path d="M6 12l6-6 6 6"/>',
  'arrow-right': '<path d="M5 12h14"/><path d="M13 6l6 6-6 6"/>',
  'chevron-down': '<path d="M6 9l6 6 6-6"/>',
  check: '<path d="M5 12l4 4 10-10"/>',
  bell: '<path d="M6 9a6 6 0 0 1 12 0c0 4 1.5 5 2 6H4c.5-1 2-2 2-6z"/><path d="M10 19a2 2 0 0 0 4 0"/>'
}
</script>

<template>
  <svg
    class="nav-icon"
    viewBox="0 0 24 24"
    width="16"
    height="16"
    fill="none"
    stroke="currentColor"
    stroke-width="1.6"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    v-html="PATHS[name] || ''"
  ></svg>
</template>
