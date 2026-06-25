<script setup lang="ts">
// 概览:一段引导说明 —— 先讲(可选)录入账号,再用一条「编号流程线」把功能串起来,每步展开细分能力。
// 各步可点击跳转。Hallmark redesign:保留路由/文案意图/设计 token,只重做视觉结构(居中 + 编号流程 + 子项)。
import { useRoute, useRouter } from 'vue-router'

import NavIcon from '../components/NavIcon.vue'
import {
  currentMyAccount,
  currentSocialPlatformName,
  hasMyAccount,
  isSocialPlatform,
  currentSocialTab,
  openCreateMyAccountModal
} from '../composables/useWorkspaceStore'

const route = useRoute()
const router = useRouter()

function goTab(tab: string) {
  const platform = route.params.platform as string
  if (platform) router.push({ name: 'workspace', params: { platform, tab } })
}

const steps = [
  {
    n: '01',
    icon: 'search',
    title: '找对标博主',
    tab: 'find',
    desc: '不知道学谁？把方向交给平台，挑出真正值得学的号。',
    points: [
      '智能推荐：填领域和目标，按方向契合 / 活跃度 / 体量综合打分排序',
      '指定评估：已有心仪的号，贴主页或搜名字，直接看它值不值得学',
      '关键词搜号：用昵称、赛道关键词直接搜'
    ]
  },
  {
    n: '02',
    icon: 'funnel',
    title: '学透对标',
    tab: 'collect',
    desc: '把他的爆款拆开，沉淀成一份你能反复用的「打法」。',
    points: [
      '采集爆款：高赞优先或最新，图文 + 视频都能采，视频自动取字幕 / 转写',
      '蒸馏 Skill：选题、标题结构、语气、节奏，提炼成可复用的打法 Skill',
      '笔记池：增量更新、自选选材、下架对账，贵的活只花在新笔记上'
    ]
  },
  {
    n: '03',
    icon: 'sparkles',
    title: '用他的打法创作',
    tab: 'packages',
    desc: '套用 Skill，产出你能直接发的内容。',
    points: [
      '选题策划：基于 Skill 给一批可执行的选题方案',
      '一键成稿：图文 / 口播脚本一次产出，自带质量自检',
      '平台合规：自动规避限流词，标注需手动调整的残留',
      '绑定账号：创作时选目标账号，发布后回填，进效果看板统计'
    ]
  },
  {
    n: '04',
    icon: 'target',
    title: '诊断差距 & 持续提升',
    tab: 'audit',
    desc: '看清差在哪、补在哪，再看到自己的真实成长。',
    points: [
      '对标诊断：和对标博主逐项比，指出短板 + 立刻能做的动作',
      'Skill 优化：用真笔记把 Skill 练得更像本人，给前后对比和是否采纳建议',
      '效果看板：涨粉、发布转化、省时、相似度趋近，一页看成长'
    ]
  }
]
</script>

<template>
  <section v-if="isSocialPlatform && currentSocialTab === 'overview'" class="overview">
    <header class="ov-head">
      <p class="ov-kicker">{{ currentSocialPlatformName }} 内容工作台</p>
      <h1 class="ov-title">一个人，做出一个团队的内容产能</h1>
      <p class="ov-lead">把你想学的{{ currentSocialPlatformName }}头部博主，变成你自己能日更的内容，还告诉你差在哪、怎么补。</p>
    </header>

    <!-- 录入账号:未录入→引导卡+按钮;已录入→只显示账号,无按钮 -->
    <div v-if="!hasMyAccount" class="ov-account ov-account-cta">
      <NavIcon name="user" />
      <div class="ov-account-text">
        <strong>先录入你的账号（可选）</strong>
        <span>让对标更准、还能看到自己的成长。只想产出内容？直接从下面「找对标」开始也行。</span>
      </div>
      <button type="button" class="primary" @click="openCreateMyAccountModal">录入账号</button>
    </div>
    <div v-else class="ov-account ov-account-done">
      <div class="ov-avatar">{{ (currentMyAccount?.display_name || '我').slice(0, 1) }}</div>
      <div class="ov-account-text">
        <strong>我的账号 · {{ currentMyAccount?.display_name }}</strong>
        <span>{{ currentMyAccount?.follower_count || 0 }} 粉丝 · 已采 {{ currentMyAccount?.sample_count || 0 }} 篇 · 对标 / 诊断都会用它</span>
      </div>
      <NavIcon name="check" class="ov-done-icon" />
    </div>

    <p class="ov-sub">从找到对标，到练成自己的产能 —— 四步走：</p>

    <ol class="ov-flow">
      <li v-for="step in steps" :key="step.tab" class="ov-step">
        <span class="ov-num" aria-hidden="true">{{ step.n }}</span>
        <div class="ov-step-main">
          <button type="button" class="ov-step-head" @click="goTab(step.tab)">
            <NavIcon :name="step.icon" class="ov-step-icon" />
            <span class="ov-step-title">{{ step.title }}</span>
            <span class="ov-step-go">进入<NavIcon name="arrow-right" /></span>
          </button>
          <p class="ov-step-desc">{{ step.desc }}</p>
          <ul class="ov-points">
            <li v-for="(p, j) in step.points" :key="j">{{ p }}</li>
          </ul>
        </div>
      </li>
    </ol>
  </section>
</template>

<style scoped>
/* Hallmark · redesign · genre: editorial · 流程脊线 macrostructure
 * pre-emit critique: P5 H5 E4 S4 R5 V4
 * contrast: pass · mobile: 320/375/414/768 single-column
 */
.overview {
  max-width: 820px;
  margin: 0 auto;            /* 居中:不再贴左侧导航栏 */
  padding: 8px 24px 48px;
}
.ov-head {
  text-align: center;
  max-width: 620px;
  margin: 0 auto 28px;
}
.ov-kicker {
  font-size: 0.78rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--color-accent, #2563eb);
  margin: 0 0 10px;
  font-weight: 600;
}
.ov-title {
  font-size: clamp(1.5rem, 1.1rem + 1.6vw, 2.05rem);
  line-height: 1.2;
  letter-spacing: -0.01em;
  margin: 0 0 10px;
  overflow-wrap: anywhere;
}
.ov-lead {
  color: var(--color-ink-2, #6b7280);
  line-height: 1.75;
  margin: 0;
}
.ov-account {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 14px;
  margin-bottom: 28px;
}
.ov-account-cta {
  background: color-mix(in srgb, var(--color-accent, #2563eb) 8%, transparent);
  border: 1px solid color-mix(in srgb, var(--color-accent, #2563eb) 30%, transparent);
}
.ov-account-done {
  background: var(--color-field, #fff);
  border: 1px solid var(--color-field-border, #c8ced4);
}
.ov-account-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.ov-account-text strong { font-weight: 600; }
.ov-account-text span {
  font-size: 0.85rem;
  color: var(--color-ink-2, #6b7280);
}
.ov-account .primary {
  margin-left: auto;
  white-space: nowrap;
}
.ov-avatar {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: var(--color-paper-3, #eef0f3);
  color: var(--color-ink-2, #6b7280);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  flex: none;
}
.ov-done-icon {
  margin-left: auto;
  color: var(--color-ok, #2e9e5b);
}
.ov-sub {
  color: var(--color-ink-2, #6b7280);
  font-size: 0.92rem;
  margin: 0 0 18px;
}

/* 编号流程脊线:左侧大编号 + 贯穿竖线,区别于「四张一样的圆角卡片」 */
.ov-flow {
  list-style: none;
  margin: 0;
  padding: 0;
  position: relative;
}
.ov-step {
  display: grid;
  grid-template-columns: 56px 1fr;
  gap: 16px;
  position: relative;
  padding-bottom: 26px;
}
/* 竖线:连接相邻编号,最后一步不画 */
.ov-step:not(:last-child)::before {
  content: '';
  position: absolute;
  left: 27px;
  top: 46px;
  bottom: -4px;
  width: 2px;
  background: var(--color-field-border, #d6dbe1);
}
.ov-num {
  width: 56px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--color-accent, #2563eb);
  background: color-mix(in srgb, var(--color-accent, #2563eb) 9%, var(--color-paper, #fff));
  border-radius: 12px;
  z-index: 1;
}
.ov-step-main { min-width: 0; }
.ov-step-head {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  padding: 4px 0;
  background: none;
  border: none;
  cursor: pointer;
  color: var(--color-ink, #1f2430);
}
.ov-step-icon { color: var(--color-accent, #2563eb); flex: none; }
.ov-step-title {
  font-size: 1.12rem;
  font-weight: 700;
  letter-spacing: -0.005em;
}
.ov-step-go {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 0.82rem;
  color: var(--color-ink-3, #9aa0a6);
  opacity: 0;
  transform: translateX(-4px);
  transition: opacity 0.15s, transform 0.15s, color 0.15s;
  white-space: nowrap;
}
.ov-step-head:hover .ov-step-title { color: var(--color-accent, #2563eb); }
.ov-step-head:hover .ov-step-go,
.ov-step-head:focus-visible .ov-step-go {
  opacity: 1;
  transform: translateX(0);
  color: var(--color-accent, #2563eb);
}
.ov-step-head:focus-visible {
  outline: 2px solid var(--color-accent, #2563eb);
  outline-offset: 3px;
  border-radius: 6px;
}
.ov-step-desc {
  color: var(--color-ink-2, #4b5563);
  line-height: 1.6;
  margin: 4px 0 10px;
}
.ov-points {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.ov-points li {
  position: relative;
  padding-left: 18px;
  font-size: 0.9rem;
  line-height: 1.6;
  color: var(--color-ink-2, #6b7280);
}
/* 自绘短横作为子项标记:比圆点更克制、不那么「模板感」 */
.ov-points li::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0.66em;
  width: 9px;
  height: 2px;
  background: var(--color-accent, #2563eb);
  opacity: 0.6;
}

@media (max-width: 560px) {
  .overview { padding: 4px 16px 40px; }
  .ov-step { grid-template-columns: 40px 1fr; gap: 12px; }
  .ov-step:not(:last-child)::before { left: 19px; }
  .ov-num { width: 40px; height: 34px; font-size: 1.2rem; border-radius: 10px; }
  .ov-step-go { opacity: 1; transform: none; }  /* 触屏无 hover,直接显示「进入」 */
}
</style>
