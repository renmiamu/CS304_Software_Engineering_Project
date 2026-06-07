import type {
  ApprovalAction,
  AssistantMode,
  AuthUser,
  ChatMessage,
  DashboardSummary,
  SourceConnection,
  SyncJob,
  ToolLog,
} from '~/types/app'

function isoOffset(hours: number) {
  return new Date(Date.now() - hours * 60 * 60 * 1000).toISOString()
}

function deepCopy<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

export const serviceOptions = [
  { label: 'Teaching Information System', value: 'tis' },
  { label: 'Blackboard', value: 'blackboard' },
  { label: 'SUSTech Mail', value: 'mail' },
]

const initialSources: SourceConnection[] = [
  {
    id: 'bb',
    name: 'Blackboard',
    description: 'Calendar, grades, and files from Blackboard database snapshots.',
    status: 'needs_sync',
    reason: 'not_synced',
    lastCheckedAt: isoOffset(1),
    itemsImported: 0,
    details: 'No synchronized Blackboard data yet.',
  },
  {
    id: 'tis',
    name: 'TIS',
    description: 'Schedule, GPA/rank, and credit information from TIS database snapshots.',
    status: 'needs_sync',
    reason: 'not_synced',
    lastCheckedAt: isoOffset(1),
    itemsImported: 0,
    details: 'No synchronized TIS data yet.',
  },
  {
    id: 'mail',
    name: 'Mail',
    description: 'Mailbox login, inbox sync, reading, and SMTP sending.',
    status: 'needs_sync',
    lastCheckedAt: isoOffset(1),
    itemsImported: 0,
    details: 'Connect a mailbox before syncing messages.',
  },
]

const initialSyncJobs: SyncJob[] = []

const initialApprovals: ApprovalAction[] = [
  {
    id: 'approval-1',
    title: 'Reschedule database lab reminder',
    description: 'Move reminder from 20:00 to 18:30 because a group meeting overlaps.',
    target: 'Calendar reminder',
    riskLevel: 'high',
    state: 'pending',
  },
  {
    id: 'approval-2',
    title: 'Draft reply to TA',
    description: 'Prepare a response asking for clarification on grading policy.',
    target: 'University Mail',
    riskLevel: 'medium',
    state: 'pending',
  },
]

const initialMessages: ChatMessage[] = [
  {
    id: 'msg-1',
    role: 'assistant',
    content: 'Morning. I found one Blackboard deadline conflict and one mail reminder that may affect this week.',
    timestamp: isoOffset(2),
    mode: 'general',
  },
  {
    id: 'msg-2',
    role: 'assistant',
    content: 'You can switch to campus mode for policy questions or automator mode for file and schedule actions.',
    timestamp: isoOffset(2),
    mode: 'general',
  },
]

const initialToolLogs: ToolLog[] = [
  {
    id: 'tool-1',
    label: 'Mailbox parser',
    status: 'completed',
    detail: 'Extracted 2 deadline candidates from unread course emails.',
    timestamp: isoOffset(2),
  },
  {
    id: 'tool-2',
    label: 'Calendar conflict detector',
    status: 'needs-approval',
    detail: 'Proposed 1 reminder change and is waiting for your confirmation.',
    timestamp: isoOffset(2),
  },
]

export function createMockUser(username: string): AuthUser {
  const handle = username.split('@')[0].trim() || 'student'

  return {
    name: handle,
    email: username.includes('@') ? username : `${handle}@mail.sustech.edu.cn`,
    major: 'Software Engineering',
    year: '2026',
    token: `demo-${handle}-token`,
    authSource: 'live',
  }
}

export function createSourceConnections() {
  return deepCopy(initialSources)
}

export function createSyncJobs() {
  return deepCopy(initialSyncJobs)
}

export function createApprovalActions() {
  return deepCopy(initialApprovals)
}

export function createInitialMessages() {
  return deepCopy(initialMessages)
}

export function createToolLogs() {
  return deepCopy(initialToolLogs)
}

export function createDashboardSummary(input: {
  approvals: ApprovalAction[]
  sources: SourceConnection[]
}): DashboardSummary {
  const connectedSources = input.sources.filter(source => source.status === 'synced').length
  const needsSyncSources = input.sources.filter(source => source.status === 'needs_sync').length
  const pendingApprovals = input.approvals.filter(action => action.state === 'pending').length
  const nextAttentionSource = input.sources.find(source => source.status !== 'synced')

  return {
    todayFocus: 'Prioritize today schedule and near-term deadlines, then verify source health.',
    pendingTasks: needsSyncSources,
    pendingApprovals,
    connectedSources,
    nextSyncLabel: nextAttentionSource
      ? `${nextAttentionSource.name}: ${nextAttentionSource.status}`
      : 'All sources are synchronized',
  }
}

export function createAssistantReply(mode: AssistantMode, prompt: string) {
  const normalizedPrompt = prompt.trim()

  if (mode === 'campus') {
    return `Campus knowledge mode checked the indexed handbook notes. For "${normalizedPrompt}", I would answer with the relevant policy section first, then point you to the original source text for verification.`
  }

  if (mode === 'automator') {
    return `Automator mode translated "${normalizedPrompt}" into a proposed action plan. I added the risky step to the approval queue instead of executing it directly.`
  }

  return `I combined your current dashboard context with recent sync results. For "${normalizedPrompt}", I would prioritize the Blackboard deadlines first, then update your reminders and study queue.`
}
