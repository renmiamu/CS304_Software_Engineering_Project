<script setup lang="ts">
import {
  IconArrowRight,
  IconClockHour4,
  IconLink,
  IconSparkles,
} from '@tabler/icons-vue'
import { appNavigationItems } from '@/lib/navigation'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

definePageMeta({
  layout: 'app',
})

const workspace = useWorkspaceStore()
const DEADLINE_DISPLAY_LIMIT = 5
const quickLinks = computed(() => appNavigationItems.filter(item => item.path !== '/dashboard'))
const deadlineQuickStart = {
  title: 'Manage Deadlines',
  description: 'Add, complete, or remove due-date tasks on Schedule.',
  path: '/schedule#deadlines',
  icon: IconClockHour4,
}
const quickStartActions = computed(() => [deadlineQuickStart, ...quickLinks.value])
const upcomingDeadlines = computed(() => workspace.upcomingDeadlines.value.slice(0, DEADLINE_DISPLAY_LIMIT))
const sourceHealthyLabel = computed(() => `${workspace.dashboardSummary.value.connectedSources}/${workspace.sources.value.length}`)

function formatDate(value: string) {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}
</script>

<template>
  <div class="w-full flex flex-col gap-4">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div class="flex items-center gap-2">
        <Button as-child variant="outline">
          <NuxtLink to="/sources">
            <IconLink class="size-4" />
            Source Console
          </NuxtLink>
        </Button>
        <Button as-child>
          <NuxtLink to="/assistant">
            <IconSparkles class="size-4" />
            Open Assistant
          </NuxtLink>
        </Button>
      </div>
    </div>

    <main class="@container/main flex flex-1 flex-col gap-4 md:gap-6">
      <div class="grid grid-cols-1 gap-4 *:data-[slot=card]:bg-gradient-to-t *:data-[slot=card]:shadow-xs @xl/main:grid-cols-2 @5xl/main:grid-cols-3">
        <Card class="@container/card">
          <CardHeader>
            <CardDescription>Upcoming Deadlines</CardDescription>
            <CardTitle class="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
              {{ workspace.upcomingDeadlines.value.length }}
            </CardTitle>
            <CardAction>
              <Badge variant="outline">DDL</Badge>
            </CardAction>
          </CardHeader>
          <CardFooter class="flex-col items-start gap-1.5 text-sm">
            <div class="line-clamp-1 flex gap-2 font-medium">
              Upcoming submissions <IconClockHour4 class="size-4" />
            </div>
          </CardFooter>
        </Card>

        <Card class="@container/card">
          <CardHeader>
            <CardDescription>Source Health</CardDescription>
            <CardTitle class="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
              {{ sourceHealthyLabel }}
            </CardTitle>
            <CardAction>
              <Badge variant="outline">Sync</Badge>
            </CardAction>
          </CardHeader>
          <CardFooter class="flex-col items-start gap-1.5 text-sm">
            <div class="line-clamp-1 flex gap-2 font-medium">Connection status</div>
            <div class="text-muted-foreground">{{ workspace.dashboardSummary.value.nextSyncLabel }}</div>
          </CardFooter>
        </Card>

      </div>

      <div class="grid grid-cols-1 gap-4 @xl/main:grid-cols-2">
        <ScheduleWidget />
        <Card>
          <CardHeader>
            <CardTitle>Upcoming Deadlines</CardTitle>
          </CardHeader>
          <CardContent class="space-y-3">
            <div
              v-for="deadline in upcomingDeadlines"
              :key="deadline.id"
              class="rounded-lg border bg-muted/40 p-3"
            >
              <div class="flex items-center justify-between gap-2">
                <p class="text-sm font-medium">{{ deadline.title }}</p>
                <Badge variant="outline">{{ deadline.eventType }}</Badge>
              </div>
              <p class="mt-1 text-xs text-muted-foreground">{{ deadline.calendarName }}</p>
              <p class="mt-1 text-xs text-muted-foreground">{{ formatDate(deadline.endTime) }}</p>
            </div>

            <div v-if="upcomingDeadlines.length === 0" class="space-y-3">
              <EmptyState
                title="No upcoming deadlines"
                description="Add deadlines on Schedule or run source sync from Sources if your calendar is outdated."
              />
              <Button as-child variant="outline" size="sm">
                <NuxtLink to="/schedule#deadlines">Manage Deadlines</NuxtLink>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Quick Launch</CardTitle>
        </CardHeader>
        <CardContent class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <NuxtLink
            v-for="item in quickStartActions"
            :key="item.path"
            :to="item.path"
            class="group rounded-lg border bg-card p-4 transition hover:bg-accent"
          >
            <div class="flex items-center justify-between">
              <component :is="item.icon" v-if="item.icon" class="size-4 text-muted-foreground" />
              <IconArrowRight class="size-4 text-muted-foreground transition group-hover:translate-x-0.5" />
            </div>
            <p class="mt-3 text-sm font-medium">{{ item.title }}</p>
            <p v-if="'description' in item && item.description" class="mt-1 text-xs text-muted-foreground">
              {{ item.description }}
            </p>
          </NuxtLink>
        </CardContent>
      </Card>
    </main>
  </div>
</template>
