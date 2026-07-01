<script setup lang="ts">
// Cadence 落地页(面向内容创作者/运营)。纯展示;复用 main.css 设计变量。(部署路径仍为 /PubSync/,不属品牌名)
// 进入工作台/登录 = 登录入口 login.html(如 /PubSync/login.html)。
const appUrl = `${import.meta.env.BASE_URL || '/'}login.html`
// 检测本地是否已登录:有 token 就把按钮文案换成「进入工作台」,点了直接进工作台(login.html 已登录态直达,跳过登录页)。
// token 失效也无妨:进入后 App 会做 401 处理并退回登录。
const loggedIn = Boolean(window.localStorage.getItem('pubsync_token'))

const valueProps = [
  { t: '不知道写什么', d: '采集对标博主内容,蒸馏成可复用的「创作方法论 Skill」。选题、结构、表达照着打法走,不再拍脑袋。' },
  { t: '写得慢、质量飘', d: 'AI 创作自带质量自检与多轮自我修订,达不到分数线会自动重写,产出稳定不靠运气。' },
  { t: '不知道差在哪', d: '账号诊断:把你的账号和对标账号逐维度对比,指出优势、短板和「立即能做」的增长动作。' },
  { t: '平台限流踩坑', d: '生成时自动规避三平台的限流/违禁词(极限词、医疗功效、诱导营销…),发布更安心。' }
]

const steps = [
  { n: '01', t: '采集 & 蒸馏', d: '采集对标博主的公开内容(图文/视频,支持视频字幕 ASR),提炼出方法论 Skill,沉淀为你的「博主资产」。' },
  { n: '02', t: '诊断', d: '登记「我的账号」后,做对标诊断(我 vs 对标账号逐维度找差距)或单独「诊断我的」账号,拿到可执行结论。' },
  { n: '03', t: '创作 & 发布', d: '基于 Skill 生成文字 / 图文 / 口播 / 视频脚本,自动配图、规避限流词,一键进入草稿箱。' }
]

const platforms = [
  { name: '公众号', d: '每日早报流程化向导:抓新闻 → 勾选 → 生成文章 → 预览/编辑 → 推送草稿箱。' },
  { name: '小红书', d: '博主蒸馏 + 账号诊断 + 对标博主创作,按小红书的内容形态产出。' },
  { name: '抖音', d: '同一套蒸馏/诊断/创作流水线,适配抖音的口播与视频脚本。' }
]

const highlights = [
  { t: '质量保证 harness', d: '生成→校验→修订的闭环 + 确定性质量评分,把"能用"做到"稳定可用"。' },
  { t: '限流词三层防线', d: '提示词规避 + 命中强制重写 + 残留标注,内置词库可在后台扩展。' },
  { t: '思考过程可视化', d: '蒸馏与创作时,实时展示 AI 的分析与优化过程,不再是黑盒。' },
  { t: '独立管理后台', d: '模型 / ASR / 任务队列集中管理,改配置即时生效,无需重新部署。' },
  { t: '费用台账', d: 'TikHub 与大模型花费按工作空间、按渠道清晰记账,成本一目了然。' },
  { t: '多内容形态', d: '纯文字、图文、口播、视频脚本各有专门的创作逻辑,不是一套模板套到底。' }
]
</script>

<template>
  <div class="lp">
    <header class="lp-nav">
      <div class="lp-wrap lp-nav__inner">
        <div class="lp-brand"><strong>Cadence</strong><span>多平台内容自动化</span></div>
        <a class="link-button primary" :href="appUrl">{{ loggedIn ? '进入工作台' : '登录' }}</a>
      </div>
    </header>

    <section class="lp-hero">
      <div class="lp-wrap">
        <span class="lp-badge">公众号 · 小红书 · 抖音</span>
        <h1>一个人,运营出一个团队的内容产能</h1>
        <p class="lp-lead">
          Cadence 把「拆解对标博主 → 诊断账号 → AI 创作 → 多平台发布」串成一条流水线。
          从找选题到出稿,自动化搞定,把时间还给真正重要的事。
        </p>
        <div class="lp-cta">
          <a class="link-button primary lp-cta__main" :href="appUrl">{{ loggedIn ? '进入工作台' : '免费进入工作台' }}</a>
          <a class="link-button" href="#how">看看怎么用</a>
        </div>
        <p v-if="loggedIn" class="lp-note">检测到你已登录,点上方按钮直接进入工作台。</p>
        <p v-else class="lp-note">基于真实采集内容驱动 · 产出自带质量自检 · 自动规避平台限流词</p>
      </div>
    </section>

    <section class="lp-section">
      <div class="lp-wrap">
        <h2 class="lp-h2">把内容创作里最磨人的环节,交给它</h2>
        <div class="lp-grid lp-grid--4">
          <article v-for="v in valueProps" :key="v.t" class="lp-card">
            <h3>{{ v.t }}</h3>
            <p>{{ v.d }}</p>
          </article>
        </div>
      </div>
    </section>

    <section id="how" class="lp-section lp-section--soft">
      <div class="lp-wrap">
        <h2 class="lp-h2">三步,从对标到出稿</h2>
        <div class="lp-grid lp-grid--3">
          <article v-for="s in steps" :key="s.n" class="lp-step">
            <span class="lp-step__n">{{ s.n }}</span>
            <h3>{{ s.t }}</h3>
            <p>{{ s.d }}</p>
          </article>
        </div>
      </div>
    </section>

    <section class="lp-section">
      <div class="lp-wrap">
        <h2 class="lp-h2">一套流水线,覆盖三大平台</h2>
        <div class="lp-grid lp-grid--3">
          <article v-for="p in platforms" :key="p.name" class="lp-card lp-card--platform">
            <span class="lp-pill">{{ p.name }}</span>
            <p>{{ p.d }}</p>
          </article>
        </div>
      </div>
    </section>

    <section class="lp-section lp-section--soft">
      <div class="lp-wrap">
        <h2 class="lp-h2">认真做产出质量的细节</h2>
        <div class="lp-grid lp-grid--3">
          <article v-for="h in highlights" :key="h.t" class="lp-card">
            <h3>{{ h.t }}</h3>
            <p>{{ h.d }}</p>
          </article>
        </div>
      </div>
    </section>

    <section class="lp-section">
      <div class="lp-wrap lp-who">
        <h2 class="lp-h2">谁在用</h2>
        <p>个人博主 · 新媒体运营 · 多账号内容矩阵 —— 想把对标做扎实、把产出做稳定的人。</p>
      </div>
    </section>

    <section class="lp-band">
      <div class="lp-wrap lp-band__inner">
        <div>
          <h2>现在就把内容产能拉满</h2>
          <p>登录即可开始采集、诊断和创作。</p>
        </div>
        <a class="link-button lp-band__btn" :href="appUrl">进入工作台</a>
      </div>
    </section>

    <footer class="lp-footer">
      <div class="lp-wrap lp-footer__inner">
        <span>Cadence · 多平台内容自动化</span>
        <a :href="appUrl">进入工作台</a>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.lp {
  color: var(--color-ink);
  background: var(--color-paper);
}
.lp-wrap {
  width: min(1080px, 92vw);
  margin: 0 auto;
}

.lp-nav {
  position: sticky;
  top: 0;
  z-index: 10;
  border-bottom: var(--rule-hair);
  background: color-mix(in oklab, var(--color-paper), transparent 8%);
  backdrop-filter: saturate(1.2) blur(6px);
}
.lp-nav__inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-sm) 0;
}
.lp-brand {
  display: flex;
  align-items: baseline;
  gap: var(--space-2xs);
}
.lp-brand strong {
  font-family: var(--font-display);
  font-size: var(--text-lg);
}
.lp-brand span {
  color: var(--color-ink-3);
  font-size: var(--text-xs);
}

.lp-hero {
  padding: clamp(48px, 9vw, 110px) 0 clamp(40px, 7vw, 84px);
  background:
    radial-gradient(1200px 360px at 18% -10%, var(--color-accent-soft), transparent 70%),
    var(--color-paper);
  text-align: center;
}
.lp-badge {
  display: inline-block;
  padding: 4px 14px;
  border: 1px solid var(--color-rule-strong);
  border-radius: var(--radius-pill);
  background: var(--color-surface);
  color: var(--color-accent-ink);
  font-size: var(--text-xs);
  font-weight: 700;
}
.lp-hero h1 {
  margin: var(--space-md) auto var(--space-sm);
  max-width: 16em;
  font-family: var(--font-display);
  font-size: clamp(28px, 5vw, 52px);
  line-height: 1.15;
}
.lp-lead {
  margin: 0 auto;
  max-width: 40em;
  color: var(--color-ink-2);
  font-size: clamp(15px, 1.6vw, 19px);
  line-height: 1.7;
}
.lp-cta {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--space-xs);
  margin: var(--space-lg) 0 var(--space-sm);
}
.lp-cta__main {
  min-width: 188px;
}
.lp-note {
  color: var(--color-ink-3);
  font-size: var(--text-xs);
}

.lp-section {
  padding: clamp(44px, 7vw, 88px) 0;
}
.lp-section--soft {
  background: var(--color-paper-3);
}
.lp-h2 {
  margin: 0 0 var(--space-lg);
  text-align: center;
  font-family: var(--font-display);
  font-size: clamp(22px, 3vw, 32px);
  line-height: 1.25;
}

.lp-grid {
  display: grid;
  gap: var(--space-md);
}
.lp-grid--4 {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}
.lp-grid--3 {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.lp-card {
  border: var(--rule-hair);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  padding: var(--space-md);
}
.lp-card h3 {
  margin: 0 0 var(--space-2xs);
  font-size: var(--text-lg);
}
.lp-card p {
  margin: 0;
  color: var(--color-ink-2);
  line-height: 1.7;
}
.lp-card--platform {
  border-top: 3px solid var(--color-accent);
  border-radius: 0 0 var(--radius-lg) var(--radius-lg);
}
.lp-pill {
  display: inline-block;
  margin-bottom: var(--space-2xs);
  padding: 2px 12px;
  border-radius: var(--radius-pill);
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
  font-weight: 800;
}

.lp-step {
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  border: var(--rule-hair);
  padding: var(--space-md);
}
.lp-step__n {
  font-family: var(--font-mono);
  font-size: var(--text-2xl);
  font-weight: 900;
  color: var(--color-accent);
}
.lp-step h3 {
  margin: var(--space-2xs) 0;
  font-size: var(--text-lg);
}
.lp-step p {
  margin: 0;
  color: var(--color-ink-2);
  line-height: 1.7;
}

.lp-who {
  text-align: center;
}
.lp-who p {
  max-width: 42em;
  margin: 0 auto;
  color: var(--color-ink-2);
  font-size: clamp(15px, 1.6vw, 18px);
  line-height: 1.7;
}

.lp-band {
  padding: clamp(36px, 6vw, 72px) 0;
  background: var(--color-accent);
  color: var(--color-paper);
}
.lp-band__inner {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
}
.lp-band h2 {
  margin: 0 0 6px;
  font-family: var(--font-display);
  font-size: clamp(20px, 2.6vw, 28px);
}
.lp-band p {
  margin: 0;
  opacity: 0.9;
}
.lp-band__btn {
  background: var(--color-paper);
  color: var(--color-accent-ink);
  border-color: var(--color-paper);
  font-weight: 800;
  min-width: 160px;
}

.lp-footer {
  padding: var(--space-md) 0;
  border-top: var(--rule-hair);
}
.lp-footer__inner {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2xs);
  color: var(--color-ink-3);
  font-size: var(--text-sm);
}

@media (max-width: 880px) {
  .lp-grid--4 {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .lp-grid--3 {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 520px) {
  .lp-grid--4 {
    grid-template-columns: 1fr;
  }
}
</style>
