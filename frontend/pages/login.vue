<script setup lang="ts">
import { IconAlertCircle, IconArrowRight, IconLock } from '@tabler/icons-vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import type { ApiError } from '~/types/app'

definePageMeta({
  layout: 'auth',
  colorMode: 'light',
})

const route = useRoute()
const session = useSessionStore()

const form = reactive({
  username: '',
  password: '',
  loginMethod: 'cas' as const,
})

const isSubmitting = ref(false)
const errorMessage = ref('')

const reasonMessage = computed(() => {
  const reason = typeof route.query.reason === 'string' ? route.query.reason : ''
  if (reason === 'expired') {
    return 'Your session expired. Please sign in again.'
  }
  if (reason === 'missing_user_id') {
    return 'This account does not contain a valid user ID. Please sign in with CAS student ID.'
  }
  return ''
})

const canSubmit = computed(() => !isSubmitting.value)

function toLoginErrorMessage(error: unknown) {
  const apiError = error as ApiError
  const normalizedMessage = apiError?.message?.toLowerCase?.() ?? ''

  if (apiError?.status === 401) {
    return 'Username or password is incorrect.'
  }

  if (apiError?.status === 400 && normalizedMessage.includes('unsupported service')) {
    return 'CAS login is unavailable for this account. Please check your credentials and retry.'
  }

  if (apiError?.status >= 500) {
    return 'Authentication service is temporarily unavailable. Please try again shortly.'
  }

  if (apiError?.status === 0) {
    return 'Unable to connect to backend authentication service.'
  }

  if (typeof apiError?.message === 'string' && apiError.message.trim()) {
    return apiError.message
  }

  return 'Unable to create a session right now.'
}

async function handleSubmit() {
  errorMessage.value = ''

  if (!form.username.trim() || !form.password.trim()) {
    errorMessage.value = 'Username and password are required.'
    return
  }

  isSubmitting.value = true

  try {
    const loginResult = await session.login({
      username: form.username.trim(),
      password: form.password,
      loginMethod: form.loginMethod,
    })

    if (!loginResult || !session.session.value) {
      return
    }

    await navigateTo('/dashboard')
  }
  catch (error) {
    errorMessage.value = toLoginErrorMessage(error)
  }
  finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <LayoutAuth>
    <div class="mx-auto grid w-full max-w-md gap-5">
      <div class="space-y-2">
        <div class="inline-flex w-fit items-center gap-2 rounded-full border border-[var(--auth-border)] bg-card/60 px-3 py-1 text-xs text-muted-foreground">
          <IconLock class="size-3.5" />
          Secure login
        </div>
        <h1
          class="text-2xl font-semibold tracking-tight text-foreground"
          style="font-family: 'SF Pro Display', 'SF Pro Text', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', 'Segoe UI', sans-serif;"
        >
          Welcome back
        </h1>
      </div>

      <Card class="border-[var(--auth-border)] bg-card/80 shadow-none backdrop-blur-sm">
        <CardHeader class="space-y-1">
          <CardTitle>Account</CardTitle>
        </CardHeader>
        <CardContent>
          <form class="grid gap-4" @submit.prevent="handleSubmit">
            <label class="grid gap-2">
              <span class="text-sm font-medium">Username</span>
              <Input
                v-model="form.username"
                type="text"
                autocomplete="username"
                placeholder="Student ID or your email"
              />
            </label>

            <label class="grid gap-2">
              <span class="text-sm font-medium">Password</span>
              <Input
                v-model="form.password"
                type="password"
                autocomplete="current-password"
                placeholder="Enter your CAS password"
              />
            </label>

            <p
              v-if="reasonMessage"
              class="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800"
            >
              <span class="inline-flex items-center gap-1">
                <IconAlertCircle class="size-4" />
                {{ reasonMessage }}
              </span>
            </p>

            <p v-if="errorMessage" class="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {{ errorMessage }}
            </p>

            <Button type="submit" class="w-full" :disabled="!canSubmit">
              <IconArrowRight class="size-4" />
              {{ isSubmitting ? 'Signing in...' : 'Enter dashboard' }}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  </LayoutAuth>
</template>
