<script setup lang="ts">
import { IconLayoutDashboard, IconLogout2 } from '@tabler/icons-vue'
import { Moon, Sun } from 'lucide-vue-next'
import type { NavLink, NavParent } from '~/types/nav'
import { appNavigationMenu } from '@/lib/navigation'
import { Button } from '@/components/ui/button'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarRail,
  useSidebar,
} from '@/components/ui/sidebar'

const route = useRoute()
const session = useSessionStore()
const { sidebar } = useAppSettings()
const { setOpenMobile } = useSidebar()
const colorMode = useColorMode()

const userName = computed(() => session.user.value?.name ?? 'student')
const userEmail = computed(() => session.user.value?.email ?? 'student@mail.sustech.edu.cn')
const isDarkMode = computed(() => colorMode.value === 'dark')

function isParent(item: NavLink | NavParent): item is NavParent {
  return 'children' in item
}

function isActivePath(path: string) {
  return route.path === path || route.path.startsWith(`${path}/`)
}

function isActiveParent(item: NavParent) {
  return item.children.some(child => isActivePath(child.path))
}

function closeMobileSidebar() {
  setOpenMobile(false)
}

async function handleLogout() {
  await session.logout()
  await navigateTo('/login')
}

function toggleColorMode() {
  colorMode.preference = colorMode.value === 'dark' ? 'light' : 'dark'
}
</script>

<template>
  <Sidebar :collapsible="sidebar.collapsible" :side="sidebar.side" :variant="sidebar.variant">
    <SidebarHeader class="gap-3">
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton as-child size="lg" class="data-[slot=sidebar-menu-button]:!p-2">
            <NuxtLink to="/dashboard" @click="closeMobileSidebar">
              <span class="flex size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                <IconLayoutDashboard class="size-4" />
              </span>
              <span class="grid text-left">
                <span class="text-sm font-semibold">SUSTech Assistant</span>
              </span>
            </NuxtLink>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    </SidebarHeader>

    <SidebarContent>
      <SidebarGroup v-for="group in appNavigationMenu" :key="group.heading">
        <SidebarGroupLabel>{{ group.heading }}</SidebarGroupLabel>
        <SidebarMenu>
          <SidebarMenuItem v-for="item in group.items" :key="item.title">
            <template v-if="isParent(item)">
              <SidebarMenuButton :is-active="isActiveParent(item)">
                <component :is="item.icon" v-if="item.icon" />
                <span>{{ item.title }}</span>
              </SidebarMenuButton>
              <SidebarMenuSub>
                <SidebarMenuSubItem v-for="child in item.children" :key="child.path">
                  <SidebarMenuSubButton as-child :is-active="isActivePath(child.path)">
                    <NuxtLink :to="child.path" @click="closeMobileSidebar">
                      <component :is="child.icon" v-if="child.icon" />
                      <span>{{ child.title }}</span>
                    </NuxtLink>
                  </SidebarMenuSubButton>
                </SidebarMenuSubItem>
              </SidebarMenuSub>
            </template>

            <SidebarMenuButton v-else as-child :is-active="isActivePath(item.path)" :tooltip="item.title">
              <NuxtLink :to="item.path" @click="closeMobileSidebar">
                <component :is="item.icon" v-if="item.icon" />
                <span>{{ item.title }}</span>
              </NuxtLink>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarGroup>

      <SidebarGroup class="mt-auto">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton :tooltip="isDarkMode ? 'Switch to light' : 'Switch to dark'" @click="toggleColorMode">
              <Sun v-if="isDarkMode" />
              <Moon v-else />
              <span>Theme</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarGroup>
    </SidebarContent>

    <SidebarFooter class="gap-3">
      <div class="rounded-lg border border-sidebar-border bg-sidebar p-3">
        <p class="text-sm font-medium">{{ userName }}</p>
        <p class="text-xs text-muted-foreground">{{ userEmail }}</p>
      </div>
      <Button variant="outline" class="w-full justify-start" @click="handleLogout">
        <IconLogout2 class="size-4" />
        Sign out
      </Button>
    </SidebarFooter>

    <SidebarRail />
  </Sidebar>
</template>
