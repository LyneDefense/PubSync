<script setup lang="ts">
// 建档状态清单:5 行(资料/笔记池/数据·轨迹·运营·合规/详情级/创作画像),
// 每行 状态 + 就地入口;一次一操作(有任务在跑就锁全部 + 顶部进度)。判定字段全来自 dossier_overview。
import { computed } from 'vue'

import type { BloggerDossier, BloggerProfile } from '../../api/types'

const props = defineProps<{ dossier: BloggerDossier; blogger: BloggerProfile; busy: boolean }>()
const emit = defineEmits<{
  (e: 'build'): void
  (e: 'rebuild'): void
  (e: 'redistill'): void
  (e: 'upgrade'): void
  (e: 'sync', mode: 'incremental' | 'full'): void
  (e: 'audience'): void
  (e: 'refresh'): void
}>()

const pool = computed(() => props.dossier.pool)
const hasPool = computed(() => pool.value.total > 0)
const hasProfile = computed(() => props.blogger.follower_count != null)
const distilled = computed(() => props.dossier.portraits.length > 0)
const stale = computed(() => props.dossier.portraits.some((p) => p.stale))
const canDistill = computed(() => pool.value.full_count >= 8)
const locked = computed(() => props.busy) // busy 已含「构建中」→ 一次一操作

function fmt(n: number): string {
  if (n >= 10000) {
    const w = n / 10000
    return `${w >= 100 ? Math.round(w) : Number(w.toFixed(1))}w`
  }
  return String(n)
}
</script>

<template>
  <section class="ck">
    <div class="ck__head">
      <h3>建档清单</h3>
      <button v-if="!hasPool && !busy" type="button" class="ck__cta" :disabled="busy" @click="emit('build')">
        一键构建画像
      </button>
    </div>
    <p v-if="!hasPool && !busy" class="ck__intro">
      依次:拉资料 → 全量列表入池 → 数据/成长/运营/合规 → 相关样本升详情 → 蒸馏创作画像。约 10–20 分钟,后台执行。
    </p>

    <ol class="ck__rows">
      <!-- ① 资料 -->
      <li class="ck__row">
        <span class="ck__mark" :class="hasProfile ? 'is-done' : 'is-pending'" />
        <div class="ck__main">
          <span class="ck__label">账号资料</span>
          <span class="ck__status">
            {{ hasProfile ? `粉丝 ${fmt(blogger.follower_count as number)} · 平台 ${pool.note_total ?? '?'} 篇` : '未拉取' }}
          </span>
        </div>
        <button type="button" class="ck__btn" :disabled="locked" @click="emit('refresh')">刷新</button>
      </li>

      <!-- ② 笔记池 -->
      <li class="ck__row">
        <span class="ck__mark" :class="hasPool ? 'is-done' : 'is-pending'" />
        <div class="ck__main">
          <span class="ck__label">笔记池</span>
          <span class="ck__status">
            {{ hasPool ? `已入池 ${pool.total} 篇` : '空' }}
            <em v-if="hasPool && pool.note_total" class="ck__muted">平台现有 {{ pool.note_total }}</em>
            <em v-if="hasPool && !pool.reached_end" class="ck__warn">未到底</em>
          </span>
        </div>
        <button type="button" class="ck__btn" :disabled="locked" @click="emit('sync', 'incremental')">增量补采</button>
        <button type="button" class="ck__btn" :disabled="locked" @click="emit('sync', 'full')">全量校准</button>
      </li>

      <!-- ③ 数据·轨迹·运营·合规(读池即算)+ 受众需求 -->
      <li class="ck__row">
        <span class="ck__mark" :class="hasPool ? 'is-done' : 'is-pending'" />
        <div class="ck__main">
          <span class="ck__label">数据 · 轨迹 · 运营 · 合规</span>
          <span class="ck__status">
            {{ hasPool ? '已就绪' : '待入池' }} · 受众需求{{ dossier.audience ? '已生成' : '未生成' }}
          </span>
        </div>
        <button type="button" class="ck__btn" :disabled="locked || !hasPool" @click="emit('audience')">
          {{ dossier.audience ? '重算受众' : '生成受众' }}
        </button>
      </li>

      <!-- ④ 详情级 -->
      <li class="ck__row">
        <span class="ck__mark" :class="pool.full_count > 0 ? (canDistill ? 'is-done' : 'is-warn') : 'is-pending'" />
        <div class="ck__main">
          <span class="ck__label">详情级笔记</span>
          <span class="ck__status">
            已详情 {{ pool.full_count }} 篇<em v-if="pool.full_count < 8" class="ck__warn"> · 不足 8 篇不能蒸馏</em>
          </span>
        </div>
        <button type="button" class="ck__btn" :disabled="locked || !hasPool" @click="emit('upgrade')">升级详情</button>
      </li>

      <!-- ⑤ 创作画像 -->
      <li class="ck__row">
        <span class="ck__mark" :class="distilled ? (stale ? 'is-warn' : 'is-done') : 'is-pending'" />
        <div class="ck__main">
          <span class="ck__label">创作画像</span>
          <span class="ck__status">{{ distilled ? (stale ? '已蒸馏 · 可能过时' : '已蒸馏') : '未蒸馏' }}</span>
        </div>
        <template v-if="distilled">
          <button type="button" class="ck__btn" :disabled="locked" @click="emit('redistill')">更新画像</button>
          <button type="button" class="ck__btn" :disabled="locked" @click="emit('rebuild')">彻底重建</button>
        </template>
        <button
          v-else
          type="button"
          class="ck__btn"
          :disabled="locked || !canDistill"
          :title="canDistill ? '' : '详情级需 ≥8 篇'"
          @click="emit('redistill')"
        >
          蒸馏画像
        </button>
      </li>
    </ol>
  </section>
</template>

<style scoped>
.ck {
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  padding: 14px 16px;
}
.ck__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.ck__head h3 {
  margin: 0;
  font-size: 14.5px;
  font-weight: 680;
}
.ck__cta {
  height: 32px;
  padding: 0 16px;
  border: 0;
  border-radius: 9px;
  background: var(--color-accent);
  color: #fff;
  font-size: 13px;
  font-weight: 620;
  cursor: pointer;
}
.ck__cta:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.ck__intro {
  margin: 8px 0 0;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--color-ink-3);
}
.ck__rows {
  list-style: none;
  margin: 10px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}
.ck__row {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 10px 0;
  border-top: 1px solid var(--color-rule);
}
.ck__row:first-child {
  border-top: 0;
}
.ck__mark {
  flex: 0 0 auto;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  border: 1.5px solid var(--color-rule-strong);
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  color: transparent;
}
.ck__mark.is-done {
  background: var(--color-accent);
  border-color: var(--color-accent);
  color: #fff;
}
.ck__mark.is-done::before {
  content: '✓';
}
.ck__mark.is-warn {
  border-color: #d9a441;
  color: #d9a441;
}
.ck__mark.is-warn::before {
  content: '!';
}
.ck__main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.ck__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-ink);
}
.ck__status {
  font-size: 12px;
  color: var(--color-ink-3);
}
.ck__muted {
  font-style: normal;
  margin-left: 4px;
  color: var(--color-ink-3);
}
.ck__warn {
  font-style: normal;
  margin-left: 4px;
  color: #8a5a12;
}
.ck__btn {
  flex: 0 0 auto;
  height: 30px;
  padding: 0 12px;
  border: 1px solid var(--color-field-border);
  border-radius: 8px;
  background: var(--color-surface);
  color: var(--color-ink-2);
  font-size: 12.5px;
  cursor: pointer;
  transition: border-color 140ms var(--ease-out);
}
.ck__btn:hover:not(:disabled) {
  border-color: var(--color-accent);
  color: var(--color-accent-ink);
}
.ck__btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
