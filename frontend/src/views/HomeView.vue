<script setup lang="ts">
// 首页 Hub(对象驱动):接下来提示 + 我的账号/草稿入口 + 博主档案卡片墙。
// 数据用 store 现有的 bloggers/myAccounts/草稿(当前平台;跨平台合并在 UI·9)。每张卡按 platform 打标签。
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import type { BloggerProfile } from '../api/types'
import { bloggers, myAccounts, visibleXhsPackages } from '../composables/useWorkspaceStore'

const router = useRouter()
const benchmarks = computed(() => bloggers.value.filter((b) => b.account_type !== 'mine'))
const distilledCount = computed(() => benchmarks.value.filter((b) => b.last_distilled_at).length)
const draftCount = computed(() => visibleXhsPackages.value.length)
const accountCount = computed(() => myAccounts.value.length)

// 「接下来」按当前状态给一句提示 + 一个主行动。
const nextStep = computed(() => {
  if (!benchmarks.value.length) return { text: '先加一个想学的对标博主,开始你的第一次创作。', cta: '加对标博主', act: () => router.push({ name: 'find' }) }
  if (distilledCount.value === 0) return { text: '已有对标博主,给它建档蒸馏出创作画像。', cta: '去建档', act: () => openBlogger(benchmarks.value[0], 'dossier') }
  const parts = [`${distilledCount.value} 个博主已出画像`]
  if (draftCount.value) parts.push(`${draftCount.value} 篇草稿`)
  return { text: parts.join(' · '), cta: '开始创作', act: () => router.push({ name: 'create' }) }
})

function openBlogger(b: BloggerProfile, view: 'dossier' | 'analysis') {
  router.push({ name: 'blogger', params: { id: b.id }, query: { view } })
}
function createWith(b: BloggerProfile) {
  router.push({ name: 'create', query: { blogger: b.id } })
}
function openAccount() {
  const a = myAccounts.value[0] // TODO UI·5:多账号时给一个选择/列表,现取第一个
  if (a) router.push({ name: 'account', params: { id: a.id } })
}
function platMeta(p: string) {
  return p === 'douyin' ? { name: '抖音', dot: '#1c2024' } : { name: '小红书', dot: '#e24b4a' }
}
</script>

<template>
  <section class="home">
    <!-- 接下来 -->
    <div class="hb-next">
      <span class="hb-next-ico" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
      </span>
      <div class="hb-next-txt">
        <strong>接下来</strong>
        <p>{{ nextStep.text }}</p>
      </div>
      <button type="button" class="hb-next-btn" @click="nextStep.act()">{{ nextStep.cta }}</button>
    </div>

    <!-- 我的账号 / 发布草稿 -->
    <div class="hb-tiles">
      <button type="button" class="hb-tile" :class="{ dim: !accountCount }" @click="openAccount">
        <svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="8" r="4" /><path d="M4 21c0-4 4-6 8-6s8 2 8 6" /></svg>
        <span class="hb-tile-label">我的账号</span>
        <span class="hb-tile-count">{{ accountCount }} 个</span>
      </button>
      <button type="button" class="hb-tile" @click="router.push({ name: 'drafts' })">
        <svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" /></svg>
        <span class="hb-tile-label">发布草稿</span>
        <span class="hb-tile-count">{{ draftCount }} 篇</span>
      </button>
      <!-- 公众号本轮独立不动,仍走旧壳;从首页留一个入口,别把它孤立了。 -->
      <button type="button" class="hb-tile" @click="router.push({ name: 'workspace', params: { platform: 'wechat', tab: 'brief' } })">
        <svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 8v4l3 2" /></svg>
        <span class="hb-tile-label">公众号早报</span>
        <span class="hb-tile-count">进入 →</span>
      </button>
    </div>

    <!-- 博主档案 -->
    <div class="hb-sec">博主档案</div>
    <div class="hb-wall">
      <article v-for="b in benchmarks" :key="b.id" class="bcard">
        <button type="button" class="bcard-head" @click="openBlogger(b, 'dossier')">
          <span class="bcard-avatar" :class="{ lit: b.last_distilled_at }">{{ (b.display_name || '?').slice(0, 1) }}</span>
          <span class="bcard-id">
            <span class="bcard-name">{{ b.display_name }}</span>
            <span class="bcard-meta">{{ b.niche || '未设置领域' }} · {{ b.last_distilled_at ? '已出画像' : '未蒸馏' }}</span>
          </span>
          <span class="bcard-plat">
            <span class="bcard-dot" :style="{ background: platMeta(b.platform).dot }"></span>{{ platMeta(b.platform).name }}
          </span>
        </button>
        <div class="bcard-chips">
          <button type="button" @click="openBlogger(b, 'dossier')">档案</button>
          <button type="button" @click="openBlogger(b, 'analysis')">分析</button>
          <button type="button" class="lit" @click="createWith(b)">用它创作</button>
        </div>
      </article>

      <button type="button" class="bcard-add" @click="router.push({ name: 'find' })">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
        加对标博主
      </button>
    </div>
  </section>
</template>

<style scoped>
.hb-next {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--color-accent-tint);
  border: 1px solid var(--color-accent-soft-bd);
  border-radius: 12px;
  padding: 12px 14px;
  margin-bottom: 16px;
}
.hb-next-ico { color: var(--color-accent); flex: 0 0 auto; display: inline-flex; }
.hb-next-txt { flex: 1; min-width: 0; }
.hb-next-txt strong { display: block; font-size: 14px; font-weight: 640; color: var(--color-accent-ink); }
.hb-next-txt p { margin: 1px 0 0; font-size: 13px; color: var(--color-accent-ink); }
.hb-next-btn {
  flex: 0 0 auto;
  border: 1px solid var(--color-accent-soft-bd);
  background: var(--color-surface);
  color: var(--color-accent-ink);
  border-radius: 8px;
  padding: 6px 13px;
  font-size: 13px;
  cursor: pointer;
}
.hb-next-btn:hover { border-color: var(--color-accent); }

.hb-tiles {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 10px;
  margin-bottom: 18px;
}
.hb-tile {
  display: flex;
  align-items: center;
  gap: 10px;
  text-align: left;
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-lg);
  padding: 13px 15px;
  cursor: pointer;
  color: var(--color-ink-2);
  transition: border-color 120ms var(--ease-out);
}
.hb-tile:hover { border-color: var(--color-accent-soft-bd); }
.hb-tile.dim { opacity: 0.6; cursor: default; }
.hb-tile.dim:hover { border-color: var(--color-rule); }
.hb-tile-label { font-size: 13.5px; font-weight: 600; color: var(--color-ink); }
.hb-tile-count { margin-left: auto; font-size: 12px; color: var(--color-ink-3); }

.hb-sec { font-size: 13px; color: var(--color-ink-3); margin: 2px 2px 9px; }
.hb-wall {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 10px;
}
.bcard {
  display: flex;
  flex-direction: column;
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-lg);
  padding: 13px;
}
.bcard-head {
  display: flex;
  align-items: center;
  gap: 9px;
  border: 0;
  background: none;
  cursor: pointer;
  padding: 0;
  margin-bottom: 10px;
  text-align: left;
}
.bcard-avatar {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--color-paper-3);
  color: var(--color-ink-2);
  font-size: 14px;
  font-weight: 600;
  flex: 0 0 auto;
}
.bcard-avatar.lit { background: var(--color-accent-soft); color: var(--color-accent-ink); }
.bcard-id { flex: 1; min-width: 0; }
.bcard-name { display: block; font-size: 14px; font-weight: 620; color: var(--color-ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.bcard-meta { display: block; margin-top: 1px; font-size: 12px; color: var(--color-ink-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.bcard-plat {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--color-ink-2);
  background: var(--color-paper-3);
  border-radius: 999px;
  padding: 2px 8px;
}
.bcard-dot { width: 6px; height: 6px; border-radius: 50%; }
.bcard-chips { display: flex; gap: 6px; }
.bcard-chips button {
  border: 0;
  background: var(--color-paper-3);
  color: var(--color-ink-2);
  border-radius: 7px;
  padding: 3px 10px;
  font-size: 12px;
  cursor: pointer;
}
.bcard-chips button:hover { background: var(--color-rule); }
.bcard-chips button.lit { background: var(--color-accent-soft); color: var(--color-accent-ink); }
.bcard-chips button.lit:hover { background: var(--color-accent-soft-bd); }
.bcard-add {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border: 1px dashed var(--color-rule-strong);
  background: none;
  border-radius: var(--radius-lg);
  color: var(--color-ink-2);
  font-size: 13px;
  cursor: pointer;
  min-height: 92px;
}
.bcard-add:hover { border-color: var(--color-accent-soft-bd); color: var(--color-accent-ink); }
</style>
