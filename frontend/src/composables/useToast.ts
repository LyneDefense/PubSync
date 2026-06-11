import { ref } from 'vue'

// Module-level singleton: the app shows a single global status/error message,
// so the state lives at module scope and every caller (App.vue and any future
// component) shares the same refs.
const message = ref('')
const isError = ref(false)

function showMessage(text: string, error = false): void {
  message.value = text
  isError.value = error
}

export function useToast() {
  return { message, isError, showMessage }
}
