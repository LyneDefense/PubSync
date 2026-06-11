<script setup lang="ts">
import { reactive } from 'vue'

defineProps<{ loading: boolean; message: string }>()
const emit = defineEmits<{ (e: 'submit', credentials: { username: string; password: string }): void }>()

const form = reactive({ username: '', password: '' })

function onSubmit() {
  emit('submit', { username: form.username, password: form.password })
}
</script>

<template>
  <main class="login-shell">
    <form class="login-panel" @submit.prevent="onSubmit">
      <div>
        <p class="brand-context">PubSync</p>
        <h1>登录工作台</h1>
      </div>
      <label>
        用户名
        <input v-model="form.username" type="text" autocomplete="username" required />
      </label>
      <label>
        密码
        <input v-model="form.password" type="password" autocomplete="current-password" required />
      </label>
      <button type="submit" class="primary" :disabled="loading">
        {{ loading ? '登录中' : '登录' }}
      </button>
      <p v-if="message" class="message error" role="alert">{{ message }}</p>
    </form>
  </main>
</template>
