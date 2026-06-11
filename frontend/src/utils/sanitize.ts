import DOMPurify from 'dompurify'

/**
 * Sanitize HTML before injecting it via `v-html`.
 *
 * The article preview and blogger distillation reports are produced by an LLM
 * (and are user-editable), so they are untrusted. Sanitizing here removes script
 * vectors (e.g. `<script>`, `onerror=`, `javascript:` URLs) while keeping the
 * formatting markup the previews rely on.
 */
export function sanitizeHtml(html: string | null | undefined): string {
  if (!html) {
    return ''
  }
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
}
