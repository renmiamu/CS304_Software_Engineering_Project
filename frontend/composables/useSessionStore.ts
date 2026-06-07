import {
  SESSION_COOKIE_KEY,
  computeExpiresAt,
  isSessionExpired,
  normalizeStoredSession,
  parseJwtExpAt,
  redirectToLoginWithReason,
} from '~/lib/auth-session'
import type { LoginCredentials, LoginResult, StoredSession } from '~/types/app'

function parseUserId(candidate: unknown) {
  if (typeof candidate === 'number' && Number.isInteger(candidate) && candidate > 0) {
    return candidate
  }

  if (typeof candidate === 'string' && /^\d+$/.test(candidate)) {
    return Number(candidate)
  }

  return null
}

export function useSessionStore() {
  const sessionCookie = useCookie<StoredSession | null>(SESSION_COOKIE_KEY, {
    default: () => null,
    sameSite: 'lax',
  })

  const normalizedCookieSession = normalizeStoredSession(sessionCookie.value)
  if (sessionCookie.value && !normalizedCookieSession) {
    sessionCookie.value = null
  }

  const session = useState<StoredSession | null>('session', () => normalizedCookieSession)
  if (session.value === null && normalizedCookieSession) {
    session.value = normalizedCookieSession
  }

  const isAuthenticated = computed(() => Boolean(session.value?.isAuthenticated) && !isSessionExpired(session.value))
  const user = computed(() => session.value?.user ?? null)

  function setSession(nextSession: StoredSession | null) {
    session.value = nextSession
    sessionCookie.value = nextSession
  }

  async function expireSession() {
    await redirectToLoginWithReason('expired')
  }

  async function enforceSessionActive() {
    if (!session.value || isSessionExpired(session.value)) {
      await expireSession()
      return null
    }
    return session.value
  }

  async function login(credentials: LoginCredentials): Promise<LoginResult | null> {
    const api = useApiClient()
    const result = await api.login(credentials)
    const userId = parseUserId(result.userInit?.user_id)

    if (!userId) {
      await redirectToLoginWithReason('missing_user_id')
      return null
    }

    const loginAt = new Date().toISOString()
    const jwtExpAt = parseJwtExpAt(result.accessToken)
    const expiresAt = computeExpiresAt(loginAt, jwtExpAt)

    setSession({
      isAuthenticated: true,
      accessToken: result.accessToken,
      tokenType: result.tokenType,
      userId,
      loginMethod: result.loginMethod,
      loginAt,
      expiresAt,
      jwtExpAt,
      user: result.user,
    })

    return result
  }

  async function logout() {
    const api = useApiClient()
    await api.logout(session.value)
    setSession(null)
    useWorkspaceStore().resetWorkspace()
  }

  return {
    session,
    user,
    isAuthenticated,
    login,
    logout,
    setSession,
    expireSession,
    enforceSessionActive,
  }
}
