import type { StoredSession } from '~/types/app'

export const SESSION_COOKIE_KEY = 'student-assistant-session'
const TWELVE_HOURS_MS = 12 * 60 * 60 * 1000

function toJsonRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object') {
    return null
  }
  return value as Record<string, unknown>
}

function decodeBase64Url(value: string) {
  const normalized = value.replace(/-/g, '+').replace(/_/g, '/')
  const padding = normalized.length % 4
  const padded = padding === 0 ? normalized : normalized.padEnd(normalized.length + (4 - padding), '=')

  if (typeof atob === 'function') {
    return atob(padded)
  }

  return Buffer.from(padded, 'base64').toString('utf-8')
}

export function parseJwtExpAt(accessToken: string): string | undefined {
  if (!accessToken || !accessToken.includes('.')) {
    return undefined
  }

  try {
    const payloadRaw = accessToken.split('.')[1]
    if (!payloadRaw) {
      return undefined
    }

    const payload = JSON.parse(decodeBase64Url(payloadRaw)) as { exp?: number }
    if (!payload.exp || Number.isNaN(payload.exp)) {
      return undefined
    }

    return new Date(payload.exp * 1000).toISOString()
  }
  catch {
    return undefined
  }
}

export function computeExpiresAt(loginAtIso: string, jwtExpAtIso?: string): string {
  const loginAt = new Date(loginAtIso).getTime()
  const fallbackExp = loginAt + TWELVE_HOURS_MS

  if (!Number.isFinite(loginAt)) {
    return new Date(Date.now() + TWELVE_HOURS_MS).toISOString()
  }

  if (!jwtExpAtIso) {
    return new Date(fallbackExp).toISOString()
  }

  const jwtExp = new Date(jwtExpAtIso).getTime()
  if (!Number.isFinite(jwtExp)) {
    return new Date(fallbackExp).toISOString()
  }

  return new Date(Math.min(jwtExp, fallbackExp)).toISOString()
}

export function isSessionExpired(candidate: StoredSession | null, now = Date.now()) {
  if (!candidate?.expiresAt) {
    return true
  }

  const expiresAt = new Date(candidate.expiresAt).getTime()
  if (!Number.isFinite(expiresAt)) {
    return true
  }

  return now >= expiresAt
}

export function normalizeStoredSession(candidate: StoredSession | null) {
  if (!candidate) {
    return null
  }

  const user = toJsonRecord(candidate.user)
  const hasAuthFields = Boolean(
    candidate.isAuthenticated
      && candidate.accessToken
      && candidate.tokenType
      && Number.isInteger(candidate.userId)
      && (candidate.loginMethod === 'cas' || candidate.loginMethod === 'mail')
      && candidate.loginAt
      && candidate.expiresAt
      && user?.email
      && user?.name
      && user?.authSource === 'live',
  )

  if (!hasAuthFields) {
    return null
  }

  if (isSessionExpired(candidate)) {
    return null
  }

  return candidate
}

export function clearAuthState() {
  const sessionCookie = useCookie<StoredSession | null>(SESSION_COOKIE_KEY, {
    default: () => null,
    sameSite: 'lax',
  })
  const sessionState = useState<StoredSession | null>('session', () => null)
  const workspace = useWorkspaceStore()

  sessionCookie.value = null
  sessionState.value = null
  workspace.resetWorkspace()
}

export async function redirectToLoginWithReason(reason: 'expired' | 'missing_user_id') {
  clearAuthState()

  if (!process.client) {
    return
  }

  const route = useRoute()
  if (route.path !== '/login') {
    await navigateTo(`/login?reason=${reason}`)
    return
  }

  const currentReason = typeof route.query.reason === 'string' ? route.query.reason : ''
  if (currentReason !== reason) {
    await navigateTo(`/login?reason=${reason}`)
  }
}
