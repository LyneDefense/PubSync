// 博主档案(画像)页状态与动作:聚合读 + 一键建档 + 笔记池同步 + 爆文归因。
// 独立于 useWorkspaceStore(那边已 3000 行),只从它借 选中博主/任务壳/消息。
import { ref, watch } from 'vue'

import {
  buildBloggerDossier,
  getBloggerDossier,
  runBloggerAttribution,
  syncBloggerPool,
} from '../api'
import type { BloggerDossier } from '../api/types'
import {
  currentSocialTab,
  pendingAction,
  runTaskAction,
  selectedBloggerId,
  showMessage,
} from './useWorkspaceStore'

export const dossier = ref<BloggerDossier | null>(null)
export const dossierLoading = ref(false)
export const attributionRunning = ref(false)

export async function loadDossier() {
  if (!selectedBloggerId.value) {
    dossier.value = null
    return
  }
  dossierLoading.value = true
  try {
    dossier.value = await getBloggerDossier(selectedBloggerId.value)
  } catch (error) {
    dossier.value = null
    showMessage(error instanceof Error ? error.message : '档案加载失败', true)
  } finally {
    dossierLoading.value = false
  }
}

// 进入画像页 / 切换博主时自动加载。
watch([selectedBloggerId, currentSocialTab], ([id, tab]) => {
  if (tab === 'dossier' && id) void loadDossier()
})

export async function handleBuildDossier() {
  if (!selectedBloggerId.value) {
    showMessage('请先选择博主', true)
    return
  }
  await runTaskAction(
    'dossier',
    '已提交构建博主画像任务',
    () => buildBloggerDossier(selectedBloggerId.value!),
    loadDossier,
    '构建仍在后台执行，请稍后回来查看'
  )
  await loadDossier()
}

export async function handleSyncPool(mode: 'incremental' | 'full') {
  if (!selectedBloggerId.value) return
  await runTaskAction(
    'pool-sync',
    mode === 'full' ? '已提交笔记池全量校准任务' : '已提交笔记池增量更新任务',
    () => syncBloggerPool(selectedBloggerId.value!, mode),
    loadDossier,
    '同步仍在后台执行，请稍后刷新查看'
  )
  await loadDossier()
}

export async function handleRunAttribution() {
  if (!selectedBloggerId.value || attributionRunning.value) return
  attributionRunning.value = true
  try {
    await runBloggerAttribution(selectedBloggerId.value)
    showMessage('爆文归因完成')
    await loadDossier()
  } catch (error) {
    showMessage(error instanceof Error ? error.message : '归因分析失败', true)
  } finally {
    attributionRunning.value = false
  }
}

export function dossierBusy(): boolean {
  return pendingAction.value === 'dossier' || pendingAction.value === 'pool-sync' || Boolean(dossier.value?.building)
}
