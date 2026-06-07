<script setup lang="ts">
import { IconFile, IconTimeline, IconAward } from '@tabler/icons-vue'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import type { BBFileItem, BBGradeItem } from '~/types/app'

definePageMeta({
  layout: 'app',
})

const workspace = useWorkspaceStore()
const DEADLINE_DISPLAY_LIMIT = 10

const recentDeadlines = computed(() => workspace.upcomingDeadlines.value.slice(0, DEADLINE_DISPLAY_LIMIT))

interface CourseGroup<T> {
  courseName: string
  items: T[]
}

const fileGroups = computed<CourseGroup<BBFileItem>[]>(() => {
  const map: Record<string, BBFileItem[]> = {}
  for (const f of workspace.fileItems.value) {
    const key = f.course || 'Uncategorized'
    ;(map[key] ??= []).push(f)
  }
  return Object.entries(map)
    .map(([courseName, items]) => ({ courseName, items }))
    .sort((a, b) => a.courseName.localeCompare(b.courseName))
})

const gradeGroups = computed<CourseGroup<BBGradeItem>[]>(() => {
  const map: Record<string, BBGradeItem[]> = {}
  for (const g of workspace.gradeItems.value) {
    const key = g.courseName || 'Uncategorized'
    ;(map[key] ??= []).push(g)
  }
  return Object.entries(map)
    .map(([courseName, items]) => ({ courseName, items }))
    .sort((a, b) => a.courseName.localeCompare(b.courseName))
})

const totalFiles = computed(() => workspace.fileItems.value.length)
const totalGrades = computed(() => workspace.gradeItems.value.length)

function formatDate(value?: string) {
  if (!value) return '-'
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

onMounted(() => {
  void workspace.loadCalendarItems()
})
</script>

<template>
  <div class="w-full flex flex-col gap-4">
    <main class="@container/main flex flex-col gap-4 md:gap-6">

      <Card>
        <CardHeader>
          <div class="flex items-center gap-2">
            <IconFile class="size-4 text-muted-foreground" />
            <CardTitle>Course Files</CardTitle>
            <span class="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
              {{ totalFiles }} files
            </span>
          </div>
        </CardHeader>
        <CardContent>
          <Accordion v-if="fileGroups.length > 0" type="multiple">
            <AccordionItem v-for="group in fileGroups" :key="group.courseName" :value="group.courseName">
              <AccordionTrigger>
                <div class="flex items-center gap-2">
                  <span>{{ group.courseName }}</span>
                  <span class="rounded-full bg-muted/60 px-1.5 py-0.5 text-xs text-muted-foreground">
                    {{ group.items.length }}
                  </span>
                </div>
              </AccordionTrigger>
              <AccordionContent>
                <div class="space-y-2">
                  <div
                    v-for="item in group.items"
                    :key="item.id"
                    class="flex items-center justify-between rounded-md border bg-muted/40 px-3 py-2"
                  >
                    <div class="min-w-0 flex-1">
                      <p class="truncate text-sm font-medium">{{ item.fileName }}</p>
                      <p class="text-xs text-muted-foreground">{{ item.content || 'No description' }}</p>
                    </div>
                    <a
                      :href="item.fileUrl"
                      target="_blank"
                      rel="noreferrer"
                      class="ml-3 shrink-0 text-xs text-primary underline"
                    >
                      Open
                    </a>
                  </div>
                </div>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
          <EmptyState
            v-else
            title="No file resources"
            description="Sync sources to load BB file records."
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div class="flex items-center gap-2">
            <IconAward class="size-4 text-muted-foreground" />
            <CardTitle>Grade Items</CardTitle>
            <span class="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
              {{ totalGrades }} items
            </span>
          </div>
        </CardHeader>
        <CardContent>
          <Accordion v-if="gradeGroups.length > 0" type="multiple">
            <AccordionItem v-for="group in gradeGroups" :key="group.courseName" :value="group.courseName">
              <AccordionTrigger>
                <div class="flex items-center gap-2">
                  <span>{{ group.courseName }}</span>
                  <span class="rounded-full bg-muted/60 px-1.5 py-0.5 text-xs text-muted-foreground">
                    {{ group.items.length }}
                  </span>
                </div>
              </AccordionTrigger>
              <AccordionContent>
                <div class="space-y-2">
                  <div
                    v-for="item in group.items"
                    :key="item.id"
                    class="flex items-center justify-between rounded-md border bg-muted/40 px-3 py-2"
                  >
                    <span class="text-sm font-medium">{{ item.itemName }}</span>
                    <span class="text-sm tabular-nums text-muted-foreground">{{ item.fullGrade }}</span>
                  </div>
                </div>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
          <EmptyState
            v-else
            title="No grade records"
            description="Sync sources to load latest grade rows."
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div class="flex items-center gap-2">
            <IconTimeline class="size-4 text-muted-foreground" />
            <CardTitle>Upcoming Deadlines</CardTitle>
            <span class="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
              {{ recentDeadlines.length }}
            </span>
          </div>
        </CardHeader>
        <CardContent>
          <div class="space-y-2">
            <div
              v-for="deadline in recentDeadlines"
              :key="deadline.id"
              class="flex items-center justify-between rounded-md border bg-muted/40 px-3 py-2"
            >
              <div>
                <p class="text-sm font-medium">{{ deadline.title }}</p>
                <p class="text-xs text-muted-foreground">{{ deadline.calendarName }}</p>
              </div>
              <span class="text-xs tabular-nums text-muted-foreground">{{ formatDate(deadline.endTime) }}</span>
            </div>
          </div>
          <EmptyState
            v-if="recentDeadlines.length === 0"
            title="No deadline records"
            description="No upcoming events are currently cached."
          />
        </CardContent>
      </Card>

    </main>
  </div>
</template>
