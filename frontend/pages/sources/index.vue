<script setup lang="ts">
import { IconExternalLink, IconLock, IconMail, IconRefresh, IconServer2, IconTimeline, IconX } from '@tabler/icons-vue'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { WORKSPACE_QUERY_KEYS } from '~/composables/useWorkspaceStore'
import type { ApiError, MailAccount, MailProvider, MailSyncInput, MailSyncResult, SourceReason, SourceStatus } from '~/types/app'

definePageMeta({
  layout: 'app',
})

const workspace = useWorkspaceStore()
const api = useApiClient()
const sessionStore = useSessionStore()
const isSyncing = computed(() => workspace.activeSourceSyncId.value !== null)
const isManualSyncing = computed(() => workspace.activeSourceSyncId.value === 'all')
const autoSyncMeta = computed(() => workspace.autoSyncMeta.value)
const showMailLogin = ref(false)
const mailAccount = ref<MailAccount | null>(null)
const isMailAccountLoading = ref(false)
const isMailLoggingIn = ref(false)
const isMailSyncing = ref(false)
const mailLoginError = ref('')
const mailLoginStatus = ref('')
const mailSyncStatus = ref('')
const mailLoginForm = reactive({
  provider: 'qq' as MailProvider,
  emailAddress: '',
  password: '',
})
const mailSyncForm = reactive<MailSyncInput>({
  folder: 'INBOX',
  limit: 20,
  unreadOnly: false,
})
const mailLimitOptions = [10, 20, 50, 100]

const syncedCount = computed(() => workspace.sources.value.filter(source => source.status === 'synced').length)
const needsSyncCount = computed(() => workspace.sources.value.filter(source => source.status === 'needs_sync').length)
const authExpiredCount = computed(() => workspace.sources.value.filter(source => source.status === 'auth_expired').length)
const hasMailAccount = computed(() => Boolean(mailAccount.value?.loggedIn))
const autoSyncHint = computed(() => {
  if (autoSyncMeta.value.autoSyncState === 'running') {
    return 'Background auto-sync is running.'
  }
  if (autoSyncMeta.value.autoSyncState === 'backoff') {
    return autoSyncMeta.value.nextAutoSyncAllowedAt
      ? `Background auto-sync failed. Next retry after ${formatDate(autoSyncMeta.value.nextAutoSyncAllowedAt)}.`
      : 'Background auto-sync failed. Waiting for next retry window.'
  }
  return autoSyncMeta.value.lastAutoSyncAt
    ? `Last background auto-sync at ${formatDate(autoSyncMeta.value.lastAutoSyncAt)}.`
    : 'Background auto-sync has not run yet in this session.'
})

function formatDate(value?: string) {
  if (!value) {
    return '-'
  }

  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

function sourceTone(status: SourceStatus) {
  if (status === 'synced') {
    return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  }
  if (status === 'needs_sync') {
    return 'border-amber-200 bg-amber-50 text-amber-700'
  }
  return 'border-red-200 bg-red-50 text-red-700'
}

function sourceStatusLabel(status: SourceStatus) {
  if (status === 'synced') {
    return 'synced'
  }
  if (status === 'needs_sync') {
    return 'needs sync'
  }
  return 'auth expired'
}

function sourceReasonLabel(reason?: SourceReason) {
  if (reason === 'cas_required') {
    return 'CAS login required'
  }
  if (reason === 'not_implemented') {
    return 'Backend API not implemented'
  }
  if (reason === 'not_synced') {
    return 'Run sync/all first'
  }
  if (reason === 'unsupported_login_method') {
    return 'Login method unsupported'
  }
  if (reason === 'auth_expired') {
    return 'Session expired'
  }
  if (reason === 'sync_failed') {
    return 'Sync failed'
  }
  return ''
}

function syncTone(status: string) {
  if (status === 'success') {
    return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  }
  if (status === 'warning') {
    return 'border-amber-200 bg-amber-50 text-amber-700'
  }
  return 'border-red-200 bg-red-50 text-red-700'
}

function toApiMessage(error: unknown, fallback: string) {
  const apiError = error as Partial<ApiError>
  return typeof apiError.message === 'string' && apiError.message.trim()
    ? apiError.message
    : fallback
}

function openMailLogin() {
  mailLoginError.value = ''
  mailLoginStatus.value = ''
  showMailLogin.value = true
}

function closeMailLogin() {
  showMailLogin.value = false
  mailLoginForm.password = ''
}

async function loadMailAccount() {
  const session = await sessionStore.enforceSessionActive()
  if (!session) {
    return
  }

  isMailAccountLoading.value = true
  mailLoginError.value = ''
  try {
    mailAccount.value = await api.getMailAccount(session)
    if (mailAccount.value.loggedIn) {
      mailLoginForm.provider = mailAccount.value.provider ?? 'qq'
      mailLoginForm.emailAddress = mailAccount.value.mailbox ?? ''
    }
  }
  catch (error) {
    mailLoginError.value = toApiMessage(error, 'Unable to read mailbox account status.')
  }
  finally {
    isMailAccountLoading.value = false
  }
}

async function loginMailFromSources() {
  if (!mailLoginForm.emailAddress.trim()) {
    mailLoginError.value = 'Email address is required.'
    return
  }
  if (!mailLoginForm.password.trim()) {
    mailLoginError.value = 'Mailbox authorization code or password is required.'
    return
  }

  const session = await sessionStore.enforceSessionActive()
  if (!session) {
    return
  }

  isMailLoggingIn.value = true
  mailLoginError.value = ''
  mailLoginStatus.value = ''
  try {
    const account = await api.loginMailAccount(session, {
      provider: mailLoginForm.provider,
      emailAddress: mailLoginForm.emailAddress.trim(),
      password: mailLoginForm.password,
    })
    mailAccount.value = account
    mailLoginForm.password = ''
    mailLoginStatus.value = `Mailbox connected: ${account.mailbox ?? mailLoginForm.emailAddress.trim()}`
    mailSyncStatus.value = mailLoginStatus.value
    await workspace.refreshWorkspaceQuery(WORKSPACE_QUERY_KEYS.sources)
  }
  catch (error) {
    mailLoginError.value = toApiMessage(error, 'Unable to log in to this mailbox.')
  }
  finally {
    isMailLoggingIn.value = false
  }
}

async function syncMailFromSources() {
  const session = await sessionStore.enforceSessionActive()
  if (!session || !hasMailAccount.value) {
    return
  }

  isMailSyncing.value = true
  mailSyncStatus.value = ''
  mailLoginError.value = ''
  try {
    const result: MailSyncResult | null = await workspace.syncMailSource({ ...mailSyncForm })
    if (!result) {
      return
    }
    mailSyncStatus.value = `Synced ${result.fetched} fetched, ${result.inserted} inserted, ${result.updated} updated.`
  }
  catch (error) {
    mailSyncStatus.value = toApiMessage(error, 'Unable to sync mailbox messages.')
  }
  finally {
    isMailSyncing.value = false
  }
}

async function syncCasFromSources() {
  await workspace.syncCasSources()
}

async function syncAllFromSources() {
  if (!hasMailAccount.value) {
    openMailLogin()
    mailLoginStatus.value = 'Connect a mailbox before running Sync All Sources.'
    return
  }

  isMailSyncing.value = true
  mailSyncStatus.value = ''
  mailLoginError.value = ''
  try {
    const result = await workspace.syncAllSourcesWithMail({ ...mailSyncForm })
    if (result) {
      mailSyncStatus.value = `Sync All completed. Mail synced ${result.fetched} fetched, ${result.inserted} inserted, ${result.updated} updated.`
    }
  }
  catch (error) {
    mailSyncStatus.value = toApiMessage(error, 'Sync All completed CAS sync, but mail sync failed.')
  }
  finally {
    isMailSyncing.value = false
  }
}

onMounted(() => {
  void loadMailAccount()
})
</script>

<template>
  <div class="w-full flex flex-col gap-4">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <Button :disabled="isSyncing || isMailSyncing" @click="syncAllFromSources">
        <IconRefresh class="size-4" />
        {{ isManualSyncing || isMailSyncing ? 'Syncing...' : 'Sync All Sources' }}
      </Button>
    </div>

    <main class="@container/main flex flex-col gap-4 md:gap-6">
      <div class="grid grid-cols-1 gap-4 @xl/main:grid-cols-3">
        <Card>
          <CardHeader>
            <CardDescription>Synchronized</CardDescription>
            <CardTitle class="text-3xl">{{ syncedCount }}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Needs Sync</CardDescription>
            <CardTitle class="text-3xl">{{ needsSyncCount }}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Auth Expired</CardDescription>
            <CardTitle class="text-3xl">{{ authExpiredCount }}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      <div class="grid gap-4 @4xl/main:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <CardHeader>
            <div class="flex items-center gap-2">
              <IconServer2 class="size-4 text-muted-foreground" />
              <CardTitle>Connections</CardTitle>
            </div>
          </CardHeader>
          <CardContent class="space-y-3">
            <p class="rounded-md border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
              {{ autoSyncHint }}
            </p>
            <div
              v-for="source in workspace.sources.value"
              :key="source.id"
              class="rounded-lg border bg-card p-4"
            >
              <div class="space-y-2">
                <div class="flex flex-wrap items-center gap-2">
                  <p class="text-sm font-semibold">{{ source.name }}</p>
                  <span class="rounded-full border px-2 py-0.5 text-xs font-medium" :class="sourceTone(source.status)">
                    {{ sourceStatusLabel(source.status) }}
                  </span>
                </div>
                <p class="text-sm text-muted-foreground">{{ source.description }}</p>
                <p
                  v-if="source.reason"
                  class="text-xs font-medium text-amber-700"
                >
                  {{ sourceReasonLabel(source.reason) }}
                </p>
                <div v-if="source.id === 'bb' || source.id === 'tis'" class="pt-1">
                  <Button size="sm" :disabled="isSyncing" @click="syncCasFromSources">
                    <IconRefresh class="size-4" />
                    {{ isManualSyncing ? 'Syncing...' : 'Sync CAS Info' }}
                  </Button>
                </div>
                <div v-if="source.id === 'mail'" class="space-y-3 pt-1">
                  <p v-if="hasMailAccount" class="text-xs text-muted-foreground">
                    Connected mailbox: {{ mailAccount?.mailbox }}
                  </p>
                  <p v-if="source.id === 'mail' && mailSyncStatus" class="rounded-md border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
                    {{ mailSyncStatus }}
                  </p>
                  <div class="flex flex-wrap gap-2">
                  <div class="flex flex-wrap gap-2">
                      <Label for="sources-mail-limit">Recent mail</Label>
                      <select
                        id="sources-mail-limit"
                        v-model.number="mailSyncForm.limit"
                        class="h-9 rounded-md border border-input bg-background px-3 text-sm text-foreground shadow-xs outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]"
                      >
                        <option v-for="option in mailLimitOptions" :key="option" :value="option">
                          {{ option }}
                        </option>
                      </select>
                    </div>
                    <Button v-if="!hasMailAccount" size="sm" :disabled="isMailAccountLoading" @click="openMailLogin">
                      <IconMail class="size-4" />
                      {{ isMailAccountLoading ? 'Checking...' : 'Log in mailbox' }}
                    </Button>
                    <Button v-else size="sm" :disabled="isMailSyncing" @click="syncMailFromSources">
                      <IconRefresh class="size-4" />
                      {{ isMailSyncing ? 'Syncing...' : 'Sync Mail' }}
                    </Button>
                    <Button size="sm" variant="outline" @click="navigateTo('/mail')">
                      <IconExternalLink class="size-4" />
                      Open Mail
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div class="flex items-center gap-2">
              <IconTimeline class="size-4 text-muted-foreground" />
              <CardTitle>Recent Sync Jobs</CardTitle>
            </div>
          </CardHeader>
          <CardContent class="space-y-3">
            <div
              v-for="job in workspace.syncJobs.value"
              :key="job.id"
              class="rounded-lg border bg-muted/40 p-3"
            >
              <div class="flex items-center justify-between gap-2">
                <p class="text-sm font-medium">{{ job.title }}</p>
                <span class="rounded-full border px-2 py-0.5 text-xs capitalize" :class="syncTone(job.status)">
                  {{ job.status }}
                </span>
              </div>
              <p class="mt-1 text-xs text-muted-foreground">{{ job.detail }}</p>
              <p class="mt-1 text-xs text-muted-foreground">{{ formatDate(job.runAt) }}</p>
            </div>
          </CardContent>
        </Card>
      </div>

    </main>

    <div
      v-if="showMailLogin"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="sources-mail-login-title"
    >
      <div class="w-full max-w-lg overflow-hidden rounded-lg border bg-background shadow-xl">
        <div class="flex items-start justify-between border-b bg-card px-5 py-4">
          <div class="space-y-2">
            <div class="inline-flex w-fit items-center gap-2 rounded-full border bg-muted/40 px-3 py-1 text-xs text-muted-foreground">
              <IconLock class="size-3.5" />
              Mail login
            </div>
            <div>
              <h2 id="sources-mail-login-title" class="text-lg font-semibold">Mailbox Account</h2>
            </div>
          </div>
          <button type="button" class="rounded-md p-1 hover:bg-muted" aria-label="Close mailbox login" @click="closeMailLogin">
            <IconX class="size-4" />
          </button>
        </div>
        <div class="space-y-4 px-5 py-4">
          <div class="grid gap-3 sm:grid-cols-[minmax(0,0.35fr)_minmax(0,0.65fr)]">
            <div class="min-w-0 space-y-2">
              <Label for="sources-mail-provider">Provider</Label>
              <select
                id="sources-mail-provider"
                v-model="mailLoginForm.provider"
                class="h-9 w-full min-w-0 rounded-md border bg-background px-3 text-sm"
              >
                <option value="qq">QQ Mail</option>
                <option value="exmail">Tencent Exmail</option>
              </select>
            </div>
            <div class="min-w-0 space-y-2">
              <Label for="sources-mail-address">Email</Label>
              <Input id="sources-mail-address" v-model="mailLoginForm.emailAddress" placeholder="student@qq.com" autocomplete="username" />
            </div>
          </div>
          <div class="space-y-2">
            <Label for="sources-mail-password">Authorization code / password</Label>
            <Input
              id="sources-mail-password"
              v-model="mailLoginForm.password"
              type="password"
              placeholder="Mailbox authorization code"
              autocomplete="current-password"
              @keydown.enter="loginMailFromSources"
            />
          </div>
          <p v-if="mailLoginError" class="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {{ mailLoginError }}
          </p>
          <p v-if="mailLoginStatus" class="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            {{ mailLoginStatus }}
          </p>
        </div>
        <div class="flex flex-wrap justify-end gap-2 border-t px-5 py-4">
          <Button variant="outline" @click="closeMailLogin">Close</Button>
          <Button :disabled="isMailLoggingIn" @click="loginMailFromSources">
            <IconMail class="size-4" />
            {{ isMailLoggingIn ? 'Connecting...' : 'Connect Mailbox' }}
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>
