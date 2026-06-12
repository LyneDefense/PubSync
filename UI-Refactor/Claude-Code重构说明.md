# PubSync UI 重构 — Claude Code 交接说明

> 目标：把当前「深色 + 霓虹青绿 + 网格底纹」的科技感 UI，改造成
> 「浅色中性底 + 沉稳墨绿强调色 + 高密度」的专业工具风。
> 视觉参照：项目里的 `PubSync 重构.dc.html`（用浏览器打开看目标效果，右上角可切换墨绿/暖陶主色）。

设计原则：**去网格、去霓虹、去发光描边；用浅色中性底 + 单一克制强调色；
状态用语义色片而非发光；系统字 + 字重建立层级。**

---

## 第 1 步（最关键）：替换 `src/assets/main.css` 里的 `:root` 令牌值

整个 App 都吃这组变量，改完即可全局换肤。把 `:root { … }` 里这些变量的**值**替换为下面的浅色版（变量名保持不变）：

```css
:root {
  color-scheme: light;                 /* 原来是 dark */

  /* 底色 / 表面：深 → 浅 */
  --color-paper:          #f4f5f6;      /* 页面底 */
  --color-paper-2:        #ffffff;      /* 卡片 / 列表填充 */
  --color-paper-3:        #eef0f2;      /* hover / raised */
  --color-surface:        #ffffff;
  --color-surface-solid:  #ffffff;
  --color-surface-raised: #ffffff;      /* 次级按钮底 */

  /* 文字：浅 → 深 */
  --color-ink:    #1c2024;
  --color-ink-2:  #565d66;
  --color-ink-3:  #878f99;

  /* 描边：去掉青光，改中性细线 */
  --color-rule:        #e8eaed;
  --color-rule-strong: #cfd4d9;

  /* 强调色：霓虹青绿 → 沉稳墨绿 */
  --color-accent:      #0d7361;
  --color-accent-soft: #eaf3ee;         /* 选中态浅底 */
  --color-accent-ink:  #0d5a4a;         /* 激活 Tab 文字（深绿，保证可读） */

  /* 语义色（保持，仅微调到浅色可读） */
  --color-blue:   #3a6ad6;
  --color-danger: #b4453a;
  --color-focus:  #c08a1e;

  --color-shadow: rgba(20, 30, 40, 0.08);
}
```

> 想看暖色方案：只把上面三个 accent 变量改成
> `--color-accent:#bd5b34; --color-accent-soft:#f6ece4; --color-accent-ink:#9a4f2c;` 即可。

---

## 第 2 步：删掉 body 的网格底纹（"AI 感"头号来源）

把 `body { background: …多层 linear-gradient… }` 改成纯色：

```css
body {
  min-width: 320px;
  margin: 0;
  background: var(--color-paper);       /* 删掉两层 1px 网格 + 斜向渐变 */
  color: var(--color-ink);
}
```

同时删掉 `background-size: 44px 44px, 44px 44px, auto;` 那一行。

---

## 第 3 步（可选，去 AI 感加分）：换字体

把字体变量改成系统字栈（刻意不用 Inter，更不像 AI 模板）：

```css
--font-display: "PingFang SC", "Microsoft YaHei", ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
--font-body:    "PingFang SC", "Microsoft YaHei", ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
```

---

## 第 4 步：组件级微调（令牌换肤之后再做这些）

这些是结构/样式微调，建议对照 `PubSync 重构.dc.html` 逐项改：

1. **去掉发光描边**：全局搜索 `box-shadow` 里带 accent/青色的阴影、`--color-rule-strong` 当发光用的地方，改为 1px 中性描边。卡片阴影统一为 `0 1px 2px rgba(20,30,40,0.04)` 或无阴影。
2. **向导别再"剧场化"**（`.creator-shell` / `.creator-step-header` / `.creator-arrow`）：
   - 居中巨标题 `.creator-step-header h3`（2rem）→ 缩小，移到卡片头部左对齐；
   - 两侧 52px 大圆箭头 `.creator-arrow` → 去掉，改成卡片底部的「← 上一步 / 下一步 →」按钮条；
   - 顶部加一条**紧凑横向步骤条**（圆点 24px + 文字，连线 flex:1），参照设计稿。
3. **卡片圆角/间距**：卡片 `border-radius:14px`，内部块 11–12px；列表项之间用 `gap` 而非 margin。
4. **状态用语义色片**（不要发光）：成功=墨绿浅底、失败=砖红浅底、进行中=蓝浅底、待确认=琥珀浅底，圆角 6px、字 11–12px。
5. **强调色用法收敛**：只在「激活 Tab 下划线 / 选中态 / 主按钮 / 步骤圆点 / 标签」用强调色，其余一律中性。

---

## 给 Claude Code 的提示词（直接复制）

```
请帮我把前端 UI 从"深色科技感"改造成"浅色专业工具风"。
完整方案见项目根目录的 `Claude-Code-重构说明.md`，视觉目标见 `PubSync 重构.dc.html`（用浏览器打开参照）。

请按文档顺序执行：
1. 先改 src/assets/main.css 的 :root 令牌值（第 1 步）和 body 背景去网格（第 2 步）——这两步是全局换肤，做完先让我在浏览器里确认整体观感。
2. 确认 OK 后，再做第 4 步的组件级微调，重点是 .creator-shell 向导：去掉两侧大圆箭头和居中巨标题，改成顶部紧凑步骤条 + 底部上一步/下一步按钮条。
3. 每改完一块停下来让我确认，不要一次性全改。

约束：不要新增依赖；保留现有的 class 名和 DOM 结构（除非第 4 步明确要求调整）；中文文案不要改。
```
