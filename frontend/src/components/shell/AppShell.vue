<script setup lang="ts">
// 对象驱动新外壳:顶栏(品牌 + ⌘K占位 + ＋创作 + 账号菜单)+ 内容区(router-view)。
// 没有左侧功能栏 —— 导航靠首页选对象 + 页面内面包屑返回。与旧 sh-shell(App.vue)并存,按 route.meta.shell='new' 分流。
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { currentUsername, currentTenantName, handleLogout, showMessage } from '../../composables/useWorkspaceStore'

const router = useRouter()
const showMenu = ref(false)
const menuRef = ref<HTMLElement | null>(null)
const initial = computed(() => (currentUsername.value || '?').slice(0, 1).toUpperCase())

function onDocDown(e: MouseEvent) {
  if (showMenu.value && menuRef.value && !menuRef.value.contains(e.target as Node)) showMenu.value = false
}
onMounted(() => document.addEventListener('mousedown', onDocDown))
onUnmounted(() => document.removeEventListener('mousedown', onDocDown))
</script>

<template>
  <div class="ns">
    <header class="ns-top">
      <button type="button" class="ns-brand" @click="router.push({ name: 'home' })" aria-label="回到首页">
        <svg class="ns-logo" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" aria-hidden="true"><path d="M12 3l8 4-8 4-8-4 8-4z" /><path d="M4 12l8 4 8-4" /><path d="M4 16.5l8 4 8-4" /></svg>
        <span class="ns-brand-name">Cadence</span>
      </button>

      <span class="ns-spacer"></span>

      <button type="button" class="ns-k" @click="showMessage('全局搜索即将上线，敬请期待')">
        <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></svg>
        <span class="ns-k-txt">跳转</span><kbd>⌘K</kbd>
      </button>

      <button type="button" class="ns-create" @click="router.push({ name: 'create' })">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
        创作
      </button>

      <div ref="menuRef" class="ns-user">
        <button type="button" class="ns-avatar-btn" :aria-expanded="showMenu" aria-haspopup="menu" @click="showMenu = !showMenu">
          <span class="ns-avatar">{{ initial }}</span>
        </button>
        <div v-if="showMenu" class="ns-menu" role="menu">
          <div class="ns-menu-head">
            <strong>{{ currentUsername }}</strong>
            <span v-if="currentTenantName">{{ currentTenantName }}</span>
          </div>
          <button type="button" role="menuitem" @click="handleLogout">退出登录</button>
        </div>
      </div>
    </header>

    <main class="ns-main">
      <div class="ns-container">
        <router-view />
      </div>
    </main>
  </div>
</template>

<style scoped>
.ns {
  display: grid;
  grid-template-rows: 56px minmax(0, 1fr);
  height: 100vh;
  overflow: hidden;
  background: var(--color-paper);
}
.ns-top {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-rule);
}
.ns-brand {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 0;
  background: none;
  cursor: pointer;
  padding: 6px 4px;
}
.ns-logo { color: var(--color-accent); flex: 0 0 auto; }
.ns-brand-name { font-size: 15px; font-weight: 680; letter-spacing: -0.01em; color: var(--color-ink); }
.ns-spacer { flex: 1; }
.ns-k {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 10px;
  border: 1px solid var(--color-rule);
  border-radius: 8px;
  background: var(--color-surface);
  color: var(--color-ink-3);
  font-size: 12.5px;
  cursor: pointer;
}
.ns-k:hover { border-color: var(--color-rule-strong); }
.ns-k kbd {
  font-family: inherit;
  font-size: 11px;
  color: var(--color-ink-3);
  border: 1px solid var(--color-rule);
  border-radius: 5px;
  padding: 0 5px;
}
.ns-create {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 32px;
  padding: 0 13px;
  border: 0;
  border-radius: 8px;
  background: var(--color-accent);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 140ms var(--ease-out);
}
.ns-create:hover { background: var(--color-accent-press); }
.ns-user { position: relative; }
.ns-avatar-btn { border: 0; background: none; cursor: pointer; padding: 2px; }
.ns-avatar {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--color-paper-3);
  color: var(--color-ink-2);
  font-size: 12.5px;
  font-weight: 640;
}
.ns-menu {
  position: absolute;
  top: 40px;
  right: 0;
  min-width: 168px;
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: 12px;
  box-shadow: var(--shadow-panel);
  padding: 6px;
  z-index: 20;
}
.ns-menu-head {
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 7px 10px 9px;
  border-bottom: 1px solid var(--color-rule);
  margin-bottom: 4px;
}
.ns-menu-head strong { font-size: 13.5px; color: var(--color-ink); }
.ns-menu-head span { font-size: 11.5px; color: var(--color-ink-3); }
.ns-menu button {
  width: 100%;
  text-align: left;
  border: 0;
  background: none;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
  color: var(--color-ink-2);
  cursor: pointer;
}
.ns-menu button:hover { background: var(--color-paper-3); color: var(--color-danger); }
.ns-main { overflow-y: auto; }
.ns-container { max-width: 880px; margin: 0 auto; padding: 18px 20px 60px; }

@media (max-width: 560px) {
  .ns-k-txt { display: none; }
  .ns-container { padding: 14px 14px 48px; }
}
</style>
