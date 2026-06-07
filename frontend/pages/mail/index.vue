<script setup lang="ts">
import {
  IconChevronRight,
  IconExternalLink,
  IconInbox,
  IconLogout,
  IconMailForward,
  IconRefresh,
  IconSend,
} from '@tabler/icons-vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { ApiError, MailAccount, MailMessage, MailSendResult } from '~/types/app'

definePageMeta({
  layout: 'app',
})

const api = useApiClient()
const sessionStore = useSessionStore()

const account = ref<MailAccount | null>(null)
const messages = ref<MailMessage[]>([])
const selectedMessage = ref<MailMessage | null>(null)
const accountError = ref('')
const mailboxStatus = ref('')
const composeStatus = ref('')
const isLoadingAccount = ref(false)
const isLoadingMessages = ref(false)
const isLoadingDetail = ref(false)
const isSending = ref(false)
const isLoggingOut = ref(false)
const isComposeOpen = ref(false)

const composeForm = reactive({
  to: '',
  cc: '',
  bcc: '',
  subject: '',
  body: '',
})

const hasMailbox = computed(() => Boolean(account.value?.loggedIn))
const mailGridClass = computed(() => {
  return isComposeOpen.value
    ? '@6xl/main:grid-cols-[0.82fr_minmax(0,1.35fr)_minmax(18rem,0.9fr)]'
    : '@6xl/main:grid-cols-[0.82fr_minmax(0,1.35fr)]'
})
const sortedMessages = computed(() => {
  return [...messages.value].sort((a, b) => {
    const left = a.receivedAt ? new Date(a.receivedAt).getTime() : 0
    const right = b.receivedAt ? new Date(b.receivedAt).getTime() : 0
    return right - left
  })
})

function toApiMessage(error: unknown, fallback: string) {
  const apiError = error as Partial<ApiError>
  return typeof apiError.message === 'string' && apiError.message.trim()
    ? apiError.message
    : fallback
}

function formatDate(value?: string | null) {
  if (!value) {
    return '-'
  }

  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function parseAddresses(value: string) {
  return value
    .split(/[,\n;]/)
    .map(item => item.trim())
    .filter(Boolean)
}

function requireSendForm() {
  if (parseAddresses(composeForm.to).length === 0) {
    composeStatus.value = 'At least one recipient is required.'
    return false
  }
  if (!composeForm.subject.trim()) {
    composeStatus.value = 'Subject is required.'
    return false
  }
  if (!composeForm.body.trim()) {
    composeStatus.value = 'Body is required.'
    return false
  }
  return true
}

async function activeSession() {
  return await sessionStore.enforceSessionActive()
}

async function loadAccount() {
  const session = await activeSession()
  if (!session) {
    return
  }

  isLoadingAccount.value = true
  accountError.value = ''
  try {
    account.value = await api.getMailAccount(session)
  }
  catch (error) {
    accountError.value = toApiMessage(error, 'Unable to read mailbox account status.')
  }
  finally {
    isLoadingAccount.value = false
  }
}

async function loadMessages() {
  const session = await activeSession()
  if (!session || !hasMailbox.value) {
    return
  }

  isLoadingMessages.value = true
  accountError.value = ''
  mailboxStatus.value = ''
  try {
    messages.value = await api.listMailMessages(session, {
      folder: 'INBOX',
      limit: 50,
    })
    if (messages.value.length > 0 && !selectedMessage.value) {
      await openMessage(messages.value[0])
    }
  }
  catch (error) {
    accountError.value = toApiMessage(error, 'Unable to read mailbox messages.')
  }
  finally {
    isLoadingMessages.value = false
  }
}

async function refreshMailbox() {
  await loadAccount()
  if (hasMailbox.value) {
    await loadMessages()
  }
}

async function logoutMailbox() {
  const session = await activeSession()
  if (!session || !hasMailbox.value) {
    return
  }

  isLoggingOut.value = true
  accountError.value = ''
  mailboxStatus.value = ''
  try {
    await api.logoutMailAccount(session)
    account.value = { loggedIn: false, provider: null, mailbox: null, loggedInAt: null }
    messages.value = []
    selectedMessage.value = null
    composeStatus.value = ''
    mailboxStatus.value = 'Mailbox logged out.'
    isComposeOpen.value = false
  }
  catch (error) {
    accountError.value = toApiMessage(error, 'Unable to log out of the mailbox.')
  }
  finally {
    isLoggingOut.value = false
  }
}

async function openMessage(message: MailMessage) {
  const session = await activeSession()
  if (!session) {
    return
  }

  selectedMessage.value = message
  isLoadingDetail.value = true
  accountError.value = ''
  try {
    selectedMessage.value = await api.getMailMessage(session, message.id)
  }
  catch (error) {
    accountError.value = toApiMessage(error, 'Unable to read mailbox message detail.')
  }
  finally {
    isLoadingDetail.value = false
  }
}

async function sendMail() {
  if (!requireSendForm()) {
    return
  }

  const session = await activeSession()
  if (!session || !hasMailbox.value) {
    return
  }

  isSending.value = true
  composeStatus.value = ''
  try {
    const result: MailSendResult = await api.sendMail(session, {
      toAddresses: parseAddresses(composeForm.to),
      ccAddresses: parseAddresses(composeForm.cc),
      bccAddresses: parseAddresses(composeForm.bcc),
      subject: composeForm.subject.trim(),
      body: composeForm.body.trim(),
    })
    composeStatus.value = `Sent "${result.subject}" at ${formatDate(result.sentAt)}.`
    composeForm.to = ''
    composeForm.cc = ''
    composeForm.bcc = ''
    composeForm.subject = ''
    composeForm.body = ''
  }
  catch (error) {
    composeStatus.value = toApiMessage(error, 'Unable to send this email.')
  }
  finally {
    isSending.value = false
  }
}

onMounted(async () => {
  await refreshMailbox()
})
</script>

<template>
  <div class="w-full flex flex-col gap-4">
    <div class="flex flex-wrap items-center justify-end gap-3">
      <div class="flex flex-wrap gap-2">
        <Button variant="outline" :disabled="isLoadingAccount || isLoadingMessages" @click="refreshMailbox">
          <IconRefresh class="size-4" />
          {{ isLoadingAccount || isLoadingMessages ? 'Refreshing...' : 'Refresh' }}
        </Button>
        <Button v-if="hasMailbox" variant="outline" :disabled="isLoggingOut" @click="logoutMailbox">
          <IconLogout class="size-4" />
          {{ isLoggingOut ? 'Logging out...' : 'Log out mailbox' }}
        </Button>
        <Button variant="outline" @click="navigateTo('/sources')">
          <IconExternalLink class="size-4" />
          Integrations
        </Button>
        <Button
          class="border-orange-600 bg-orange-500 text-white shadow-xs hover:bg-orange-600 focus-visible:ring-orange-500/40"
          @click="isComposeOpen = true"
        >
          <IconSend class="size-4" />
          Send Mail
        </Button>
      </div>
    </div>

    <p v-if="accountError" class="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
      {{ accountError }}
    </p>
    <p v-if="mailboxStatus" class="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
      {{ mailboxStatus }}
    </p>

    <EmptyState
      v-if="!hasMailbox && !isLoadingAccount"
      title="Mailbox not connected"
      description="Log in to a mailbox from Integrations before reading or sending mail."
    />

    <main
      v-else
      class="@container/main grid gap-4"
      :class="mailGridClass"
    >
      <Card class="min-h-[34rem] overflow-hidden bg-card">
        <CardHeader class="border-b">
          <div class="flex items-center gap-2">
            <IconInbox class="size-4 text-muted-foreground" />
            <CardTitle>Inbox</CardTitle>
            <Badge variant="outline">{{ sortedMessages.length }}</Badge>
          </div>
        </CardHeader>
        <CardContent class="max-h-[calc(100vh-16rem)] space-y-2 overflow-y-auto p-3">
          <button
            v-for="message in sortedMessages"
            :key="message.id"
            type="button"
            class="w-full rounded-md border bg-background p-3 text-left hover:bg-muted/30"
            :class="{ 'border-primary/60 ring-1 ring-primary/20': selectedMessage?.id === message.id }"
            @click="openMessage(message)"
          >
            <div class="flex items-start justify-between gap-2">
              <p class="line-clamp-1 text-sm font-medium">{{ message.subject || '(No subject)' }}</p>
              <span class="shrink-0 text-xs text-muted-foreground">{{ formatDate(message.receivedAt) }}</span>
            </div>
            <p class="line-clamp-1 text-xs text-muted-foreground">{{ message.fromAddress }}</p>
            <p class="mt-1 line-clamp-2 text-xs text-muted-foreground">{{ message.snippet || message.textBody }}</p>
          </button>
          <EmptyState
            v-if="sortedMessages.length === 0 && !isLoadingMessages"
            title="No synced mail"
            description="Run Sync Mail from Integrations, then refresh this inbox."
          />
          <p v-if="isLoadingMessages" class="text-sm text-muted-foreground">Loading messages...</p>
        </CardContent>
      </Card>

      <Card class="min-h-[34rem] overflow-hidden bg-card">
        <CardHeader class="border-b">
          <div class="flex items-center gap-2">
            <IconMailForward class="size-4 text-muted-foreground" />
            <CardTitle>Message Detail</CardTitle>
          </div>
        </CardHeader>
        <CardContent class="max-h-[calc(100vh-16rem)] overflow-y-auto p-5">
          <div v-if="selectedMessage" class="space-y-4">
            <div class="space-y-1">
              <div class="flex flex-wrap items-center gap-2">
                <h3 class="text-lg font-semibold">{{ selectedMessage.subject || '(No subject)' }}</h3>
                <Badge v-if="!selectedMessage.isSeen" variant="outline">Unread</Badge>
                <Badge v-if="selectedMessage.hasAttachment" variant="outline">Attachment</Badge>
              </div>
              <p class="text-sm text-muted-foreground">From {{ selectedMessage.fromAddress }}</p>
              <p class="text-sm text-muted-foreground">To {{ selectedMessage.toAddress }}</p>
              <p v-if="selectedMessage.ccAddress" class="text-sm text-muted-foreground">Copy {{ selectedMessage.ccAddress }}</p>
              <p class="text-xs text-muted-foreground">{{ formatDate(selectedMessage.receivedAt) }}</p>
            </div>
            <div class="min-h-80 whitespace-pre-wrap rounded-md border bg-background p-4 text-sm leading-6">
              {{ selectedMessage.textBody || selectedMessage.htmlBody || 'No body content.' }}
            </div>
            <p v-if="isLoadingDetail" class="text-xs text-muted-foreground">Loading full message...</p>
          </div>
          <EmptyState
            v-else
            title="No message selected"
            description="Select a synced message to inspect its content."
          />
        </CardContent>
      </Card>

      <Card v-if="isComposeOpen" class="min-h-[34rem] overflow-hidden bg-card transition-[width] duration-200">
        <CardHeader class="border-b">
          <div class="flex items-center justify-between gap-2">
            <div class="flex min-w-0 items-center gap-2">
              <IconSend class="size-4 text-muted-foreground" />
              <CardTitle class="truncate">Compose</CardTitle>
            </div>
            <Button variant="outline" size="sm" class="shrink-0" @click="isComposeOpen = false">
              <IconChevronRight class="size-4" />
              Collapse
            </Button>
          </div>
        </CardHeader>
        <CardContent class="max-h-[calc(100vh-16rem)] space-y-4 overflow-y-auto p-5">
          <div class="space-y-2">
            <Label for="compose-to">To</Label>
            <Input id="compose-to" v-model="composeForm.to" placeholder="teacher@example.com" />
          </div>
          <div class="grid gap-3 sm:grid-cols-2">
            <div class="space-y-2">
              <Label for="compose-cc">Copy</Label>
              <Input id="compose-cc" v-model="composeForm.cc" placeholder="Optional, visible to all recipients" />
            </div>
            <div class="space-y-2">
              <Label for="compose-bcc">Hidden copy</Label>
              <Input id="compose-bcc" v-model="composeForm.bcc" placeholder="Optional, hidden from other recipients" />
            </div>
          </div>
          <div class="space-y-2">
            <Label for="compose-subject">Subject</Label>
            <Input id="compose-subject" v-model="composeForm.subject" />
          </div>
          <div class="space-y-2">
            <Label for="compose-body">Body</Label>
            <textarea
              id="compose-body"
              v-model="composeForm.body"
              class="min-h-48 w-full rounded-md border bg-background px-3 py-2 text-sm"
            />
          </div>
          <div class="space-y-3">
            <Button class="w-full" :disabled="isSending" @click="sendMail">
              <IconSend class="size-4" />
              {{ isSending ? 'Sending...' : 'Send Mail' }}
            </Button>
            <p v-if="composeStatus" class="rounded-md border bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
              {{ composeStatus }}
            </p>
          </div>
        </CardContent>
      </Card>
    </main>
  </div>
</template>
