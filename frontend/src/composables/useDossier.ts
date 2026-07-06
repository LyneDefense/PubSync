// 博主档案(画像)页状态与动作:聚合读 + 一键建档 + 笔记池同步 + 爆文归因。
// 独立于 useWorkspaceStore(那边已 3000 行),只从它借 选中博主/任务壳/消息。
import { ref, watch } from 'vue'

import {
  buildBloggerDossier,
  collectBlogger,
  collectBloggerByUrls,
  getBloggerDossier,
  redistillBloggerDossier,
  runBloggerAudience,
  syncBloggerPool,
} from '../api'
import type { BloggerDossier } from '../api/types'
import {
  currentSocialTab,
  pendingAction,
  refreshSelectedBlogger,
  runTaskAction,
  selectedBloggerId,
  showMessage,
} from './useWorkspaceStore'

export const dossier = ref<BloggerDossier | null>(null)
export const dossierLoading = ref(false)
export const audienceRunning = ref(false)

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

// 进入画像页(assets 为并入前的别名) / 切换博主时自动加载:档案聚合 + 笔记池/快照/蒸馏记录(store)。
watch([selectedBloggerId, currentSocialTab], ([id, tab]) => {
  if (!id || !['dossier', 'assets', 'my-accounts'].includes(tab as string)) return
  void loadDossier()
  void refreshSelectedBlogger()
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
    reloadAll,
    '构建仍在后台执行，请稍后回来查看'
  )
  await reloadAll()
}

async function reloadAll() {
  await Promise.all([loadDossier(), refreshSelectedBlogger()])
}

// 更新画像(轻量重蒸):用现有详情池重蒸,不重拉平台。
export async function handleRedistill() {
  if (!selectedBloggerId.value) {
    showMessage('请先选择博主', true)
    return
  }
  await runTaskAction(
    'dossier',
    '已提交更新画像任务',
    () => redistillBloggerDossier(selectedBloggerId.value!),
    reloadAll,
    '更新仍在后台执行，请稍后回来查看'
  )
  await reloadAll()
}

export async function handleSyncPool(mode: 'incremental' | 'full') {
  if (!selectedBloggerId.value) return
  await runTaskAction(
    'pool-sync',
    mode === 'full' ? '已提交笔记池全量校准任务' : '已提交笔记池增量更新任务',
    () => syncBloggerPool(selectedBloggerId.value!, mode),
    reloadAll,
    '同步仍在后台执行，请稍后刷新查看'
  )
  await reloadAll()
}

// 升级详情(建档清单④):系统选片(smart:中位数+最近+爆文保底),升级到详情级。
export async function handleUpgradeDetail(sampleLimit = 80, contentTypes = ['image', 'video']) {
  if (!selectedBloggerId.value) return
  await runTaskAction(
    'dossier',
    '已提交升级详情任务',
    () =>
      collectBlogger(selectedBloggerId.value!, {
        sample_limit: sampleLimit,
        comments_per_post: 20,
        order: 'smart',
        content_types: contentTypes,
        backfill: true,
      }),
    reloadAll,
    '升级仍在后台执行，请稍后刷新查看'
  )
  await reloadAll()
}

// 定向补采(建档清单④模式B):粘链接补/深挖指定笔记。
export async function handleUpgradeByUrls(urls: string[]) {
  if (!selectedBloggerId.value || !urls.length) return
  await runTaskAction(
    'dossier',
    `已提交定向补采 ${urls.length} 条任务`,
    () => collectBloggerByUrls(selectedBloggerId.value!, { urls, comments_per_post: 20 }),
    reloadAll,
    '补采仍在后台执行，请稍后刷新查看'
  )
  await reloadAll()
}

export async function handleRunAudience() {
  if (!selectedBloggerId.value || audienceRunning.value) return
  audienceRunning.value = true
  try {
    await runBloggerAudience(selectedBloggerId.value)
    showMessage('受众需求分析完成')
    await loadDossier()
  } catch (error) {
    showMessage(error instanceof Error ? error.message : '受众需求分析失败', true)
  } finally {
    audienceRunning.value = false
  }
}

export function dossierBusy(): boolean {
  return pendingAction.value === 'dossier' || pendingAction.value === 'pool-sync' || Boolean(dossier.value?.building)
}
