import {
  createDashboardSummary,
  createSourceConnections,
  createSyncJobs,
} from '~/lib/mock-data'
import { isSessionExpired } from '~/lib/auth-session'
import { normalizeCitationSources } from '~/composables/useApiClient'
import type { BBCalendarItemPatch, BBCalendarItemPayload, SourceReadSnapshot } from '~/composables/useApiClient'
import type { TisCreditResponse, TisGradeResponse, TisInfoResponse, TisScheduleCourse, ScheduleEvent, ScheduleEventCreate, ScheduleEventUpdate } from '~/types/tis'
import type {
  BackendChatSessionSummary,
  BackendChatMessageRecord,
  ApiError,
  BBFileItem,
  BBGradeItem,
  ApprovalAction,
  AssistantConversation,
  AssistantConversationSummary,
  AssistantModel,
  AssistantMode,
  ChatStreamMode,
  ChatMessage,
  KnowledgeBaseItem,
  KnowledgeBackendState,
  KnowledgeScope,
  ScheduleDeadline,
  SendMessageInput,
  SourceConnection,
  SourceReason,
  SourceStatus,
  StoredSession,
  SyncJob,
  MailSyncInput,
  MailSyncResult,
  ToolLog,
  TraceStep,
  IdentityCardData,
} from '~/types/app'

let assistantBootstrapPromise: Promise<void> | null = null
let assistantCreateSessionPromise: Promise<string> | null = null

const CONVERSATIONS_STORAGE_KEY = 'assistant-conversations-v2'
const ACTIVE_CONVERSATION_STORAGE_KEY = 'assistant-active-conversation-v2'
const ASSISTANT_FILE_FLOW_MIGRATION_KEY = 'assistant-file-flow-migration'
const ASSISTANT_FILE_FLOW_MIGRATION_VERSION = 'v1'
const MAX_CONVERSATIONS = 20
const DEFAULT_CONVERSATION_TITLE = 'New chat'
const DEFAULT_ASSISTANT_MODEL: AssistantModel = 'deepseek-chat'
const DEFAULT_KNOWLEDGE_BACKEND_STATE: KnowledgeBackendState = 'unavailable'
const SOURCE_SYNC_TIME_STORAGE_KEY_PREFIX = 'workspace-source-last-synced-v1'
const UNAVAILABLE_ASSISTANT_CAPABILITY_MESSAGE = 'Not integrated with the current backend.'

export const WORKSPACE_QUERY_KEYS = {
  profile: 'profile',
  academicSnapshot: 'academicSnapshot',
  scheduleToday: 'scheduleToday',
  sources: 'sources',
} as const

type WorkspaceQueryKey = typeof WORKSPACE_QUERY_KEYS[keyof typeof WORKSPACE_QUERY_KEYS]

interface WorkspaceQueryMeta {
  isLoading: boolean
  error: string | null
  fetchedAt: number | null
  staleAt: number | null
}

type AutoSyncState = 'idle' | 'running' | 'backoff'

interface AutoSyncMeta {
  autoSyncState: AutoSyncState
  lastAutoSyncAt: string | null
  nextAutoSyncAllowedAt: string | null
  autoSyncFailureCount: number
  lastAutoSyncError: string | null
}

interface PermanentKnowledgeBaseRef {
  id: string
  name: string
  fileCount: number
}

const WORKSPACE_QUERY_STALE_MS: Record<WorkspaceQueryKey, number> = {
  [WORKSPACE_QUERY_KEYS.profile]: 30 * 60 * 1000,
  [WORKSPACE_QUERY_KEYS.academicSnapshot]: 5 * 60 * 1000,
  [WORKSPACE_QUERY_KEYS.scheduleToday]: 2 * 60 * 1000,
  [WORKSPACE_QUERY_KEYS.sources]: 60 * 1000,
}

const AUTO_SYNC_HARD_STALE_MS = 6 * 60 * 60 * 1000
const HEAVY_READ_STALE_MS = 24 * 60 * 60 * 1000
const AUTO_SYNC_COOLDOWN_MS = 10 * 60 * 1000
const AUTO_SYNC_LOGIN_DELAY_MS = 1200
const AUTO_SYNC_BACKOFF_MS = [60 * 1000, 5 * 60 * 1000, 15 * 60 * 1000, 30 * 60 * 1000]
const DEFAULT_MAIL_SYNC_INPUT: MailSyncInput = {
  folder: 'INBOX',
  limit: 20,
  unreadOnly: false,
}
let autoSyncFocusListenerRef: (() => void) | null = null
let autoSyncOnlineListenerRef: (() => void) | null = null

function createEmptySourceSnapshot(): SourceReadSnapshot {
  return {
    bbCourseCount: null,
    bbCalendarCount: 0,
    bbGradesCount: 0,
    bbFilesCount: 0,
    tisScheduleCount: 0,
    tisGpa: null,
    tisRank: null,
    tisCreditTotal: null,
  }
}

function toRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object') {
    return null
  }
  return value as Record<string, unknown>
}

function toFirstRecord(value: unknown): Record<string, unknown> | null {
  const record = toRecord(value)
  if (record) {
    return record
  }

  if (!Array.isArray(value) || value.length === 0) {
    return null
  }

  return toRecord(value[0])
}

function pickRecordString(record: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const candidate = record[key]
    if (typeof candidate === 'string' && candidate.trim()) {
      return candidate.trim()
    }
    if (typeof candidate === 'number' && Number.isFinite(candidate)) {
      return String(candidate)
    }
  }
  return ''
}

export const assistantModelOptions: Array<{ value: AssistantModel, label: string }> = [
  { value: 'deepseek-chat', label: 'Fast' },
  { value: 'deepseek-reasoner', label: 'Thinking' },
  { value: 'deep-research', label: 'Deep Research' },
]

function wait(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

function nowIso() {
  return new Date().toISOString()
}

function createEmptyIdentityCard(): IdentityCardData {
  return {
    user_id: '',
    name: '',
    pinyin_name: '',
    photo: '',
    gender: '',
    birth_date: '',
    college: '',
    dormitory: '',
    phone: '',
    email: '',
    gpa: '',
    rank: '',
    department: '',
    interest: '',
  }
}

function parseDateSafe(value: string) {
  const timestamp = new Date(value).getTime()
  if (!Number.isFinite(timestamp)) {
    return null
  }
  return new Date(timestamp)
}

function normalizeDeadlines(events: unknown): ScheduleDeadline[] {
  if (!Array.isArray(events)) {
    return []
  }

  return events.flatMap((event, index) => {
    const record = toRecord(event)
    if (!record) {
      return []
    }

    const title = typeof record.title === 'string' ? record.title.trim() : ''
    const endTime = typeof record.end === 'string' ? record.end : ''
    if (!title || !endTime) {
      return []
    }

    const rawId = record.id
    const id = rawId === undefined || rawId === null || String(rawId).trim() === ''
      ? `ddl-${index}-${title}`
      : String(rawId)

    return [{
      id,
      title,
      endTime,
      calendarName: typeof record.calendarName === 'string' ? record.calendarName : 'Untitled calendar',
      eventType: typeof record.eventType === 'string' ? record.eventType : 'Uncategorized',
      color: typeof record.color === 'string' ? record.color : '#64748b',
      isUserCreated: Boolean(record.userCreated),
      completed: Boolean(record.completed),
    }]
  })
}

function normalizeGradeItems(items: unknown): BBGradeItem[] {
  if (!Array.isArray(items)) {
    return []
  }

  return items.flatMap((item, index) => {
    const record = toRecord(item)
    if (!record) {
      return []
    }

    const courseName = typeof record.course_name === 'string' ? record.course_name : ''
    const itemName = typeof record.item_name === 'string' ? record.item_name : ''
    const fullGrade = typeof record.full_grade === 'string' ? record.full_grade : ''
    if (!itemName || !fullGrade) {
      return []
    }

    return [{
      id: `grade-${index}-${itemName}`,
      courseName: courseName || 'Unknown course',
      itemName,
      fullGrade,
    }]
  })
}

function normalizeFileItems(items: unknown): BBFileItem[] {
  if (!Array.isArray(items)) {
    return []
  }

  return items.flatMap((item, index) => {
    const record = toRecord(item)
    if (!record) {
      return []
    }

    const fileName = typeof record.file_name === 'string' ? record.file_name : ''
    const fileUrl = typeof record.file_url === 'string' ? record.file_url : ''
    if (!fileName || !fileUrl) {
      return []
    }

    return [{
      id: `file-${index}-${fileName}`,
      course: typeof record.course === 'string' ? record.course : 'Unknown course',
      content: typeof record.content === 'string' ? record.content : '',
      fileName,
      fileUrl,
    }]
  })
}

function normalizeCustomScheduleType(value?: string | null) {
  const normalized = typeof value === 'string' ? value.trim() : ''
  return normalized || 'custom'
}

function parseIsoTime(value: string | null) {
  if (!value) {
    return null
  }
  const timestamp = new Date(value).getTime()
  return Number.isFinite(timestamp) ? timestamp : null
}

function isPastIsoTime(value: string | null, nowMs = Date.now()) {
  const timestamp = parseIsoTime(value)
  return timestamp !== null && timestamp <= nowMs
}

function addMsToIso(ms: number) {
  return new Date(Date.now() + ms).toISOString()
}

function toKnownCount(value: number | null | undefined) {
  return typeof value === 'number' ? value : 0
}

function normalizeDateDisplay(value: string) {
  const trimmed = value.trim()
  if (!trimmed) {
    return ''
  }
  const match = trimmed.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})/)
  if (!match) {
    return ''
  }

  const year = match[1]
  const month = match[2].padStart(2, '0')
  const day = match[3].padStart(2, '0')
  return `${year}-${month}-${day}`
}

function toPhotoDataUrl(base64: string, imageType?: string) {
  const trimmed = base64.trim()
  if (!trimmed) {
    return ''
  }
  if (trimmed.startsWith('data:image/')) {
    return trimmed
  }

  const normalizedType = (imageType || 'jpeg').replace(/^image\//, '').trim() || 'jpeg'
  return `data:image/${normalizedType};base64,${trimmed}`
}

function createId(prefix: string) {
  return `${prefix}-${Math.random().toString(36).slice(2, 9)}`
}

function formatSizeLabel(size: number) {
  if (!Number.isFinite(size) || size <= 0) {
    return '0 KB'
  }

  if (size < 1024) {
    return '1 KB'
  }

  const kb = size / 1024
  if (kb < 1024) {
    return `${Math.round(kb)} KB`
  }

  const mb = kb / 1024
  return `${mb.toFixed(1)} MB`
}

function isUnavailableApiError(error: unknown) {
  const apiError = error as { code?: string, status?: number }
  return apiError?.code === 'unavailable' || apiError?.status === 503
}

const ASSISTANT_MODEL_SET = new Set<AssistantModel>([
  'deepseek-chat',
  'deepseek-reasoner',
  'deep-research',
])

function normalizeAssistantModel(model: unknown): AssistantModel {
  return typeof model === 'string' && ASSISTANT_MODEL_SET.has(model as AssistantModel)
    ? model as AssistantModel
    : DEFAULT_ASSISTANT_MODEL
}

function resolveAssistantModelForSearch(model: AssistantModel, webSearchEnabled: boolean): AssistantModel {
  if (webSearchEnabled && model === 'deepseek-chat') {
    return 'deepseek-reasoner'
  }
  if (!webSearchEnabled && model === 'deep-research') {
    return 'deepseek-reasoner'
  }
  return model
}

function resolveChatStreamMode(model: AssistantModel, webSearchEnabled: boolean): ChatStreamMode {
  if (webSearchEnabled && model === 'deep-research') {
    return 'deep-research'
  }
  return webSearchEnabled ? 'web-search' : 'standard'
}

function normalizeMode(mode: unknown): AssistantMode {
  void mode
  return 'general'
}

function normalizeKnowledgeScope(scope: unknown): KnowledgeScope {
  return scope === 'permanent' ? 'permanent' : 'temporary'
}

function createKnowledgeBaseItem(partial: Partial<KnowledgeBaseItem> & { scope: KnowledgeScope }): KnowledgeBaseItem {
  return {
    id: partial.id ?? createId(partial.scope === 'permanent' ? 'perm-kb' : 'temp-kb'),
    name: partial.name ?? 'Untitled file',
    sizeLabel: partial.sizeLabel ?? '0 KB',
    uploadedAt: partial.uploadedAt ?? nowIso(),
    scope: partial.scope,
    mimeType: partial.mimeType,
    conversationId: partial.conversationId,
  }
}

function normalizeKnowledgeItems(value: unknown, scope: KnowledgeScope): KnowledgeBaseItem[] {
  if (!Array.isArray(value)) {
    return []
  }

  return value.flatMap((entry) => {
    if (!entry || typeof entry !== 'object') {
      return []
    }

    const item = entry as Record<string, unknown>
    const name = typeof item.name === 'string' && item.name.trim() ? item.name.trim() : ''
    if (!name) {
      return []
    }

    return [createKnowledgeBaseItem({
      id: typeof item.id === 'string' ? item.id : undefined,
      name,
      sizeLabel: typeof item.sizeLabel === 'string' && item.sizeLabel.trim() ? item.sizeLabel.trim() : '0 KB',
      uploadedAt: typeof item.uploadedAt === 'string' ? item.uploadedAt : nowIso(),
      scope: normalizeKnowledgeScope(item.scope) === 'permanent' ? 'permanent' : scope,
      mimeType: typeof item.mimeType === 'string' && item.mimeType.trim() ? item.mimeType.trim() : undefined,
      conversationId: typeof item.conversationId === 'string' && item.conversationId.trim() ? item.conversationId.trim() : undefined,
    })]
  })
}

function normalizeKnowledgeIds(value: unknown) {
  if (!Array.isArray(value)) {
    return []
  }

  return value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
}

function isMessageRole(role: unknown): role is ChatMessage['role'] {
  return role === 'user' || role === 'assistant' || role === 'system'
}

function normalizeTrace(value: unknown): TraceStep[] {
  if (!Array.isArray(value)) {
    return []
  }

  return value.flatMap((entry) => {
    if (!entry || typeof entry !== 'object') {
      return []
    }

    const item = entry as Record<string, unknown>
    if (item.status !== 'running' && item.status !== 'completed') {
      return []
    }

    return [{
      id: typeof item.id === 'string' ? item.id : createId('trace'),
      label: typeof item.label === 'string' ? item.label : 'Trace step',
      detail: typeof item.detail === 'string' ? item.detail : '',
      status: item.status,
      timestamp: typeof item.timestamp === 'string' ? item.timestamp : nowIso(),
    }]
  })
}

function normalizeMessages(value: unknown): ChatMessage[] {
  if (!Array.isArray(value)) {
    return []
  }

  return value.flatMap((entry) => {
    if (!entry || typeof entry !== 'object') {
      return []
    }

    const item = entry as Record<string, unknown>
    if (!isMessageRole(item.role)) {
      return []
    }

    const linkedApprovalIds = Array.isArray(item.linkedApprovalIds)
      ? item.linkedApprovalIds.filter(value => typeof value === 'string')
      : []
    const traceState = item.traceState === 'running' || item.traceState === 'done' || item.traceState === 'idle'
      ? item.traceState
      : 'idle'
    const model = item.model === undefined ? undefined : normalizeAssistantModel(item.model)
    const temporaryKnowledgeIds = normalizeKnowledgeIds(item.temporaryKnowledgeIds)
    const permanentKnowledgeIds = normalizeKnowledgeIds(item.permanentKnowledgeIds)

    return [{
      id: typeof item.id === 'string' ? item.id : createId('msg'),
      role: item.role,
      content: typeof item.content === 'string' ? item.content : '',
      timestamp: typeof item.timestamp === 'string' ? item.timestamp : nowIso(),
      mode: normalizeMode(item.mode),
      model,
      temporaryKnowledgeIds,
      permanentKnowledgeIds,
      status: item.status === 'streaming' || item.status === 'done' || item.status === 'failed' || item.status === 'idle'
        ? item.status
        : 'idle',
      thinkingContent: typeof item.thinkingContent === 'string' ? item.thinkingContent : '',
      citations: normalizeCitationSources(item.citations),
      recommendedQuestions: parseRecommendedQuestions(item.recommendedQuestions),
      errorMessage: typeof item.errorMessage === 'string' ? item.errorMessage : '',
      linkedApprovalIds,
      traceState,
      trace: normalizeTrace(item.trace),
    }]
  })
}

function normalizeApprovals(value: unknown): ApprovalAction[] {
  if (!Array.isArray(value)) {
    return []
  }

  return value.flatMap((entry) => {
    if (!entry || typeof entry !== 'object') {
      return []
    }

    const item = entry as Record<string, unknown>
    if ((item.riskLevel !== 'medium' && item.riskLevel !== 'high') || (item.state !== 'pending' && item.state !== 'approved' && item.state !== 'rejected')) {
      return []
    }

    return [{
      id: typeof item.id === 'string' ? item.id : createId('approval'),
      title: typeof item.title === 'string' ? item.title : 'Approval action',
      description: typeof item.description === 'string' ? item.description : '',
      target: typeof item.target === 'string' ? item.target : 'System action',
      riskLevel: item.riskLevel,
      state: item.state,
    }]
  })
}

function normalizeBackendTimestamp(value: string) {
  const parsed = parseDateSafe(value)
  return parsed ? parsed.toISOString() : nowIso()
}

function parseRecommendedQuestions(value: unknown) {
  if (typeof value === 'string') {
    try {
      return parseRecommendedQuestions(JSON.parse(value))
    }
    catch {
      return []
    }
  }

  if (!Array.isArray(value)) {
    if (value && typeof value === 'object') {
      return parseRecommendedQuestions((value as Record<string, unknown>).recommended_questions)
    }
    return []
  }

  return value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
}

function preferNonEmptyArray<T>(primary: T[] | undefined, fallback: T[] | undefined) {
  return primary && primary.length > 0 ? primary : fallback ?? []
}

function isDefaultBackendSessionName(sessionId: string, sessionName: string) {
  return sessionName.trim() === `session-${sessionId}`
}

function shouldUseFirstQuestionTitle(conversation: AssistantConversation, firstQuestion?: string | null) {
  if (!firstQuestion?.trim()) {
    return false
  }

  const title = conversation.title.trim()
  if (!title || title === DEFAULT_CONVERSATION_TITLE) {
    return true
  }

  return Boolean(conversation.backendSessionId && title === `session-${conversation.backendSessionId}`)
}

function toConversationTitle(sessionName: string, messageText?: string) {
  const trimmedMessage = messageText?.trim()
  if (trimmedMessage) {
    return makeConversationTitle(trimmedMessage)
  }

  const trimmedSessionName = sessionName.trim()
  return trimmedSessionName || DEFAULT_CONVERSATION_TITLE
}

function buildMessagesFromBackend(records: BackendChatMessageRecord[]): ChatMessage[] {
  const messages: ChatMessage[] = []

  for (const record of records) {
    const timestamp = normalizeBackendTimestamp(record.created_at)
    messages.push({
      id: `${record.message_id}-user`,
      role: 'user',
      content: record.user_question ?? '',
      timestamp,
      mode: 'general',
      status: 'done',
    })

    messages.push({
      id: `${record.message_id}-assistant`,
      role: 'assistant',
      content: record.model_answer ?? '',
      timestamp,
      mode: 'general',
      status: 'done',
      thinkingContent: typeof record.think === 'string' ? record.think : '',
      citations: normalizeCitationSources(record.documents),
      recommendedQuestions: parseRecommendedQuestions(record.recommended_questions),
    })
  }

  return messages
}

function mergeHydratedMessagesWithExisting(
  hydratedMessages: ChatMessage[],
  existingMessages: ChatMessage[],
) {
  if (hydratedMessages.length === 0 && existingMessages.length > 0) {
    return existingMessages
  }

  const mergedMessages = hydratedMessages.map((message, index) => {
    const existing = existingMessages[index]
    if (existing && message.role === existing.role && !message.content.trim() && existing.content.trim()) {
      return {
        ...message,
        content: existing.content,
        thinkingContent: message.thinkingContent?.trim() ? message.thinkingContent : existing.thinkingContent,
        citations: preferNonEmptyArray(message.citations, existing.citations),
        recommendedQuestions: preferNonEmptyArray(message.recommendedQuestions, existing.recommendedQuestions),
      }
    }

    if (message.role !== 'assistant') {
      return message
    }

    if (!existing || existing.role !== 'assistant') {
      return message
    }

    return {
      ...message,
      citations: preferNonEmptyArray(message.citations, existing.citations),
      recommendedQuestions: preferNonEmptyArray(message.recommendedQuestions, existing.recommendedQuestions),
    }
  })

  return existingMessages.length > mergedMessages.length
    ? [...mergedMessages, ...existingMessages.slice(mergedMessages.length)]
    : mergedMessages
}

function buildConversationFromBackend(
  session: BackendChatSessionSummary,
  existing?: AssistantConversation | null,
): AssistantConversation {
  const title = isDefaultBackendSessionName(session.session_id, session.session_name) && existing?.title
    ? existing.title
    : toConversationTitle(session.session_name)

  return createConversation({
    id: existing?.id ?? createId('conv'),
    backendSessionId: session.session_id,
    backendHydratedAt: nowIso(),
    title,
    createdAt: normalizeBackendTimestamp(session.created_at),
    updatedAt: normalizeBackendTimestamp(session.updated_at),
    assistantModel: existing?.assistantModel ?? DEFAULT_ASSISTANT_MODEL,
    temporaryKnowledgeItems: existing?.temporaryKnowledgeItems ?? [],
    permanentKnowledgeIds: existing?.permanentKnowledgeIds ?? [],
    messages: existing?.messages ?? [],
    approvals: existing?.approvals ?? [],
  })
}

function createConversation(partial?: Partial<AssistantConversation>): AssistantConversation {
  const timestamp = nowIso()
  return {
    id: partial?.id ?? createId('conv'),
    backendSessionId: partial?.backendSessionId ?? null,
    backendHydratedAt: partial?.backendHydratedAt ?? null,
    title: partial?.title ?? DEFAULT_CONVERSATION_TITLE,
    createdAt: partial?.createdAt ?? timestamp,
    updatedAt: partial?.updatedAt ?? timestamp,
    assistantMode: partial?.assistantMode ?? 'general',
    assistantModel: partial?.assistantModel ?? DEFAULT_ASSISTANT_MODEL,
    temporaryKnowledgeItems: partial?.temporaryKnowledgeItems ?? [],
    permanentKnowledgeIds: partial?.permanentKnowledgeIds ?? [],
    messages: partial?.messages ?? [],
    approvals: partial?.approvals ?? [],
  }
}

function sortConversations(conversations: AssistantConversation[]) {
  return [...conversations]
    .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
    .slice(0, MAX_CONVERSATIONS)
}

function normalizeConversations(value: unknown): AssistantConversation[] {
  if (!Array.isArray(value)) {
    return []
  }

  const seen = new Set<string>()
  const normalized = value.flatMap((entry) => {
    if (!entry || typeof entry !== 'object') {
      return []
    }

    const item = entry as Record<string, unknown>
    const id = typeof item.id === 'string' ? item.id : createId('conv')
    if (seen.has(id)) {
      return []
    }
    seen.add(id)

    return [
      createConversation({
        id,
        backendSessionId: typeof item.backendSessionId === 'string' && item.backendSessionId.trim()
          ? item.backendSessionId.trim()
          : null,
        backendHydratedAt: typeof item.backendHydratedAt === 'string' ? item.backendHydratedAt : null,
        title: typeof item.title === 'string' && item.title.trim() ? item.title : DEFAULT_CONVERSATION_TITLE,
        createdAt: typeof item.createdAt === 'string' ? item.createdAt : nowIso(),
        updatedAt: typeof item.updatedAt === 'string' ? item.updatedAt : nowIso(),
        assistantMode: normalizeMode(item.assistantMode),
        assistantModel: normalizeAssistantModel(item.assistantModel),
        temporaryKnowledgeItems: normalizeKnowledgeItems(item.temporaryKnowledgeItems, 'temporary'),
        permanentKnowledgeIds: normalizeKnowledgeIds(item.permanentKnowledgeIds),
        messages: normalizeMessages(item.messages),
        approvals: normalizeApprovals(item.approvals),
      }),
    ]
  })

  return sortConversations(normalized)
}

function makeTraceTemplate(prompt: string, webSearchEnabled: boolean, temporaryKnowledgeCount: number, permanentKnowledgeCount: number) {
  const preview = prompt.length > 42 ? `${prompt.slice(0, 42)}...` : prompt

  return [
    {
      label: 'Context merge',
      detail: webSearchEnabled
        ? `Searching the web and workspace context for "${preview}".`
        : `Loading workspace context for "${preview}".`,
    },
    {
      label: 'Knowledge binding',
      detail: `Using ${temporaryKnowledgeCount} temporary item(s) and ${permanentKnowledgeCount} permanent item(s).`,
    },
    { label: 'Response drafting', detail: 'Composing the final assistant reply.' },
  ]
}

function makeConversationTitle(prompt: string) {
  const trimmed = prompt.trim()
  if (!trimmed) {
    return DEFAULT_CONVERSATION_TITLE
  }

  return trimmed.length > 40 ? `${trimmed.slice(0, 40)}...` : trimmed
}

export function useWorkspaceStore() {
  const conversations = useState<AssistantConversation[]>('assistant-conversations', () => [createConversation()])
  const activeConversationId = useState<string | null>('assistant-active-conversation-id', () => conversations.value[0]?.id ?? null)
  const conversationsLoaded = useState<boolean>('assistant-conversations-loaded', () => false)
  const conversationsWatchBound = useState<boolean>('assistant-conversations-watch-bound', () => false)

  const sources = useState('workspace-sources', createSourceConnections)
  const syncJobs = useState<SyncJob[]>('workspace-sync-jobs', createSyncJobs)
  const identityCard = useState<IdentityCardData>('workspace-identity-card', createEmptyIdentityCard)
  const sourceSnapshot = useState<SourceReadSnapshot>('workspace-source-snapshot', createEmptySourceSnapshot)
  const tisScheduleCourses = useState<TisScheduleCourse[]>('workspace-tis-schedule-courses', () => [])
  const customScheduleEvents = useState<ScheduleEvent[]>('workspace-custom-schedule-events', () => [])
  const scheduleEventsPending = ref(false)
  const scheduleEventsError = ref('')
  const deadlineItems = useState<ScheduleDeadline[]>('workspace-deadline-items', () => [])
  const gradeItems = useState<BBGradeItem[]>('workspace-grade-items', () => [])
  const fileItems = useState<BBFileItem[]>('workspace-file-items', () => [])
  const academicProfile = useState<{
    grade: TisGradeResponse
    credit: TisCreditResponse
    info: TisInfoResponse['data'] | null
  }>('workspace-academic-profile', () => ({
    grade: {},
    credit: {
      total_credit: 0,
      category_credit: {},
    },
    info: null,
  }))
  const sourceSnapshotUpdatedAt = useState<string | null>('workspace-source-snapshot-updated-at', () => null)
  const profileHydratedFromBackend = useState<boolean>('workspace-profile-hydrated-from-backend', () => false)
  const sessionHydrationState = useState<'idle' | 'running' | 'done'>('workspace-session-hydration-state', () => 'idle')
  const queryMetaByKey = useState<Record<string, WorkspaceQueryMeta>>('workspace-query-meta', () => ({}))
  const autoSyncMeta = useState<AutoSyncMeta>('workspace-auto-sync-meta', () => ({
    autoSyncState: 'idle',
    lastAutoSyncAt: null,
    nextAutoSyncAllowedAt: null,
    autoSyncFailureCount: 0,
    lastAutoSyncError: null,
  }))
  const autoSyncListenersBound = useState<boolean>('workspace-auto-sync-listeners-bound', () => false)
  const lastBbCoursesReadAt = useState<string | null>('workspace-bb-courses-read-at', () => null)
  const lastTisInfoReadAt = useState<string | null>('workspace-tis-info-read-at', () => null)
  const lastTisPhotoReadAt = useState<string | null>('workspace-tis-photo-read-at', () => null)
  const isSendingMessage = useState<boolean>('assistant-is-sending', () => false)
  const isBootstrappingAssistant = useState<boolean>('assistant-is-bootstrapping', () => false)
  const activeAssistantLoadConversationId = useState<string | null>('assistant-active-load-conversation-id', () => null)
  const assistantUnavailableMessage = useState<string>('assistant-unavailable-message', () => UNAVAILABLE_ASSISTANT_CAPABILITY_MESSAGE)
  const activeSourceSyncId = useState<string | null>('workspace-active-sync', () => null)
  const permanentKnowledgeItems = useState<KnowledgeBaseItem[]>('workspace-permanent-knowledge-items', () => [])
  const permanentKnowledgeBackendState = useState<KnowledgeBackendState>(
    'workspace-permanent-knowledge-backend-state',
    () => DEFAULT_KNOWLEDGE_BACKEND_STATE,
  )
  const permanentKnowledgeBases = useState<PermanentKnowledgeBaseRef[]>('workspace-permanent-knowledge-bases', () => [])
  const activePermanentKnowledgeBaseId = useState<string | null>('workspace-active-permanent-knowledge-base-id', () => null)
  const permanentKnowledgeLoading = useState<boolean>('workspace-permanent-knowledge-loading', () => false)
  const permanentKnowledgeError = useState<string | null>('workspace-permanent-knowledge-error', () => null)
  const permanentKnowledgeStatusMessage = useState<string | null>('workspace-permanent-knowledge-status-message', () => null)

  function toScopedQueryKey(queryKey: WorkspaceQueryKey, userId: number) {
    return `${queryKey}:${userId}`
  }

  function getQueryMeta(queryKey: WorkspaceQueryKey, userId: number): WorkspaceQueryMeta {
    return queryMetaByKey.value[toScopedQueryKey(queryKey, userId)] ?? {
      isLoading: false,
      error: null,
      fetchedAt: null,
      staleAt: null,
    }
  }

  function setQueryMeta(queryKey: WorkspaceQueryKey, userId: number, nextMeta: WorkspaceQueryMeta) {
    queryMetaByKey.value = {
      ...queryMetaByKey.value,
      [toScopedQueryKey(queryKey, userId)]: nextMeta,
    }
  }

  function setQueryLoading(queryKey: WorkspaceQueryKey, userId: number) {
    const current = getQueryMeta(queryKey, userId)
    setQueryMeta(queryKey, userId, {
      ...current,
      isLoading: true,
      error: null,
    })
  }

  function setQuerySuccess(queryKey: WorkspaceQueryKey, userId: number) {
    const fetchedAt = Date.now()
    setQueryMeta(queryKey, userId, {
      isLoading: false,
      error: null,
      fetchedAt,
      staleAt: fetchedAt + WORKSPACE_QUERY_STALE_MS[queryKey],
    })
  }

  function setQueryError(queryKey: WorkspaceQueryKey, userId: number, message: string) {
    const current = getQueryMeta(queryKey, userId)
    setQueryMeta(queryKey, userId, {
      ...current,
      isLoading: false,
      error: message,
    })
  }

  function invalidateWorkspaceQueries(userId: number, queryKeys: WorkspaceQueryKey[]) {
    for (const queryKey of queryKeys) {
      const current = getQueryMeta(queryKey, userId)
      setQueryMeta(queryKey, userId, {
        ...current,
        staleAt: 0,
      })
    }
  }

  function isQueryFresh(queryKey: WorkspaceQueryKey, userId: number) {
    const staleAt = getQueryMeta(queryKey, userId).staleAt
    return typeof staleAt === 'number' && staleAt > Date.now()
  }

  function toApiError(error: unknown): ApiError {
    const candidate = error as ApiError
    if (typeof candidate?.status === 'number') {
      return candidate
    }

    return {
      status: 0,
      message: 'Unknown API error.',
    }
  }

  function updateSourceState(
    sourceId: string,
    payload: {
      status: SourceStatus
      reason?: SourceReason
      details: string
      itemsImported?: number
      syncedAt?: string
    },
  ) {
    const now = nowIso()
    sources.value = sources.value.map((source) => {
      if (source.id !== sourceId) {
        return source
      }

      return {
        ...source,
        status: payload.status,
        reason: payload.reason,
        details: payload.details,
        itemsImported: typeof payload.itemsImported === 'number' ? payload.itemsImported : source.itemsImported,
        lastCheckedAt: now,
        lastSyncedAt: payload.syncedAt ?? source.lastSyncedAt,
      }
    })
  }

  function pushSyncJob(sourceId: string, title: string, status: SyncJob['status'], detail: string) {
    syncJobs.value = [
      {
        id: createId('sync'),
        title,
        sourceId,
        status,
        runAt: nowIso(),
        detail,
      },
      ...syncJobs.value,
    ]
  }

  function setSourceSnapshot(nextSnapshot: SourceReadSnapshot) {
    sourceSnapshot.value = {
      ...nextSnapshot,
    }
    sourceSnapshotUpdatedAt.value = nowIso()
  }

  function patchAutoSyncMeta(next: Partial<AutoSyncMeta>) {
    autoSyncMeta.value = {
      ...autoSyncMeta.value,
      ...next,
    }
  }

  function isHardStaleSnapshot(nowMs = Date.now()) {
    const updatedAt = parseIsoTime(sourceSnapshotUpdatedAt.value)
    if (updatedAt === null) {
      return true
    }
    return nowMs - updatedAt >= AUTO_SYNC_HARD_STALE_MS
  }

  function isHeavyReadDue(lastReadAt: string | null, force = false, nowMs = Date.now()) {
    if (force) {
      return true
    }
    const timestamp = parseIsoTime(lastReadAt)
    if (timestamp === null) {
      return true
    }
    return nowMs - timestamp >= HEAVY_READ_STALE_MS
  }

  function nextAutoBackoffMs(failureCount: number) {
    const index = Math.min(Math.max(failureCount - 1, 0), AUTO_SYNC_BACKOFF_MS.length - 1)
    return AUTO_SYNC_BACKOFF_MS[index]
  }

  function syncTimesStorageKey(userId: number) {
    return `${SOURCE_SYNC_TIME_STORAGE_KEY_PREFIX}:${userId}`
  }

  function readPersistedSyncTimes(userId: number): Record<string, string> {
    if (!process.client) {
      return {}
    }

    try {
      const raw = localStorage.getItem(syncTimesStorageKey(userId))
      const parsed = raw ? JSON.parse(raw) : {}
      if (!parsed || typeof parsed !== 'object') {
        return {}
      }
      return parsed as Record<string, string>
    }
    catch {
      return {}
    }
  }

  function writePersistedSyncTimes(userId: number, times: Record<string, string>) {
    if (!process.client) {
      return
    }

    localStorage.setItem(syncTimesStorageKey(userId), JSON.stringify(times))
  }

  function applyPersistedSyncTimes(userId: number) {
    const times = readPersistedSyncTimes(userId)
    if (Object.keys(times).length === 0) {
      return
    }

    sources.value = sources.value.map((source) => {
      const persisted = times[source.id]
      if (!persisted) {
        return source
      }
      return {
        ...source,
        lastSyncedAt: persisted,
      }
    })
  }

  function persistSyncedAtForSources(userId: number, sourceIds: string[], syncedAt: string) {
    const nextTimes = readPersistedSyncTimes(userId)
    for (const sourceId of sourceIds) {
      nextTimes[sourceId] = syncedAt
    }
    writePersistedSyncTimes(userId, nextTimes)

    sources.value = sources.value.map((source) => {
      if (!sourceIds.includes(source.id)) {
        return source
      }
      return {
        ...source,
        lastSyncedAt: syncedAt,
      }
    })
  }

  function syncIdentityFromSession(session: StoredSession) {
    identityCard.value = {
      ...identityCard.value,
      user_id: String(session.userId),
      name: session.user.name || identityCard.value.name,
      email: session.user.email || identityCard.value.email,
    }
  }

  async function hydrateUserInterest(session: StoredSession) {
    const api = useApiClient()
    try {
      const interest = await api.getUserInterest(session)
      identityCard.value = {
        ...identityCard.value,
        interest,
      }
    }
    catch (error) {
      const apiError = toApiError(error)
      setQueryError(WORKSPACE_QUERY_KEYS.profile, session.userId, apiError.message || 'Failed to hydrate profile interests.')
    }
  }

  function markMailNeedsLogin() {
    updateSourceState('mail', {
      status: 'needs_sync',
      details: 'Connect a mailbox before syncing messages.',
      itemsImported: 0,
    })
  }

  function markMailSynced(session: StoredSession, result: MailSyncResult, actionLabel: string) {
    const syncedAt = nowIso()
    updateSourceState('mail', {
      status: 'synced',
      reason: undefined,
      details: `Mailbox ${result.mailbox} synced from ${result.folder} (${result.fetched} fetched, ${result.inserted} inserted, ${result.updated} updated).`,
      itemsImported: result.fetched,
      syncedAt,
    })
    persistSyncedAtForSources(session.userId, ['mail'], syncedAt)
    setQuerySuccess(WORKSPACE_QUERY_KEYS.sources, session.userId)
    pushSyncJob('mail', actionLabel, 'success', `Mail sync completed: ${result.fetched} fetched, ${result.inserted} inserted, ${result.updated} updated.`)
  }

  async function refreshMailSourceState(session: StoredSession, actionLabel: string) {
    const api = useApiClient()
    try {
      const account = await api.getMailAccount(session)
      if (!account.loggedIn || !account.mailbox) {
        markMailNeedsLogin()
        return
      }

      const mailSource = sources.value.find(source => source.id === 'mail')
      if (mailSource?.lastSyncedAt) {
        updateSourceState('mail', {
          status: 'synced',
          reason: undefined,
          details: `Mailbox connected: ${account.mailbox}. Last mail sync is recorded.`,
          itemsImported: mailSource.itemsImported,
          syncedAt: mailSource.lastSyncedAt,
        })
        return
      }

      updateSourceState('mail', {
        status: 'needs_sync',
        details: account.loggedIn && account.mailbox
          ? `Mailbox connected: ${account.mailbox}. Sync mail to load messages.`
          : 'Connect a mailbox before syncing messages.',
        itemsImported: 0,
      })
    }
    catch (error) {
      const apiError = toApiError(error)
      updateSourceState('mail', {
        status: 'needs_sync',
        reason: 'sync_failed',
        details: apiError.message || 'Unable to read mailbox account status.',
        itemsImported: 0,
      })
      pushSyncJob('mail', actionLabel, 'warning', apiError.message || 'Unable to read mailbox account status.')
    }
  }

  function markCasRequiredState() {
    updateSourceState('bb', {
      status: 'needs_sync',
      reason: 'cas_required',
      details: 'CAS login is required before Blackboard data can be synchronized.',
      itemsImported: 0,
    })
    updateSourceState('tis', {
      status: 'needs_sync',
      reason: 'cas_required',
      details: 'CAS login is required before TIS data can be synchronized.',
      itemsImported: 0,
    })
    markMailNeedsLogin()
  }

  function unbindAutoSyncListeners() {
    if (!process.client || !autoSyncListenersBound.value) {
      return
    }

    if (autoSyncFocusListenerRef) {
      window.removeEventListener('focus', autoSyncFocusListenerRef)
    }
    if (autoSyncOnlineListenerRef) {
      window.removeEventListener('online', autoSyncOnlineListenerRef)
    }

    autoSyncFocusListenerRef = null
    autoSyncOnlineListenerRef = null
    autoSyncListenersBound.value = false
  }

  function bindAutoSyncListeners() {
    if (!process.client || autoSyncListenersBound.value) {
      return
    }

    autoSyncFocusListenerRef = () => {
      void maybeAutoSync('resume:focus')
    }
    autoSyncOnlineListenerRef = () => {
      void maybeAutoSync('resume:online')
    }

    window.addEventListener('focus', autoSyncFocusListenerRef)
    window.addEventListener('online', autoSyncOnlineListenerRef)
    autoSyncListenersBound.value = true

    window.setTimeout(() => {
      void maybeAutoSync('login')
    }, AUTO_SYNC_LOGIN_DELAY_MS)
  }

  function persistConversations() {
    if (!process.client) {
      return
    }

    localStorage.setItem(CONVERSATIONS_STORAGE_KEY, JSON.stringify(conversations.value))
    localStorage.setItem(ACTIVE_CONVERSATION_STORAGE_KEY, activeConversationId.value ?? '')
  }

  function ensureActiveConversation() {
    if (conversations.value.length === 0) {
      const fallback = createConversation()
      conversations.value = [fallback]
      activeConversationId.value = fallback.id
      return
    }

    if (!activeConversationId.value || !conversations.value.some(conversation => conversation.id === activeConversationId.value)) {
      activeConversationId.value = conversations.value[0].id
    }
  }

  function loadConversationsFromStorage() {
    if (!process.client) {
      return
    }

    try {
      const rawConversations = localStorage.getItem(CONVERSATIONS_STORAGE_KEY)
      const parsed = rawConversations ? JSON.parse(rawConversations) : []
      const normalized = normalizeConversations(parsed)
      if (normalized.length > 0) {
        conversations.value = normalized
      }
    }
    catch {
      conversations.value = [createConversation()]
    }

    const savedActiveConversationId = localStorage.getItem(ACTIVE_CONVERSATION_STORAGE_KEY)
    if (savedActiveConversationId && conversations.value.some(conversation => conversation.id === savedActiveConversationId)) {
      activeConversationId.value = savedActiveConversationId
    }
  }

  function loadKnowledgeStateFromStorage() {
    if (!process.client) {
      return
    }

    permanentKnowledgeBackendState.value = DEFAULT_KNOWLEDGE_BACKEND_STATE
    permanentKnowledgeItems.value = []
    permanentKnowledgeBases.value = []
    activePermanentKnowledgeBaseId.value = null
    permanentKnowledgeLoading.value = false
    permanentKnowledgeError.value = null
    permanentKnowledgeStatusMessage.value = null
  }

  function migrateLegacyAssistantFileFlowState() {
    if (!process.client) {
      return
    }

    try {
      if (localStorage.getItem(ASSISTANT_FILE_FLOW_MIGRATION_KEY) === ASSISTANT_FILE_FLOW_MIGRATION_VERSION) {
        return
      }

      let conversationsChanged = false
      conversations.value = sortConversations(conversations.value.map((conversation) => {
        if (conversation.permanentKnowledgeIds.length === 0) {
          return conversation
        }

        conversationsChanged = true
        return {
          ...conversation,
          permanentKnowledgeIds: [],
        }
      }))

      const hadLegacyUiState = permanentKnowledgeItems.value.length > 0
        || permanentKnowledgeBases.value.length > 0
        || Boolean(activePermanentKnowledgeBaseId.value)
      permanentKnowledgeItems.value = []
      permanentKnowledgeBases.value = []
      activePermanentKnowledgeBaseId.value = null

      if (conversationsChanged || hadLegacyUiState) {
        persistConversations()
      }

      localStorage.setItem(ASSISTANT_FILE_FLOW_MIGRATION_KEY, ASSISTANT_FILE_FLOW_MIGRATION_VERSION)
    }
    catch {
      permanentKnowledgeItems.value = []
      permanentKnowledgeBases.value = []
      activePermanentKnowledgeBaseId.value = null
    }
  }

  ensureActiveConversation()

  if (process.client && !conversationsLoaded.value) {
    loadConversationsFromStorage()
    loadKnowledgeStateFromStorage()
    migrateLegacyAssistantFileFlowState()
    ensureActiveConversation()
    conversationsLoaded.value = true
  }

  if (process.client && !conversationsWatchBound.value) {
    watch([conversations, activeConversationId], () => {
      persistConversations()
    }, { deep: true })
    conversationsWatchBound.value = true
  }

  const activeConversation = computed(() => {
    return conversations.value.find(conversation => conversation.id === activeConversationId.value) ?? null
  })

  function patchConversation(conversationId: string | null, updater: (conversation: AssistantConversation) => AssistantConversation) {
    if (!conversationId) {
      return
    }

    conversations.value = sortConversations(conversations.value.map((conversation) => {
      if (conversation.id !== conversationId) {
        return conversation
      }

      const nextConversation = updater(conversation)
      return {
        ...nextConversation,
        id: conversation.id,
        createdAt: conversation.createdAt,
        updatedAt: nowIso(),
      }
    }))
  }

  const assistantModel = computed<AssistantModel>({
    get: () => activeConversation.value?.assistantModel ?? DEFAULT_ASSISTANT_MODEL,
    set: (value) => {
      patchConversation(activeConversationId.value, conversation => ({
        ...conversation,
        assistantModel: normalizeAssistantModel(value),
      }))
    },
  })

  const temporaryKnowledgeItems = computed<KnowledgeBaseItem[]>({
    get: () => activeConversation.value?.temporaryKnowledgeItems ?? [],
    set: (items) => {
      patchConversation(activeConversationId.value, conversation => ({
        ...conversation,
        temporaryKnowledgeItems: [...items],
      }))
    },
  })

  const permanentKnowledgeIds = computed<string[]>({
    get: () => activeConversation.value?.permanentKnowledgeIds ?? [],
    set: (ids) => {
      patchConversation(activeConversationId.value, conversation => ({
        ...conversation,
        permanentKnowledgeIds: [...ids],
      }))
    },
  })

  const messages = computed<ChatMessage[]>({
    get: () => activeConversation.value?.messages ?? [],
    set: (nextMessages) => {
      patchConversation(activeConversationId.value, conversation => ({
        ...conversation,
        messages: [...nextMessages],
      }))
    },
  })

  const approvals = computed<ApprovalAction[]>({
    get: () => activeConversation.value?.approvals ?? [],
    set: (nextApprovals) => {
      patchConversation(activeConversationId.value, conversation => ({
        ...conversation,
        approvals: [...nextApprovals],
      }))
    },
  })

  const pendingApprovalsAll = computed(() => conversations.value
    .flatMap(conversation => conversation.approvals)
    .filter(action => action.state === 'pending'))

  const toolLogs = computed<ToolLog[]>(() => {
    const conversation = activeConversation.value
    if (!conversation) {
      return []
    }

    const traceLogs = conversation.messages
      .flatMap(message => (message.trace ?? []).map(step => ({
        id: step.id,
        label: step.label,
        status: step.status,
        detail: step.detail,
        timestamp: step.timestamp,
      })))

    const approvalLogs = conversation.approvals
      .filter(action => action.state === 'pending')
      .map(action => ({
        id: `${action.id}-approval-log`,
        label: 'Approval required',
        status: 'needs-approval' as const,
        detail: `${action.title} is waiting for approval.`,
        timestamp: conversation.updatedAt,
      }))

    return [...approvalLogs, ...traceLogs].sort((a, b) => b.timestamp.localeCompare(a.timestamp))
  })

  const conversationSummaries = computed<AssistantConversationSummary[]>(() => {
    return sortConversations(conversations.value).map(conversation => ({
      id: conversation.id,
      title: conversation.title,
      createdAt: conversation.createdAt,
      updatedAt: conversation.updatedAt,
      messageCount: conversation.messages.length,
      pendingApprovalCount: conversation.approvals.filter(action => action.state === 'pending').length,
    }))
  })

  const upcomingDeadlines = computed(() => {
    const now = Date.now()
    return deadlineItems.value
      .filter((item) => {
        const timestamp = parseIsoTime(item.endTime)
        return timestamp !== null && timestamp >= now
      })
      .sort((a, b) => {
        const left = parseIsoTime(a.endTime) ?? 0
        const right = parseIsoTime(b.endTime) ?? 0
        return left - right
      })
  })


  const dashboardSummary = computed(() => createDashboardSummary({
    approvals: pendingApprovalsAll.value,
    sources: sources.value,
  }))

  function patchMessage(
    conversationId: string,
    messageId: string,
    updater: (message: ChatMessage) => ChatMessage,
  ) {
    patchConversation(conversationId, conversation => ({
      ...conversation,
      messages: conversation.messages.map((message) => {
        if (message.id !== messageId) {
          return message
        }
        return updater(message)
      }),
    }))
  }

  async function hydrateConversationMessagesFromBackend(conversationId: string) {
    const sessionStore = useSessionStore()
    const activeSession = await sessionStore.enforceSessionActive()
    const targetConversation = conversations.value.find(conversation => conversation.id === conversationId)
    if (!activeSession || !targetConversation?.backendSessionId) {
      return false
    }

    activeAssistantLoadConversationId.value = conversationId
    try {
      const api = useApiClient()
      const records = await api.listChatMessages(activeSession, targetConversation.backendSessionId)
      patchConversation(conversationId, conversation => ({
        ...conversation,
        title: shouldUseFirstQuestionTitle(conversation, records[0]?.user_question)
          ? makeConversationTitle(records[0].user_question)
          : conversation.title,
        backendHydratedAt: nowIso(),
        messages: mergeHydratedMessagesWithExisting(buildMessagesFromBackend(records), conversation.messages),
      }))
      return true
    }
    finally {
      activeAssistantLoadConversationId.value = null
    }
  }

  async function bootstrapAssistantConversations(force = false) {
    const sessionStore = useSessionStore()
    const activeSession = await sessionStore.enforceSessionActive()
    if (!activeSession) {
      return false
    }

    if (!force && assistantBootstrapPromise) {
      await assistantBootstrapPromise
      return true
    }

    const run = async () => {
      isBootstrappingAssistant.value = true
      try {
        const api = useApiClient()
        const response = await api.listChatSessions(activeSession)
        const existingByBackendId = new Map(
          conversations.value
            .filter(conversation => typeof conversation.backendSessionId === 'string' && conversation.backendSessionId)
            .map(conversation => [conversation.backendSessionId as string, conversation]),
        )

        const remoteConversations = response.sessions.map(sessionSummary =>
          buildConversationFromBackend(sessionSummary, existingByBackendId.get(sessionSummary.session_id)),
        )

        const localDrafts = conversations.value.filter(conversation => !conversation.backendSessionId)

        conversations.value = sortConversations([
          ...localDrafts,
          ...remoteConversations,
        ])

        ensureActiveConversation()

        const current = conversations.value.find(conversation => conversation.id === activeConversationId.value) ?? conversations.value[0]
        if (current?.backendSessionId) {
          await hydrateConversationMessagesFromBackend(current.id)
        }
      }
      finally {
        isBootstrappingAssistant.value = false
        assistantBootstrapPromise = null
      }
    }

    assistantBootstrapPromise = run()
    await assistantBootstrapPromise
    return true
  }

  async function ensureBackendSessionId(conversationId: string) {
    const existing = conversations.value.find(conversation => conversation.id === conversationId)
    if (existing?.backendSessionId) {
      return existing.backendSessionId
    }

    const sessionStore = useSessionStore()
    const activeSession = await sessionStore.enforceSessionActive()
    if (!activeSession) {
      return null
    }

    if (!assistantCreateSessionPromise) {
      const api = useApiClient()
      assistantCreateSessionPromise = api.createChatSession(activeSession)
        .then((response) => {
          const sessionId = response.session_id
          patchConversation(conversationId, conversation => ({
            ...conversation,
            backendSessionId: sessionId,
            backendHydratedAt: nowIso(),
          }))
          return sessionId
        })
        .finally(() => {
          assistantCreateSessionPromise = null
        })
    }

    return assistantCreateSessionPromise
  }

  async function ensureFileActionSession() {
    ensureActiveConversation()
    const conversationId = activeConversationId.value
    if (!conversationId) {
      return null
    }

    const sessionId = await ensureBackendSessionId(conversationId)
    if (!sessionId) {
      return null
    }

    return {
      conversationId,
      sessionId,
    }
  }

  async function ensureActiveAssistantBackendSession() {
    return await ensureFileActionSession()
  }

  function createConversationSession(title = DEFAULT_CONVERSATION_TITLE) {
    const nextConversation = createConversation({
      title: title.trim() || DEFAULT_CONVERSATION_TITLE,
    })
    conversations.value = sortConversations([nextConversation, ...conversations.value])
    activeConversationId.value = nextConversation.id
    return nextConversation
  }

  function switchConversation(conversationId: string) {
    if (conversations.value.some(conversation => conversation.id === conversationId)) {
      activeConversationId.value = conversationId
      void hydrateConversationMessagesFromBackend(conversationId)
    }
  }

  function deleteConversation(conversationId: string) {
    const target = conversations.value.find(conversation => conversation.id === conversationId)
    if (!target) {
      return Promise.resolve(false)
    }

    const sessionStore = useSessionStore()
    const removeLocally = () => {
      conversations.value = sortConversations(conversations.value.filter(conversation => conversation.id !== conversationId))
      ensureActiveConversation()
      return true
    }

    if (!target.backendSessionId) {
      return Promise.resolve(removeLocally())
    }

    return sessionStore.enforceSessionActive()
      .then(async (activeSession) => {
        if (!activeSession) {
          throw {
            status: 401,
            message: 'Authentication is required to delete conversations.',
          } satisfies ApiError
        }

        const api = useApiClient()
        await api.deleteChatSession(activeSession, target.backendSessionId as string)
        return removeLocally()
      })
  }

  function renameConversation(conversationId: string, title: string) {
    const trimmed = title.trim()
    if (!trimmed) {
      return Promise.resolve(false)
    }

    const target = conversations.value.find(conversation => conversation.id === conversationId)
    if (!target) {
      return Promise.resolve(false)
    }

    const applyLocalRename = () => {
      patchConversation(conversationId, conversation => ({
        ...conversation,
        title: trimmed,
        updatedAt: nowIso(),
      }))
      return true
    }

    if (!target.backendSessionId) {
      return Promise.resolve(applyLocalRename())
    }

    const sessionStore = useSessionStore()
    return sessionStore.enforceSessionActive()
      .then(async (activeSession) => {
        if (!activeSession) {
          throw {
            status: 401,
            message: 'Authentication is required to rename conversations.',
          } satisfies ApiError
        }

        const api = useApiClient()
        await api.renameChatSession(activeSession, target.backendSessionId as string, trimmed)
        return applyLocalRename()
      })
  }

  function searchConversations(query: string) {
    const normalized = query.trim().toLowerCase()
    if (!normalized) {
      return conversationSummaries.value
    }

    return conversationSummaries.value.filter(conversation => conversation.title.toLowerCase().includes(normalized))
  }

  function setPermanentKnowledgeIdsForActiveConversation(ids: string[]) {
    permanentKnowledgeIds.value = [...new Set(ids.filter(item => typeof item === 'string' && item.trim().length > 0))]
  }

  async function uploadTemporaryKnowledge(files: File[]) {
    if (files.length === 0) {
      return false
    }

    const fileAction = await ensureFileActionSession()
    if (!fileAction) {
      return false
    }

    const sessionStore = useSessionStore()
    const activeSession = await sessionStore.enforceSessionActive()
    if (!activeSession) {
      return false
    }

    const api = useApiClient()
    const successfulFiles: File[] = []
    let lastUploadError: ApiError | null = null

    for (const file of files) {
      try {
        await api.quickParseSessionFile(activeSession, fileAction.sessionId, file)
        successfulFiles.push(file)
      }
      catch (error) {
        lastUploadError = toApiError(error)
      }
    }

    if (successfulFiles.length === 0) {
      if (lastUploadError) {
        throw lastUploadError
      }
      return false
    }

    try {
      await api.getParsedContent(activeSession, fileAction.sessionId)
    }
    catch {
      // Parsed content shape is intentionally unstable; uploads still succeed without it.
    }

    patchConversation(fileAction.conversationId, (conversation) => {
      const existingByName = new Map(conversation.temporaryKnowledgeItems.map(item => [item.name, item]))
      const nextItems = [...conversation.temporaryKnowledgeItems]

      for (const file of successfulFiles) {
        const uploadedAt = nowIso()
        const nextItem = createKnowledgeBaseItem({
          id: `${fileAction.sessionId}:${file.name}:${uploadedAt}`,
          name: file.name,
          sizeLabel: formatSizeLabel(file.size),
          uploadedAt,
          scope: 'temporary',
          mimeType: file.type || undefined,
          conversationId: fileAction.conversationId,
        })

        const existing = existingByName.get(file.name)
        if (existing) {
          const index = nextItems.findIndex(item => item.id === existing.id)
          if (index >= 0) {
            nextItems[index] = nextItem
          }
          continue
        }

        nextItems.push(nextItem)
      }

      return {
        ...conversation,
        temporaryKnowledgeItems: nextItems,
      }
    })

    return true
  }

  function removeTemporaryKnowledgeItem(itemId: string) {
    patchConversation(activeConversationId.value, conversation => ({
      ...conversation,
      temporaryKnowledgeItems: conversation.temporaryKnowledgeItems.filter(item => item.id !== itemId),
    }))
  }

  function clearTemporaryKnowledgeItems() {
    patchConversation(activeConversationId.value, conversation => ({
      ...conversation,
      temporaryKnowledgeItems: [],
    }))
  }

  function setPermanentKnowledgeBackendState(state: KnowledgeBackendState) {
    permanentKnowledgeBackendState.value = state
    if (state !== 'ready') {
      permanentKnowledgeItems.value = []
      permanentKnowledgeBases.value = []
      activePermanentKnowledgeBaseId.value = null
    }
  }

  function replacePermanentKnowledgeItems(items: KnowledgeBaseItem[]) {
    const nextItems = items.map(item => createKnowledgeBaseItem({
      ...item,
      scope: 'permanent',
    }))
    permanentKnowledgeItems.value = nextItems
    return true
  }

  function setActivePermanentKnowledgeBase(baseId: string | null) {
    activePermanentKnowledgeBaseId.value = typeof baseId === 'string' && baseId.trim() ? baseId.trim() : null
  }

  async function syncPermanentKnowledgeFromBackend() {
    const sessionStore = useSessionStore()
    const activeSession = await sessionStore.enforceSessionActive()
    if (!activeSession) {
      setPermanentKnowledgeBackendState('unavailable')
      permanentKnowledgeError.value = UNAVAILABLE_ASSISTANT_CAPABILITY_MESSAGE
      permanentKnowledgeStatusMessage.value = null
      return false
    }

    permanentKnowledgeLoading.value = true
    permanentKnowledgeError.value = null

    try {
      const api = useApiClient()
      const basesResponse = await api.listAssistantKnowledgeBases(activeSession)
      const activeBase = basesResponse.items[0] ?? null
      const filesResponse = activeBase
        ? await api.listAssistantKnowledgeBaseFiles(activeSession, activeBase.id)
        : { backendState: basesResponse.backendState, items: [] }
      const knowledgeBases = basesResponse.items as Array<{ id: string, name: string, fileCount: number }>
      const knowledgeFiles = filesResponse.items as Array<{ id: string, filename: string, size: number, createdAt: string, mimeType?: string }>

      permanentKnowledgeBases.value = knowledgeBases.map(item => ({
        id: item.id,
        name: item.name,
        fileCount: item.fileCount,
      }))
      activePermanentKnowledgeBaseId.value = activeBase?.id ?? null
      permanentKnowledgeItems.value = knowledgeFiles.map(file => createKnowledgeBaseItem({
        id: file.id,
        name: file.filename,
        sizeLabel: formatSizeLabel(file.size),
        uploadedAt: file.createdAt,
        scope: 'permanent',
        mimeType: file.mimeType,
      }))
      setPermanentKnowledgeBackendState('ready')
      permanentKnowledgeStatusMessage.value = `${permanentKnowledgeItems.value.length} knowledge-base file${permanentKnowledgeItems.value.length === 1 ? '' : 's'} loaded.`
      return true
    }
    catch (error) {
      const apiError = toApiError(error)
      if (isUnavailableApiError(apiError)) {
        setPermanentKnowledgeBackendState('unavailable')
      }
      permanentKnowledgeError.value = apiError.message || UNAVAILABLE_ASSISTANT_CAPABILITY_MESSAGE
      permanentKnowledgeStatusMessage.value = null
      return false
    }
    finally {
      permanentKnowledgeLoading.value = false
    }
  }

  async function syncConversationTitleFromBackend(conversationId: string) {
    const sessionStore = useSessionStore()
    const activeSession = await sessionStore.enforceSessionActive()
    const targetConversation = conversations.value.find(conversation => conversation.id === conversationId)
    if (!activeSession || !targetConversation?.backendSessionId) {
      return false
    }

    const api = useApiClient()
    const response = await api.listChatSessions(activeSession)
    const backendSession = response.sessions.find(session => session.session_id === targetConversation.backendSessionId)
    if (!backendSession || isDefaultBackendSessionName(backendSession.session_id, backendSession.session_name)) {
      return false
    }

    patchConversation(conversationId, conversation => ({
      ...conversation,
      title: backendSession.session_name.trim(),
      updatedAt: normalizeBackendTimestamp(backendSession.updated_at),
    }))
    return true
  }

  async function uploadPermanentKnowledge(files: File[]) {
    if (files.length === 0) {
      return false
    }

    const fileAction = await ensureFileActionSession()
    if (!fileAction) {
      setPermanentKnowledgeBackendState('unavailable')
      permanentKnowledgeError.value = UNAVAILABLE_ASSISTANT_CAPABILITY_MESSAGE
      permanentKnowledgeStatusMessage.value = null
      return false
    }

    const sessionStore = useSessionStore()
    const activeSession = await sessionStore.enforceSessionActive()
    if (!activeSession) {
      setPermanentKnowledgeBackendState('unavailable')
      permanentKnowledgeError.value = UNAVAILABLE_ASSISTANT_CAPABILITY_MESSAGE
      permanentKnowledgeStatusMessage.value = null
      return false
    }

    permanentKnowledgeLoading.value = true
    permanentKnowledgeError.value = null
    permanentKnowledgeStatusMessage.value = 'Uploading files to the global knowledge base...'

    try {
      const api = useApiClient()
      const response = await api.uploadAssistantKnowledgeBaseFile(activeSession, {
        sessionId: fileAction.sessionId,
        files,
      })

      setPermanentKnowledgeBackendState('ready')
      const uploadedCount = response.successfulFiles.length
      const totalCount = response.totalFiles
      const joinedMessage = uploadedCount > 0
        ? `${response.message} Added to the current conversation.`
        : response.message
      permanentKnowledgeStatusMessage.value = `${joinedMessage} (${uploadedCount}/${totalCount})`
      permanentKnowledgeError.value = response.failedFiles.length > 0 && uploadedCount === 0
        ? joinedMessage
        : null
      await syncPermanentKnowledgeFromBackend()
      patchConversation(fileAction.conversationId, conversation => ({
        ...conversation,
        permanentKnowledgeIds: [],
      }))
      return uploadedCount > 0
    }
    catch (error) {
      const apiError = toApiError(error)
      if (apiError.code === 'unavailable') {
        setPermanentKnowledgeBackendState('unavailable')
      }
      else {
        setPermanentKnowledgeBackendState('ready')
      }
      permanentKnowledgeError.value = apiError.message || 'Unable to upload assistant knowledge files.'
      permanentKnowledgeStatusMessage.value = null
      return false
    }
    finally {
      permanentKnowledgeLoading.value = false
    }
  }

  function removePermanentKnowledgeItem(itemId: string) {
    permanentKnowledgeIds.value = permanentKnowledgeIds.value.filter(id => id !== itemId)
  }

  async function deletePermanentKnowledgeFile(itemId: string) {
    const target = permanentKnowledgeItems.value.find(item => item.id === itemId)
    if (!target) {
      return false
    }

    const sessionStore = useSessionStore()
    const activeSession = await sessionStore.enforceSessionActive()
    if (!activeSession) {
      return false
    }

    permanentKnowledgeLoading.value = true
    permanentKnowledgeError.value = null
    try {
      await useApiClient().deleteAssistantKnowledgeBaseFile(activeSession, target.name)
      permanentKnowledgeItems.value = permanentKnowledgeItems.value.filter(item => item.id !== itemId)
      permanentKnowledgeStatusMessage.value = `${target.name} deleted.`
      return true
    }
    catch (error) {
      const apiError = toApiError(error)
      permanentKnowledgeError.value = apiError.message || 'Unable to delete knowledge-base file.'
      return false
    }
    finally {
      permanentKnowledgeLoading.value = false
    }
  }

  function clearPermanentKnowledgeItems() {
    setPermanentKnowledgeIdsForActiveConversation([])
  }

  function appendTraceStep(messageId: string, step: Omit<TraceStep, 'id' | 'timestamp' | 'status'>) {
    patchMessage(activeConversationId.value ?? '', messageId, message => ({
      ...message,
      traceState: 'running',
      trace: [
        ...(message.trace ?? []),
        {
          id: createId('trace'),
          label: step.label,
          detail: step.detail,
          status: 'running',
          timestamp: nowIso(),
        },
      ],
    }))
  }

  function finalizeTrace(messageId: string) {
    patchMessage(activeConversationId.value ?? '', messageId, message => ({
      ...message,
      traceState: 'idle',
      trace: [],
    }))
  }

  async function sendMessage(input: SendMessageInput) {
    const trimmed = input.content.trim()
    if (!trimmed || isSendingMessage.value) {
      return
    }

    const sessionStore = useSessionStore()
    const activeSession = await sessionStore.enforceSessionActive()
    if (!activeSession) {
      return
    }

    ensureActiveConversation()
    const currentConversation = activeConversation.value
    if (!currentConversation) {
      return
    }

    const conversationId = currentConversation.id
    const webSearchEnabled = input.webSearchEnabled === true
    const model = resolveAssistantModelForSearch(normalizeAssistantModel(input.model), webSearchEnabled)
    const streamMode = resolveChatStreamMode(model, webSearchEnabled)
    const nextTemporaryKnowledgeIds = normalizeKnowledgeIds(input.temporaryKnowledgeIds ?? [])
    const nextPermanentKnowledgeIds: string[] = []
    const hasUserPrompt = currentConversation.messages.some(message => message.role === 'user')
    const userMessageId = createId('msg')
    const assistantMessageId = createId('msg')

    isSendingMessage.value = true

    patchConversation(conversationId, (conversation) => {
      const nextConversation: AssistantConversation = {
        ...conversation,
        title: !hasUserPrompt ? makeConversationTitle(trimmed) : conversation.title,
        assistantModel: model,
        temporaryKnowledgeItems: conversation.temporaryKnowledgeItems,
        permanentKnowledgeIds: nextPermanentKnowledgeIds,
        messages: [
          ...conversation.messages,
          {
            id: userMessageId,
            role: 'user',
            content: trimmed,
            timestamp: nowIso(),
            mode: conversation.assistantMode,
            model,
            temporaryKnowledgeIds: nextTemporaryKnowledgeIds,
            permanentKnowledgeIds: nextPermanentKnowledgeIds,
            status: 'done',
          },
          {
            id: assistantMessageId,
            role: 'assistant',
            content: '',
            timestamp: nowIso(),
            mode: conversation.assistantMode,
            model,
            temporaryKnowledgeIds: nextTemporaryKnowledgeIds,
            permanentKnowledgeIds: nextPermanentKnowledgeIds,
            status: 'streaming',
            thinkingContent: '',
            citations: [],
            recommendedQuestions: [],
            errorMessage: '',
            traceState: 'running',
            trace: [],
            linkedApprovalIds: [],
          },
        ],
      }

      return nextConversation
    })

    try {
      const backendSessionId = await ensureBackendSessionId(conversationId)
      if (!backendSessionId) {
        throw {
          status: 500,
          message: 'Failed to create assistant session.',
        } satisfies ApiError
      }

      appendTraceStep(assistantMessageId, {
        label: 'Assistant session ready',
        detail: `Using backend session ${backendSessionId}.`,
      })
      finalizeTrace(assistantMessageId)

      await useApiClient().streamChatOnDocs(activeSession, {
        sessionId: backendSessionId,
        message: trimmed,
        deepThink: streamMode === 'standard' && model === 'deepseek-reasoner',
        streamMode,
        onEvent: (event) => {
          if (event.type === 'delta') {
            patchMessage(conversationId, assistantMessageId, message => ({
              ...message,
              content: `${message.content}${event.content}`,
              status: 'streaming',
            }))
            return
          }

          if (event.type === 'thinking') {
            patchMessage(conversationId, assistantMessageId, message => ({
              ...message,
              thinkingContent: `${message.thinkingContent ?? ''}${event.content}`,
              status: 'streaming',
            }))
            return
          }

          if (event.type === 'recommendations') {
            patchMessage(conversationId, assistantMessageId, message => ({
              ...message,
              recommendedQuestions: event.items,
            }))
            return
          }

          if (event.type === 'documents') {
            patchMessage(conversationId, assistantMessageId, message => ({
              ...message,
              citations: event.citations,
            }))
            return
          }

          if (event.type === 'approval') {
            patchConversation(conversationId, conversation => ({
              ...conversation,
              approvals: [
                ...conversation.approvals.filter(item => item.id !== event.approval.id),
                event.approval,
              ],
              messages: conversation.messages.map(message => {
                if (message.id !== assistantMessageId) {
                  return message
                }
                return {
                  ...message,
                  linkedApprovalIds: [
                    ...new Set([...(message.linkedApprovalIds ?? []), event.approval.id]),
                  ],
                }
              }),
            }))
            return
          }

          if (event.type === 'error') {
            patchMessage(conversationId, assistantMessageId, message => ({
              ...message,
              status: 'failed',
              errorMessage: event.message,
            }))
            return
          }

          if (event.type === 'end') {
            patchMessage(conversationId, assistantMessageId, message => ({
              ...message,
              status: 'done',
            }))
          }
        },
      })

      await hydrateConversationMessagesFromBackend(conversationId)
      await syncConversationTitleFromBackend(conversationId)
    }
    catch (error) {
      const apiError = toApiError(error)
      patchMessage(conversationId, assistantMessageId, message => ({
        ...message,
        status: 'failed',
        errorMessage: apiError.message || 'Assistant response failed.',
      }))
    }
    finally {
      isSendingMessage.value = false
    }
  }

  async function updateApproval(actionId: string, nextState: ApprovalAction['state']) {
    const targetConversation = conversations.value.find(conversation => conversation.approvals.some(action => action.id === actionId))
    if (!targetConversation) {
      return
    }

    const sessionStore = useSessionStore()
    const activeSession = await sessionStore.enforceSessionActive()
    if (!activeSession) {
      return
    }

    const approved = nextState === 'approved'
    const resolution = await useApiClient().resolveAgentApproval(activeSession, actionId, approved)

    patchConversation(targetConversation.id, (conversation) => {
      const action = conversation.approvals.find(item => item.id === actionId)
      if (!action) {
        return conversation
      }

      return {
        ...conversation,
        approvals: conversation.approvals.map((item) => {
          if (item.id !== actionId) {
            return item
          }

          return {
            ...item,
            state: resolution.state,
          }
        }),
        messages: [
          ...conversation.messages,
          {
            id: createId('msg'),
            role: resolution.success ? 'system' : 'assistant',
            content: resolution.message || `${action.title} was ${nextState}.`,
            timestamp: nowIso(),
            mode: 'general',
            model: conversation.assistantModel,
            temporaryKnowledgeIds: conversation.temporaryKnowledgeItems.map(item => item.id),
            permanentKnowledgeIds: conversation.permanentKnowledgeIds,
            status: resolution.success ? 'done' : 'failed',
          },
        ],
      }
    })
  }

  function resetWorkspace() {
    conversations.value = [createConversation()]
    activeConversationId.value = conversations.value[0].id
    sources.value = createSourceConnections()
    syncJobs.value = createSyncJobs()
    identityCard.value = createEmptyIdentityCard()
    sourceSnapshot.value = createEmptySourceSnapshot()
    tisScheduleCourses.value = []
    deadlineItems.value = []
    gradeItems.value = []
    fileItems.value = []
    academicProfile.value = {
      grade: {},
      credit: {
        total_credit: 0,
        category_credit: {},
      },
      info: null,
    }
    sourceSnapshotUpdatedAt.value = null
    profileHydratedFromBackend.value = false
    sessionHydrationState.value = 'idle'
    queryMetaByKey.value = {}
    autoSyncMeta.value = {
      autoSyncState: 'idle',
      lastAutoSyncAt: null,
      nextAutoSyncAllowedAt: null,
      autoSyncFailureCount: 0,
      lastAutoSyncError: null,
    }
    lastBbCoursesReadAt.value = null
    lastTisInfoReadAt.value = null
    lastTisPhotoReadAt.value = null
    isSendingMessage.value = false
    activeSourceSyncId.value = null
    permanentKnowledgeItems.value = []
    permanentKnowledgeBackendState.value = DEFAULT_KNOWLEDGE_BACKEND_STATE
    permanentKnowledgeBases.value = []
    activePermanentKnowledgeBaseId.value = null
    permanentKnowledgeLoading.value = false
    permanentKnowledgeError.value = null
    permanentKnowledgeStatusMessage.value = null
    isBootstrappingAssistant.value = false
    activeAssistantLoadConversationId.value = null

    if (process.client) {
      unbindAutoSyncListeners()
      localStorage.removeItem(CONVERSATIONS_STORAGE_KEY)
      localStorage.removeItem(ACTIVE_CONVERSATION_STORAGE_KEY)
    }
  }

  async function hydrateProfileFromTis(session: StoredSession, force = false) {
    if (session.loginMethod !== 'cas') {
      return
    }

    if (!isHeavyReadDue(lastTisInfoReadAt.value, force)) {
      return
    }

    const api = useApiClient()
    setQueryLoading(WORKSPACE_QUERY_KEYS.profile, session.userId)

    try {
      const response = await api.getUserProfile(session)
      const record = response && typeof response === 'object'
        ? response as Record<string, unknown>
        : null
      if (!record) {
        setQueryError(WORKSPACE_QUERY_KEYS.profile, session.userId, 'No profile fields returned from backend storage.')
        return
      }

      const nextDepartment = pickRecordString(record, ['department', '院系名称', '专业名称', '闄㈢郴鍚嶇О'])
      const nextCollege = pickRecordString(record, ['college', '所属书院名称', '书院', '鎵€灞炰功闄㈠悕绉?'])
      const nextName = pickRecordString(record, ['name', '姓名', '濮撳悕'])
      const nextPinyinName = pickRecordString(record, ['pinyin_name', '姓名拼音', '英文姓名', '濮撳悕鎷奸煶'])
      const nextGenderRaw = pickRecordString(record, ['gender', '性别', '性别代码', '鎬у埆'])
      const nextGender = nextGenderRaw === '1'
        ? '男'
        : nextGenderRaw === '2'
          ? '女'
          : nextGenderRaw
      const nextBirthDate = normalizeDateDisplay(pickRecordString(record, ['birth_date', '出生日期', '鍑虹敓鏃ユ湡']))
      const nextDormitory = pickRecordString(record, ['dormitory', '宿舍号', '宿舍', '瀹胯垗鍙?', '瀹胯垗'])
      const nextPhone = pickRecordString(record, ['phone', '联系电话', '手机号', '手机号码', '鑱旂郴鐢佃瘽', '鎵嬫満鍙?', '鎵嬫満鍙风爜'])
      const nextEmail = pickRecordString(record, ['email', '电子邮箱', '邮箱', '鐢靛瓙閭', '閭'])
      const nextInterest = pickRecordString(record, ['interest', 'interests', '鍏磋叮鐖卞ソ'])
      const nextUserId = pickRecordString(record, ['user_id', 'student_id', '学号', '瀛﹀彿']) || String(session.userId)
      academicProfile.value = {
        ...academicProfile.value,
        info: record,
      }
      identityCard.value = {
        ...identityCard.value,
        user_id: nextUserId,
        name: nextName || identityCard.value.name,
        pinyin_name: nextPinyinName || identityCard.value.pinyin_name,
        photo: toPhotoDataUrl(pickRecordString(record, ['photo'])) || identityCard.value.photo,
        gender: nextGender || identityCard.value.gender,
        birth_date: nextBirthDate || identityCard.value.birth_date,
        college: nextCollege || identityCard.value.college,
        dormitory: nextDormitory || identityCard.value.dormitory,
        phone: nextPhone || identityCard.value.phone,
        email: nextEmail || identityCard.value.email || session.user.email,
        department: nextDepartment || identityCard.value.department,
        interest: identityCard.value.interest || nextInterest,
      }
      await hydrateUserInterest(session)
      profileHydratedFromBackend.value = true
      lastTisInfoReadAt.value = nowIso()
      setQuerySuccess(WORKSPACE_QUERY_KEYS.profile, session.userId)
    }
    catch (error) {
      // Non-blocking enhancement only; keep local identity defaults.
      const apiError = toApiError(error)
      setQueryError(WORKSPACE_QUERY_KEYS.profile, session.userId, apiError.message || 'Failed to hydrate profile.')
    }
  }
  async function markSourceError(sourceId: string, actionLabel: string, error: unknown) {
    const apiError = toApiError(error)

    if (apiError.status === 404) {
      updateSourceState(sourceId, {
        status: 'needs_sync',
        reason: 'not_synced',
        details: 'No synchronized data found yet. Run CAS sync first.',
        itemsImported: 0,
      })
      pushSyncJob(sourceId, actionLabel, 'warning', 'No synchronized data found.')
      return
    }

    if (apiError.status === 401) {
      updateSourceState(sourceId, {
        status: 'auth_expired',
        reason: 'auth_expired',
        details: 'Authentication expired. Please sign in again.',
      })
      pushSyncJob(sourceId, actionLabel, 'failed', 'Authentication expired.')
      return
    }

    if (apiError.status === 400 && apiError.message.toLowerCase().includes('current login method does not support')) {
      updateSourceState(sourceId, {
        status: 'needs_sync',
        reason: 'unsupported_login_method',
        details: 'Current login method does not support this source. Please use CAS login.',
        itemsImported: 0,
      })
      pushSyncJob(sourceId, actionLabel, 'warning', 'Current login method does not support this source.')
      return
    }

    updateSourceState(sourceId, {
      status: 'needs_sync',
      reason: 'sync_failed',
      details: apiError.message || 'Source synchronization failed.',
    })
    pushSyncJob(sourceId, actionLabel, 'failed', apiError.message || 'Source synchronization failed.')
  }

  async function readSnapshotPipeline(
    session: StoredSession,
    actionPrefix: string,
    options?: {
      force?: boolean
    },
  ) {
    const api = useApiClient()
    await refreshMailSourceState(session, `${actionPrefix}: Mail account`)

    if (
      !options?.force
      && isQueryFresh(WORKSPACE_QUERY_KEYS.academicSnapshot, session.userId)
      && isQueryFresh(WORKSPACE_QUERY_KEYS.scheduleToday, session.userId)
      && isQueryFresh(WORKSPACE_QUERY_KEYS.sources, session.userId)
    ) {
      return {
        bbReadOk: true,
        tisReadOk: true,
      }
    }

    setQueryLoading(WORKSPACE_QUERY_KEYS.academicSnapshot, session.userId)
    setQueryLoading(WORKSPACE_QUERY_KEYS.scheduleToday, session.userId)
    setQueryLoading(WORKSPACE_QUERY_KEYS.sources, session.userId)

    const [bbResult, tisResult] = await Promise.allSettled([
      Promise.all([api.bbCalendar(session), api.listBBCalendarItems(session), api.bbGrades(session), api.bbFiles(session)]),
      Promise.all([api.tisSchedule(session), api.tisGrade(session), api.tisCredit(session)]),
    ])

    const nextSnapshot: SourceReadSnapshot = {
      ...sourceSnapshot.value,
    }

    let bbReadOk = false
    let tisReadOk = false

    if (bbResult.status === 'fulfilled') {
      const [calendar, calendarItems, grades, files] = bbResult.value
      const normalizedCalendarItems = normalizeDeadlines(calendarItems.events)
      deadlineItems.value = normalizedCalendarItems.length > 0
        ? normalizedCalendarItems
        : normalizeDeadlines(calendar.events)
      gradeItems.value = normalizeGradeItems(grades.grades)
      fileItems.value = normalizeFileItems(files.files)
      nextSnapshot.bbCalendarCount = Array.isArray(calendar.events) ? calendar.events.length : 0
      nextSnapshot.bbGradesCount = Array.isArray(grades.grades) ? grades.grades.length : 0
      nextSnapshot.bbFilesCount = Array.isArray(files.files) ? files.files.length : 0
      const imported = (
        toKnownCount(nextSnapshot.bbCourseCount)
        + nextSnapshot.bbCalendarCount
        + nextSnapshot.bbGradesCount
        + nextSnapshot.bbFilesCount
      )
      updateSourceState('bb', {
        status: 'synced',
        reason: undefined,
        details: `Blackboard snapshot loaded from database (${imported} records, courses cached).`,
        itemsImported: imported,
      })
      pushSyncJob('bb', `${actionPrefix}: Blackboard read`, 'success', 'Blackboard data pulled from database.')
      bbReadOk = true
    }
    else {
      deadlineItems.value = []
      gradeItems.value = []
      fileItems.value = []
      await markSourceError('bb', `${actionPrefix}: Blackboard read`, bbResult.reason)
    }

    if (tisResult.status === 'fulfilled') {
      const [schedule, grade, credit] = tisResult.value
      tisScheduleCourses.value = Array.isArray(schedule.courses) ? (schedule.courses as TisScheduleCourse[]) : []
      academicProfile.value = {
        ...academicProfile.value,
        grade: {
          GPA: grade.GPA ?? null,
          Rank: grade.Rank ?? null,
        },
        credit: {
          total_credit: typeof credit.total_credit === 'number' ? credit.total_credit : 0,
          category_credit: credit.category_credit ?? {},
        },
      }
      nextSnapshot.tisScheduleCount = Array.isArray(schedule.courses) ? schedule.courses.length : 0
      nextSnapshot.tisGpa = grade.GPA ?? null
      nextSnapshot.tisRank = grade.Rank ?? null
      nextSnapshot.tisCreditTotal = typeof credit.total_credit === 'number' ? credit.total_credit : null
      identityCard.value = {
        ...identityCard.value,
        gpa: nextSnapshot.tisGpa !== null && nextSnapshot.tisGpa !== undefined ? String(nextSnapshot.tisGpa) : identityCard.value.gpa,
        rank: nextSnapshot.tisRank !== null && nextSnapshot.tisRank !== undefined ? String(nextSnapshot.tisRank) : identityCard.value.rank,
      }
      const imported = (
        nextSnapshot.tisScheduleCount
        + (nextSnapshot.tisGpa !== null && nextSnapshot.tisGpa !== undefined ? 1 : 0)
        + (nextSnapshot.tisCreditTotal !== null && nextSnapshot.tisCreditTotal !== undefined ? 1 : 0)
      )
      updateSourceState('tis', {
        status: 'synced',
        reason: undefined,
        details: `TIS data loaded from database (${imported} records).`,
        itemsImported: imported,
      })
      pushSyncJob('tis', `${actionPrefix}: TIS read`, 'success', 'TIS data pulled from database.')
      tisReadOk = true
      setQuerySuccess(WORKSPACE_QUERY_KEYS.academicSnapshot, session.userId)
      setQuerySuccess(WORKSPACE_QUERY_KEYS.scheduleToday, session.userId)
    }
    else {
      tisScheduleCourses.value = []
      await markSourceError('tis', `${actionPrefix}: TIS read`, tisResult.reason)
      const apiError = toApiError(tisResult.reason)
      setQueryError(WORKSPACE_QUERY_KEYS.academicSnapshot, session.userId, apiError.message || 'Failed to read TIS snapshot.')
      setQueryError(WORKSPACE_QUERY_KEYS.scheduleToday, session.userId, apiError.message || 'Failed to read TIS schedule.')
    }

    if (bbReadOk || tisReadOk) {
      setSourceSnapshot(nextSnapshot)
      setQuerySuccess(WORKSPACE_QUERY_KEYS.sources, session.userId)
    }
    else {
      setQueryError(WORKSPACE_QUERY_KEYS.sources, session.userId, 'Failed to refresh sources snapshot.')
    }

    return {
      bbReadOk,
      tisReadOk,
    }
  }

  async function refreshHeavySnapshotFields(
    session: StoredSession,
    actionPrefix: string,
    options?: {
      force?: boolean
    },
  ) {
    if (session.loginMethod !== 'cas') {
      return
    }

    const api = useApiClient()

    if (isHeavyReadDue(lastBbCoursesReadAt.value, options?.force)) {
      try {
        const courses = await api.bbCourses(session)
        const nextSnapshot: SourceReadSnapshot = {
          ...sourceSnapshot.value,
          bbCourseCount: Array.isArray(courses.courses) ? courses.courses.length : 0,
        }
        setSourceSnapshot(nextSnapshot)
        lastBbCoursesReadAt.value = nowIso()
        setQuerySuccess(WORKSPACE_QUERY_KEYS.sources, session.userId)
        pushSyncJob('bb', `${actionPrefix}: Blackboard courses`, 'success', 'Blackboard courses count refreshed.')
      }
      catch (error) {
        const apiError = toApiError(error)
        pushSyncJob('bb', `${actionPrefix}: Blackboard courses`, 'warning', apiError.message || 'Failed to refresh Blackboard courses count.')
      }
    }

    await hydrateProfileFromTis(session, options?.force ?? false)

  }

  async function pullAfterSync(
    session: StoredSession,
    actionPrefix: string,
  ) {
    invalidateWorkspaceQueries(session.userId, [
      WORKSPACE_QUERY_KEYS.academicSnapshot,
      WORKSPACE_QUERY_KEYS.scheduleToday,
      WORKSPACE_QUERY_KEYS.sources,
    ])
    const readResult = await readSnapshotPipeline(session, `${actionPrefix} pull`, { force: true })
    if (readResult.bbReadOk && readResult.tisReadOk) {
      const syncedAt = nowIso()
      persistSyncedAtForSources(session.userId, ['bb', 'tis'], syncedAt)
      return {
        ...readResult,
        fullyRefreshed: true,
      }
    }

    return {
      ...readResult,
      fullyRefreshed: false,
    }
  }

  function shouldAutoSync(session: StoredSession) {
    if (session.loginMethod !== 'cas') {
      return false
    }
    if (sessionHydrationState.value === 'running') {
      return false
    }
    if (activeSourceSyncId.value) {
      return false
    }
    if (autoSyncMeta.value.autoSyncState === 'running') {
      return false
    }
    const nowMs = Date.now()
    if (autoSyncMeta.value.nextAutoSyncAllowedAt && !isPastIsoTime(autoSyncMeta.value.nextAutoSyncAllowedAt, nowMs)) {
      return false
    }
    if (!isHardStaleSnapshot(nowMs)) {
      return false
    }
    return true
  }

  async function maybeAutoSync(reason: string) {
    const session = useSessionStore().session.value
    if (!session?.isAuthenticated || isSessionExpired(session)) {
      return false
    }
    if (!shouldAutoSync(session)) {
      return false
    }

    const api = useApiClient()
    const attemptedAt = nowIso()
    patchAutoSyncMeta({
      autoSyncState: 'running',
      lastAutoSyncAt: attemptedAt,
      lastAutoSyncError: null,
    })
    activeSourceSyncId.value = 'auto'

    try {
      await api.syncAll(session)
      pushSyncJob('bb', `Auto sync (${reason})`, 'success', 'Background sync/all completed successfully.')
      const readResult = await pullAfterSync(session, `Auto sync (${reason})`)
      if (!readResult.fullyRefreshed) {
        pushSyncJob('bb', `Auto sync (${reason})`, 'warning', 'sync/all succeeded, but snapshot pull was incomplete.')
      }

      patchAutoSyncMeta({
        autoSyncState: 'idle',
        autoSyncFailureCount: 0,
        nextAutoSyncAllowedAt: addMsToIso(AUTO_SYNC_COOLDOWN_MS),
        lastAutoSyncError: null,
      })
      void refreshHeavySnapshotFields(session, `Auto sync (${reason})`)
      return true
    }
    catch (error) {
      const apiError = toApiError(error)
      const nextFailureCount = autoSyncMeta.value.autoSyncFailureCount + 1
      const nextAllowedAt = addMsToIso(nextAutoBackoffMs(nextFailureCount))
      patchAutoSyncMeta({
        autoSyncState: 'backoff',
        autoSyncFailureCount: nextFailureCount,
        nextAutoSyncAllowedAt: nextAllowedAt,
        lastAutoSyncError: apiError.message || 'Background sync failed.',
      })
      pushSyncJob('bb', `Auto sync (${reason})`, 'warning', `Background sync failed. Next retry after ${nextAllowedAt}.`)
      return false
    }
    finally {
      activeSourceSyncId.value = null
    }
  }

  async function manualSyncPipeline(session: StoredSession) {
    const api = useApiClient()
    if (activeSourceSyncId.value) {
      return
    }

    activeSourceSyncId.value = 'all'

    try {
      if (session.loginMethod !== 'cas') {
        markCasRequiredState()
        pushSyncJob('bb', 'Manual sync', 'warning', 'CAS login is required before running sync.')
        return
      }

      try {
        await api.syncAll(session)
        pushSyncJob('bb', 'Manual sync', 'success', 'sync/all completed successfully.')
      }
      catch (error) {
        await markSourceError('bb', 'Manual sync', error)
        await markSourceError('tis', 'Manual sync', error)
        return
      }

      const readResult = await pullAfterSync(session, 'Manual sync')
      if (readResult.fullyRefreshed) {
        pushSyncJob('bb', 'Manual sync', 'success', 'Snapshot pull succeeded after sync/all.')
      }
      else {
        pushSyncJob('bb', 'Manual sync', 'warning', 'sync/all succeeded, but snapshot pull was incomplete.')
      }

      await refreshHeavySnapshotFields(session, 'Manual sync', { force: true })
      patchAutoSyncMeta({
        autoSyncState: 'idle',
        autoSyncFailureCount: 0,
        nextAutoSyncAllowedAt: addMsToIso(AUTO_SYNC_COOLDOWN_MS),
        lastAutoSyncError: null,
      })
    }
    finally {
      activeSourceSyncId.value = null
    }
  }

  async function hydrateFromSession() {
    if (sessionHydrationState.value !== 'idle') {
      return
    }

    const sessionStore = useSessionStore()
    const session = sessionStore.session.value
    if (!session?.isAuthenticated || isSessionExpired(session)) {
      sessionHydrationState.value = 'done'
      return
    }

    sessionHydrationState.value = 'running'
    try {
      bindAutoSyncListeners()
      applyPersistedSyncTimes(session.userId)
      syncIdentityFromSession(session)
      await hydrateUserInterest(session)

      if (session.loginMethod === 'mail') {
        markCasRequiredState()
        sessionHydrationState.value = 'done'
        return
      }

      await readSnapshotPipeline(session, 'Session bootstrap')
      void refreshHeavySnapshotFields(session, 'Session bootstrap')
      sessionHydrationState.value = 'done'
    }
    catch {
      sessionHydrationState.value = 'done'
    }
  }

  async function syncAllSources() {
    const sessionStore = useSessionStore()
    const activeSession = await sessionStore.enforceSessionActive()
    if (!activeSession) {
      return
    }

    await manualSyncPipeline(activeSession)
  }

  async function syncCasSources() {
    await syncAllSources()
  }

  async function syncMailSource(input: MailSyncInput = DEFAULT_MAIL_SYNC_INPUT) {
    const sessionStore = useSessionStore()
    const activeSession = await sessionStore.enforceSessionActive()
    if (!activeSession) {
      return null
    }

    const api = useApiClient()
    try {
      const result = await api.syncMail(activeSession, input)
      markMailSynced(activeSession, result, 'Mail sync')
      return result
    }
    catch (error) {
      await markSourceError('mail', 'Mail sync', error)
      throw error
    }
  }

  async function syncAllSourcesWithMail(input: MailSyncInput = DEFAULT_MAIL_SYNC_INPUT) {
    const sessionStore = useSessionStore()
    const activeSession = await sessionStore.enforceSessionActive()
    if (!activeSession) {
      return null
    }

    await manualSyncPipeline(activeSession)

    const api = useApiClient()
    try {
      const result = await api.syncMail(activeSession, input)
      markMailSynced(activeSession, result, 'Sync All Sources: Mail sync')
      return result
    }
    catch (error) {
      await markSourceError('mail', 'Sync All Sources: Mail sync', error)
      throw error
    }
  }

  async function maybeRefreshHeavySnapshot(reason: string) {
    const sessionStore = useSessionStore()
    const activeSession = await sessionStore.enforceSessionActive()
    if (!activeSession || activeSession.loginMethod !== 'cas') {
      return false
    }
    if (activeSourceSyncId.value) {
      return false
    }
    if (
      !isHeavyReadDue(lastBbCoursesReadAt.value)
      && !isHeavyReadDue(lastTisInfoReadAt.value)
      && !isHeavyReadDue(lastTisPhotoReadAt.value)
    ) {
      return false
    }

    await refreshHeavySnapshotFields(activeSession, reason)
    return true
  }

  function readQueryMetaForActiveUser(queryKey: WorkspaceQueryKey): WorkspaceQueryMeta {
    const session = useSessionStore().session.value
    if (!session?.isAuthenticated) {
      return {
        isLoading: false,
        error: null,
        fetchedAt: null,
        staleAt: null,
      }
    }

    return getQueryMeta(queryKey, session.userId)
  }

  async function refreshWorkspaceQuery(queryKey: WorkspaceQueryKey) {
    const sessionStore = useSessionStore()
    const activeSession = await sessionStore.enforceSessionActive()
    if (!activeSession) {
      return
    }

    if (queryKey === WORKSPACE_QUERY_KEYS.profile) {
      invalidateWorkspaceQueries(activeSession.userId, [WORKSPACE_QUERY_KEYS.profile])
      await hydrateProfileFromTis(activeSession, true)
      return
    }

    invalidateWorkspaceQueries(activeSession.userId, [
      WORKSPACE_QUERY_KEYS.academicSnapshot,
      WORKSPACE_QUERY_KEYS.scheduleToday,
      WORKSPACE_QUERY_KEYS.sources,
    ])
    await readSnapshotPipeline(activeSession, `Refresh ${queryKey}`, { force: true })
  }

  function cancelWorkspaceQuery(queryKey: WorkspaceQueryKey) {
    const session = useSessionStore().session.value
    if (!session?.isAuthenticated) {
      return
    }
    const current = getQueryMeta(queryKey, session.userId)
    setQueryMeta(queryKey, session.userId, {
      ...current,
      isLoading: false,
    })
  }

  async function loadCalendarItems() {
    const sessionStore = useSessionStore()
    const activeSession = await sessionStore.enforceSessionActive()
    if (!activeSession) {
      return false
    }

    const response = await useApiClient().listBBCalendarItems(activeSession)
    deadlineItems.value = normalizeDeadlines(response.events)
    setQuerySuccess(WORKSPACE_QUERY_KEYS.scheduleToday, activeSession.userId)
    return true
  }

  async function createCalendarItem(payload: BBCalendarItemPayload) {
    const sessionStore = useSessionStore()
    const activeSession = await sessionStore.enforceSessionActive()
    if (!activeSession) {
      return false
    }

    await useApiClient().createBBCalendarItem(activeSession, payload)
    await loadCalendarItems()
    return true
  }

  async function updateCalendarItem(id: string, patch: BBCalendarItemPatch) {
    const sessionStore = useSessionStore()
    const activeSession = await sessionStore.enforceSessionActive()
    if (!activeSession) {
      return false
    }

    await useApiClient().patchBBCalendarItem(activeSession, id, patch)
    await loadCalendarItems()
    return true
  }

  async function deleteCalendarItem(id: string) {
    const sessionStore = useSessionStore()
    const activeSession = await sessionStore.enforceSessionActive()
    if (!activeSession) {
      return false
    }

    await useApiClient().deleteBBCalendarItem(activeSession, id)
    await loadCalendarItems()
    return true
  }

  async function toggleCalendarItemCompleted(item: ScheduleDeadline) {
    return await updateCalendarItem(item.id, {
      completed: !item.completed,
    })
  }

  async function loadCustomScheduleEvents() {
    const sessionStore = useSessionStore()
    const activeSession = await sessionStore.enforceSessionActive()
    if (!activeSession) return false
    scheduleEventsPending.value = true
    scheduleEventsError.value = ''
    try {
      const response = await useApiClient().listScheduleEvents(activeSession)
      if (Array.isArray(response)) {
        customScheduleEvents.value = response
          .map(event => ({
            ...event,
            schedule_type: normalizeCustomScheduleType(event.schedule_type),
          }))
          .filter(event => normalizeCustomScheduleType(event.schedule_type) !== 'course')
      } else {
        scheduleEventsError.value = 'Failed to load schedule events.'
        customScheduleEvents.value = []
      }
      return true
    } catch (error) {
      scheduleEventsError.value = error instanceof Error ? error.message : 'Unknown error'
      return false
    } finally {
      scheduleEventsPending.value = false
    }
  }

  async function createCustomScheduleEvent(payload: ScheduleEventCreate) {
    const sessionStore = useSessionStore()
    const activeSession = await sessionStore.enforceSessionActive()
    if (!activeSession) return false
    scheduleEventsPending.value = true
    scheduleEventsError.value = ''
    try {
      await useApiClient().createScheduleEvent(activeSession, payload)
      await loadCustomScheduleEvents()
      return true
    } catch (error) {
      scheduleEventsError.value = error instanceof Error ? error.message : 'Failed to create event.'
      return false
    } finally {
      scheduleEventsPending.value = false
    }
  }

  async function updateCustomScheduleEvent(eventId: number, payload: ScheduleEventUpdate) {
    const sessionStore = useSessionStore()
    const activeSession = await sessionStore.enforceSessionActive()
    if (!activeSession) return false
    scheduleEventsPending.value = true
    scheduleEventsError.value = ''
    try {
      await useApiClient().updateScheduleEvent(activeSession, eventId, payload)
      await loadCustomScheduleEvents()
      return true
    } catch (error) {
      scheduleEventsError.value = error instanceof Error ? error.message : 'Failed to update event.'
      return false
    } finally {
      scheduleEventsPending.value = false
    }
  }

  async function deleteCustomScheduleEvent(eventId: number) {
    const sessionStore = useSessionStore()
    const activeSession = await sessionStore.enforceSessionActive()
    if (!activeSession) return false
    scheduleEventsPending.value = true
    scheduleEventsError.value = ''
    try {
      await useApiClient().deleteScheduleEvent(activeSession, eventId)
      await loadCustomScheduleEvents()
      return true
    } catch (error) {
      scheduleEventsError.value = error instanceof Error ? error.message : 'Failed to delete event.'
      return false
    } finally {
      scheduleEventsPending.value = false
    }
  }

  async function saveIdentityInterest(interest: string) {
    const normalized = interest.trim()
    const sessionStore = useSessionStore()
    const activeSession = await sessionStore.enforceSessionActive()
    if (!activeSession) {
      throw {
        status: 401,
        message: 'Authentication is required to save interests.',
      } satisfies ApiError
    }

    const savedInterest = await useApiClient().saveUserInterest(activeSession, normalized)
    identityCard.value = {
      ...identityCard.value,
      interest: savedInterest,
    }
    invalidateWorkspaceQueries(activeSession.userId, [WORKSPACE_QUERY_KEYS.profile])
  }


  return {
    assistantModel,
    assistantModelOptions,
    isBootstrappingAssistant,
    activeAssistantLoadConversationId,
    assistantUnavailableMessage,
    temporaryKnowledgeItems,
    permanentKnowledgeIds,
    permanentKnowledgeItems,
    permanentKnowledgeBackendState,
    permanentKnowledgeBases,
    activePermanentKnowledgeBaseId,
    permanentKnowledgeLoading,
    permanentKnowledgeError,
    permanentKnowledgeStatusMessage,
    messages,
    toolLogs,
    approvals,
    conversations,
    conversationSummaries,
    activeConversationId,
    activeConversation,
    pendingApprovalsAll,
    sources,
    syncJobs,
    identityCard,
    academicProfile,
    tisScheduleCourses,
    customScheduleEvents,
    scheduleEventsPending,
    scheduleEventsError,
    loadCustomScheduleEvents,
    createCustomScheduleEvent,
    updateCustomScheduleEvent,
    deleteCustomScheduleEvent,
    deadlineItems,
    gradeItems,
    fileItems,
    upcomingDeadlines,
    profileHydratedFromBackend,
    sourceSnapshot,
    sourceSnapshotUpdatedAt,
    dashboardSummary,
    autoSyncMeta,
    isSendingMessage,
    activeSourceSyncId,
    createConversation: createConversationSession,
    bootstrapAssistant: bootstrapAssistantConversations,
    ensureActiveAssistantBackendSession,
    switchConversation,
    deleteConversation,
    renameConversation,
    searchConversations,
    appendTraceStep,
    finalizeTrace,
    resetWorkspace,
    hydrateFromSession,
    maybeAutoSync,
    maybeRefreshHeavySnapshot,
    syncAllSources,
    syncAllSourcesWithMail,
    syncCasSources,
    syncMailSource,
    readQueryMetaForActiveUser,
    refreshWorkspaceQuery,
    cancelWorkspaceQuery,
    sendMessage,
    updateApproval,
    loadCalendarItems,
    createCalendarItem,
    updateCalendarItem,
    deleteCalendarItem,
    toggleCalendarItemCompleted,
    saveIdentityInterest,
    setPermanentKnowledgeIdsForActiveConversation,
    uploadTemporaryKnowledge,
    removeTemporaryKnowledgeItem,
    clearTemporaryKnowledgeItems,
    setPermanentKnowledgeBackendState,
    setActivePermanentKnowledgeBase,
    syncPermanentKnowledgeFromBackend,
    replacePermanentKnowledgeItems,
    uploadPermanentKnowledge,
    removePermanentKnowledgeItem,
    deletePermanentKnowledgeFile,
    clearPermanentKnowledgeItems,
  }
}
