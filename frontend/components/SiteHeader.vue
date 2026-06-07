<script setup lang="ts">
import { IconClockHour4, IconShieldCheck } from '@tabler/icons-vue'
import { getPageMeta } from '@/lib/navigation'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { SidebarTrigger } from '@/components/ui/sidebar'
import type { MailAccount } from '~/types/app'

const route = useRoute()
const workspace = useWorkspaceStore()
const sessionStore = useSessionStore()
const api = useApiClient()

const pageMeta = computed(() => getPageMeta(route.path))
const isMailRoute = computed(() => route.path === '/mail' || route.path.startsWith('/mail/'))
const mailAccount = ref<MailAccount | null>(null)
const mailAccountLabel = computed(() => {
  if (!isMailRoute.value || !mailAccount.value?.loggedIn || !mailAccount.value.mailbox) {
    return ''
  }

  return `Connected mailbox: ${mailAccount.value.mailbox}`
})

async function loadMailAccountForHeader() {
  if (!isMailRoute.value) {
    mailAccount.value = null
    return
  }

  const session = await sessionStore.enforceSessionActive()
  if (!session) {
    mailAccount.value = null
    return
  }

  try {
    mailAccount.value = await api.getMailAccount(session)
  }
  catch {
    mailAccount.value = null
  }
}

watch(isMailRoute, () => {
  void loadMailAccountForHeader()
}, { immediate: true })
</script>

<template>
  <header class="sticky top-0 z-10 h-(--header-height) flex items-center gap-4 border-b bg-background px-4 md:px-6 md:peer-data-[variant=inset]:top-2 md:peer-data-[variant=inset]:rounded-tl-xl md:peer-data-[variant=inset]:rounded-tr-xl">
    <div class="w-full flex items-center gap-3">
      <SidebarTrigger />
      <Separator orientation="vertical" class="h-5" />

      <div class="min-w-0">
      <h2 class="text-2xl font-bold tracking-tight">{{ pageMeta?.title ?? 'SUSTech Assistant' }}</h2>
      </div>

      <div class="ml-auto flex items-center gap-2">
        <Badge v-if="mailAccountLabel" variant="outline" class="hidden max-w-[32rem] truncate md:inline-flex">
          {{ mailAccountLabel }}
        </Badge>
        <Badge variant="outline" class="hidden gap-1.5 md:inline-flex">
          <IconClockHour4 class="size-3.5" />
          {{ workspace.dashboardSummary.value.nextSyncLabel }}
        </Badge>
        <Badge variant="outline" class="gap-1.5">
          <IconShieldCheck class="size-3.5" />
          Live Auth
        </Badge>
      </div>
    </div>
  </header>
</template>
