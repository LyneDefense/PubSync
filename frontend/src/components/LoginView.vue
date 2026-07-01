<script setup lang="ts">
// 登录页:左品牌叙事 + 右登录表单。接口保持不变(App.vue / AdminApp.vue 共用):
// props(loading/message) + emit('submit', {username, password})。其余(密码显隐/主题色/保持登录/本地校验)为组件内本地态。
import { computed, reactive, ref } from 'vue'

const props = defineProps<{ loading: boolean; message: string }>()
const emit = defineEmits<{ (e: 'submit', credentials: { username: string; password: string }): void }>()

const form = reactive({ username: '', password: '' })
const showPassword = ref(false)
const keepLoggedIn = ref(true)
const forgotHint = ref(false)
const localError = ref('')
const theme = ref<'green' | 'warm'>('green')

// 两套主题色板(登录页自带,不依赖全局 accent)。以本地 CSS 变量注入根节点,scoped 样式引用。
const PALETTES: Record<'green' | 'warm', Record<string, string>> = {
  green: {
    '--accent': '#0d7361', '--accent-press': '#0a5e4f', '--accent-soft': '#eaf3ee',
    '--accent-ink': '#0d5a4a', '--accent-soft-bd': '#cfe6db', '--accent-tint': '#f1f8f4',
    '--accent-ring': 'rgba(13,115,97,.15)', '--accent-shadow': 'rgba(13,115,97,.4)',
    '--panel1': '#073028', '--panel2': '#0a4438', '--panelglow': '#0d6a58',
    '--glow1': 'rgba(58,214,170,.34)', '--glow2': 'rgba(13,120,100,.5)', '--spark': '#4fddb4'
  },
  warm: {
    '--accent': '#bd5b34', '--accent-press': '#a04a28', '--accent-soft': '#f6ece4',
    '--accent-ink': '#9a4f2c', '--accent-soft-bd': '#ecd8c8', '--accent-tint': '#fbf4ee',
    '--accent-ring': 'rgba(189,91,52,.15)', '--accent-shadow': 'rgba(189,91,52,.4)',
    '--panel1': '#2e1408', '--panel2': '#3d1f10', '--panelglow': '#6a3a1c',
    '--glow1': 'rgba(230,164,104,.30)', '--glow2': 'rgba(120,70,30,.5)', '--spark': '#e6a468'
  }
}
const themeVars = computed(() => PALETTES[theme.value])

const displayError = computed(() => props.message || localError.value)

const PIPELINE = [
  { key: 'collect', label: '采集蒸馏', sub: '对标 → Skill' },
  { key: 'diagnose', label: '账号诊断', sub: '逐维度找差距' },
  { key: 'create', label: 'AI 创作', sub: '生成 → 发布' }
]
const PROOF = ['质量自检', '限流规避', '全平台适配']

function onSubmit() {
  if (!form.username.trim() || !form.password) {
    localError.value = '请输入用户名和密码。'
    return
  }
  localError.value = ''
  emit('submit', { username: form.username, password: form.password })
}
</script>

<template>
  <main class="login-shell" :style="themeVars">
    <!-- 左:品牌叙事 -->
    <aside class="login-brand">
      <div class="brand-grid" aria-hidden="true"></div>
      <div class="brand-glow g1" aria-hidden="true"></div>
      <div class="brand-glow g2" aria-hidden="true"></div>

      <div class="brand-inner">
        <div class="brand-top ri" style="--d: 0ms">
          <span class="brand-badge" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M12 3l8 4-8 4-8-4 8-4z" /><path d="M4 12l8 4 8-4" /><path d="M4 16.5l8 4 8-4" /></svg>
          </span>
          <div>
            <strong>PubSync</strong>
            <span>对标驱动的内容创作引擎</span>
          </div>
        </div>

        <span class="brand-capsule ri" style="--d: 80ms"><i class="spark-dot"></i>适配全平台 · 一套创作流水线</span>

        <h1 class="brand-headline ri" style="--d: 140ms">一个人，运营出<br />一个团队的内容产能</h1>

        <p class="brand-desc ri" style="--d: 200ms">
          把「拆解对标博主 → 诊断账号 → AI 创作 → 多平台发布」串成一条流水线。从找选题到出稿，自动化搞定。
        </p>

        <div class="pipeline ri" style="--d: 260ms">
          <div class="pipe-line" aria-hidden="true"><i class="flow-dot"></i></div>
          <div v-for="(n, i) in PIPELINE" :key="n.key" class="pipe-node" :style="{ '--fd': i * 400 + 'ms' }">
            <span class="pn-ico" aria-hidden="true">
              <svg v-if="n.key === 'collect'" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5h16l-6 7v6l-4-2v-4z" /></svg>
              <svg v-else-if="n.key === 'diagnose'" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12h4l2 6 4-15 2 9h6" /></svg>
              <svg v-else viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.8 4.2L18 9l-4.2 1.8L12 15l-1.8-4.2L6 9l4.2-1.8z" /></svg>
            </span>
            <strong>{{ n.label }}</strong>
            <span>{{ n.sub }}</span>
          </div>
        </div>

        <div class="brand-proof ri" style="--d: 320ms">
          <span v-for="p in PROOF" :key="p"><i aria-hidden="true">✓</i>{{ p }}</span>
        </div>

        <p class="brand-copy">© 2025 PubSync · 内容创作工作台</p>
      </div>
    </aside>

    <!-- 右:登录表单 -->
    <section class="login-form">
      <div class="theme-dots" role="group" aria-label="主题色">
        <button type="button" class="td green" :class="{ on: theme === 'green' }" aria-label="墨绿主题" @click="theme = 'green'"></button>
        <button type="button" class="td warm" :class="{ on: theme === 'warm' }" aria-label="暖陶主题" @click="theme = 'warm'"></button>
      </div>

      <form class="form-inner" @submit.prevent="onSubmit">
        <p class="eyebrow"><span class="eb-line"></span>欢迎回来</p>
        <h2 class="form-title">登录工作台</h2>
        <p class="form-sub">输入你的账号，继续采集、诊断与创作。</p>

        <p v-if="displayError" class="error-bar" role="alert">
          <span class="eb-ico" aria-hidden="true">!</span>{{ displayError }}
        </p>

        <label class="field">
          <span class="field-label">用户名</span>
          <span class="input-wrap">
            <svg class="in-ico" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="8" r="4" /><path d="M4 20c0-3.3 3.6-6 8-6s8 2.7 8 6" /></svg>
            <input v-model="form.username" type="text" autocomplete="username" placeholder="输入用户名" />
          </span>
        </label>

        <label class="field">
          <span class="field-label-row">
            <span class="field-label">密码</span>
            <button type="button" class="link-btn" @click="forgotHint = !forgotHint">忘记密码？</button>
          </span>
          <span class="input-wrap">
            <svg class="in-ico" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4" y="10" width="16" height="10" rx="2" /><path d="M8 10V7a4 4 0 018 0v3" /></svg>
            <input v-model="form.password" :type="showPassword ? 'text' : 'password'" autocomplete="current-password" placeholder="输入密码" />
            <button type="button" class="eye" :aria-label="showPassword ? '隐藏密码' : '显示密码'" @click="showPassword = !showPassword">
              <svg v-if="showPassword" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5c5 0 9 4.5 10 7-1 2.5-5 7-10 7S3 14.5 2 12c1-2.5 5-7 10-7z" /><circle cx="12" cy="12" r="3" /></svg>
              <svg v-else viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3l18 18" /><path d="M10.6 6.2A9.7 9.7 0 0112 6c5 0 9 4.5 10 7a13 13 0 01-2.4 3.2M6.5 7.6C4.2 9 2.7 11 2 12c1 2.5 5 7 10 7a9.6 9.6 0 004.2-1" /><path d="M9.9 10.1a3 3 0 004 4" /></svg>
            </button>
          </span>
          <span v-if="forgotHint" class="forgot-hint">账号与密码由管理员开通 / 重置，请联系管理员。</span>
        </label>

        <label class="keep">
          <input v-model="keepLoggedIn" type="checkbox" />
          <span class="kbox" aria-hidden="true"></span>
          保持登录状态
        </label>

        <button type="submit" class="submit" :disabled="loading">
          <span v-if="loading" class="spin" aria-hidden="true"></span>
          {{ loading ? '登录中…' : '登录' }}
          <svg v-if="!loading" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14" /><path d="M13 6l6 6-6 6" /></svg>
        </button>

        <p class="tip-bar">
          <span class="tip-ico" aria-hidden="true">i</span>
          首次使用请联系管理员开通账号；管理员请从 <a href="admin.html">管理后台</a> 登录。
        </p>
        <p class="foot-help">需要帮助？请联系管理员开通或重置账号。</p>
      </form>
    </section>
  </main>
</template>

<style scoped>
.login-shell {
  display: flex;
  min-height: 100vh;
  font-family: 'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif;
  color: #161b19;
  background: #fbfcfb;
}

/* ============ 左:品牌叙事 ============ */
.login-brand {
  flex: 1.08;
  position: relative;
  overflow: hidden;
  background: linear-gradient(157deg, var(--panel1), var(--panel2) 55%, var(--panel1));
  color: #e8f3ef;
}
.brand-glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
  pointer-events: none;
}
.brand-glow.g1 {
  width: 420px;
  height: 420px;
  top: -120px;
  right: -80px;
  background: radial-gradient(circle, var(--glow1), transparent 70%);
  animation: glowdrift 22s ease-in-out infinite;
}
.brand-glow.g2 {
  width: 360px;
  height: 360px;
  bottom: -100px;
  left: -60px;
  background: radial-gradient(circle, var(--glow2), transparent 70%);
  animation: glowdrift2 26s ease-in-out infinite;
}
.brand-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.05) 1px, transparent 1px);
  background-size: 44px 44px;
  -webkit-mask-image: radial-gradient(circle at 30% 30%, #000 10%, transparent 75%);
  mask-image: radial-gradient(circle at 30% 30%, #000 10%, transparent 75%);
}
.brand-inner {
  position: relative;
  z-index: 1;
  height: 100%;
  box-sizing: border-box;
  padding: 52px clamp(40px, 6vw, 76px);
  display: flex;
  flex-direction: column;
  gap: 22px;
}
.brand-top {
  display: flex;
  align-items: center;
  gap: 14px;
}
.brand-badge {
  display: grid;
  place-items: center;
  width: 46px;
  height: 46px;
  border-radius: 13px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.14);
  color: var(--spark);
  flex: 0 0 auto;
}
.brand-top strong {
  display: block;
  font-size: 20px;
  font-weight: 680;
  letter-spacing: 0.01em;
}
.brand-top span {
  font-size: 12.5px;
  color: rgba(232, 243, 239, 0.65);
}
.brand-capsule {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  align-self: flex-start;
  padding: 7px 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  font-size: 12.5px;
  color: rgba(232, 243, 239, 0.9);
}
.spark-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--spark);
  box-shadow: 0 0 10px var(--spark);
}
.brand-headline {
  margin: 4px 0 0;
  font-size: clamp(28px, 3.2vw, 38px);
  font-weight: 720;
  line-height: 1.25;
  letter-spacing: -0.01em;
  color: #fff;
}
.brand-desc {
  margin: 0;
  max-width: 440px;
  font-size: 14px;
  line-height: 1.75;
  color: rgba(232, 243, 239, 0.72);
}
.pipeline {
  position: relative;
  margin-top: 8px;
  display: flex;
  gap: 10px;
  padding: 22px 18px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(6px);
  max-width: 480px;
}
.pipe-line {
  position: absolute;
  top: 42px;
  left: 18%;
  right: 18%;
  height: 1px;
  background: rgba(255, 255, 255, 0.18);
}
.flow-dot {
  position: absolute;
  top: -2px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--spark);
  box-shadow: 0 0 10px var(--spark);
  animation: flow 3.4s linear infinite;
}
.pipe-node {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 5px;
}
.pn-ico {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 11px;
  background: rgba(79, 221, 180, 0.14);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: var(--spark);
  animation: floaty 4s ease-in-out infinite;
  animation-delay: var(--fd);
}
.pipe-node strong {
  font-size: 13px;
  font-weight: 620;
  color: #eafaf4;
}
.pipe-node span {
  font-size: 11px;
  color: rgba(232, 243, 239, 0.55);
}
.brand-proof {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 18px;
  margin-top: 2px;
}
.brand-proof span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
  color: rgba(232, 243, 239, 0.7);
}
.brand-proof i {
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(79, 221, 180, 0.18);
  color: var(--spark);
  font-size: 11px;
  font-weight: 800;
  font-style: normal;
}
.brand-copy {
  margin: auto 0 0;
  font-size: 11.5px;
  color: rgba(232, 243, 239, 0.4);
}

/* ============ 右:表单 ============ */
.login-form {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
}
.theme-dots {
  position: absolute;
  top: 24px;
  right: 28px;
  display: flex;
  gap: 8px;
}
.td {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid transparent;
  cursor: pointer;
  padding: 0;
  transition: transform 120ms ease, border-color 120ms ease;
}
.td.green {
  background: #0d7361;
}
.td.warm {
  background: #bd5b34;
}
.td.on {
  border-color: #fff;
  box-shadow: 0 0 0 1.5px currentColor;
  color: var(--accent);
}
.td:hover {
  transform: scale(1.1);
}
.form-inner {
  width: 100%;
  max-width: 376px;
}
.eyebrow {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 0 12px;
  font-size: 13px;
  font-weight: 600;
  color: var(--accent-ink);
}
.eb-line {
  width: 22px;
  height: 2px;
  border-radius: 2px;
  background: var(--accent);
}
.form-title {
  margin: 0 0 8px;
  font-size: 28px;
  font-weight: 720;
  letter-spacing: -0.01em;
  color: #161b19;
}
.form-sub {
  margin: 0 0 22px;
  font-size: 13.5px;
  color: #5a655f;
}
.error-bar {
  display: flex;
  align-items: center;
  gap: 9px;
  margin: 0 0 16px;
  padding: 11px 14px;
  border-radius: 10px;
  background: #fdecec;
  border: 1px solid #f4d4d4;
  color: #a5342a;
  font-size: 13px;
}
.eb-ico {
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #a5342a;
  color: #fff;
  font-size: 12px;
  font-weight: 800;
  flex: 0 0 auto;
}
.field {
  display: block;
  margin-bottom: 16px;
}
.field-label,
.field-label-row {
  display: block;
  margin-bottom: 7px;
  font-size: 13px;
  font-weight: 600;
  color: #3a4640;
}
.field-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.link-btn {
  border: 0;
  background: none;
  padding: 0;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--accent);
  cursor: pointer;
}
.input-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 50px;
  padding: 0 14px;
  border: 1px solid #e4e8e6;
  border-radius: 12px;
  background: #f4f6f5;
  transition: background 140ms ease, border-color 140ms ease, box-shadow 140ms ease;
}
.input-wrap:focus-within {
  background: #fff;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-ring);
}
.in-ico {
  flex: 0 0 auto;
  color: #9aa5a1;
}
.input-wrap input {
  flex: 1;
  min-width: 0;
  height: 100%;
  border: 0;
  background: transparent;
  font-size: 14.5px;
  color: #161b19;
  outline: none;
}
.input-wrap input::placeholder {
  color: #9aa5a1;
}
.eye {
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #9aa5a1;
  cursor: pointer;
}
.eye:hover {
  color: #5a655f;
}
.forgot-hint {
  display: block;
  margin-top: 7px;
  font-size: 12px;
  color: #5a655f;
}
.keep {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
  font-size: 13.5px;
  color: #3a4640;
  cursor: pointer;
  user-select: none;
}
.keep input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}
.kbox {
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  width: 19px;
  height: 19px;
  border: 1.5px solid #cdd4d0;
  border-radius: 6px;
  transition: background 120ms ease, border-color 120ms ease;
}
.keep input:checked + .kbox {
  background: var(--accent);
  border-color: var(--accent);
}
.keep input:checked + .kbox::after {
  content: '✓';
  color: #fff;
  font-size: 12px;
  font-weight: 800;
}
.submit {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  height: 50px;
  border: 0;
  border-radius: 12px;
  background: var(--accent);
  color: #fff;
  font-size: 15px;
  font-weight: 650;
  cursor: pointer;
  box-shadow: 0 8px 20px -8px var(--accent-shadow);
  transition: background 140ms ease, box-shadow 140ms ease;
}
.submit:hover:not(:disabled) {
  background: var(--accent-press);
}
.submit:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}
.spin {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.45);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
.tip-bar {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  margin: 20px 0 0;
  padding: 12px 14px;
  border-radius: 10px;
  background: var(--accent-tint);
  border: 1px solid var(--accent-soft-bd);
  font-size: 12.5px;
  line-height: 1.6;
  color: #4a5751;
}
.tip-ico {
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--accent-soft);
  color: var(--accent-ink);
  font-size: 11px;
  font-weight: 800;
  font-style: italic;
}
.tip-bar a {
  color: var(--accent-ink);
  font-weight: 650;
}
.foot-help {
  margin: 14px 0 0;
  text-align: center;
  font-size: 12px;
  color: #9aa5a1;
}

/* ============ 动画 ============ */
@keyframes spin {
  to { transform: rotate(360deg); }
}
@keyframes glowdrift {
  0%, 100% { transform: translate(0, 0); }
  50% { transform: translate(-30px, 24px); }
}
@keyframes glowdrift2 {
  0%, 100% { transform: translate(0, 0); }
  50% { transform: translate(26px, -20px); }
}
@keyframes flow {
  0% { left: 0; opacity: 0; }
  12% { opacity: 1; }
  88% { opacity: 1; }
  100% { left: 100%; opacity: 0; }
}
@keyframes floaty {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-5px); }
}
@keyframes risein {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}
.ri {
  animation: risein 560ms cubic-bezier(0.2, 0.7, 0.2, 1) both;
  animation-delay: var(--d, 0ms);
}

@media (prefers-reduced-motion: reduce) {
  .brand-glow, .flow-dot, .pn-ico, .ri, .spin {
    animation: none;
  }
}

/* ============ 响应式:窄屏隐藏品牌面板,只留表单 ============ */
@media (max-width: 820px) {
  .login-brand {
    display: none;
  }
  .login-form {
    flex: 1;
  }
}
</style>
