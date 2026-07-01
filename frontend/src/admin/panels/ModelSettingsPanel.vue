<script setup lang="ts">
// 模型与生成(向导式):选供应商 → 从下拉选模型 → 填该供应商 Key。
// 文本模型一处设置、全程序生效(蒸馏/创作/诊断/对标搜寻/Skill优化都用它)。图像模型单列。
// 复用 /admin/config 的读取与保存;密钥不回显、加密保存。
import { computed, onMounted, reactive, ref } from 'vue'
import { clearAdminConfig, getAdminConfig, updateAdminConfig } from '../../api'
import type { ConfigFieldView, ConfigView } from '../../api/types'

// 各供应商可选模型(下拉,免手输;末尾「自定义…」给逃生口)。
const TEXT_MODELS: Record<string, string[]> = {
  minimax: ['MiniMax-M2.7', 'MiniMax-Text-01'],
  claude: ['claude-opus-4-8', 'claude-sonnet-4-6', 'claude-haiku-4-5-20251001'],
  openai: ['gpt-5.5', 'gpt-5.5-mini', 'gpt-4.1', 'gpt-4o'],
  glm: ['glm-4.6', 'glm-4.5', 'glm-4.5-air', 'glm-4-plus', 'glm-4-flash']
}
const IMAGE_MODELS: Record<string, string[]> = {
  openai: ['gpt-image-1', 'dall-e-3'],
  minimax: ['image-01']
}
const TEXT_PROVIDERS = [
  { value: 'minimax', label: 'MiniMax' },
  { value: 'glm', label: '智谱 GLM' },
  { value: 'claude', label: 'Claude（Anthropic）' },
  { value: 'openai', label: 'OpenAI' }
]
const IMAGE_PROVIDERS = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'minimax', label: 'MiniMax' }
]
// 供应商 → 配置键。claude 复用 anthropic_* 键。
const TEXT_KEYS: Record<string, { model: string; key: string; base: string }> = {
  minimax: { model: 'minimax_text_model', key: 'minimax_api_key', base: 'minimax_base_url' },
  glm: { model: 'glm_text_model', key: 'glm_api_key', base: 'glm_base_url' },
  claude: { model: 'anthropic_text_model', key: 'anthropic_api_key', base: 'anthropic_base_url' },
  openai: { model: 'openai_text_model', key: 'openai_api_key', base: 'openai_base_url' }
}
const IMAGE_KEYS: Record<string, string> = { openai: 'openai_image_model', minimax: 'minimax_image_model' }
const CUSTOM = '__custom__'
// 向导已接管的键;其余 model 组字段进「高级」。
const HANDLED = new Set([
  'llm_provider', 'image_provider',
  ...Object.values(TEXT_KEYS).flatMap((m) => [m.model, m.key, m.base]),
  ...Object.values(IMAGE_KEYS),
  'anthropic_version', 'anthropic_max_tokens'
])

const config = ref<ConfigView | null>(null)
const loading = ref(true)
const busy = ref('')
const message = ref('')
const error = ref('')

// 文本
const textProvider = ref('minimax')
const textModelSel = ref('')
const textModelCustom = ref('')
const textKeyDraft = ref('')
// 图像
const imageProvider = ref('openai')
const imageModelSel = ref('')
const imageModelCustom = ref('')
// 高级
const showAdvanced = ref(false)
const advDrafts = reactive<Record<string, string>>({})

const modelFields = computed<ConfigFieldView[]>(
  () => config.value?.groups.find((g) => g.key === 'model')?.fields || []
)
function field(key: string): ConfigFieldView | undefined {
  return modelFields.value.find((f) => f.key === key)
}
function valueOf(key: string): string {
  return String(field(key)?.value ?? '')
}
const textKeyField = computed(() => field(TEXT_KEYS[textProvider.value]?.key))
const advancedFields = computed(() => modelFields.value.filter((f) => !HANDLED.has(f.key)))

// 某供应商的 key 是否已配置(读各自的 *_api_key 字段)。
function keyConfigured(provider: string): boolean {
  return Boolean(field(TEXT_KEYS[provider]?.key)?.configured)
}
// 文本/图像「可用」= 该供应商 key 已配置,或本次已填了新 key。未就绪则模型与应用置灰。
const textReady = computed(() => keyConfigured(textProvider.value) || textKeyDraft.value.trim() !== '')
const imageReady = computed(() => keyConfigured(imageProvider.value))

function syncTextModelFromProvider() {
  const saved = valueOf(TEXT_KEYS[textProvider.value].model)
  const options = TEXT_MODELS[textProvider.value] || []
  if (saved && options.includes(saved)) {
    textModelSel.value = saved
    textModelCustom.value = ''
  } else if (saved) {
    textModelSel.value = CUSTOM
    textModelCustom.value = saved
  } else {
    textModelSel.value = options[0] || CUSTOM
    textModelCustom.value = ''
  }
}
function syncImageModelFromProvider() {
  const saved = valueOf(IMAGE_KEYS[imageProvider.value])
  const options = IMAGE_MODELS[imageProvider.value] || []
  if (saved && options.includes(saved)) {
    imageModelSel.value = saved
    imageModelCustom.value = ''
  } else if (saved) {
    imageModelSel.value = CUSTOM
    imageModelCustom.value = saved
  } else {
    imageModelSel.value = options[0] || CUSTOM
    imageModelCustom.value = ''
  }
}

async function reload() {
  loading.value = true
  try {
    const view = await getAdminConfig()
    config.value = view
    const prov = valueOf('llm_provider').toLowerCase()
    const provNorm = prov === 'anthropic' ? 'claude' : prov === 'zhipu' || prov === 'bigmodel' ? 'glm' : prov
    textProvider.value = provNorm in TEXT_KEYS ? provNorm : 'minimax'
    imageProvider.value = valueOf('image_provider').toLowerCase() in IMAGE_KEYS ? valueOf('image_provider').toLowerCase() : 'openai'
    syncTextModelFromProvider()
    syncImageModelFromProvider()
    textKeyDraft.value = ''
    for (const f of advancedFields.value) advDrafts[f.key] = f.is_secret ? '' : String(f.value ?? '')
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}
onMounted(reload)

function onTextProviderChange() {
  syncTextModelFromProvider()
  textKeyDraft.value = ''
}

async function saveText() {
  error.value = ''
  message.value = ''
  const model = textModelSel.value === CUSTOM ? textModelCustom.value.trim() : textModelSel.value
  if (!model) {
    error.value = '请选择或填写文本模型'
    return
  }
  busy.value = 'text'
  try {
    await updateAdminConfig('llm_provider', textProvider.value)
    await updateAdminConfig(TEXT_KEYS[textProvider.value].model, model)
    if (textKeyDraft.value.trim()) {
      await updateAdminConfig(TEXT_KEYS[textProvider.value].key, textKeyDraft.value.trim())
    }
    config.value = await getAdminConfig()
    textKeyDraft.value = ''
    message.value = `已应用文本模型:${TEXT_PROVIDERS.find((p) => p.value === textProvider.value)?.label} · ${model}（全程序生效）`
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = ''
  }
}

async function saveImage() {
  error.value = ''
  message.value = ''
  const model = imageModelSel.value === CUSTOM ? imageModelCustom.value.trim() : imageModelSel.value
  busy.value = 'image'
  try {
    await updateAdminConfig('image_provider', imageProvider.value)
    if (model) await updateAdminConfig(IMAGE_KEYS[imageProvider.value], model)
    config.value = await getAdminConfig()
    message.value = '已应用图像模型设置'
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = ''
  }
}

async function saveAdv(f: ConfigFieldView) {
  error.value = ''
  message.value = ''
  let value = advDrafts[f.key] ?? ''
  if (f.type === 'bool') value = value === 'true' ? 'true' : 'false'
  if (f.is_secret && !value.trim()) {
    error.value = `${f.label}:请输入新值再保存`
    return
  }
  busy.value = f.key
  try {
    config.value = await updateAdminConfig(f.key, value)
    message.value = `已保存:${f.label}`
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = ''
  }
}
async function clearAdv(f: ConfigFieldView) {
  busy.value = f.key
  try {
    config.value = await clearAdminConfig(f.key)
    advDrafts[f.key] = f.is_secret ? '' : String(field(f.key)?.value ?? '')
    message.value = `已清除:${f.label}`
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = ''
  }
}
</script>

<template>
  <section class="panel">
    <div class="section-header">
      <div>
        <h2>模型与生成</h2>
        <p class="toolbar-subtitle">选供应商 + 模型即可,文本模型一处设置、全程序通用。修改即时生效,密钥加密保存、不回显。</p>
      </div>
      <button type="button" @click="reload">刷新</button>
    </div>

    <p v-if="message" class="admin-flash admin-flash--ok">{{ message }}</p>
    <p v-if="error" class="admin-flash admin-flash--err">{{ error }}</p>
    <p v-if="loading" class="empty-region">加载中…</p>

    <template v-if="!loading">
      <!-- 文本模型(全局) -->
      <div class="ms-card">
        <h3>文本模型（全局通用）</h3>
        <p class="ms-hint">蒸馏、AI 创作、账号诊断、对标搜寻、Skill 优化等所有文本生成都用这一个。</p>
        <div class="ms-grid">
          <label>供应商
            <select v-model="textProvider" @change="onTextProviderChange">
              <option v-for="p in TEXT_PROVIDERS" :key="p.value" :value="p.value">
                {{ p.label }}{{ keyConfigured(p.value) ? ' ✓' : ' · 未配置 key' }}
              </option>
            </select>
          </label>
          <label>
            <span class="ms-keyhead">
              {{ TEXT_PROVIDERS.find((p) => p.value === textProvider)?.label }} API Key
              <span class="ms-badge" :class="textKeyField?.configured ? 'ms-badge--ok' : 'ms-badge--warn'">
                {{ textKeyField?.configured ? '✓ 已配置' : '未配置' }}
              </span>
            </span>
            <input
              v-model="textKeyDraft"
              type="password"
              autocomplete="off"
              :placeholder="textKeyField?.configured ? '已配置（留空保持不变）' : '请输入该供应商的 API Key'"
            />
          </label>
        </div>
        <p v-if="!textReady" class="ms-warn-line">⚠ 当前供应商的 API Key 未配置,请先在上方填写 Key,才能选用它的模型。</p>
        <label class="ms-full">模型
          <select v-model="textModelSel" :disabled="!textReady">
            <option v-for="m in (TEXT_MODELS[textProvider] || [])" :key="m" :value="m">{{ m }}</option>
            <option :value="CUSTOM">自定义…</option>
          </select>
        </label>
        <label v-if="textModelSel === CUSTOM" class="ms-full">自定义模型 ID
          <input v-model="textModelCustom" type="text" :disabled="!textReady" placeholder="填该供应商的模型 ID" />
        </label>
        <button type="button" class="primary" :disabled="busy === 'text' || !textReady" @click="saveText">应用文本模型</button>
      </div>

      <!-- 图像模型 -->
      <div class="ms-card">
        <h3>图像模型（配图用）</h3>
        <p class="ms-hint">Claude 无图像生成,配图固定走 OpenAI / MiniMax。</p>
        <div class="ms-grid">
          <label>供应商
            <select v-model="imageProvider" @change="syncImageModelFromProvider">
              <option v-for="p in IMAGE_PROVIDERS" :key="p.value" :value="p.value">
                {{ p.label }}{{ keyConfigured(p.value) ? ' ✓' : ' · 未配置 key' }}
              </option>
            </select>
          </label>
          <label>模型
            <select v-model="imageModelSel" :disabled="!imageReady">
              <option v-for="m in (IMAGE_MODELS[imageProvider] || [])" :key="m" :value="m">{{ m }}</option>
              <option :value="CUSTOM">自定义…</option>
            </select>
          </label>
        </div>
        <p v-if="!imageReady" class="ms-warn-line">⚠ {{ IMAGE_PROVIDERS.find((p) => p.value === imageProvider)?.label }} 的 API Key 未配置,请到上面「文本模型」卡选该供应商填一次 Key(key 共用)。</p>
        <label v-if="imageModelSel === CUSTOM" class="ms-full">自定义模型 ID
          <input v-model="imageModelCustom" type="text" :disabled="!imageReady" />
        </label>
        <button type="button" class="primary" :disabled="busy === 'image' || !imageReady" @click="saveImage">应用图像模型</button>
      </div>

      <!-- 高级:其余原始参数 -->
      <div class="ms-card">
        <button type="button" class="ms-adv-toggle" @click="showAdvanced = !showAdvanced">
          {{ showAdvanced ? '收起' : '展开' }}高级参数（专用模型覆盖、合成循环、Base URL 等,一般留空即可）
        </button>
        <div v-if="showAdvanced" class="ms-adv">
          <div v-for="f in advancedFields" :key="f.key" class="ms-adv-row">
            <div class="ms-adv-meta"><strong>{{ f.label }}</strong><code>{{ f.key }}</code></div>
            <div class="ms-adv-ctrl">
              <select v-if="f.type === 'bool'" v-model="advDrafts[f.key]">
                <option value="true">开启</option><option value="false">关闭</option>
              </select>
              <input v-else-if="f.is_secret" v-model="advDrafts[f.key]" type="password" autocomplete="off" :placeholder="f.configured ? '已配置(留空不变)' : '输入密钥'" />
              <input v-else v-model="advDrafts[f.key]" :type="f.type === 'int' || f.type === 'float' ? 'number' : 'text'" />
              <button type="button" class="primary" :disabled="busy === f.key" @click="saveAdv(f)">保存</button>
              <button v-if="f.source === 'db'" type="button" :disabled="busy === f.key" @click="clearAdv(f)">清除</button>
            </div>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.ms-card {
  border: var(--rule-hair);
  border-radius: var(--radius-md, 10px);
  padding: 14px 16px;
  margin-top: 14px;
}
.ms-card h3 {
  margin: 0 0 4px;
}
.ms-hint {
  margin: 0 0 12px;
  font-size: var(--text-sm, 13px);
  color: var(--color-ink-2, #6b7280);
}
.ms-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.ms-grid label,
.ms-full {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: var(--text-sm, 13px);
}
.ms-full {
  margin-top: 12px;
}
.ms-sub {
  color: var(--color-ink-2, #6b7280);
  font-size: var(--text-xs, 12px);
}
.ms-keyhead {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ms-badge {
  font-size: var(--text-xs, 11px);
  font-weight: 700;
  padding: 1px 8px;
  border-radius: 999px;
}
.ms-badge--ok {
  background: var(--color-success-bg, #e8f5ec);
  color: #2e9e5b;
}
.ms-badge--warn {
  background: var(--color-danger-bg, #fdecec);
  color: #c0392b;
}
.ms-warn-line {
  margin: 10px 0 0;
  font-size: var(--text-sm, 13px);
  color: #c0392b;
}
select:disabled,
input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.ms-card > .primary {
  margin-top: 14px;
}
.ms-adv-toggle {
  border: 0;
  background: transparent;
  color: var(--color-accent, #2563eb);
  cursor: pointer;
  padding: 0;
  font-size: var(--text-sm, 13px);
}
.ms-adv {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 12px;
}
.ms-adv-row {
  border: var(--rule-hair);
  border-radius: var(--radius-sm, 6px);
  padding: 8px 10px;
}
.ms-adv-meta {
  display: flex;
  gap: 8px;
  align-items: baseline;
  margin-bottom: 6px;
}
.ms-adv-meta code {
  font-size: var(--text-xs, 12px);
  color: var(--color-ink-2, #6b7280);
}
.ms-adv-ctrl {
  display: flex;
  gap: 8px;
}
.ms-adv-ctrl input,
.ms-adv-ctrl select {
  flex: 1;
  min-width: 0;
}
.admin-flash {
  padding: 8px 12px;
  border-radius: var(--radius-md, 8px);
  margin: 8px 0;
}
.admin-flash--ok {
  background: var(--color-success-bg, #ecfdf5);
}
.admin-flash--err {
  background: var(--color-danger-bg, #fef2f2);
}
@media (max-width: 640px) {
  .ms-grid {
    grid-template-columns: 1fr;
  }
}
</style>
