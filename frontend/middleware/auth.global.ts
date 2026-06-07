import { isSessionExpired } from '~/lib/auth-session'

export default defineNuxtRouteMiddleware(async (to) => {
  const session = useSessionStore()
  const isActive = Boolean(session.session.value?.isAuthenticated) && !isSessionExpired(session.session.value)

  if (to.path === '/') {
    return navigateTo(isActive ? '/dashboard' : '/login')
  }

  if (to.path !== '/login' && !session.session.value?.isAuthenticated) {
    return navigateTo('/login')
  }

  if (to.path !== '/login' && session.session.value?.isAuthenticated && isSessionExpired(session.session.value)) {
    await session.expireSession()
    return
  }

  if (isActive && to.path === '/login') {
    return navigateTo('/dashboard')
  }
})
