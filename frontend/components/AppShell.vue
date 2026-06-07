<script setup lang="ts">
import AppSidebar from '@/components/AppSidebar.vue'
import SiteHeader from '@/components/SiteHeader.vue'
import {
  SidebarInset,
  SidebarProvider,
} from '@/components/ui/sidebar'

const { sidebar } = useAppSettings()
const workspace = useWorkspaceStore()
const route = useRoute()

function maybeRefreshHeavyForRoute(path: string) {
  if (path !== '/profile' && path !== '/sources') {
    return
  }
  void workspace.maybeRefreshHeavySnapshot(`Route enter ${path}`)
}

onMounted(() => {
  void workspace.hydrateFromSession()
  maybeRefreshHeavyForRoute(route.path)
})

watch(() => route.path, (nextPath) => {
  maybeRefreshHeavyForRoute(nextPath)
})
</script>

<template>
  <div :style="{ '--header-height': '3.375rem' }" class="min-h-screen">
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset class="min-h-screen">
        <SiteHeader />
        <div class="flex flex-1 flex-col">
          <main
            class="@container/main flex flex-1 flex-col p-4 lg:p-6"
            :class="{
              'md:peer-data-[variant=inset]:rounded-tl-xl md:peer-data-[variant=inset]:rounded-tr-xl': sidebar.variant === 'inset',
            }"
          >
            <slot />
          </main>
        </div>
      </SidebarInset>
    </SidebarProvider>
  </div>
</template>
