<script setup lang="ts">
// 候选 | 已选 两列,泛搜索与找相似共用。候选卡展示硬数据(粉丝/获赞收藏/简介/IP/近期命中)+ 软数据(相关度/火爆度/综合分),
// 点「看依据」展开。采用→进已选 / 不要→剔除;已选→保存进对标库。
import { computed, reactive } from 'vue'
import TIcon from '../components/TIcon.vue'
import {
  discoveryOpPending,
  discoveryRecalling,
  discoveryWorkspace,
  handleDiscoveryOp,
  handleDiscoveryRecall,
  handleDiscoverySave,
  resetDiscovery
} from '../composables/useWorkspaceStore'
import type { DiscoveryCandidate } from '../api/types'

const ws = computed(() => discoveryWorkspace.value)
const busy = computed(() => discoveryRecalling.value || discoveryOpPending.value)
const open = reactive<Record<string, boolean>>({})

function fmtNum(n: number): string {
  return n >= 10000 ? `${(n / 10000).toFixed(1)}万` : `${n}`
}
function fmtFans(c: DiscoveryCandidate): string {
  return c.follower_known ? `${fmtNum(c.follower_count)}粉` : '粉丝未知'
}
</script>

<template>
  <div v-if="ws" class="dw">
    <div class="dw-top">
      <span class="dw-msg">{{ ws.message }}</span>
      <button type="button" class="dw-link" @click="resetDiscovery">重新开始</button>
    </div>

    <div class="dw-cols">
      <!-- 候选 -->
      <section class="dw-col">
        <header>
          <span class="dw-h"><TIcon name="users" /> 候选 <b>{{ ws.candidates.length }}</b></span>
          <div class="dw-acts">
            <button type="button" class="sm primary" :disabled="busy" @click="handleDiscoveryRecall()">
              {{ discoveryRecalling ? '搜罗核验中…' : '再找一批' }}
            </button>
            <button v-if="ws.candidates.length" type="button" class="sm" :disabled="busy" @click="handleDiscoveryOp('clear_candidates')">清空</button>
          </div>
        </header>
        <div class="dw-body">
          <article v-for="c in ws.candidates" :key="c.external_id" class="dw-card">
            <img v-if="c.avatar_url" :src="c.avatar_url" alt="" />
            <div class="dw-card-main">
              <div class="dw-card-top">
                <strong>{{ c.display_name }}</strong>
                <span class="dw-rel" :class="{ hi: c.relevance >= 70 }">相关 {{ Math.round(c.relevance) }}</span>
              </div>
              <div class="dw-data">
                {{ fmtFans(c) }} · 赞藏 {{ fmtNum(c.like_collect) }} ·
                <span :class="c.is_personal ? 'ok' : 'muted'">{{ c.is_personal ? '个人号' : '机构号' }}</span>
                <span v-if="c.existing_blogger_id" class="dw-tag">已在库</span>
              </div>
              <div class="dw-sub">{{ c.reason }} · 火爆 {{ Math.round(c.popularity) }} · 综合 {{ Math.round(c.score) }}</div>
              <button type="button" class="dw-why" @click="open[c.external_id] = !open[c.external_id]">
                <TIcon :name="open[c.external_id] ? 'chevron-up' : 'chevron-down'" />
                {{ open[c.external_id] ? '收起' : '看依据' }}
              </button>
              <div v-if="open[c.external_id]" class="dw-detail">
                <p><b>简介</b>：{{ c.bio || '—' }}<span v-if="c.ip_location"> · IP {{ c.ip_location }}</span></p>
                <p><b>近期命中</b>：{{ c.hit_count }} 条相关<span v-if="c.recent_titles?.length">（{{ c.recent_titles.slice(0, 3).join('；') }}）</span></p>
                <p v-if="c.relevance_reason"><b>相关度判断</b>：{{ c.relevance_reason }}</p>
              </div>
              <div class="dw-card-acts">
                <button type="button" class="adopt" :disabled="busy" @click="handleDiscoveryOp('adopt', [c.external_id])"><TIcon name="check" /> 采用</button>
                <button type="button" :disabled="busy" @click="handleDiscoveryOp('dismiss', [c.external_id])"><TIcon name="x" /> 不要</button>
              </div>
            </div>
          </article>
          <p v-if="!ws.candidates.length" class="dw-empty">点「再找一批」拉候选;看到合适的就「采用」。</p>
        </div>
      </section>

      <!-- 已选 -->
      <section class="dw-col">
        <header>
          <span class="dw-h"><TIcon name="star" /> 已选对标 <b>{{ ws.selected.length }}</b></span>
          <button type="button" class="sm save" :disabled="busy || !ws.selected.length" @click="handleDiscoverySave">保存到对标库</button>
        </header>
        <div class="dw-body">
          <article v-for="b in ws.selected" :key="b.external_id" class="dw-card">
            <div class="dw-card-main">
              <div class="dw-card-top"><strong>{{ b.display_name }}</strong><span v-if="b.existing_blogger_id" class="dw-tag">已在库</span></div>
              <div class="dw-data">{{ fmtFans(b) }} · 相关 {{ Math.round(b.relevance) }} · <span :class="b.is_personal ? 'ok' : 'muted'">{{ b.is_personal ? '个人号' : '机构号' }}</span></div>
              <div class="dw-card-acts">
                <button type="button" :disabled="busy" @click="handleDiscoveryOp('remove_selected', [b.external_id])"><TIcon name="x" /> 移除</button>
              </div>
            </div>
          </article>
          <p v-if="!ws.selected.length" class="dw-empty">把满意的号「采用」到这里,最后一键保存。</p>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.dw-top { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
.dw-msg { color: var(--color-ink-2, #6b7280); font-size: 0.86rem; }
.dw-link { border: none; background: none; cursor: pointer; color: var(--color-ink-3, #9aa0a6); font-size: 0.84rem; margin-left: auto; }
.dw-cols { display: grid; grid-template-columns: 1.35fr 1fr; gap: 12px; }
.dw-col { background: var(--color-paper-2, #f7f8fa); border-radius: 12px; padding: 10px; display: flex; flex-direction: column; min-height: 280px; }
.dw-col > header { display: flex; align-items: center; justify-content: space-between; gap: 6px; margin-bottom: 8px; }
.dw-h { font-weight: 600; font-size: 0.92rem; display: inline-flex; align-items: center; gap: 5px; }
.dw-h b { color: var(--color-ink-2, #6b7280); }
.dw-acts { display: flex; gap: 6px; }
.dw-body { display: flex; flex-direction: column; gap: 8px; max-height: 560px; overflow-y: auto; }
.dw-card { display: flex; gap: 8px; background: var(--color-field, #fff); border: 1px solid var(--color-field-border, #e2e6ea); border-radius: 10px; padding: 8px 10px; }
.dw-card img { width: 38px; height: 38px; border-radius: 50%; flex: none; object-fit: cover; }
.dw-card-main { flex: 1; min-width: 0; }
.dw-card-top { display: flex; align-items: center; justify-content: space-between; gap: 6px; }
.dw-card-top strong { font-size: 0.88rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dw-rel { font-size: 0.72rem; color: var(--color-ink-3, #9aa0a6); white-space: nowrap; border: 1px solid var(--color-field-border, #d3d7dc); border-radius: 999px; padding: 0 7px; }
.dw-rel.hi { color: #fff; background: var(--color-accent, #2563eb); border-color: var(--color-accent, #2563eb); }
.dw-data { font-size: 0.78rem; color: var(--color-ink-2, #6b7280); margin-top: 2px; }
.dw-data .ok { color: var(--color-ok, #2e9e5b); }
.dw-data .muted { color: var(--color-ink-3, #9aa0a6); }
.dw-sub { font-size: 0.74rem; color: var(--color-ink-3, #9aa0a6); margin-top: 2px; }
.dw-tag { font-size: 0.68rem; color: var(--color-ok, #2e9e5b); margin-left: 6px; }
.dw-why { border: none; background: none; cursor: pointer; color: var(--color-accent, #2563eb); font-size: 0.74rem; padding: 4px 0 2px; display: inline-flex; align-items: center; gap: 3px; }
.dw-detail { background: var(--color-paper-3, #f1f3f5); border-radius: 8px; padding: 7px 9px; margin: 2px 0 4px; }
.dw-detail p { margin: 0 0 4px; font-size: 0.76rem; color: var(--color-ink-2, #6b7280); line-height: 1.5; }
.dw-detail p:last-child { margin-bottom: 0; }
.dw-detail b { color: var(--color-ink, #374151); font-weight: 600; }
.dw-card-acts { display: flex; gap: 6px; margin-top: 6px; }
.dw-card-acts button { font-size: 0.74rem; padding: 3px 8px; border: 1px solid var(--color-field-border, #c8ced4); border-radius: 8px; background: transparent; cursor: pointer; display: inline-flex; align-items: center; gap: 3px; }
.dw-card-acts button.adopt { border-color: var(--color-accent, #2563eb); color: var(--color-accent, #2563eb); }
.dw-card-acts button:disabled { opacity: 0.5; cursor: default; }
.dw-empty { color: var(--color-ink-3, #9aa0a6); font-size: 0.8rem; text-align: center; padding: 18px 8px; }
button.sm { font-size: 0.76rem; padding: 4px 10px; border-radius: 8px; border: 1px solid var(--color-field-border, #c8ced4); background: var(--color-field, #fff); cursor: pointer; }
button.sm:disabled { opacity: 0.5; cursor: default; }
button.sm.primary { background: var(--color-accent, #2563eb); color: #fff; border-color: var(--color-accent, #2563eb); }
button.sm.save { background: var(--color-ok, #2e9e5b); color: #fff; border-color: var(--color-ok, #2e9e5b); }
@media (max-width: 720px) { .dw-cols { grid-template-columns: 1fr; } }
</style>
