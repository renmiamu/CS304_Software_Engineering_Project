<script setup lang="ts">
import {
  IconArrowUp,
  IconBook2,
  IconBrain,
  IconFiles,
  IconFolder,
  IconLoader,
  IconMessageCircle,
  IconPencil,
  IconPlus,
  IconQuote,
  IconRefresh,
  IconSearch,
  IconTrash,
  IconX,
} from '@tabler/icons-vue'
import type { AssistantSessionDocumentItem, AssistantSessionDocumentSummary } from '~/composables/useApiClient'
import type { ApprovalAction, AssistantModel, ChatMessage, CitationSource } from '~/types/app'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

definePageMeta({
  layout: 'app',
})

const workspace = useWorkspaceStore()
const draft = ref('')
const conversationSearch = ref('')
const editingConversationId = ref<string | null>(null)
const editingTitle = ref('')
const renamePending = ref(false)
const deletePendingId = ref<string | null>(null)
const conversationMutationError = ref('')
const webSearchEnabled = ref(false)
const activeSidePanel = ref<'knowledge' | 'session-documents' | 'sources' | 'workspace' | null>(null)
const activeCitationMessageId = ref<string | null>(null)
const activeCitationIndex = ref<number | null>(null)
const clientReady = ref(false)
const temporaryUploadInputRef = ref<HTMLInputElement | null>(null)
const permanentUploadInputRef = ref<HTMLInputElement | null>(null)
const sessionDocuments = ref<AssistantSessionDocumentItem[]>([])
const sessionDocumentsSummary = ref<AssistantSessionDocumentSummary | null>(null)
const sessionDocumentsLoading = ref(false)
const sessionDocumentsError = ref<string | null>(null)
const approvalMutationId = ref<string | null>(null)
const fileWorkspacePath = ref('')
const fileWorkspaceDraft = ref('')
const fileWorkspaceLoading = ref(false)
const fileWorkspaceSaving = ref(false)
const fileWorkspaceError = ref<string | null>(null)
const fileWorkspaceStatus = ref<string | null>(null)

let sessionDocumentsAbortController: AbortController | null = null
let latestSessionDocumentsRequestId = 0

const currentModel = computed({
  get: () => coerceModelForSearch(workspace.assistantModel.value, webSearchEnabled.value),
  set: (value) => {
    workspace.assistantModel.value = coerceModelForSearch(value, webSearchEnabled.value)
  },
})

const selectableModelOptions = computed(() => workspace.assistantModelOptions.map(option => ({
  ...option,
  disabled: isModelDisabled(option.value, webSearchEnabled.value),
})))

const filteredConversations = computed(() => workspace.searchConversations(conversationSearch.value))
const hasMessages = computed(() => workspace.messages.value.length > 0)
const permanentKnowledgeUnavailable = computed(() => workspace.permanentKnowledgeBackendState.value === 'unavailable')
const assistantLoading = computed(() => workspace.isBootstrappingAssistant.value)
const conversationLoading = computed(() => workspace.activeAssistantLoadConversationId.value === workspace.activeConversationId.value)
const knowledgePanelOpen = computed(() => activeSidePanel.value === 'knowledge')
const sessionDocumentsPanelOpen = computed(() => activeSidePanel.value === 'session-documents')
const sourcesPanelOpen = computed(() => activeSidePanel.value === 'sources')
const workspacePanelOpen = computed(() => activeSidePanel.value === 'workspace')
const citationMessages = computed(() => workspace.messages.value.filter(message => message.role === 'assistant' && message.citations?.length))
const hasSources = computed(() => citationMessages.value.length > 0)
const hasDocumentContext = computed(() => {
  return workspace.permanentKnowledgeItems.value.length > 0
    || workspace.temporaryKnowledgeItems.value.length > 0
    || sessionDocuments.value.length > 0
    || Boolean(sessionDocumentsSummary.value?.hasDocuments)
})
const canShowSources = computed(() => hasSources.value && hasDocumentContext.value)
const activeSourceMessage = computed(() => {
  const selected = citationMessages.value.find(message => message.id === activeCitationMessageId.value)
  return selected ?? citationMessages.value.at(-1) ?? null
})
const activeSources = computed<CitationSource[]>(() => activeSourceMessage.value?.citations ?? [])

const approvalsById = computed(() => {
  return new Map(workspace.approvals.value.map(item => [item.id, item]))
})

function isModelDisabled(model: AssistantModel, webEnabled: boolean) {
  if (webEnabled) {
    return model === 'deepseek-chat'
  }
  return model === 'deep-research'
}

function coerceModelForSearch(model: AssistantModel, webEnabled: boolean) {
  if (webEnabled && model === 'deepseek-chat') {
    return 'deepseek-reasoner'
  }
  if (!webEnabled && model === 'deep-research') {
    return 'deepseek-reasoner'
  }
  return model
}

function escapeHtml(value: string) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function sanitizeUrl(value: string) {
  const trimmed = value.trim()
  if (!trimmed) {
    return ''
  }

  if (/^https?:\/\//i.test(trimmed)) {
    return trimmed.replaceAll('"', '%22')
  }

  return ''
}

function renderInlineMarkdown(value: string) {
  let html = escapeHtml(value)

  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, label: string, url: string) => {
    const safeUrl = sanitizeUrl(url)
    if (!safeUrl) {
      return escapeHtml(label)
    }

    return `<a href="${safeUrl}" target="_blank" rel="noreferrer noopener">${escapeHtml(label)}</a>`
  })
  html = html.replace(/##(?:引用)?(\d+)(?:\$\$|##)/g, '<button type="button" class="assistant-citation-marker" data-citation-index="$1" aria-label="Open source $1">[$1]</button>')
  html = html.replace(/&lt;br\s*\/?&gt;/gi, '<br>')
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>')

  return html
}

function splitTableRow(line: string) {
  const trimmed = line.trim()
  if (!trimmed.includes('|')) {
    return []
  }

  return trimmed
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map(cell => cell.trim())
}

function isTableSeparator(line: string) {
  const cells = splitTableRow(line)
  return cells.length > 0 && cells.every(cell => /^:?-{3,}:?$/.test(cell.trim()))
}

function tableAlignments(separatorLine: string) {
  return splitTableRow(separatorLine).map((cell) => {
    const trimmed = cell.trim()
    if (trimmed.startsWith(':') && trimmed.endsWith(':')) {
      return 'center'
    }
    if (trimmed.endsWith(':')) {
      return 'right'
    }
    if (trimmed.startsWith(':')) {
      return 'left'
    }
    return null
  })
}

function renderTable(headerLine: string, separatorLine: string, bodyLines: string[]) {
  const headers = splitTableRow(headerLine)
  const alignments = tableAlignments(separatorLine)
  const rows = bodyLines
    .map(line => splitTableRow(line))
    .filter(cells => cells.length > 0)

  const alignAttribute = (index: number) => {
    const alignment = alignments[index]
    return alignment ? ` style="text-align: ${alignment}"` : ''
  }

  const thead = headers
    .map((cell, index) => `<th${alignAttribute(index)}>${renderInlineMarkdown(cell)}</th>`)
    .join('')
  const tbody = rows
    .map(row => `<tr>${row.map((cell, index) => `<td${alignAttribute(index)}>${renderInlineMarkdown(cell)}</td>`).join('')}</tr>`)
    .join('')

  return `<div class="assistant-table-wrap"><table><thead><tr>${thead}</tr></thead><tbody>${tbody}</tbody></table></div>`
}

function renderMarkdown(value: string) {
  const normalized = value.replace(/\r\n/g, '\n').trim()
  if (!normalized) {
    return ''
  }

  const lines = normalized.split('\n')
  const html: string[] = []
  let inUnorderedList = false
  let inOrderedList = false
  let inBlockquote = false
  let inParagraph = false
  let inCodeBlock = false
  let codeBuffer: string[] = []

  const closeParagraph = () => {
    if (inParagraph) {
      html.push('</p>')
      inParagraph = false
    }
  }

  const closeLists = () => {
    if (inUnorderedList) {
      html.push('</ul>')
      inUnorderedList = false
    }
    if (inOrderedList) {
      html.push('</ol>')
      inOrderedList = false
    }
  }

  const closeBlockquote = () => {
    if (inBlockquote) {
      html.push('</blockquote>')
      inBlockquote = false
    }
  }

  const flushCodeBlock = () => {
    if (!inCodeBlock) {
      return
    }

    html.push(`<pre><code>${escapeHtml(codeBuffer.join('\n'))}</code></pre>`)
    inCodeBlock = false
    codeBuffer = []
  }

  for (let index = 0; index < lines.length; index += 1) {
    const rawLine = lines[index] ?? ''
    const line = rawLine.trimEnd()
    const trimmed = line.trim()

    if (trimmed.startsWith('```')) {
      closeParagraph()
      closeLists()
      closeBlockquote()
      if (inCodeBlock) {
        flushCodeBlock()
      }
      else {
        inCodeBlock = true
      }
      continue
    }

    if (inCodeBlock) {
      codeBuffer.push(rawLine)
      continue
    }

    if (!trimmed) {
      closeParagraph()
      closeLists()
      closeBlockquote()
      continue
    }

    const nextLine = lines[index + 1]?.trim()
    if (trimmed.includes('|') && nextLine && isTableSeparator(nextLine)) {
      closeParagraph()
      closeLists()
      closeBlockquote()
      const bodyLines: string[] = []
      index += 2
      while (index < lines.length) {
        const tableLine = (lines[index] ?? '').trim()
        if (!tableLine || !tableLine.includes('|')) {
          index -= 1
          break
        }
        bodyLines.push(tableLine)
        index += 1
      }
      html.push(renderTable(trimmed, nextLine, bodyLines))
      continue
    }

    const headingMatch = trimmed.match(/^(#{1,6})\s+(.*)$/)
    if (headingMatch) {
      closeParagraph()
      closeLists()
      closeBlockquote()
      const level = headingMatch[1].length
      html.push(`<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`)
      continue
    }

    const unorderedMatch = trimmed.match(/^[-*+]\s+(.*)$/)
    if (unorderedMatch) {
      closeParagraph()
      closeBlockquote()
      if (!inUnorderedList) {
        closeLists()
        html.push('<ul>')
        inUnorderedList = true
      }
      html.push(`<li>${renderInlineMarkdown(unorderedMatch[1])}</li>`)
      continue
    }

    const orderedMatch = trimmed.match(/^\d+\.\s+(.*)$/)
    if (orderedMatch) {
      closeParagraph()
      closeBlockquote()
      if (!inOrderedList) {
        closeLists()
        html.push('<ol>')
        inOrderedList = true
      }
      html.push(`<li>${renderInlineMarkdown(orderedMatch[1])}</li>`)
      continue
    }

    const quoteMatch = trimmed.match(/^>\s?(.*)$/)
    if (quoteMatch) {
      closeParagraph()
      closeLists()
      if (!inBlockquote) {
        html.push('<blockquote>')
        inBlockquote = true
      }
      html.push(`<p>${renderInlineMarkdown(quoteMatch[1])}</p>`)
      continue
    }

    closeLists()
    closeBlockquote()
    if (!inParagraph) {
      html.push('<p>')
      inParagraph = true
    }
    else {
      html.push('<br>')
    }
    html.push(renderInlineMarkdown(trimmed))
  }

  flushCodeBlock()
  closeParagraph()
  closeLists()
  closeBlockquote()

  return html.join('')
}

function renderMessageContent(message: ChatMessage) {
  const content = message.content || (message.role === 'assistant' ? 'Thinking...' : '')
  return renderMarkdown(content)
}

function applyRecommendedQuestion(question: string) {
  draft.value = question
}

function openSourcesPanel(message?: ChatMessage, citationIndex?: number) {
  const targetMessage = message?.citations?.length
    ? message
    : citationMessages.value.at(-1)
  if (!targetMessage?.citations?.length) {
    return
  }

  activeCitationMessageId.value = targetMessage.id
  activeCitationIndex.value = citationIndex ?? targetMessage.citations[0]?.index ?? null
  activeSidePanel.value = 'sources'
}

function handleCitationClick(event: MouseEvent, message: ChatMessage) {
  const target = event.target instanceof HTMLElement
    ? event.target.closest<HTMLElement>('[data-citation-index]')
    : null
  if (!target) {
    return
  }

  const citationIndex = Number(target.dataset.citationIndex)
  openSourcesPanel(message, Number.isFinite(citationIndex) ? citationIndex : undefined)
}

function formatDate(value: string) {
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

function formatFileSize(size: number) {
  if (!Number.isFinite(size) || size <= 0) {
    return '0 KB'
  }

  const kb = size / 1024
  if (kb >= 1024) {
    return `${(kb / 1024).toFixed(1)} MB`
  }

  return `${Math.max(1, Math.round(kb))} KB`
}

function getErrorMessage(error: unknown, fallback: string) {
  if (error instanceof Error && error.message.trim()) {
    return error.message
  }

  if (error && typeof error === 'object') {
    const candidate = error as { message?: unknown }
    if (typeof candidate.message === 'string' && candidate.message.trim()) {
      return candidate.message
    }
  }

  return fallback
}

function isActiveConversation(conversationId: string) {
  return workspace.activeConversationId.value === conversationId
}

function createConversation() {
  workspace.createConversation()
}

function selectConversation(conversationId: string) {
  workspace.switchConversation(conversationId)
}

function canDeleteConversation(conversationId: string) {
  if (workspace.isSendingMessage.value) {
    return false
  }
  if (deletePendingId.value === conversationId) {
    return false
  }
  return true
}

async function removeConversation(conversationId: string) {
  if (!canDeleteConversation(conversationId)) {
    return
  }

  conversationMutationError.value = ''
  deletePendingId.value = conversationId
  try {
    await workspace.deleteConversation(conversationId)
  }
  catch (error) {
    conversationMutationError.value = error && typeof error === 'object' && 'message' in error
      ? String((error as { message: unknown }).message)
      : 'Unable to delete conversation.'
  }
  finally {
    deletePendingId.value = null
  }
}

function beginRenameConversation(conversationId: string, title: string) {
  conversationMutationError.value = ''
  editingConversationId.value = conversationId
  editingTitle.value = title
}

function cancelRenameConversation() {
  editingConversationId.value = null
  editingTitle.value = ''
}

async function submitRenameConversation(conversationId: string) {
  const trimmed = editingTitle.value.trim()
  if (!trimmed || renamePending.value) {
    cancelRenameConversation()
    return
  }

  conversationMutationError.value = ''
  renamePending.value = true
  try {
    await workspace.renameConversation(conversationId, trimmed)
    cancelRenameConversation()
  }
  catch (error) {
    conversationMutationError.value = error && typeof error === 'object' && 'message' in error
      ? String((error as { message: unknown }).message)
      : 'Unable to rename conversation.'
  }
  finally {
    renamePending.value = false
  }
}

function handleRenameKeydown(event: KeyboardEvent, conversationId: string) {
  if (event.key === 'Enter') {
    event.preventDefault()
    void submitRenameConversation(conversationId)
  }
  if (event.key === 'Escape') {
    event.preventDefault()
    cancelRenameConversation()
  }
}

function messageTone(role: ChatMessage['role']) {
  if (role === 'user') {
    return 'bg-primary text-primary-foreground'
  }

  if (role === 'system') {
    return 'bg-warning/15 text-warning-foreground ring-1 ring-warning/40'
  }

  return 'bg-secondary text-secondary-foreground'
}

function resolveApprovals(message: ChatMessage) {
  const ids = message.linkedApprovalIds ?? []
  return ids
    .map(id => approvalsById.value.get(id))
    .filter((item): item is ApprovalAction => Boolean(item))
}

async function handleApprovalAction(action: ApprovalAction, nextState: ApprovalAction['state']) {
  if (action.state !== 'pending' || approvalMutationId.value) {
    return
  }

  approvalMutationId.value = action.id
  try {
    await workspace.updateApproval(action.id, nextState)
  }
  finally {
    approvalMutationId.value = null
  }
}

function triggerTemporaryUpload() {
  temporaryUploadInputRef.value?.click()
}

function triggerPermanentUpload() {
  if (permanentKnowledgeUnavailable.value) {
    return
  }
  permanentUploadInputRef.value?.click()
}

function resetSessionDocumentsState() {
  sessionDocuments.value = []
  sessionDocumentsSummary.value = null
  sessionDocumentsError.value = null
}

async function handleTemporaryUpload(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  try {
    if (files.length > 0) {
      const uploaded = await workspace.uploadTemporaryKnowledge(files)
      if (uploaded) {
        await refreshSessionDocuments()
      }
    }
  }
  catch (error) {
    sessionDocumentsError.value = getErrorMessage(error, 'Unable to upload temporary files.')
  }
  finally {
    input.value = ''
  }
}

async function handlePermanentUpload(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  try {
    if (files.length > 0) {
      const uploaded = await workspace.uploadPermanentKnowledge(files)
      if (uploaded) {
        await refreshSessionDocuments()
      }
    }
  }
  catch (error) {
    workspace.permanentKnowledgeError.value = getErrorMessage(error, 'Unable to upload knowledge-base files.')
  }
  finally {
    input.value = ''
  }
}

async function refreshPermanentKnowledge() {
  await workspace.syncPermanentKnowledgeFromBackend()
}

async function deletePermanentKnowledge(itemId: string) {
  await workspace.deletePermanentKnowledgeFile(itemId)
}

async function refreshFileWorkspace() {
  const sessionStore = useSessionStore()
  const activeSession = await sessionStore.enforceSessionActive()
  if (!activeSession) {
    fileWorkspaceError.value = 'Authentication is required to load the file workspace.'
    return
  }

  fileWorkspaceLoading.value = true
  fileWorkspaceError.value = null
  fileWorkspaceStatus.value = null
  try {
    const api = useApiClient()
    const result = await api.getAgentFileWorkspace(activeSession)
    fileWorkspacePath.value = result.workspaceRoot
    fileWorkspaceDraft.value = result.workspaceRoot
  }
  catch (error) {
    fileWorkspaceError.value = getErrorMessage(error, 'Unable to load the file workspace.')
  }
  finally {
    fileWorkspaceLoading.value = false
  }
}

async function saveFileWorkspace() {
  const nextPath = fileWorkspaceDraft.value.trim()
  if (!nextPath || fileWorkspaceSaving.value) {
    return
  }

  const sessionStore = useSessionStore()
  const activeSession = await sessionStore.enforceSessionActive()
  if (!activeSession) {
    fileWorkspaceError.value = 'Authentication is required to update the file workspace.'
    return
  }

  fileWorkspaceSaving.value = true
  fileWorkspaceError.value = null
  fileWorkspaceStatus.value = null
  try {
    const api = useApiClient()
    const result = await api.setAgentFileWorkspace(activeSession, nextPath)
    fileWorkspacePath.value = result.workspaceRoot
    fileWorkspaceDraft.value = result.workspaceRoot
    fileWorkspaceStatus.value = result.message || 'Workspace updated.'
  }
  catch (error) {
    fileWorkspaceError.value = getErrorMessage(error, 'Unable to update the file workspace.')
  }
  finally {
    fileWorkspaceSaving.value = false
  }
}

async function refreshSessionDocuments() {
  const sessionInfo = await workspace.ensureActiveAssistantBackendSession()
  if (!sessionInfo) {
    resetSessionDocumentsState()
    sessionDocumentsError.value = 'Unable to prepare the current session.'
    return
  }

  const sessionStore = useSessionStore()
  const activeSession = await sessionStore.enforceSessionActive()
  if (!activeSession) {
    resetSessionDocumentsState()
    sessionDocumentsError.value = 'Authentication is required to load session documents.'
    return
  }

  sessionDocumentsAbortController?.abort()
  const requestId = ++latestSessionDocumentsRequestId
  const controller = new AbortController()
  sessionDocumentsAbortController = controller
  sessionDocumentsLoading.value = true
  sessionDocumentsError.value = null

  try {
    const api = useApiClient()
    const [documents, summary] = await Promise.all([
      api.listSessionDocuments(activeSession, sessionInfo.sessionId, controller.signal),
      api.getSessionDocumentsSummary(activeSession, sessionInfo.sessionId, controller.signal),
    ])

    if (requestId !== latestSessionDocumentsRequestId) {
      return
    }

    sessionDocuments.value = documents
    sessionDocumentsSummary.value = summary
  }
  catch (error) {
    if ((error as Error)?.name === 'AbortError') {
      return
    }

    if (requestId !== latestSessionDocumentsRequestId) {
      return
    }

    resetSessionDocumentsState()
    sessionDocumentsError.value = error instanceof Error ? error.message : 'Unable to load session documents.'
  }
  finally {
    if (requestId === latestSessionDocumentsRequestId) {
      sessionDocumentsLoading.value = false
    }
  }
}

function removeTemporaryKnowledge(itemId: string) {
  workspace.removeTemporaryKnowledgeItem(itemId)
}

function toggleSidePanel(panel: 'knowledge' | 'session-documents' | 'sources' | 'workspace') {
  if (panel === 'sources') {
    if (!canShowSources.value) {
      activeSidePanel.value = null
      return
    }

    if (activeSidePanel.value === 'sources') {
      activeSidePanel.value = null
      return
    }
    openSourcesPanel()
    return
  }

  activeSidePanel.value = activeSidePanel.value === panel ? null : panel
}

async function submitMessage() {
  const nextMessage = draft.value.trim()
  if (!nextMessage) {
    return
  }

  draft.value = ''
  await workspace.sendMessage({
    content: nextMessage,
    model: currentModel.value,
    webSearchEnabled: webSearchEnabled.value,
    temporaryKnowledgeIds: workspace.temporaryKnowledgeItems.value.map(item => item.id),
  })
}

watch([webSearchEnabled, () => workspace.activeConversationId.value], ([enabled]) => {
  currentModel.value = coerceModelForSearch(workspace.assistantModel.value, enabled)
}, { immediate: true })

watch(knowledgePanelOpen, (open) => {
  if (open) {
    void refreshPermanentKnowledge()
  }
})

watch(workspacePanelOpen, (open) => {
  if (open) {
    void refreshFileWorkspace()
  }
})

watch([sessionDocumentsPanelOpen, () => workspace.activeConversationId.value], ([open]) => {
  if (open) {
    void refreshSessionDocuments()
    return
  }

  sessionDocumentsAbortController?.abort()
  sessionDocumentsLoading.value = false
})

watch(() => workspace.activeConversationId.value, () => {
  activeCitationMessageId.value = null
  activeCitationIndex.value = null
  if (sourcesPanelOpen.value && !canShowSources.value) {
    activeSidePanel.value = null
  }
})

watch(canShowSources, (available) => {
  if (!available && sourcesPanelOpen.value) {
    activeSidePanel.value = null
  }
})

onMounted(() => {
  clientReady.value = true
  void workspace.bootstrapAssistant()
})
</script>

<template>
  <div v-if="clientReady" class="h-full min-h-[720px] xl:h-[calc(100dvh-var(--header-height)-3rem)] xl:min-h-0 xl:overflow-hidden">
    <div
      class="assistant-shell-grid grid h-full min-h-0 gap-4 overflow-hidden"
      :class="activeSidePanel
        ? 'xl:grid-cols-[280px_minmax(0,1fr)_360px] 2xl:grid-cols-[300px_minmax(0,1fr)_420px]'
        : 'xl:grid-cols-[300px_minmax(0,1fr)]'"
    >
      <section class="flex min-h-0 flex-col overflow-hidden rounded-[1.2rem] border border-border/70 bg-muted/35 p-4 shadow-sm">
        <div class="flex items-center justify-between gap-2">
          <Button variant="ghost" size="icon" class="size-8 rounded-lg">
            <IconMessageCircle class="size-4" />
          </Button>
          <Button variant="ghost" size="icon" class="size-8 rounded-lg">
            <IconSearch class="size-4" />
          </Button>
        </div>

        <div class="mt-4 space-y-2">
          <Button class="w-full justify-start rounded-xl" @click="createConversation">
            <IconPlus class="size-4" />
            New chat
          </Button>
          <Button
            :variant="knowledgePanelOpen ? 'secondary' : 'outline'"
            class="w-full justify-start rounded-xl"
            @click="toggleSidePanel('knowledge')"
          >
            <IconBook2 class="size-4" />
            Knowledge Base
          </Button>
          <Button
            :variant="sessionDocumentsPanelOpen ? 'secondary' : 'outline'"
            class="w-full justify-start rounded-xl"
            @click="toggleSidePanel('session-documents')"
          >
            <IconFiles class="size-4" />
            Session Documents
          </Button>
          <Button
            :variant="workspacePanelOpen ? 'secondary' : 'outline'"
            class="w-full justify-start rounded-xl"
            @click="toggleSidePanel('workspace')"
          >
            <IconFolder class="size-4" />
            Workspace
          </Button>
          <Button
            v-if="canShowSources"
            :variant="sourcesPanelOpen ? 'secondary' : 'outline'"
            class="w-full justify-start rounded-xl"
            @click="toggleSidePanel('sources')"
          >
            <IconQuote class="size-4" />
            Sources
          </Button>
        </div>

        <div class="mt-4 flex min-h-0 flex-1 flex-col border-t border-border/70 pt-4">
          <p class="mb-2 text-sm font-semibold text-foreground">Conversations</p>
          <div class="relative">
            <IconSearch class="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <input
              v-model="conversationSearch"
              id="assistant-conversation-search"
              name="assistantConversationSearch"
              type="text"
              class="h-9 w-full rounded-lg border border-input bg-background pl-8 pr-3 text-sm text-foreground outline-none transition focus:border-ring"
              placeholder="Search chat..."
            >
          </div>

          <div class="mt-3 min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
            <p v-if="conversationMutationError" class="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
              {{ conversationMutationError }}
            </p>
            <div
              v-for="conversation in filteredConversations"
              :key="conversation.id"
              class="group rounded-xl border px-3 py-2 transition"
              :class="isActiveConversation(conversation.id)
                ? 'border-primary/35 bg-primary/10'
                : 'border-border bg-background hover:border-primary/25 hover:bg-accent/40'"
              @click="selectConversation(conversation.id)"
            >
              <div class="flex items-start gap-2">
                <div class="min-w-0 flex-1">
                  <input
                    v-if="editingConversationId === conversation.id"
                    v-model="editingTitle"
                    type="text"
                    class="h-8 w-full rounded-md border border-input bg-background px-2 text-sm text-foreground outline-none focus:border-ring"
                    :disabled="renamePending"
                    @click.stop
                    @keydown="handleRenameKeydown($event, conversation.id)"
                    @blur="submitRenameConversation(conversation.id)"
                  >
                  <template v-else>
                    <p class="truncate text-sm font-medium text-foreground">{{ conversation.title }}</p>
                    <p class="mt-1 text-[11px] text-muted-foreground">{{ formatDate(conversation.updatedAt) }}</p>
                  </template>
                </div>
                <div class="flex shrink-0 items-center gap-0.5">
                  <button
                    v-if="editingConversationId !== conversation.id"
                    type="button"
                    class="rounded p-1 text-muted-foreground opacity-0 transition hover:bg-accent hover:text-accent-foreground group-hover:opacity-100"
                    :disabled="renamePending || workspace.isSendingMessage.value"
                    aria-label="Rename conversation"
                    @click.stop="beginRenameConversation(conversation.id, conversation.title)"
                  >
                    <IconPencil class="size-3.5" />
                  </button>
                  <button
                    type="button"
                    class="rounded p-1 text-muted-foreground opacity-0 transition hover:bg-accent hover:text-accent-foreground group-hover:opacity-100 disabled:opacity-40"
                    :disabled="!canDeleteConversation(conversation.id)"
                    aria-label="Delete conversation"
                    @click.stop="removeConversation(conversation.id)"
                  >
                    <IconLoader v-if="deletePendingId === conversation.id" class="size-3.5 animate-spin" />
                    <IconTrash v-else class="size-3.5" />
                  </button>
                </div>
              </div>
            </div>

            <EmptyState
              v-if="filteredConversations.length === 0 && !assistantLoading"
              title="No conversations"
              description="Start a new chat to create your first Assistant session."
            />
          </div>
        </div>
      </section>

      <section class="min-h-0 overflow-hidden rounded-[1.2rem] border border-border/70 bg-muted/35 shadow-sm">
        <div class="flex h-full min-h-0 flex-col">
          <header class="flex shrink-0 flex-col gap-3 border-b border-border/80 px-6 py-4 2xl:flex-row 2xl:items-center 2xl:justify-between">
            <p class="text-2xl font-semibold tracking-tight text-foreground">Assistant</p>
            <div class="flex flex-wrap items-center gap-2">
              <Button :variant="knowledgePanelOpen ? 'secondary' : 'outline'" class="rounded-full" @click="toggleSidePanel('knowledge')">
                <IconBook2 class="size-4" />
                Knowledge Base
              </Button>
              <Button :variant="sessionDocumentsPanelOpen ? 'secondary' : 'outline'" class="rounded-full" @click="toggleSidePanel('session-documents')">
                <IconFiles class="size-4" />
                Session Documents
              </Button>
              <Button :variant="workspacePanelOpen ? 'secondary' : 'outline'" class="rounded-full" @click="toggleSidePanel('workspace')">
                <IconFolder class="size-4" />
                Workspace
              </Button>
              <Button v-if="canShowSources" :variant="sourcesPanelOpen ? 'secondary' : 'outline'" class="rounded-full" @click="toggleSidePanel('sources')">
                <IconQuote class="size-4" />
                Sources
              </Button>
            </div>
          </header>

          <div class="min-h-0 flex-1 overflow-y-auto px-6 py-6">
            <div class="mx-auto mb-4 flex w-full max-w-3xl flex-wrap gap-3">
              <div class="rounded-2xl border border-border bg-card px-4 py-3">
                <p class="text-sm font-medium text-foreground">Trace</p>
              </div>
              <div class="rounded-2xl border border-border bg-card px-4 py-3">
                <p class="text-sm font-medium text-foreground">Approvals</p>
              </div>
            </div>

            <div v-if="assistantLoading || conversationLoading" class="mx-auto mb-4 flex w-full max-w-3xl items-center gap-2 rounded-2xl border border-border bg-card px-4 py-3 text-sm text-muted-foreground">
              <IconLoader class="size-4 animate-spin" />
              <span>{{ assistantLoading ? 'Loading conversations from backend...' : 'Loading conversation history...' }}</span>
            </div>

            <div v-if="!hasMessages" class="flex h-full flex-col items-center justify-center">
              <div class="w-full max-w-3xl">
                <p class="text-3xl font-semibold leading-tight text-foreground">How can I help you today?</p>
              </div>
            </div>

            <div v-else class="mx-auto w-full max-w-3xl space-y-4">
              <div
                v-for="message in workspace.messages.value"
                :key="message.id"
                class="flex"
                :class="message.role === 'user' ? 'justify-end' : 'justify-start'"
              >
                <div class="max-w-[92%] space-y-2">
                  <div class="rounded-[1.2rem] px-4 py-3 text-sm leading-7 shadow-sm" :class="messageTone(message.role)">
                    <div
                      v-if="message.thinkingContent"
                      class="mb-3 rounded-xl border border-border/70 bg-background/70 px-3 py-2 text-xs text-muted-foreground"
                    >
                      <div class="mb-1 flex items-center gap-1 font-medium text-foreground">
                        <IconBrain class="size-3.5" />
                        Thinking
                      </div>
                      <p class="whitespace-pre-wrap">{{ message.thinkingContent }}</p>
                    </div>
                    <div class="assistant-rich-text" @click="handleCitationClick($event, message)" v-html="renderMessageContent(message)" />
                    <p v-if="message.errorMessage" class="mt-2 text-xs text-destructive">{{ message.errorMessage }}</p>

                    <div v-if="message.status === 'done' && message.recommendedQuestions?.length" class="mt-3 flex flex-wrap gap-2">
                      <Button
                        v-for="question in message.recommendedQuestions"
                        :key="question"
                        variant="outline"
                        type="button"
                        class="h-auto rounded-full px-3 py-1 text-left text-xs font-medium leading-5"
                        @click="applyRecommendedQuestion(question)"
                      >
                        {{ question }}
                      </Button>
                    </div>
                    <p class="mt-2 text-[11px] opacity-70">{{ formatDate(message.timestamp) }}</p>
                  </div>

                  <div
                    v-for="action in resolveApprovals(message)"
                    :key="action.id"
                    class="rounded-xl border border-border bg-card p-4"
                  >
                    <div class="flex items-center justify-between gap-2">
                      <p class="text-sm font-semibold text-foreground">{{ action.title }}</p>
                      <Badge variant="outline" class="rounded-full uppercase">{{ action.state }}</Badge>
                    </div>
                    <p class="mt-2 text-sm text-muted-foreground">{{ action.description }}</p>
                    <div v-if="action.state === 'pending'" class="mt-3 flex gap-2">
                      <Button
                        type="button"
                        size="sm"
                        class="rounded-lg"
                        :disabled="approvalMutationId === action.id"
                        @click="handleApprovalAction(action, 'approved')"
                      >
                        {{ approvalMutationId === action.id ? 'Processing...' : 'Approve' }}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        class="rounded-lg"
                        :disabled="approvalMutationId === action.id"
                        @click="handleApprovalAction(action, 'rejected')"
                      >
                        Reject
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <form class="shrink-0 border-t border-border/80 px-6 py-5" @submit.prevent="submitMessage">
            <div class="mx-auto w-full max-w-3xl rounded-2xl border border-border bg-muted/40 transition focus-within:border-ring">
              <textarea
                v-model="draft"
                id="assistant-draft"
                name="assistantDraft"
                rows="2"
                class="w-full resize-none border-0 bg-transparent px-6 py-4 text-lg leading-7 text-foreground outline-none placeholder:text-muted-foreground"
                placeholder="Ask Assistant"
              />

              <div v-if="workspace.temporaryKnowledgeItems.value.length > 0" class="flex flex-wrap gap-2 px-4 pb-2">
                <Badge
                  v-for="item in workspace.temporaryKnowledgeItems.value"
                  :key="item.id"
                  variant="secondary"
                  class="flex items-center gap-2 rounded-full"
                >
                  {{ item.name }}
                  <button
                    type="button"
                    class="cursor-not-allowed text-muted-foreground/60"
                    disabled
                    title="Waiting for backend unbind support."
                  >
                    <IconX class="size-3.5" />
                  </button>
                </Badge>
                <span class="self-center text-xs text-muted-foreground">
                  Remove is waiting for backend unbind support.
                </span>
              </div>

              <div class="flex flex-wrap items-center justify-between gap-3 px-4 pb-3">
                <div class="flex min-w-0 flex-1 flex-wrap items-center gap-2">
                  <input
                    ref="temporaryUploadInputRef"
                    type="file"
                    multiple
                    class="hidden"
                    @change="handleTemporaryUpload"
                  >
                  <Button type="button" size="icon" variant="ghost" class="size-9 rounded-lg text-muted-foreground" aria-label="Upload temporary knowledge" @click="triggerTemporaryUpload">
                    <IconPlus class="size-5" />
                  </Button>

                  <div class="flex h-9 shrink-0 items-center gap-2 whitespace-nowrap rounded-xl border border-border bg-background px-3 text-xs text-muted-foreground">
                    Session temporary files
                  </div>

                  <label class="flex h-9 shrink-0 items-center gap-2 rounded-xl border border-border bg-background px-3 text-xs font-medium text-foreground">
                    <input
                      v-model="webSearchEnabled"
                      type="checkbox"
                      class="size-4 rounded border-input"
                    >
                    Web search
                  </label>

                  <div class="min-w-[190px] flex-1 rounded-xl border border-border bg-background px-1 sm:flex-none">
                    <Select v-model="currentModel">
                      <SelectTrigger class="h-9 w-full border-0 bg-transparent px-2 text-left text-sm font-medium shadow-none ring-0 focus:ring-0 sm:w-[190px]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent class="rounded-xl">
                        <SelectItem
                          v-for="option in selectableModelOptions"
                          :key="option.value"
                          :value="option.value"
                          :disabled="option.disabled"
                          class="rounded-lg"
                        >
                          {{ option.label }}
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <Button
                  type="submit"
                  size="icon"
                  aria-label="Send message"
                  class="size-11 rounded-xl bg-primary text-primary-foreground hover:bg-primary/90"
                  :disabled="workspace.isSendingMessage.value || !draft.trim()"
                >
                  <IconArrowUp class="size-4" />
                </Button>
              </div>
            </div>
          </form>
        </div>
      </section>

      <section v-if="activeSidePanel" class="min-h-0 overflow-hidden rounded-[1.2rem] border border-border/70 bg-muted/35 shadow-sm">
        <div class="flex h-full min-h-0 flex-col">
          <header class="flex shrink-0 items-center justify-between border-b border-border/80 px-4 py-4">
            <div>
              <p class="text-xl font-semibold text-foreground">
                {{ knowledgePanelOpen ? 'Knowledge Base' : sourcesPanelOpen ? 'Sources' : workspacePanelOpen ? 'Workspace' : 'Session Documents' }}
              </p>
              <p class="text-sm text-muted-foreground">
                {{ knowledgePanelOpen
                  ? 'Global knowledge uploads join the current conversation immediately.'
                  : sourcesPanelOpen
                    ? 'Full source cards for the selected assistant answer.'
                    : workspacePanelOpen
                      ? 'Choose the backend directory used by Agent file operations.'
                      : 'Read-only view of files already attached to the current session.' }}
              </p>
            </div>
            <Button variant="ghost" size="icon" class="size-8 rounded-lg" @click="activeSidePanel = null">
              <IconX class="size-4" />
            </Button>
          </header>

          <div v-if="knowledgePanelOpen" class="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">
            <Card class="gap-0 rounded-2xl border-border/80 bg-card/80 py-0">
              <CardHeader class="px-4 py-3">
                <div class="flex items-center justify-between gap-2">
                  <CardTitle class="text-base">Backend Status</CardTitle>
                  <Button variant="outline" size="sm" :disabled="workspace.permanentKnowledgeLoading.value" @click="refreshPermanentKnowledge">
                    <IconRefresh class="size-4" />
                    Refresh
                  </Button>
                </div>
              </CardHeader>
              <CardContent class="space-y-2 px-4 pb-4 pt-0">
                <Badge
                  variant="outline"
                  class="rounded-full"
                  :class="permanentKnowledgeUnavailable
                    ? 'border-destructive/40 bg-destructive/10 text-destructive'
                    : 'border-emerald-300/60 bg-emerald-100/40 text-emerald-700'"
                >
                  {{ permanentKnowledgeUnavailable ? 'Backend unavailable' : 'Backend ready' }}
                </Badge>
                <p v-if="workspace.permanentKnowledgeStatusMessage.value" class="text-sm text-muted-foreground">
                  {{ workspace.permanentKnowledgeStatusMessage.value }}
                </p>
                <p v-if="workspace.permanentKnowledgeError.value" class="text-sm text-destructive">
                  {{ workspace.permanentKnowledgeError.value }}
                </p>
              </CardContent>
            </Card>

            <Card class="gap-0 rounded-2xl border-border/80 bg-card/80 py-0">
              <CardHeader class="px-4 py-3">
                <CardTitle class="text-base">Upload Files</CardTitle>
              </CardHeader>
              <CardContent class="space-y-3 px-4 pb-4 pt-0">
                <input
                  ref="permanentUploadInputRef"
                  type="file"
                  multiple
                  class="hidden"
                  @change="handlePermanentUpload"
                >

                <Button
                  class="w-full rounded-xl"
                  :disabled="permanentKnowledgeUnavailable || workspace.permanentKnowledgeLoading.value"
                  @click="triggerPermanentUpload"
                >
                  <IconPlus class="size-4" />
                  Upload to Knowledge Base
                </Button>
              </CardContent>
            </Card>

            <Card class="gap-0 rounded-2xl border-border/80 bg-card/80 py-0">
              <CardHeader class="px-4 py-3">
                <CardTitle class="text-base">Global File History</CardTitle>
              </CardHeader>
              <CardContent class="space-y-2 px-4 pb-4 pt-0">
                <div
                  v-for="item in workspace.permanentKnowledgeItems.value"
                  :key="item.id"
                  class="flex items-center justify-between gap-3 rounded-xl border border-border bg-muted/40 p-3"
                >
                  <div class="min-w-0">
                    <p class="truncate text-sm font-medium text-foreground">{{ item.name }}</p>
                    <p class="mt-1 text-xs text-muted-foreground">{{ item.sizeLabel }} | {{ formatDate(item.uploadedAt) }}</p>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    class="size-8 shrink-0 rounded-lg text-destructive"
                    :disabled="workspace.permanentKnowledgeLoading.value"
                    aria-label="Delete knowledge-base file"
                    @click="deletePermanentKnowledge(item.id)"
                  >
                    <IconTrash class="size-4" />
                  </Button>
                </div>
                <EmptyState
                  v-if="!workspace.permanentKnowledgeLoading.value && workspace.permanentKnowledgeItems.value.length === 0"
                  title="No knowledge files"
                  description="Upload files to populate the backend knowledge list."
                />
              </CardContent>
            </Card>
          </div>

          <div v-else-if="sourcesPanelOpen" class="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">
            <Card class="gap-0 rounded-2xl border-border/80 bg-card/80 py-0">
              <CardHeader class="px-4 py-3">
                <CardTitle class="text-base">Answer Sources</CardTitle>
              </CardHeader>
              <CardContent class="space-y-3 px-4 pb-4 pt-0">
                <div
                  v-for="source in activeSources"
                  :key="`${activeSourceMessage?.id ?? 'source'}-${source.index}`"
                  class="rounded-xl border bg-background p-4 transition"
                  :class="activeCitationIndex === source.index ? 'border-primary/50 ring-2 ring-primary/15' : 'border-border'"
                >
                  <div class="flex items-start justify-between gap-3">
                    <div class="min-w-0">
                      <p class="text-sm font-semibold text-foreground">[{{ source.index }}] {{ source.title }}</p>
                      <p v-if="source.documentId" class="mt-1 break-all text-[11px] text-muted-foreground">{{ source.documentId }}</p>
                    </div>
                    <Badge variant="outline" class="shrink-0 rounded-full">Source {{ source.index }}</Badge>
                  </div>
                  <p v-if="source.excerpt" class="mt-3 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{{ source.excerpt }}</p>
                  <p v-else class="mt-3 text-sm text-muted-foreground">No source text was returned for this citation.</p>
                </div>

                <EmptyState
                  v-if="activeSources.length === 0"
                  title="No sources"
                  description="Send a document-grounded question to populate answer sources."
                />
              </CardContent>
            </Card>
          </div>

          <div v-else-if="workspacePanelOpen" class="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">
            <Card class="gap-0 rounded-2xl border-border/80 bg-card/80 py-0">
              <CardHeader class="px-4 py-3">
                <div class="flex items-center justify-between gap-2">
                  <CardTitle class="text-base">File Workspace</CardTitle>
                  <Button variant="outline" size="sm" :disabled="fileWorkspaceLoading || fileWorkspaceSaving" @click="refreshFileWorkspace">
                    <IconRefresh class="size-4" />
                    Refresh
                  </Button>
                </div>
                <CardDescription>Agent file reads, writes, creates, and deletes are scoped to this backend directory.</CardDescription>
              </CardHeader>
              <CardContent class="space-y-4 px-4 pb-4 pt-0">
                <div class="rounded-xl border border-border bg-muted/40 p-3">
                  <p class="text-xs uppercase tracking-wide text-muted-foreground">Current workspace</p>
                  <p class="mt-2 break-all text-sm font-medium text-foreground">{{ fileWorkspacePath || '-' }}</p>
                </div>

                <label class="space-y-2">
                  <span class="text-sm font-medium text-foreground">Workspace path</span>
                  <input
                    v-model="fileWorkspaceDraft"
                    class="h-10 w-full rounded-xl border border-input bg-background px-3 text-sm outline-none ring-0 focus:border-primary"
                    placeholder="F:\path\to\project"
                    :disabled="fileWorkspaceLoading || fileWorkspaceSaving"
                  >
                </label>

                <Button
                  class="w-full rounded-xl"
                  :disabled="fileWorkspaceSaving || !fileWorkspaceDraft.trim()"
                  @click="saveFileWorkspace"
                >
                  <IconLoader v-if="fileWorkspaceSaving" class="size-4 animate-spin" />
                  <IconFolder v-else class="size-4" />
                  {{ fileWorkspaceSaving ? 'Saving...' : 'Use This Workspace' }}
                </Button>

                <p v-if="fileWorkspaceStatus" class="text-sm text-emerald-700">
                  {{ fileWorkspaceStatus }}
                </p>
                <p v-if="fileWorkspaceError" class="text-sm text-destructive">
                  {{ fileWorkspaceError }}
                </p>
              </CardContent>
            </Card>
          </div>

          <div v-else class="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">
            <Card class="gap-0 rounded-2xl border-border/80 bg-card/80 py-0">
              <CardHeader class="px-4 py-3">
                <div class="flex items-center justify-between gap-2">
                  <CardTitle class="text-base">Session Summary</CardTitle>
                  <Button variant="outline" size="sm" :disabled="sessionDocumentsLoading" @click="refreshSessionDocuments">
                    <IconRefresh class="size-4" />
                    Refresh
                  </Button>
                </div>
              </CardHeader>
              <CardContent class="space-y-2 px-4 pb-4 pt-0">
                <div v-if="sessionDocumentsLoading" class="flex items-center gap-2 text-sm text-muted-foreground">
                  <IconLoader class="size-4 animate-spin" />
                  Loading session documents...
                </div>
                <p v-else-if="sessionDocumentsError" class="text-sm text-destructive">
                  {{ sessionDocumentsError }}
                </p>
                <template v-else>
                  <div class="grid grid-cols-2 gap-3">
                    <div class="rounded-xl border border-border bg-muted/40 p-3">
                      <p class="text-xs uppercase tracking-wide text-muted-foreground">Total documents</p>
                      <p class="mt-2 text-lg font-semibold text-foreground">{{ sessionDocumentsSummary?.totalDocuments ?? 0 }}</p>
                    </div>
                    <div class="rounded-xl border border-border bg-muted/40 p-3">
                      <p class="text-xs uppercase tracking-wide text-muted-foreground">Has documents</p>
                      <p class="mt-2 text-lg font-semibold text-foreground">{{ sessionDocumentsSummary?.hasDocuments ? 'Yes' : 'No' }}</p>
                    </div>
                  </div>
                  <div class="rounded-xl border border-border bg-muted/40 p-3">
                    <p class="text-xs uppercase tracking-wide text-muted-foreground">Latest upload</p>
                    <p class="mt-2 text-sm font-medium text-foreground">{{ sessionDocumentsSummary?.latestDocumentName || '-' }}</p>
                    <p class="mt-1 text-xs text-muted-foreground">{{ formatDate(sessionDocumentsSummary?.latestUploadTime || '') }}</p>
                  </div>
                </template>
              </CardContent>
            </Card>

            <Card class="gap-0 rounded-2xl border-border/80 bg-card/80 py-0">
              <CardHeader class="px-4 py-3">
                <CardTitle class="text-base">Session Files</CardTitle>
              </CardHeader>
              <CardContent class="px-4 pb-4 pt-0">
                <div class="max-h-[420px] space-y-2 overflow-y-auto pr-1">
                  <div
                    v-for="item in sessionDocuments"
                    :key="item.id"
                    class="rounded-xl border border-border bg-muted/40 p-3"
                  >
                    <p class="truncate text-sm font-medium text-foreground">{{ item.filename }}</p>
                    <p class="mt-1 text-xs text-muted-foreground">{{ formatFileSize(item.size) }} | {{ formatDate(item.uploadedAt) }}</p>
                  </div>

                  <EmptyState
                    v-if="!sessionDocumentsLoading && !sessionDocumentsError && sessionDocuments.length === 0"
                    title="No session files"
                    description="Upload a temporary file or a knowledge-base file to populate this panel."
                  />
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>
    </div>
  </div>
  <div v-else class="h-full min-h-[720px]" />
</template>

<style scoped>
.assistant-rich-text {
  color: inherit;
}

.assistant-rich-text :deep(p) {
  margin: 0;
}

.assistant-rich-text :deep(p + p),
.assistant-rich-text :deep(p + ul),
.assistant-rich-text :deep(p + ol),
.assistant-rich-text :deep(p + pre),
.assistant-rich-text :deep(p + blockquote),
.assistant-rich-text :deep(ul + p),
.assistant-rich-text :deep(ol + p),
.assistant-rich-text :deep(pre + p),
.assistant-rich-text :deep(blockquote + p),
.assistant-rich-text :deep(h1 + p),
.assistant-rich-text :deep(h2 + p),
.assistant-rich-text :deep(h3 + p),
.assistant-rich-text :deep(h4 + p),
.assistant-rich-text :deep(h5 + p),
.assistant-rich-text :deep(h6 + p),
.assistant-rich-text :deep(p + .assistant-table-wrap),
.assistant-rich-text :deep(.assistant-table-wrap + p),
.assistant-rich-text :deep(.assistant-table-wrap + h1),
.assistant-rich-text :deep(.assistant-table-wrap + h2),
.assistant-rich-text :deep(.assistant-table-wrap + h3),
.assistant-rich-text :deep(.assistant-table-wrap + h4) {
  margin-top: 0.75rem;
}

.assistant-rich-text :deep(h1),
.assistant-rich-text :deep(h2),
.assistant-rich-text :deep(h3),
.assistant-rich-text :deep(h4),
.assistant-rich-text :deep(h5),
.assistant-rich-text :deep(h6) {
  margin: 1rem 0 0;
  font-weight: 700;
  line-height: 1.4;
}

.assistant-rich-text :deep(h1) {
  font-size: 1.25rem;
}

.assistant-rich-text :deep(h2) {
  font-size: 1.125rem;
}

.assistant-rich-text :deep(h3) {
  font-size: 1rem;
}

.assistant-rich-text :deep(h4) {
  font-size: 0.95rem;
}

.assistant-rich-text :deep(h5),
.assistant-rich-text :deep(h6) {
  font-size: 0.9rem;
}

.assistant-rich-text :deep(.assistant-table-wrap) {
  margin-top: 0.75rem;
  overflow-x: auto;
}

.assistant-rich-text :deep(table) {
  min-width: 100%;
  border-collapse: collapse;
  font-size: 0.92em;
}

.assistant-rich-text :deep(th),
.assistant-rich-text :deep(td) {
  border: 1px solid color-mix(in srgb, currentColor 16%, transparent);
  padding: 0.45rem 0.6rem;
  vertical-align: top;
}

.assistant-rich-text :deep(th) {
  background: color-mix(in srgb, currentColor 8%, transparent);
  font-weight: 700;
}

.assistant-rich-text :deep(ul),
.assistant-rich-text :deep(ol) {
  margin: 0.75rem 0 0;
  padding-left: 1.25rem;
}

.assistant-rich-text :deep(li + li) {
  margin-top: 0.25rem;
}

.assistant-rich-text :deep(ul) {
  list-style: disc;
}

.assistant-rich-text :deep(ol) {
  list-style: decimal;
}

.assistant-rich-text :deep(pre) {
  margin: 0.75rem 0 0;
  overflow-x: auto;
  border-radius: 0.875rem;
  border: 1px solid color-mix(in srgb, currentColor 12%, transparent);
  background: color-mix(in srgb, currentColor 6%, transparent);
  padding: 0.875rem 1rem;
}

.assistant-rich-text :deep(pre code) {
  background: transparent;
  padding: 0;
  color: inherit;
}

.assistant-rich-text :deep(code) {
  border-radius: 0.4rem;
  background: color-mix(in srgb, currentColor 10%, transparent);
  padding: 0.1rem 0.35rem;
  font-size: 0.9em;
}

.assistant-rich-text :deep(.assistant-citation-marker) {
  margin-left: 0.15rem;
  border-radius: 999px;
  border: 1px solid hsl(var(--border));
  background: hsl(var(--background) / 0.7);
  padding: 0.02rem 0.3rem;
  font-size: 0.72em;
  font-weight: 700;
  line-height: 1;
  color: hsl(var(--foreground));
  cursor: pointer;
  vertical-align: baseline;
}

.assistant-rich-text :deep(.assistant-citation-marker:hover) {
  border-color: hsl(var(--primary) / 0.5);
  background: hsl(var(--primary) / 0.1);
  color: hsl(var(--primary));
}

.assistant-rich-text :deep(blockquote) {
  margin: 0.75rem 0 0;
  border-left: 3px solid color-mix(in srgb, currentColor 25%, transparent);
  padding-left: 0.9rem;
  opacity: 0.9;
}

.assistant-rich-text :deep(a) {
  text-decoration: underline;
  text-underline-offset: 0.15rem;
}
</style>
