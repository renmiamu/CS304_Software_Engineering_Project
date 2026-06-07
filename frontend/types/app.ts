export type AssistantMode = 'general'
export type AssistantModel = 'deepseek-chat' | 'deepseek-reasoner' | 'deep-research'
export type ChatStreamMode = 'standard' | 'web-search' | 'deep-research'
export type KnowledgeBackendState = 'ready' | 'unavailable'
export type KnowledgeScope = 'temporary' | 'permanent'
export type LoginMethod = 'cas' | 'mail'
export type AssistantCapabilityState = 'available' | 'unavailable'
export type SourceStatus = 'synced' | 'needs_sync' | 'auth_expired'
export type SourceReason =
  | 'not_synced'
  | 'cas_required'
  | 'not_implemented'
  | 'auth_expired'
  | 'unsupported_login_method'
  | 'sync_failed'
  | 'unknown'

export interface SendMessageInput {
  content: string
  model: AssistantModel
  webSearchEnabled?: boolean
  temporaryKnowledgeIds?: string[]
  permanentKnowledgeIds?: string[]
}

export interface BackendChatSessionSummary {
  session_id: string
  session_name: string
  user_id: string
  created_at: string
  updated_at: string
}

export interface BackendChatSessionListResponse {
  user_id: string
  sessions: BackendChatSessionSummary[]
}

export interface BackendChatSessionRenameResponse {
  session_id: string
  session_name: string
  status: string
  message: string
}

export interface BackendChatSessionDeleteResponse {
  session_id: string
  deleted: boolean
  deleted_messages: number
  deleted_documents: number
  status: string
  message: string
}

export interface BackendChatMessageRecord {
  message_id: string
  session_id: string
  user_question: string
  model_answer: string
  documents?: unknown
  recommended_questions?: unknown
  think?: string | null
  created_at: string
}

export interface CitationSource {
  index: number
  title: string
  excerpt: string
  documentId?: string
}

export type AssistantStreamEvent =
  | { type: 'documents', citations: CitationSource[] }
  | { type: 'delta', content: string }
  | { type: 'thinking', content: string }
  | { type: 'recommendations', items: string[] }
  | { type: 'approval', approval: ApprovalAction }
  | { type: 'end' }
  | { type: 'error', message: string }

export interface KnowledgeBaseItem {
  id: string
  name: string
  sizeLabel: string
  uploadedAt: string
  scope: KnowledgeScope
  mimeType?: string
  conversationId?: string
}

export interface AuthUser {
  name: string
  email: string
  major: string
  year: string
  token: string
  authSource: 'live'
}

export interface StoredSession {
  isAuthenticated: boolean
  accessToken: string
  tokenType: string
  userId: number
  loginMethod: LoginMethod
  loginAt: string
  expiresAt: string
  jwtExpAt?: string
  user: AuthUser
}

export interface UserInit {
  ok: boolean
  user_id?: number
  created?: boolean
  reason?: string
  error?: string
}

export interface AuthServiceItem {
  key: string
  label: string
  url: string
}

export interface ApiError {
  status: number
  message: string
  code?: string
  details?: unknown
}

export type MailProvider = 'qq' | 'exmail'

export interface MailAccount {
  loggedIn: boolean
  provider: MailProvider | null
  mailbox: string | null
  loggedInAt: string | null
}

export interface MailLoginInput {
  provider: MailProvider
  emailAddress: string
  password: string
}

export interface MailSyncInput {
  folder: string
  limit: number
  unreadOnly: boolean
}

export interface MailSyncResult {
  mailbox: string
  folder: string
  requestedLimit: number
  unreadOnly: boolean
  fetched: number
  inserted: number
  updated: number
}

export interface MailMessage {
  id: number
  mailbox: string
  folder: string
  imapUid: string
  messageId: string
  subject: string
  fromAddress: string
  toAddress: string
  ccAddress: string | null
  receivedAt: string | null
  rawDate: string
  snippet: string
  textBody: string
  htmlBody: string | null
  isSeen: boolean
  hasAttachment: boolean
  syncedAt: string | null
}

export interface MailSendInput {
  toAddresses: string[]
  ccAddresses: string[]
  bccAddresses: string[]
  subject: string
  body: string
  htmlBody?: string | null
}

export interface MailSendResult {
  mailbox: string
  toAddresses: string[]
  ccAddresses: string[]
  bccCount: number
  subject: string
  messageId: string
  sentAt: string
}

export interface DashboardSummary {
  todayFocus: string
  pendingTasks: number
  pendingApprovals: number
  connectedSources: number
  nextSyncLabel: string
}

export interface SourceConnection {
  id: string
  name: string
  description: string
  status: SourceStatus
  reason?: SourceReason
  lastCheckedAt: string
  lastSyncedAt?: string
  itemsImported: number
  details: string
}

export interface SyncJob {
  id: string
  title: string
  sourceId: string
  status: 'success' | 'warning' | 'failed'
  runAt: string
  detail: string
}

export interface BBDeadlineItem {
  id: string
  title: string
  endTime: string
  calendarName: string
  eventType: string
  color: string
  isUserCreated: boolean
  completed: boolean
}

export interface BBGradeItem {
  id: string
  courseName: string
  itemName: string
  fullGrade: string
}

export interface BBFileItem {
  id: string
  course: string
  content: string
  fileName: string
  fileUrl: string
}

export interface ScheduleDeadline {
  id: string
  title: string
  endTime: string
  calendarName: string
  eventType: string
  color: string
  isUserCreated: boolean
  completed: boolean
}

export interface IdentityCardData {
  user_id: string
  name: string
  pinyin_name: string
  photo: string
  gender: string
  birth_date: string
  college: string
  dormitory: string
  phone: string
  email: string
  gpa: string
  rank: string
  department: string
  interest: string
}

export interface ApprovalAction {
  id: string
  title: string
  description: string
  target: string
  riskLevel: 'medium' | 'high'
  state: 'pending' | 'approved' | 'rejected'
}

export interface TraceStep {
  id: string
  label: string
  detail: string
  status: 'running' | 'completed'
  timestamp: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  mode: AssistantMode
  model?: AssistantModel
  temporaryKnowledgeIds?: string[]
  permanentKnowledgeIds?: string[]
  status?: 'idle' | 'streaming' | 'done' | 'failed'
  thinkingContent?: string
  citations?: CitationSource[]
  recommendedQuestions?: string[]
  errorMessage?: string
  trace?: TraceStep[]
  traceState?: 'idle' | 'running' | 'done'
  linkedApprovalIds?: string[]
}

export interface ToolLog {
  id: string
  label: string
  status: 'running' | 'completed' | 'needs-approval'
  detail: string
  timestamp: string
}

export interface AssistantConversation {
  id: string
  backendSessionId?: string | null
  backendHydratedAt?: string | null
  title: string
  createdAt: string
  updatedAt: string
  assistantMode: AssistantMode
  assistantModel: AssistantModel
  temporaryKnowledgeItems: KnowledgeBaseItem[]
  permanentKnowledgeIds: string[]
  messages: ChatMessage[]
  approvals: ApprovalAction[]
}

export interface AssistantConversationSummary {
  id: string
  title: string
  createdAt: string
  updatedAt: string
  messageCount: number
  pendingApprovalCount: number
}

export interface LoginCredentials {
  username: string
  password: string
  loginMethod: LoginMethod
}

export interface LoginResult {
  accessToken: string
  tokenType: string
  loginMethod: LoginMethod
  userInit: UserInit
  user: AuthUser
}
