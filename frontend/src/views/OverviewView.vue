<script setup lang="ts">
// 概览:一段引导说明 —— 先讲(可选)录入账号,再用一条线把功能串起来。各步可点击跳转。
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
  { icon: 'search', title: '找对标博主', tab: 'find', desc: '不知道学谁？填几句话(领域、想做什么),平台帮你找到值得学的号并打分。' },
  { icon: 'funnel', title: '学透对标', tab: 'collect', desc: '采集他的爆款笔记,提炼成一份可复用的「打法 Skill」——选题、标题、结构、语气都在里面。' },
  { icon: 'sparkles', title: '用他的打法创作', tab: 'packages', desc: '套用 Skill,一键产出你能直接发的图文 / 脚本,自带质量自检和限流词规避。' },
  { icon: 'target', title: '诊断差距 & 持续提升', tab: 'audit', desc: '拿你的账号和对标比,指出短板和能立刻做的动作;再把 Skill 练得更像,看到真实成长。' }
]
</script>

<template>
  <section v-if="isSocialPlatform && currentSocialTab === 'overview'" class="overview">
    <h1 class="ov-title">一个人，做出一个团队的内容产能</h1>
    <p class="ov-lead">把你「想学的{{ currentSocialPlatformName }}头部博主」变成「你自己能日更的内容」，还告诉你差在哪、怎么补。</p>

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

    <p class="ov-sub">接着，这条线就是平台的用法：</p>
    <div class="ov-flow">
      <template v-for="(step, i) in steps" :key="step.tab">
        <button type="button" class="ov-step" @click="goTab(step.tab)">
          <NavIcon :name="step.icon" />
          <span class="ov-step-body">
            <strong>{{ step.title }}</strong>
            <small>{{ step.desc }}</small>
          </span>
          <NavIcon name="arrow-right" class="ov-step-go" />
        </button>
        <div v-if="i < steps.length - 1" class="ov-chevron"><NavIcon name="chevron-down" /></div>
      </template>
    </div>
  </section>
</template>

<style scoped>
.overview {
  max-width: 760px;
}
.ov-title {
  font-size: 1.6rem;
  margin: 0 0 6px;
}
.ov-lead {
  color: var(--color-ink-2, #6b7280);
  line-height: 1.7;
  margin: 0 0 18px;
}
.ov-account {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  border-radius: 14px;
  margin-bottom: 18px;
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
.ov-account-text strong {
  font-weight: 600;
}
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
  margin: 0 0 10px;
}
.ov-flow {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.ov-step {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  width: 100%;
  text-align: left;
  padding: 14px;
  border: 1px solid var(--color-field-border, #c8ced4);
  border-radius: 14px;
  background: var(--color-field, #fff);
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.ov-step:hover {
  border-color: var(--color-accent, #2563eb);
  box-shadow: var(--ring-accent, 0 0 0 3px rgba(37, 99, 235, 0.12));
}
.ov-step-body {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}
.ov-step-body strong {
  font-weight: 600;
}
.ov-step-body small {
  color: var(--color-ink-2, #6b7280);
  line-height: 1.6;
  font-size: 0.88rem;
}
.ov-step-go {
  margin-left: auto;
  color: var(--color-ink-3, #9aa0a6);
  flex: none;
}
.ov-chevron {
  text-align: center;
  color: var(--color-ink-3, #9aa0a6);
  line-height: 1;
}
</style>
