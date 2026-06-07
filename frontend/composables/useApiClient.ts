import { redirectToLoginWithReason } from '~/lib/auth-session'
import type {
  AssistantStreamEvent,
  ApiError,
  BackendChatMessageRecord,
  BackendChatSessionListResponse,
  BackendChatSessionRenameResponse,
  BackendChatSessionDeleteResponse,
  ChatStreamMode,
  CitationSource,
  LoginCredentials,
  LoginMethod,
  LoginResult,
  MailAccount,
  MailLoginInput,
  MailMessage,
  MailSendInput,
  MailSendResult,
  MailSyncInput,
  MailSyncResult,
  StoredSession,
  UserInit,
} from '~/types/app'
import type { TisScheduleResponse, TisInfoResponse, TisGradeResponse, TisCreditResponse, ScheduleEvent, ScheduleEventCreate, ScheduleEventUpdate } from '~/types/tis'

const pendingRequests = new Map<string, Promise<any>>()

function normalizeDisplayName(username: string) {
  const base = username.split('@')[0].trim()
  return base || 'student'
}

function normalizeEmail(username: string) {
  return username.includes('@')
    ? username
    : `${normalizeDisplayName(username)}@mail.sustech.edu.cn`
}

function toApiError(error: unknown, fallbackMessage: string): ApiError {
  const fetchError = error as {
    statusCode?: number
    message?: string
    data?: unknown
    response?: {
      status?: number
      _data?: unknown
    }
  }

  const status = fetchError.statusCode ?? fetchError.response?.status ?? 0
  const payload = fetchError.data ?? fetchError.response?._data
  let message = fallbackMessage
  let code: string | undefined
  let details: unknown

  if (payload && typeof payload === 'object') {
    const record = payload as Record<string, unknown>

    if (typeof record.detail === 'string' && record.detail.trim()) {
      message = record.detail
    }
    else if (typeof record.message === 'string' && record.message.trim()) {
      message = record.message
    }

    if (record.error && typeof record.error === 'object') {
      const errorRecord = record.error as Record<string, unknown>
      if (typeof errorRecord.message === 'string' && errorRecord.message.trim()) {
        message = errorRecord.message
      }
      if (typeof errorRecord.code === 'string') {
        code = errorRecord.code
      }
      details = errorRecord.details
    }
    else {
      if (typeof record.code === 'string') {
        code = record.code
      }
      details = record.details
    }
  }

  if (status === 0 && (!message || message === fallbackMessage) && fetchError.message) {
    message = fetchError.message
  }

  return {
    status,
    message,
    code,
    details,
  }
}

function resolveService(loginMethod: LoginMethod) {
  return loginMethod === 'mail' ? 'mail' : 'all'
}

function toBearer(tokenType = 'bearer', accessToken?: string): string {
  if (!accessToken) {
    return ''
  }

  const normalizedTokenType = tokenType.trim() ? tokenType.trim() : 'bearer'
  return `${normalizedTokenType} ${accessToken}`
}

function getCookiesFile(config: ReturnType<typeof useRuntimeConfig>) {
  const candidate = config.public.cookiesFile
  return typeof candidate === 'string' && candidate.trim()
    ? candidate.trim()
    : ''
}

function withCookiesFile(path: string, cookiesFile: string) {
  if (!cookiesFile) {
    return path
  }

  return `${path}?cookies_file=${encodeURIComponent(cookiesFile)}`
}

function toInvalidLoginMethodMessage(apiError: ApiError) {
  if (apiError.status !== 400) {
    return apiError
  }

  if (!apiError.message.toLowerCase().includes('invalid sid in token')) {
    return apiError
  }

  return {
    ...apiError,
    message: 'Current login method does not support this feature. Please sign in with CAS.',
  }
}

async function normalizeProtectedError(error: unknown, fallbackMessage: string): Promise<never> {
  const apiError = toInvalidLoginMethodMessage(toApiError(error, fallbackMessage))
  if (apiError.status === 401) {
    await redirectToLoginWithReason('expired')
  }
  throw apiError
}

async function normalizeAssistantKnowledgeBaseError(error: unknown, fallbackMessage: string): Promise<never> {
  const apiError = toApiError(error, fallbackMessage)
  if (apiError.status === 401) {
    await redirectToLoginWithReason('expired')
  }

  const unavailableStatuses = new Set([0, 404, 405, 501, 502, 503, 504])
  if (unavailableStatuses.has(apiError.status) || apiError.code === 'unavailable') {
    throw {
      ...apiError,
      status: apiError.status && apiError.status !== 0 ? apiError.status : 503,
      message: apiError.message || fallbackMessage,
      code: 'unavailable',
    }
  }

  throw apiError
}

export interface SourceReadSnapshot {
  bbCourseCount?: number | null
  bbCalendarCount: number
  bbGradesCount: number
  bbFilesCount: number
  tisScheduleCount: number
  tisGpa?: number | string | null
  tisRank?: number | string | null
  tisCreditTotal?: number | null
}

export interface AssistantKnowledgeBaseSummary {
  id: string
  name: string
  description?: string
  fileCount: number
  createdAt: string
  updatedAt: string
}

export interface AssistantKnowledgeBaseFileItem {
  id: string
  knowledgeBaseId: string
  filename: string
  mimeType: string
  size: number
  createdAt: string
  source?: 'upload' | 'sync'
}

export interface AssistantSessionDocumentItem {
  id: string
  sessionId: string
  filename: string
  mimeType: string
  size: number
  uploadedAt: string
}

export interface AssistantSessionDocumentSummary {
  sessionId: string
  hasDocuments: boolean
  latestDocumentName: string
  latestDocumentType: string
  latestUploadTime: string
  totalDocuments: number
}

export interface AssistantApprovalResolution {
  success: boolean
  actionId: string
  state: 'pending' | 'approved' | 'rejected'
  message: string
  target: string
}

export interface AssistantKnowledgeHistoryFileItem {
  id: string
  filename: string
  uploadedAt: string
  updatedAt: string
}

export interface AssistantKnowledgeBaseListResponse {
  backendState: 'ready' | 'unavailable'
  items: AssistantKnowledgeBaseSummary[]
}

export interface AssistantKnowledgeBaseFileListResponse {
  backendState: 'ready' | 'unavailable'
  items: AssistantKnowledgeBaseFileItem[]
}

export interface AssistantKnowledgeBaseUploadInput {
  sessionId: string
  files: File[]
}

export interface AssistantKnowledgeUploadResult {
  status: 'success' | 'partial_success' | 'failed'
  message: string
  successfulFiles: string[]
  failedFiles: string[]
  totalFiles: number
}

interface BackendSessionDocumentRecord {
  id?: string | number
  session_id?: string
  document_name?: string
  document_type?: string
  file_size?: number
  upload_time?: string
  created_at?: string
  updated_at?: string
}

interface BackendSessionDocumentListResponse {
  session_id?: string
  documents?: BackendSessionDocumentRecord[]
}

interface BackendSessionDocumentSummaryResponse {
  session_id?: string
  has_documents?: boolean
  latest_document_name?: string
  latest_document_type?: string
  latest_upload_time?: string
  total_documents?: number
}

interface BackendHistoryFileRecord {
  user_id?: string
  file_name?: string
  created_at?: string
  updated_at?: string
}

interface BackendKnowledgeUploadResponse {
  status?: string
  message?: string
  successful_files?: string[]
  failed_files?: string[]
  total_files?: number
}

interface BackendUserInterestResponse {
  user_id?: string | number
  interest?: string | null
}

interface BackendUserProfileResponse {
  user_id?: string | number
  name?: string | null
  pinyin_name?: string | null
  photo?: string | null
  gender?: string | null
  birth_date?: string | null
  college?: string | null
  dormitory?: string | null
  phone?: string | null
  email?: string | null
  gpa?: string | number | null
  rank?: string | number | null
  department?: string | null
  interest?: string | null
}

interface BackendBBCalendarItemRecord {
  id?: string | number
  title?: string
  end?: string
  completed?: boolean
  color?: string
  calendarName?: string
  eventType?: string
  userCreated?: boolean
}

interface BackendBBCalendarItemsResponse {
  events?: BackendBBCalendarItemRecord[]
}

interface BackendMailAccountResponse {
  logged_in?: boolean
  provider?: string | null
  mailbox?: string | null
  logged_in_at?: string | null
}

interface BackendMailSyncResponse {
  mailbox?: string
  folder?: string
  requested_limit?: number
  unread_only?: boolean
  fetched?: number
  inserted?: number
  updated?: number
}

interface BackendMailMessageRecord {
  id?: number | string
  mailbox?: string
  folder?: string
  imap_uid?: string | number
  message_id?: string
  subject?: string
  from_address?: string
  to_address?: string
  cc_address?: string | null
  received_at?: string | null
  raw_date?: string
  snippet?: string
  text_body?: string
  html_body?: string | null
  is_seen?: boolean
  has_attachment?: boolean
  synced_at?: string | null
}

interface BackendMailMessagesResponse {
  messages?: BackendMailMessageRecord[]
}

interface BackendMailSendResponse {
  mailbox?: string
  to_addresses?: string[]
  cc_addresses?: string[]
  bcc_count?: number
  subject?: string
  message_id?: string
  sent_at?: string
}

export interface BBCalendarItemPayload {
  title: string
  end: string
  completed?: boolean
  color?: string
  calendarName?: string
  eventType?: string
  userCreated?: boolean
}

export interface BBCalendarItemPatch {
  title?: string
  end?: string
  completed?: boolean
  color?: string
  calendarName?: string
  eventType?: string
  userCreated?: boolean
}

export interface ChatStreamInput {
  sessionId: string
  message: string
  deepThink?: boolean
  streamMode?: ChatStreamMode
  signal?: AbortSignal
  onEvent: (event: AssistantStreamEvent) => void
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

function readStringField(record: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = record[key]
    if (typeof value === 'string' && value.trim()) {
      return value.trim()
    }
    if ((typeof value === 'number' || typeof value === 'bigint') && String(value).trim()) {
      return String(value)
    }
  }

  return ''
}

function toExcerpt(value: string) {
  const normalized = value.replace(/\s+/g, ' ').trim()
  return normalized
}

export function normalizeCitationSources(value: unknown): CitationSource[] {
  if (typeof value === 'string') {
    try {
      return normalizeCitationSources(JSON.parse(value))
    }
    catch {
      return []
    }
  }

  if (!Array.isArray(value)) {
    return []
  }

  return value.flatMap((entry, index) => {
    if (!entry || typeof entry !== 'object') {
      return []
    }

    const record = entry as Record<string, unknown>
    const title = readStringField(record, ['document_name', 'docnm', 'filename', 'file_name', 'title'])
    const excerpt = readStringField(record, ['excerpt', 'content_with_weight', 'content', 'text', 'snippet'])
    const documentId = readStringField(record, ['documentId', 'document_id', 'doc_id', 'id'])

    return [{
      index: index + 1,
      title: title || `Source ${index + 1}`,
      excerpt: toExcerpt(excerpt),
      ...(documentId ? { documentId } : {}),
    }]
  })
}

function inferMimeTypeFromFilename(filename: string) {
  const normalized = filename.toLowerCase()
  if (normalized.endsWith('.pdf')) {
    return 'application/pdf'
  }
  if (normalized.endsWith('.md') || normalized.endsWith('.markdown')) {
    return 'text/markdown'
  }
  if (normalized.endsWith('.txt')) {
    return 'text/plain'
  }
  if (normalized.endsWith('.doc')) {
    return 'application/msword'
  }
  if (normalized.endsWith('.docx')) {
    return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  }
  if (normalized.endsWith('.ppt')) {
    return 'application/vnd.ms-powerpoint'
  }
  if (normalized.endsWith('.pptx')) {
    return 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
  }
  return 'application/octet-stream'
}

function toAssistantKnowledgeBaseFileItem(record: BackendHistoryFileRecord, index: number): AssistantKnowledgeBaseFileItem | null {
  const filename = typeof record.file_name === 'string' ? record.file_name.trim() : ''
  if (!filename) {
    return null
  }

  const uploadedAt = typeof record.created_at === 'string' && record.created_at.trim()
    ? record.created_at.trim()
    : typeof record.updated_at === 'string' && record.updated_at.trim()
      ? record.updated_at.trim()
      : new Date().toISOString()
  const stableId = `${filename}:${uploadedAt}:${index}`

  return {
    id: stableId,
    knowledgeBaseId: 'global',
    filename,
    mimeType: inferMimeTypeFromFilename(filename),
    size: 0,
    createdAt: uploadedAt,
    source: 'upload',
  }
}

function toAssistantSessionDocumentItem(record: BackendSessionDocumentRecord, fallbackSessionId: string): AssistantSessionDocumentItem | null {
  const filename = typeof record.document_name === 'string' ? record.document_name.trim() : ''
  if (!filename) {
    return null
  }

  const uploadedAt = typeof record.upload_time === 'string' && record.upload_time.trim()
    ? record.upload_time.trim()
    : typeof record.created_at === 'string' && record.created_at.trim()
      ? record.created_at.trim()
      : new Date().toISOString()
  const rawId = record.id
  return {
    id: rawId === undefined || rawId === null ? `${fallbackSessionId}:${filename}:${uploadedAt}` : String(rawId),
    sessionId: typeof record.session_id === 'string' && record.session_id.trim() ? record.session_id.trim() : fallbackSessionId,
    filename,
    mimeType: typeof record.document_type === 'string' && record.document_type.trim()
      ? inferMimeTypeFromFilename(`${filename}.${record.document_type.trim()}`)
      : inferMimeTypeFromFilename(filename),
    size: typeof record.file_size === 'number' && Number.isFinite(record.file_size) ? record.file_size : 0,
    uploadedAt,
  }
}

function normalizeMailProvider(provider: unknown): MailAccount['provider'] {
  return provider === 'qq' || provider === 'exmail' ? provider : null
}

function toMailAccount(response: BackendMailAccountResponse): MailAccount {
  return {
    loggedIn: Boolean(response.logged_in),
    provider: normalizeMailProvider(response.provider),
    mailbox: typeof response.mailbox === 'string' && response.mailbox.trim() ? response.mailbox.trim() : null,
    loggedInAt: typeof response.logged_in_at === 'string' && response.logged_in_at.trim() ? response.logged_in_at.trim() : null,
  }
}

function toMailSyncResult(response: BackendMailSyncResponse): MailSyncResult {
  return {
    mailbox: typeof response.mailbox === 'string' ? response.mailbox : '',
    folder: typeof response.folder === 'string' ? response.folder : 'INBOX',
    requestedLimit: typeof response.requested_limit === 'number' ? response.requested_limit : 0,
    unreadOnly: Boolean(response.unread_only),
    fetched: typeof response.fetched === 'number' ? response.fetched : 0,
    inserted: typeof response.inserted === 'number' ? response.inserted : 0,
    updated: typeof response.updated === 'number' ? response.updated : 0,
  }
}

function toMailMessage(record: BackendMailMessageRecord): MailMessage | null {
  const id = typeof record.id === 'number'
    ? record.id
    : typeof record.id === 'string' && /^\d+$/.test(record.id)
      ? Number(record.id)
      : null

  if (id === null) {
    return null
  }

  return {
    id,
    mailbox: typeof record.mailbox === 'string' ? record.mailbox : '',
    folder: typeof record.folder === 'string' ? record.folder : '',
    imapUid: record.imap_uid === undefined || record.imap_uid === null ? '' : String(record.imap_uid),
    messageId: typeof record.message_id === 'string' ? record.message_id : '',
    subject: typeof record.subject === 'string' ? record.subject : '(No subject)',
    fromAddress: typeof record.from_address === 'string' ? record.from_address : '',
    toAddress: typeof record.to_address === 'string' ? record.to_address : '',
    ccAddress: typeof record.cc_address === 'string' ? record.cc_address : null,
    receivedAt: typeof record.received_at === 'string' ? record.received_at : null,
    rawDate: typeof record.raw_date === 'string' ? record.raw_date : '',
    snippet: typeof record.snippet === 'string' ? record.snippet : '',
    textBody: typeof record.text_body === 'string' ? record.text_body : '',
    htmlBody: typeof record.html_body === 'string' ? record.html_body : null,
    isSeen: Boolean(record.is_seen),
    hasAttachment: Boolean(record.has_attachment),
    syncedAt: typeof record.synced_at === 'string' ? record.synced_at : null,
  }
}

function toMailSendResult(response: BackendMailSendResponse): MailSendResult {
  return {
    mailbox: typeof response.mailbox === 'string' ? response.mailbox : '',
    toAddresses: Array.isArray(response.to_addresses) ? response.to_addresses : [],
    ccAddresses: Array.isArray(response.cc_addresses) ? response.cc_addresses : [],
    bccCount: typeof response.bcc_count === 'number' ? response.bcc_count : 0,
    subject: typeof response.subject === 'string' ? response.subject : '',
    messageId: typeof response.message_id === 'string' ? response.message_id : '',
    sentAt: typeof response.sent_at === 'string' ? response.sent_at : '',
  }
}

function parseSseEventBlock(rawBlock: string): { event: string, data: string } | null {
  const lines = rawBlock.split(/\r?\n/)
  let eventName = 'message'
  const dataLines: string[] = []

  for (const line of lines) {
    if (!line.trim()) {
      continue
    }
    if (line.startsWith('event:')) {
      eventName = line.slice(6).trim() || 'message'
      continue
    }
    if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trim())
    }
  }

  if (dataLines.length === 0) {
    return null
  }

  return {
    event: eventName,
    data: dataLines.join('\n'),
  }
}

function parseAssistantStreamEvent(rawEvent: { event: string, data: string }): AssistantStreamEvent | null {
  if (rawEvent.event === 'end') {
    return { type: 'end' }
  }

  if (rawEvent.event === 'error') {
    try {
      const payload = JSON.parse(rawEvent.data) as { content?: string }
      return {
        type: 'error',
        message: typeof payload.content === 'string' && payload.content.trim()
          ? payload.content
          : 'Assistant stream failed.',
      }
    }
    catch {
      return {
        type: 'error',
        message: rawEvent.data || 'Assistant stream failed.',
      }
    }
  }

  try {
    const payload = JSON.parse(rawEvent.data) as Record<string, unknown>
    if (payload.approval && typeof payload.approval === 'object') {
      const approval = payload.approval as Record<string, unknown>
      const riskLevel = approval.riskLevel === 'medium' ? 'medium' : 'high'
      const state = approval.state === 'approved' || approval.state === 'rejected' ? approval.state : 'pending'
      return {
        type: 'approval',
        approval: {
          id: typeof approval.id === 'string' ? approval.id : '',
          title: typeof approval.title === 'string' ? approval.title : 'Pending approval',
          description: typeof approval.description === 'string' ? approval.description : '',
          target: typeof approval.target === 'string' ? approval.target : 'action',
          riskLevel,
          state,
        },
      }
    }

    if (Array.isArray(payload.documents)) {
      return {
        type: 'documents',
        citations: normalizeCitationSources(payload.documents),
      }
    }

    if (Array.isArray(payload.recommended_questions)) {
      return {
        type: 'recommendations',
        items: parseRecommendedQuestions(payload.recommended_questions),
      }
    }

    if (payload.role === 'assistant' && typeof payload.content === 'string') {
      return payload.thinking === true
        ? { type: 'thinking', content: payload.content }
        : { type: 'delta', content: payload.content }
    }
  }
  catch {
    return null
  }

  return null
}

export function useApiClient() {
  const config = useRuntimeConfig()
  const cookiesFile = getCookiesFile(config)

  async function login(credentials: LoginCredentials): Promise<LoginResult> {
    const body = new URLSearchParams()
    body.set('username', credentials.username)
    body.set('password', credentials.password)

    try {
      const response = await $fetch<{
        access_token: string
        token_type: string
        user_init?: UserInit
      }>(`/api/v1/auth/login?service=${encodeURIComponent(resolveService(credentials.loginMethod))}`, {
        baseURL: config.public.apiBase,
        method: 'POST',
        body,
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      })

      return {
        accessToken: response.access_token,
        tokenType: response.token_type,
        loginMethod: credentials.loginMethod,
        userInit: response.user_init ?? { ok: false, reason: 'missing user_init' },
        user: {
          name: normalizeDisplayName(credentials.username),
          email: normalizeEmail(credentials.username),
          major: 'Software Engineering',
          year: '2026',
          token: response.access_token,
          authSource: 'live',
        },
      }
    }
    catch (error) {
      throw toApiError(error, 'Unable to create a session right now.')
    }
  }

  async function logout(session?: StoredSession | null) {
    try {
      await $fetch('/api/v1/auth/logout', {
        baseURL: config.public.apiBase,
        method: 'POST',
        headers: session?.accessToken
          ? {
              Authorization: toBearer(session.tokenType, session.accessToken),
            }
          : undefined,
      })
    }
    catch {
      // Best effort only. Local session cleanup continues in the caller.
    }
  }

  async function syncAll(session: StoredSession) {
    try {
      return await $fetch<{ sync_summary?: unknown }>(withCookiesFile('/api/v1/sync/all', cookiesFile), {
        baseURL: config.public.apiBase,
        method: 'POST',
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to synchronize source data.')
    }
  }

  async function bbCalendar(session: StoredSession) {
    try {
      return await $fetch<{ events?: unknown[] }>(withCookiesFile('/api/v1/bb/calendar', cookiesFile), {
        baseURL: config.public.apiBase,
        method: 'POST',
        body: {},
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to read Blackboard calendar data.')
    }
  }

  async function listBBCalendarItems(session: StoredSession, signal?: AbortSignal) {
    try {
      return await $fetch<BackendBBCalendarItemsResponse>('/api/v1/bb/calendar/items', {
        baseURL: config.public.apiBase,
        method: 'GET',
        signal,
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to read manual calendar items.')
    }
  }

  async function createBBCalendarItem(session: StoredSession, payload: BBCalendarItemPayload, signal?: AbortSignal) {
    try {
      return await $fetch<BackendBBCalendarItemRecord>('/api/v1/bb/calendar/items', {
        baseURL: config.public.apiBase,
        method: 'POST',
        body: {
          completed: false,
          color: '#64748b',
          calendarName: 'Manual',
          eventType: 'task',
          userCreated: true,
          ...payload,
        },
        signal,
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to create manual calendar item.')
    }
  }

  async function patchBBCalendarItem(session: StoredSession, id: string | number, patch: BBCalendarItemPatch, signal?: AbortSignal) {
    try {
      return await $fetch<BackendBBCalendarItemRecord>(`/api/v1/bb/calendar/items/${encodeURIComponent(String(id))}`, {
        baseURL: config.public.apiBase,
        method: 'PATCH',
        body: patch,
        signal,
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to update manual calendar item.')
    }
  }

  async function deleteBBCalendarItem(session: StoredSession, id: string | number, signal?: AbortSignal) {
    try {
      return await $fetch<{ deleted?: boolean, id?: string | number }>(`/api/v1/bb/calendar/items/${encodeURIComponent(String(id))}`, {
        baseURL: config.public.apiBase,
        method: 'DELETE',
        signal,
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to delete manual calendar item.')
    }
  }

  async function bbCourses(session: StoredSession) {
    try {
      return await $fetch<{ courses?: unknown[] }>(withCookiesFile('/api/v1/bb/courses', cookiesFile), {
        baseURL: config.public.apiBase,
        method: 'POST',
        body: {},
        headers: session.accessToken
          ? {
              Authorization: toBearer(session.tokenType, session.accessToken),
            }
          : undefined,
      })
    }
    catch (error) {
      throw toApiError(error, 'Unable to read Blackboard courses.')
    }
  }

  async function bbGrades(session: StoredSession) {
    try {
      return await $fetch<{ grades?: unknown[] }>(withCookiesFile('/api/v1/bb/grades', cookiesFile), {
        baseURL: config.public.apiBase,
        method: 'POST',
        body: {},
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to read Blackboard grades.')
    }
  }

  async function bbFiles(session: StoredSession) {
    try {
      return await $fetch<{ files?: unknown[] }>(withCookiesFile('/api/v1/bb/files', cookiesFile), {
        baseURL: config.public.apiBase,
        method: 'POST',
        body: {},
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to read Blackboard files.')
    }
  }

  async function tisSchedule(session: StoredSession, signal?: AbortSignal) {
    const endpoint = '/api/v1/tis/schedule'
    const cacheKey = `POST:${endpoint}`
    if (pendingRequests.has(cacheKey)) {
      return pendingRequests.get(cacheKey)
    }

    const promise = $fetch<{ courses?: unknown[] }>(endpoint, {
      baseURL: config.public.apiBase,
      method: 'POST',
      body: {},
      signal,
      headers: {
        Authorization: toBearer(session.tokenType, session.accessToken),
      },
    }).catch(error => {
      if (error instanceof Error && error.name === 'AbortError') throw error
      return normalizeProtectedError(error, 'Unable to read TIS schedule.')
    }).finally(() => {
      pendingRequests.delete(cacheKey)
    })
    pendingRequests.set(cacheKey, promise)
    return promise
  }

  async function listScheduleEvents(session: StoredSession, signal?: AbortSignal) {
    const endpoint = '/api/v1/schedule/events'
    return $fetch<ScheduleEvent[]>(endpoint, {
      baseURL: config.public.apiBase,
      method: 'GET',
      signal,
      headers: {
        Authorization: toBearer(session.tokenType, session.accessToken),
      },
    }).catch(error => {
      if (error instanceof Error && error.name === 'AbortError') throw error
      return normalizeProtectedError(error, 'Unable to read schedule events.')
    })
  }

  async function createScheduleEvent(session: StoredSession, payload: ScheduleEventCreate) {
    return $fetch<ScheduleEvent>('/api/v1/schedule/events', {
      baseURL: config.public.apiBase,
      method: 'POST',
      body: payload,
      headers: {
        Authorization: toBearer(session.tokenType, session.accessToken),
      },
    }).catch(error => {
      if (error instanceof Error && error.name === 'AbortError') throw error
      return normalizeProtectedError(error, 'Unable to create schedule event.')
    })
  }

  async function updateScheduleEvent(session: StoredSession, eventId: number, payload: ScheduleEventUpdate) {
    return $fetch<ScheduleEvent>(`/api/v1/schedule/events/${eventId}`, {
      baseURL: config.public.apiBase,
      method: 'PATCH',
      body: payload,
      headers: {
        Authorization: toBearer(session.tokenType, session.accessToken),
      },
    }).catch(error => {
      if (error instanceof Error && error.name === 'AbortError') throw error
      return normalizeProtectedError(error, 'Unable to update schedule event.')
    })
  }

  async function deleteScheduleEvent(session: StoredSession, eventId: number) {
    return $fetch('/api/v1/schedule/events/' + eventId, {
      baseURL: config.public.apiBase,
      method: 'DELETE',
      headers: {
        Authorization: toBearer(session.tokenType, session.accessToken),
      },
    }).catch(error => {
      if (error instanceof Error && error.name === 'AbortError') throw error
      return normalizeProtectedError(error, 'Unable to delete schedule event.')
    })
  }

  async function tisGrade(session: StoredSession, signal?: AbortSignal) {
    const endpoint = '/api/v1/tis/grade'
    const cacheKey = `GET:${endpoint}`
    if (pendingRequests.has(cacheKey)) {
      return pendingRequests.get(cacheKey)
    }

    const promise = $fetch<{ GPA?: number | string, Rank?: number | string }>(endpoint, {
      baseURL: config.public.apiBase,
      method: 'GET',
      signal,
      headers: {
        Authorization: toBearer(session.tokenType, session.accessToken),
      },
    }).catch(error => {
      if (error instanceof Error && error.name === 'AbortError') throw error
      return normalizeProtectedError(error, 'Unable to read TIS grade.')
    }).finally(() => {
      pendingRequests.delete(cacheKey)
    })
    pendingRequests.set(cacheKey, promise)
    return promise
  }

  async function tisCredit(session: StoredSession, signal?: AbortSignal) {
    const endpoint = '/api/v1/tis/credit'
    const cacheKey = `GET:${endpoint}`
    if (pendingRequests.has(cacheKey)) {
      return pendingRequests.get(cacheKey)
    }

    const promise = $fetch<{ total_credit?: number, category_credit?: Record<string, number> }>(endpoint, {
      baseURL: config.public.apiBase,
      method: 'GET',
      signal,
      headers: {
        Authorization: toBearer(session.tokenType, session.accessToken),
      },
    }).catch(error => {
      if (error instanceof Error && error.name === 'AbortError') throw error
      return normalizeProtectedError(error, 'Unable to read TIS credits.')
    }).finally(() => {
      pendingRequests.delete(cacheKey)
    })
    pendingRequests.set(cacheKey, promise)
    return promise
  }

  async function tisInfo(session: StoredSession, signal?: AbortSignal) {
    const endpoint = '/api/v1/tis/info'
    const cacheKey = `POST:${endpoint}`
    if (pendingRequests.has(cacheKey)) {
      return pendingRequests.get(cacheKey)
    }

    const promise = $fetch<{ data?: unknown }>(endpoint, {
      baseURL: config.public.apiBase,
      method: 'POST',
      body: {},
      signal,
      headers: session.accessToken
        ? {
            Authorization: toBearer(session.tokenType, session.accessToken),
          }
        : undefined,
    }).catch(error => {
      if (error instanceof Error && error.name === 'AbortError') throw error
      throw toApiError(error, 'Unable to read TIS profile info.')
    }).finally(() => {
      pendingRequests.delete(cacheKey)
    })
    pendingRequests.set(cacheKey, promise)
    return promise
  }

  async function tisPhoto(session: StoredSession, signal?: AbortSignal) {
    const endpoint = '/api/v1/tis/photo'
    const cacheKey = `POST:${endpoint}`
    if (pendingRequests.has(cacheKey)) {
      return pendingRequests.get(cacheKey)
    }

    const promise = $fetch<{ base64?: string, filename?: string, type?: string, size?: number, saved_path?: string | null }>(endpoint, {
      baseURL: config.public.apiBase,
      method: 'POST',
      body: {},
      signal,
      headers: {
        Authorization: toBearer(session.tokenType, session.accessToken),
      },
    }).catch(error => {
      if (error instanceof Error && error.name === 'AbortError') throw error
      return normalizeProtectedError(error, 'Unable to read TIS photo.')
    }).finally(() => {
      pendingRequests.delete(cacheKey)
    })
    pendingRequests.set(cacheKey, promise)
    return promise
  }

  async function getUserProfile(session: StoredSession, signal?: AbortSignal) {
    try {
      return await $fetch<BackendUserProfileResponse>('/api/v1/user/profile', {
        baseURL: config.public.apiBase,
        method: 'GET',
        signal,
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to read profile from backend storage.')
    }
  }

  async function getUserInterest(session: StoredSession, signal?: AbortSignal) {
    try {
      const response = await $fetch<BackendUserInterestResponse>('/api/v1/user/interest', {
        baseURL: config.public.apiBase,
        method: 'GET',
        signal,
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })
      return typeof response.interest === 'string' ? response.interest : ''
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to read profile interests.')
    }
  }

  async function createUserInterest(session: StoredSession, interest: string, signal?: AbortSignal) {
    try {
      const response = await $fetch<BackendUserInterestResponse>('/api/v1/user/interest', {
        baseURL: config.public.apiBase,
        method: 'POST',
        body: { interest },
        signal,
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })
      return typeof response.interest === 'string' ? response.interest : interest
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to create profile interests.')
    }
  }

  async function patchUserInterest(session: StoredSession, interest: string, signal?: AbortSignal) {
    try {
      const response = await $fetch<BackendUserInterestResponse>('/api/v1/user/interest', {
        baseURL: config.public.apiBase,
        method: 'PATCH',
        body: { interest },
        signal,
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })
      return typeof response.interest === 'string' ? response.interest : interest
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to update profile interests.')
    }
  }

  async function deleteUserInterest(session: StoredSession, signal?: AbortSignal) {
    try {
      const response = await $fetch<BackendUserInterestResponse>('/api/v1/user/interest', {
        baseURL: config.public.apiBase,
        method: 'DELETE',
        signal,
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })
      return typeof response.interest === 'string' ? response.interest : ''
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to clear profile interests.')
    }
  }

  async function saveUserInterest(session: StoredSession, interest: string, signal?: AbortSignal) {
    const normalized = interest.trim()
    if (!normalized) {
      return deleteUserInterest(session, signal)
    }

    try {
      const existing = await getUserInterest(session, signal)
      return existing.trim()
        ? await patchUserInterest(session, normalized, signal)
        : await createUserInterest(session, normalized, signal)
    }
    catch (error) {
      const apiError = toApiError(error, 'Unable to save profile interests.')
      if (apiError.status === 404) {
        return createUserInterest(session, normalized, signal)
      }
      throw apiError
    }
  }

  async function createChatSession(session: StoredSession) {
    try {
      return await $fetch<{ session_id: string, status: string, message: string }>('/api/v1/chat/create_session', {
        baseURL: config.public.apiBase,
        method: 'POST',
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to create assistant session.')
    }
  }

  async function listChatSessions(session: StoredSession, signal?: AbortSignal) {
    try {
      return await $fetch<BackendChatSessionListResponse>('/api/v1/history/get_sessions', {
        baseURL: config.public.apiBase,
        method: 'GET',
        signal,
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to load assistant conversations.')
    }
  }

  async function listChatMessages(session: StoredSession, sessionId: string, signal?: AbortSignal) {
    try {
      return await $fetch<BackendChatMessageRecord[]>('/api/v1/history/get_messages', {
        baseURL: config.public.apiBase,
        method: 'GET',
        signal,
        query: {
          session_id: sessionId,
        },
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to load conversation messages.')
    }
  }

  async function renameChatSession(
    session: StoredSession,
    sessionId: string,
    sessionName: string,
    signal?: AbortSignal,
  ) {
    try {
      return await $fetch<BackendChatSessionRenameResponse>(
        `/api/v1/history/sessions/${encodeURIComponent(sessionId)}/rename`,
        {
          baseURL: config.public.apiBase,
          method: 'PATCH',
          signal,
          body: {
            session_name: sessionName,
          },
          headers: {
            Authorization: toBearer(session.tokenType, session.accessToken),
          },
        },
      )
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to rename assistant conversation.')
    }
  }

  async function deleteChatSession(session: StoredSession, sessionId: string, signal?: AbortSignal) {
    try {
      return await $fetch<BackendChatSessionDeleteResponse>(
        `/api/v1/history/sessions/${encodeURIComponent(sessionId)}`,
        {
          baseURL: config.public.apiBase,
          method: 'DELETE',
          signal,
          headers: {
            Authorization: toBearer(session.tokenType, session.accessToken),
          },
        },
      )
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to delete assistant conversation.')
    }
  }

  async function streamChatOnDocs(session: StoredSession, input: ChatStreamInput) {
    const streamMode = input.streamMode ?? 'standard'
    const endpoint = streamMode === 'web-search'
      ? '/api/v1/chat/ai_search/'
      : streamMode === 'deep-research'
        ? '/api/v1/chat/deep_research/'
        : '/api/v1/chat/chat_on_docs'
    const url = new URL(endpoint, config.public.apiBase)
    url.searchParams.set('session_id', input.sessionId)
    if (streamMode === 'standard' && input.deepThink) {
      url.searchParams.set('deep_think', 'true')
    }

    let response: Response
    try {
      response = await fetch(url.toString(), {
        method: 'POST',
        signal: input.signal,
        headers: {
          'Content-Type': 'application/json',
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
        body: JSON.stringify({
          message: input.message,
        }),
      })
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to stream assistant response.')
    }

    if (!response.ok || !response.body) {
      return normalizeProtectedError({
        statusCode: response.status,
        response: {
          status: response.status,
          _data: { detail: `Assistant stream request failed (${response.status}).` },
        },
      }, 'Unable to stream assistant response.')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    const separatorPattern = /\r?\n\r?\n/
    while (true) {
      const { done, value } = await reader.read()
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done })

      let separatorMatch = separatorPattern.exec(buffer)
      while (separatorMatch && typeof separatorMatch.index === 'number') {
        const separatorIndex = separatorMatch.index
        const separatorLength = separatorMatch[0].length
        const block = buffer.slice(0, separatorIndex)
        buffer = buffer.slice(separatorIndex + separatorLength)
        const parsedBlock = parseSseEventBlock(block)
        if (parsedBlock) {
          const parsedEvent = parseAssistantStreamEvent(parsedBlock)
          if (parsedEvent) {
            input.onEvent(parsedEvent)
          }
        }
        separatorMatch = separatorPattern.exec(buffer)
      }

      if (done) {
        break
      }
    }
  }

  async function listAssistantKnowledgeBases(session: StoredSession, signal?: AbortSignal) {
    const endpoint = '/api/v1/history/get_files'
    const cacheKey = `GET:knowledge-bases:${endpoint}`
    if (pendingRequests.has(cacheKey)) {
      return pendingRequests.get(cacheKey)
    }

    const promise = $fetch<BackendHistoryFileRecord[]>(endpoint, {
      baseURL: config.public.apiBase,
      method: 'GET',
      signal,
      headers: {
        Authorization: toBearer(session.tokenType, session.accessToken),
      },
    }).then((records) => {
      const files = Array.isArray(records)
        ? records
          .map((record, index) => toAssistantKnowledgeBaseFileItem(record, index))
          .filter((item): item is AssistantKnowledgeBaseFileItem => Boolean(item))
        : []
      const latest = files[0]?.createdAt ?? new Date().toISOString()
      return {
        backendState: 'ready' as const,
        items: [{
          id: 'global',
          name: 'Global Knowledge Base',
          description: 'User-level knowledge uploaded through the current backend.',
          fileCount: files.length,
          createdAt: latest,
          updatedAt: latest,
        }],
      }
    }).catch(error => normalizeAssistantKnowledgeBaseError(error, 'Unable to read assistant knowledge bases.'))
      .finally(() => {
        pendingRequests.delete(cacheKey)
      })
    pendingRequests.set(cacheKey, promise)
    return promise
  }

  async function listAssistantKnowledgeBaseFiles(session: StoredSession, knowledgeBaseId: string, signal?: AbortSignal) {
    void knowledgeBaseId
    const endpoint = '/api/v1/history/get_files'
    const cacheKey = `GET:knowledge-files:${endpoint}`
    if (pendingRequests.has(cacheKey)) {
      return pendingRequests.get(cacheKey)
    }

    const promise = $fetch<BackendHistoryFileRecord[]>(endpoint, {
      baseURL: config.public.apiBase,
      method: 'GET',
      signal,
      headers: {
        Authorization: toBearer(session.tokenType, session.accessToken),
      },
    }).then((records) => ({
      backendState: 'ready' as const,
      items: Array.isArray(records)
        ? records
          .map((record, index) => toAssistantKnowledgeBaseFileItem(record, index))
          .filter((item): item is AssistantKnowledgeBaseFileItem => Boolean(item))
        : [],
    })).catch(error => normalizeAssistantKnowledgeBaseError(error, 'Unable to read assistant knowledge base files.'))
      .finally(() => {
        pendingRequests.delete(cacheKey)
      })
    pendingRequests.set(cacheKey, promise)
    return promise
  }

  async function deleteAssistantKnowledgeBaseFile(session: StoredSession, fileName: string, signal?: AbortSignal) {
    try {
      return await $fetch<{ message?: string }>(`/api/v1/history/delete_file/${encodeURIComponent(fileName)}`, {
        baseURL: config.public.apiBase,
        method: 'DELETE',
        signal,
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to delete knowledge-base file.')
    }
  }

  async function uploadAssistantKnowledgeBaseFile(session: StoredSession, input: AssistantKnowledgeBaseUploadInput, signal?: AbortSignal) {
    if (input.files.length === 0) {
      return {
        status: 'failed',
        message: 'No files selected.',
        successfulFiles: [],
        failedFiles: [],
        totalFiles: 0,
      } satisfies AssistantKnowledgeUploadResult
    }

    const endpoint = '/api/v1/chat/upload_files'
    const formData = new FormData()
    for (const file of input.files) {
      formData.append('files', file, file.name)
    }

    try {
      const response = await $fetch<BackendKnowledgeUploadResponse>(endpoint, {
        baseURL: config.public.apiBase,
        method: 'POST',
        body: formData,
        signal,
        query: {
          session_id: input.sessionId,
        },
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })

      const successfulFiles = Array.isArray(response.successful_files)
        ? response.successful_files.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
        : []
      const failedFiles = Array.isArray(response.failed_files)
        ? response.failed_files.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
        : []
      const totalFiles = typeof response.total_files === 'number' && Number.isFinite(response.total_files)
        ? response.total_files
        : input.files.length

      return {
        status: response.status === 'partial_success'
          ? 'partial_success'
          : response.status === 'success'
            ? 'success'
            : failedFiles.length > 0
              ? 'failed'
              : 'success',
        message: typeof response.message === 'string' && response.message.trim()
          ? response.message.trim()
          : successfulFiles.length > 0
            ? 'Files uploaded successfully.'
            : 'File upload failed.',
        successfulFiles,
        failedFiles,
        totalFiles,
      } satisfies AssistantKnowledgeUploadResult
    }
    catch (error) {
      return normalizeAssistantKnowledgeBaseError(error, 'Unable to upload assistant knowledge base file.')
    }
  }

  async function quickParseSessionFile(session: StoredSession, sessionId: string, file: File, signal?: AbortSignal) {
    const endpoint = '/api/v1/chat/quick_parse'
    const formData = new FormData()
    formData.set('file', file, file.name)

    try {
      return await $fetch<unknown>(endpoint, {
        baseURL: config.public.apiBase,
        method: 'POST',
        body: formData,
        signal,
        query: {
          session_id: sessionId,
        },
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to parse temporary assistant file.')
    }
  }

  async function getParsedContent(session: StoredSession, sessionId: string, signal?: AbortSignal) {
    try {
      return await $fetch<unknown>('/api/v1/chat/get_parsed_content', {
        baseURL: config.public.apiBase,
        method: 'GET',
        signal,
        query: {
          session_id: sessionId,
        },
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to read parsed temporary assistant content.')
    }
  }

  async function getMailAccount(session: StoredSession, signal?: AbortSignal) {
    try {
      const response = await $fetch<BackendMailAccountResponse>('/api/v1/mail/account', {
        baseURL: config.public.apiBase,
        method: 'GET',
        signal,
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })
      return toMailAccount(response)
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to read mailbox account status.')
    }
  }

  async function loginMailAccount(session: StoredSession, input: MailLoginInput, signal?: AbortSignal) {
    try {
      const response = await $fetch<BackendMailAccountResponse>('/api/v1/mail/account/login', {
        baseURL: config.public.apiBase,
        method: 'POST',
        body: {
          provider: input.provider,
          email_address: input.emailAddress,
          password: input.password,
        },
        signal,
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })
      return toMailAccount(response)
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to log in to this mailbox.')
    }
  }

  async function logoutMailAccount(session: StoredSession, signal?: AbortSignal) {
    try {
      await $fetch('/api/v1/mail/account/logout', {
        baseURL: config.public.apiBase,
        method: 'POST',
        signal,
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to log out of the mailbox.')
    }
  }

  async function syncMail(session: StoredSession, input: MailSyncInput, signal?: AbortSignal) {
    try {
      const response = await $fetch<BackendMailSyncResponse>('/api/v1/mail/sync', {
        baseURL: config.public.apiBase,
        method: 'POST',
        body: {
          folder: input.folder,
          limit: input.limit,
          unread_only: input.unreadOnly,
        },
        signal,
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })
      return toMailSyncResult(response)
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to sync mailbox messages.')
    }
  }

  async function listMailMessages(session: StoredSession, input?: { folder?: string, limit?: number }, signal?: AbortSignal) {
    try {
      const response = await $fetch<BackendMailMessagesResponse>('/api/v1/mail/messages', {
        baseURL: config.public.apiBase,
        method: 'GET',
        query: {
          folder: input?.folder,
          limit: input?.limit,
        },
        signal,
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })
      return (response.messages ?? [])
        .map(toMailMessage)
        .filter((message): message is MailMessage => Boolean(message))
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to read mailbox messages.')
    }
  }

  async function getMailMessage(session: StoredSession, mailId: number, signal?: AbortSignal) {
    try {
      const response = await $fetch<BackendMailMessageRecord>(`/api/v1/mail/messages/${mailId}`, {
        baseURL: config.public.apiBase,
        method: 'GET',
        signal,
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })
      const message = toMailMessage(response)
      if (!message) {
        throw {
          status: 502,
          message: 'Mailbox message response is invalid.',
        } satisfies ApiError
      }
      return message
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to read mailbox message detail.')
    }
  }

  async function sendMail(session: StoredSession, input: MailSendInput, signal?: AbortSignal) {
    try {
      const response = await $fetch<BackendMailSendResponse>('/api/v1/mail/send', {
        baseURL: config.public.apiBase,
        method: 'POST',
        body: {
          to_addresses: input.toAddresses,
          cc_addresses: input.ccAddresses,
          bcc_addresses: input.bccAddresses,
          subject: input.subject,
          body: input.body,
          html_body: input.htmlBody ?? null,
        },
        signal,
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })
      return toMailSendResult(response)
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to send this email.')
    }
  }

  async function listSessionDocuments(session: StoredSession, sessionId: string, signal?: AbortSignal) {
    try {
      const response = await $fetch<BackendSessionDocumentListResponse>(`/api/v1/chat/sessions/${encodeURIComponent(sessionId)}/documents`, {
        baseURL: config.public.apiBase,
        method: 'GET',
        signal,
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })
      return (response.documents ?? [])
        .map(item => toAssistantSessionDocumentItem(item, sessionId))
        .filter((item): item is AssistantSessionDocumentItem => Boolean(item))
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to read session assistant files.')
    }
  }

  async function getSessionDocumentsSummary(session: StoredSession, sessionId: string, signal?: AbortSignal) {
    try {
      const response = await $fetch<BackendSessionDocumentSummaryResponse>(`/api/v1/chat/sessions/${encodeURIComponent(sessionId)}/documents/summary`, {
        baseURL: config.public.apiBase,
        method: 'GET',
        signal,
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })
      return {
        sessionId,
        hasDocuments: Boolean(response.has_documents),
        latestDocumentName: typeof response.latest_document_name === 'string' ? response.latest_document_name : '',
        latestDocumentType: typeof response.latest_document_type === 'string' ? response.latest_document_type : '',
        latestUploadTime: typeof response.latest_upload_time === 'string' ? response.latest_upload_time : '',
        totalDocuments: typeof response.total_documents === 'number' && Number.isFinite(response.total_documents)
          ? response.total_documents
          : 0,
      } satisfies AssistantSessionDocumentSummary
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to read session assistant file summary.')
    }
  }

  async function resolveAgentApproval(session: StoredSession, actionId: string, approved: boolean) {
    try {
      const response = await $fetch<{
        success: boolean
        action_id: string
        state: string
        message: string
        target: string
      }>('/api/v1/chat/agent/approval', {
        baseURL: config.public.apiBase,
        method: 'POST',
        body: {
          action_id: actionId,
          approved,
        },
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })

      return {
        success: Boolean(response.success),
        actionId: typeof response.action_id === 'string' ? response.action_id : actionId,
        state: response.state === 'approved' || response.state === 'rejected' ? response.state : 'pending',
        message: typeof response.message === 'string' ? response.message : '',
        target: typeof response.target === 'string' ? response.target : 'action',
      } satisfies AssistantApprovalResolution
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to resolve approval action.')
    }
  }

  async function getAgentFileWorkspace(session: StoredSession) {
    try {
      const response = await $fetch<{
        success: boolean
        workspace_root: string
      }>('/api/v1/chat/agent/file_workspace', {
        baseURL: config.public.apiBase,
        method: 'GET',
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })

      return {
        success: Boolean(response.success),
        workspaceRoot: typeof response.workspace_root === 'string' ? response.workspace_root : '',
      }
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to read file workspace.')
    }
  }

  async function setAgentFileWorkspace(session: StoredSession, path: string) {
    try {
      const response = await $fetch<{
        success: boolean
        workspace_root: string
        message: string
      }>('/api/v1/chat/agent/file_workspace', {
        baseURL: config.public.apiBase,
        method: 'POST',
        body: {
          path,
        },
        headers: {
          Authorization: toBearer(session.tokenType, session.accessToken),
        },
      })

      return {
        success: Boolean(response.success),
        workspaceRoot: typeof response.workspace_root === 'string' ? response.workspace_root : path,
        message: typeof response.message === 'string' ? response.message : '',
      }
    }
    catch (error) {
      return normalizeProtectedError(error, 'Unable to update file workspace.')
    }
  }

  return {
    login,
    logout,
    syncAll,
    bbCourses,
    bbCalendar,
    listBBCalendarItems,
    createBBCalendarItem,
    patchBBCalendarItem,
    deleteBBCalendarItem,
    bbGrades,
    bbFiles,
    tisSchedule,
    listScheduleEvents,
    createScheduleEvent,
    updateScheduleEvent,
    deleteScheduleEvent,
    tisGrade,
    tisCredit,
    tisInfo,
    tisPhoto,
    getUserProfile,
    getUserInterest,
    createUserInterest,
    patchUserInterest,
    deleteUserInterest,
    saveUserInterest,
    createChatSession,
    listChatSessions,
    listChatMessages,
    renameChatSession,
    deleteChatSession,
    streamChatOnDocs,
    resolveAgentApproval,
    getAgentFileWorkspace,
    setAgentFileWorkspace,
    quickParseSessionFile,
    getParsedContent,
    getMailAccount,
    loginMailAccount,
    logoutMailAccount,
    syncMail,
    listMailMessages,
    getMailMessage,
    sendMail,
    listSessionDocuments,
    getSessionDocumentsSummary,
    listAssistantKnowledgeBases,
    listAssistantKnowledgeBaseFiles,
    deleteAssistantKnowledgeBaseFile,
    uploadAssistantKnowledgeBaseFile,
  }
}
