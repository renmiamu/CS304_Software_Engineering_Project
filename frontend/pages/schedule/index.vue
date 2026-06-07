<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { usePreferredReducedMotion } from '@vueuse/core'
import {
  IconCheck,
  IconChevronLeft,
  IconChevronRight,
  IconClockHour4,
  IconEdit,
  IconMessageCircle,
  IconPlus,
  IconTimelineEventText,
  IconTrash,
} from '@tabler/icons-vue'
import type { ScheduleDeadline } from '~/types/app'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import type { ScheduleRenderableItem } from '~/composables/useScheduleCalendar'
import {
  SLOT_DEFINITIONS,
  addDays,
  addMonths,
  cloneDate,
  formatDateKey,
  formatMonthLabel,
  formatWeekRangeLabel,
  getMonthGridRange,
  getMonthStart,
  getWeekStart,
  getWeekdayLabel,
  parseQueryDate,
  parseViewMode,
  startOfDay,
  toCustomScheduleRenderableItems,
  toScheduleRenderableItems,
} from '~/composables/useScheduleCalendar'

definePageMeta({
  layout: 'app',
})

type ViewMode = 'week' | 'month'

interface WeekLayoutItem extends ScheduleRenderableItem {
  lane: number
  laneCount: number
  stackIndex: number
  stackTotal: number
}

const SLOT_HEIGHT = 64

const workspace = useWorkspaceStore()
const route = useRoute()
const router = useRouter()
const reducedMotion = usePreferredReducedMotion()

const viewMode = ref<ViewMode>('week')
const anchorDate = ref(startOfDay(new Date()))
const eventPending = ref(false)
const eventError = ref('')
const editingEventId = ref<number | null>(null)
const eventForm = reactive({
  name: '',
  weekday: 1,
  start_time: '16:00',
  end_time: '18:00',
  location: '',
  schedule_type: 'sports',
  description: '',
})

function defaultDeadlineDueAt() {
  const due = new Date()
  due.setHours(due.getHours() + 2, 0, 0, 0)
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${due.getFullYear()}-${pad(due.getMonth() + 1)}-${pad(due.getDate())}T${pad(due.getHours())}:${pad(due.getMinutes())}`
}

const deadlinePending = ref(false)
const deadlineActionId = ref<string | null>(null)
const deadlineError = ref('')
const deadlineForm = reactive({
  title: '',
  dueAt: defaultDeadlineDueAt(),
})

const sortedDeadlines = computed(() => {
  const todayStart = startOfDay(new Date()).getTime()

  return [...workspace.deadlineItems.value]
    .filter((item) => {
      const endTime = Date.parse(item.endTime)
      return !Number.isNaN(endTime) && endTime >= todayStart
    })
    .sort((left, right) => {
      if (left.completed !== right.completed) {
        return left.completed ? 1 : -1
      }

      const leftTime = Date.parse(left.endTime)
      const rightTime = Date.parse(right.endTime)
      const safeLeft = Number.isNaN(leftTime) ? Number.MAX_SAFE_INTEGER : leftTime
      const safeRight = Number.isNaN(rightTime) ? Number.MAX_SAFE_INTEGER : rightTime
      return safeLeft - safeRight
    })
})

function toBackendDeadlineEnd(value: string) {
  const trimmed = value.trim()
  if (!trimmed) {
    return ''
  }
  return trimmed.length === 16 ? `${trimmed}:00` : trimmed
}

function formatDeadlineDate(value: string) {
  const parsed = Date.parse(value)
  if (Number.isNaN(parsed)) {
    return value || '-'
  }

  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(parsed))
}

const EVENT_TYPE_OPTIONS = [
  { value: 'sports', label: 'Sports', color: '#81c784' },
  { value: 'meeting', label: 'Meeting', color: '#64b5f6' },
  { value: 'study', label: 'Study', color: '#ba68c8' },
  { value: 'entertainment', label: 'Entertainment', color: '#ffb74d' },
  { value: 'custom', label: 'Custom', color: '#b0bec5' },
  { value: 'other', label: 'Other', color: '#b0bec5' },
]

const WEEKDAY_OPTIONS = [
  { value: 1, label: 'Monday' },
  { value: 2, label: 'Tuesday' },
  { value: 3, label: 'Wednesday' },
  { value: 4, label: 'Thursday' },
  { value: 5, label: 'Friday' },
  { value: 6, label: 'Saturday' },
  { value: 7, label: 'Sunday' },
]

const HOUR_OPTIONS = Array.from({ length: 16 }, (_, i) => {
  const h = i + 8
  return { value: h, label: String(h).padStart(2, '0') }
})
const MINUTE_OPTIONS = Array.from({ length: 12 }, (_, i) => {
  const m = i * 5
  return { value: m, label: String(m).padStart(2, '0') }
})

function splitTime(value: string) {
  const [h, m] = value.split(':').map(Number)
  return { hour: Number.isFinite(h) ? h : 16, minute: Number.isFinite(m) ? m : 0 }
}
function joinTime(hour: number, minute: number) {
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`
}

function syncStateFromRoute() {
  const nextView = parseViewMode(route.query.view)
  const nextDate = parseQueryDate(route.query.date) ?? startOfDay(new Date())

  if (viewMode.value !== nextView) {
    viewMode.value = nextView
  }

  if (formatDateKey(anchorDate.value) !== formatDateKey(nextDate)) {
    anchorDate.value = nextDate
  }
}

function syncRouteFromState() {
  const nextView = viewMode.value
  const nextDate = formatDateKey(anchorDate.value)
  const currentView = parseViewMode(route.query.view)
  const currentDate = parseQueryDate(route.query.date)
  const currentDateKey = currentDate ? formatDateKey(currentDate) : ''

  if (currentView === nextView && currentDateKey === nextDate) {
    return
  }

  void router.replace({
    query: {
      ...route.query,
      view: nextView,
      date: nextDate,
    },
  })
}

syncStateFromRoute()

watch(() => route.query, () => {
  syncStateFromRoute()
})

watch([viewMode, anchorDate], () => {
  syncRouteFromState()
}, { immediate: true })

const todayKey = computed(() => formatDateKey(new Date()))

const weekStart = computed(() => getWeekStart(anchorDate.value))

const weekDates = computed(() => {
  return Array.from({ length: 7 }, (_, index) => addDays(weekStart.value, index))
})

const monthGrid = computed(() => getMonthGridRange(anchorDate.value))

const monthDates = computed(() => {
  const dates: Date[] = []
  let cursor = cloneDate(monthGrid.value.start)
  while (cursor.getTime() <= monthGrid.value.end.getTime()) {
    dates.push(cursor)
    cursor = addDays(cursor, 1)
  }
  return dates
})

const activeRange = computed(() => {
  if (viewMode.value === 'week') {
    return {
      start: weekStart.value,
      end: addDays(weekStart.value, 6),
    }
  }

  return {
    start: monthGrid.value.start,
    end: monthGrid.value.end,
  }
})

const calendarItems = computed(() => {
  const courses = toScheduleRenderableItems(
    workspace.tisScheduleCourses.value,
    activeRange.value.start,
    activeRange.value.end,
  )
  const customs = toCustomScheduleRenderableItems(
    workspace.customScheduleEvents.value,
    activeRange.value.start,
    activeRange.value.end,
  )
  return [...courses, ...customs]
})

const weekItemsByDate = computed(() => {
  const grouped = new Map<string, ScheduleRenderableItem[]>()
  for (const item of calendarItems.value) {
    const list = grouped.get(item.date) ?? []
    list.push(item)
    grouped.set(item.date, list)
  }

  const normalized = new Map<string, WeekLayoutItem[]>()
  for (const [date, items] of grouped.entries()) {
    normalized.set(date, layoutDayItems(items))
  }

  return normalized
})

const monthItemsByDate = computed(() => {
  const grouped = new Map<string, ScheduleRenderableItem[]>()
  for (const item of calendarItems.value) {
    const list = grouped.get(item.date) ?? []
    list.push(item)
    grouped.set(item.date, list)
  }

  for (const [date, items] of grouped.entries()) {
    grouped.set(date, [...items].sort((left, right) => {
      if (left.startSlot === right.startSlot) {
        return left.endSlot - right.endSlot
      }
      return left.startSlot - right.startSlot
    }))
  }

  return grouped
})

const displayLabel = computed(() => {
  if (viewMode.value === 'week') {
    return formatWeekRangeLabel(anchorDate.value)
  }
  return formatMonthLabel(anchorDate.value)
})

const viewTransitionKey = computed(() => {
  if (viewMode.value === 'week') {
    return `week-${formatDateKey(weekStart.value)}`
  }
  return `month-${formatDateKey(getMonthStart(anchorDate.value))}`
})

const hasWeekItems = computed(() => {
  return weekDates.value.some(date => {
    const key = formatDateKey(date)
    return (weekItemsByDate.value.get(key)?.length ?? 0) > 0
  })
})

const hasMonthItems = computed(() => {
  return monthDates.value.some(date => {
    const key = formatDateKey(date)
    return (monthItemsByDate.value.get(key)?.length ?? 0) > 0
  })
})

const selectedItem = ref<ScheduleRenderableItem | null>(null)
const targetEl = ref<HTMLElement | null>(null)
const popoverPos = ref({ x: 0, y: 0 })
const popoverMode = ref<'view' | 'edit'>('view')

type PopoverEditForm = {
  name: string
  weekday: number
  start_time: string
  end_time: string
  location: string
  schedule_type: string
}
const popoverEditForm = reactive<PopoverEditForm>({
  name: '',
  weekday: 1,
  start_time: '16:00',
  end_time: '18:00',
  location: '',
  schedule_type: 'sports',
})

function recalcPopoverPos() {
  if (!targetEl.value) return
  const rect = targetEl.value.getBoundingClientRect()
  popoverPos.value = {
    x: Math.min(rect.left, window.innerWidth - 280),
    y: Math.min(rect.bottom + 4, window.innerHeight - 320),
  }
}

function handleItemClick(item: ScheduleRenderableItem, event: MouseEvent) {
  if (item.type === 'course') return
  event.preventDefault()
  event.stopPropagation()
  if (selectedItem.value?.id === item.id) {
    closePopover()
    return
  }
  selectedItem.value = item
  popoverMode.value = 'view'
  targetEl.value = event.currentTarget as HTMLElement
  recalcPopoverPos()
  window.addEventListener('scroll', recalcPopoverPos, true)
}

function closePopover() {
  selectedItem.value = null
  targetEl.value = null
  window.removeEventListener('scroll', recalcPopoverPos, true)
}

function onOverlayMousedown() {
  closePopover()
}

function openPopoverEdit() {
  const id = selectedItem.value?.id
  if (!id?.startsWith('custom-')) return
  const eventId = Number(id.split('-')[1])
  if (!eventId || Number.isNaN(eventId)) return
  const event = workspace.customScheduleEvents.value.find(e => e.schedule_id === eventId)
  if (!event) return
  popoverEditForm.name = event.name
  popoverEditForm.weekday = event.weekday ?? 1
  popoverEditForm.start_time = event.start_time || '16:00'
  popoverEditForm.end_time = event.end_time || '18:00'
  popoverEditForm.location = event.location
  popoverEditForm.schedule_type = event.schedule_type || 'other'
  popoverMode.value = 'edit'
  recalcPopoverPos()
}

async function submitPopoverEdit() {
  if (!popoverEditForm.name.trim() || eventPending.value) return
  const id = selectedItem.value?.id
  if (!id?.startsWith('custom-')) return
  const eventId = Number(id.split('-')[1])
  if (!eventId || Number.isNaN(eventId)) return
  eventPending.value = true
  try {
    await workspace.updateCustomScheduleEvent(eventId, {
      name: popoverEditForm.name.trim(),
      weekday: popoverEditForm.weekday,
      start_time: popoverEditForm.start_time,
      end_time: popoverEditForm.end_time,
      location: popoverEditForm.location.trim() || undefined,
      schedule_type: popoverEditForm.schedule_type,
    })
    closePopover()
  } catch (error) {
    // error handled by store
  } finally {
    eventPending.value = false
  }
}

async function popoverDelete() {
  const id = selectedItem.value?.id
  if (!id?.startsWith('custom-')) return
  const eventId = Number(id.split('-')[1])
  if (eventId && !Number.isNaN(eventId)) {
    await deleteEvent(eventId)
    closePopover()
  }
}

const popoverStyle = computed(() => ({
  left: `${popoverPos.value.x}px`,
  top: `${popoverPos.value.y}px`,
}))

const customEvents = computed(() => workspace.customScheduleEvents.value)

function setViewMode(mode: ViewMode) {
  viewMode.value = mode
}

function goToToday() {
  anchorDate.value = startOfDay(new Date())
}

function goToPrevious() {
  anchorDate.value = viewMode.value === 'week'
    ? addDays(anchorDate.value, -7)
    : addMonths(anchorDate.value, -1)
}

function goToNext() {
  anchorDate.value = viewMode.value === 'week'
    ? addDays(anchorDate.value, 7)
    : addMonths(anchorDate.value, 1)
}

function weekdayLabel(value: number) {
  const option = WEEKDAY_OPTIONS.find(o => o.value === value)
  return option ? option.label : String(value)
}

function eventTypeColor(type: string) {
  const option = EVENT_TYPE_OPTIONS.find(o => o.value === type)
  return option ? option.color : '#b0bec5'
}

function eventTypeLabel(type: string) {
  const option = EVENT_TYPE_OPTIONS.find(o => o.value === type)
  return option ? option.label : type
}

function formatEventTime(startTime: string, endTime: string) {
  return `${startTime || '--:--'} - ${endTime || '--:--'}`
}

function resetEventForm() {
  eventForm.name = ''
  eventForm.weekday = 1
  eventForm.start_time = '16:00'
  eventForm.end_time = '18:00'
  eventForm.location = ''
  eventForm.schedule_type = 'sports'
  eventForm.description = ''
  editingEventId.value = null
}

function formatWeekHeaderDate(date: Date) {
  return new Intl.DateTimeFormat('en-US', {
    month: 'numeric',
    day: 'numeric',
  }).format(date)
}

function formatMonthDay(date: Date) {
  return new Intl.DateTimeFormat('en-US', { day: 'numeric' }).format(date)
}

function isToday(date: Date) {
  return formatDateKey(date) === todayKey.value
}

function isCurrentMonth(date: Date) {
  const anchor = anchorDate.value
  return date.getFullYear() === anchor.getFullYear() && date.getMonth() === anchor.getMonth()
}

function getWeekItems(date: Date) {
  return weekItemsByDate.value.get(formatDateKey(date)) ?? []
}

function getMonthItems(date: Date) {
  return monthItemsByDate.value.get(formatDateKey(date)) ?? []
}

const pxPerMinute = 32 / 50

function parseTimeStrToMinutes(timeStr: string) {
  if (!timeStr) return 0
  const parts = timeStr.split(':')
  if (parts.length !== 2) return 0
  return Number.parseInt(parts[0], 10) * 60 + Number.parseInt(parts[1], 10)
}

function weekItemStyle(item: WeekLayoutItem) {
  const startMins = parseTimeStrToMinutes(item.startTime)
  const endMins = parseTimeStrToMinutes(item.endTime)
  const durationMins = Math.max(10, endMins - startMins) // at least 10 mins

  const top = (startMins - 480) * pxPerMinute
  const height = durationMins * pxPerMinute

  const offsetX = item.stackTotal > 1 ? item.stackIndex * 6 : 0
  const shadow = item.stackTotal > 1
    ? `0 ${2 + item.stackIndex * 2}px ${4 + item.stackIndex * 3}px rgba(0,0,0,${0.08 + item.stackIndex * 0.04})`
    : '0 2px 4px rgba(0,0,0,0.05)'

  return {
    top: `${top}px`,
    height: `${height}px`,
    width: `calc(100% - ${8 + offsetX}px)`,
    left: `${4 + offsetX}px`,
    zIndex: item.zIndex ?? 0,
    boxShadow: shadow,
  }
}

function scheduleToneClass(type: string) {
  if (type === 'course') return 'schedule-tone-course'
  if (type === 'sports') return 'schedule-tone-sports'
  if (type === 'meeting') return 'schedule-tone-meeting'
  if (type === 'study') return 'schedule-tone-study'
  if (type === 'entertainment') return 'schedule-tone-entertainment'
  return 'schedule-tone-custom'
}

function scheduleTypeLabel(type: string) {
  if (type === 'course') return 'Course'
  return eventTypeLabel(type)
}

function layoutDayItems(items: ScheduleRenderableItem[]) {
  const sorted = [...items].sort((a, b) => a.zIndex - b.zIndex)
  const n = sorted.length

  // Build overlap graph: items[i] overlaps with items[j] if time ranges intersect.
  const overlaps: boolean[][] = Array.from({ length: n }, () => Array(n).fill(false))
  for (let i = 0; i < n; i++) {
    const si = parseTimeStrToMinutes(sorted[i].startTime)
    const ei = parseTimeStrToMinutes(sorted[i].endTime)
    for (let j = i + 1; j < n; j++) {
      const sj = parseTimeStrToMinutes(sorted[j].startTime)
      const ej = parseTimeStrToMinutes(sorted[j].endTime)
      if (si < ej && sj < ei) {
        overlaps[i][j] = overlaps[j][i] = true
      }
    }
  }

  // Assign stack indices within each connected overlap component.
  const visited = new Array(n).fill(false)
  const stackIndex = new Array(n).fill(0)
  const stackTotal = new Array(n).fill(1)

  for (let i = 0; i < n; i++) {
    if (visited[i]) continue
    // Find connected component via BFS
    const component: number[] = []
    const queue = [i]
    visited[i] = true
    while (queue.length) {
      const u = queue.shift()!
      component.push(u)
      for (let v = 0; v < n; v++) {
        if (overlaps[u][v] && !visited[v]) {
          visited[v] = true
          queue.push(v)
        }
      }
    }
    // Assign stackIndex by zIndex order within component
    const compSorted = [...component].sort((a, b) => sorted[a].zIndex - sorted[b].zIndex)
    compSorted.forEach((idx, pos) => {
      stackIndex[idx] = pos
      stackTotal[idx] = compSorted.length
    })
  }

  return sorted.map((item, idx) => ({
    ...item,
    lane: 0,
    laneCount: 1,
    stackIndex: stackIndex[idx],
    stackTotal: stackTotal[idx],
  }))
}

function beginEditEvent(eventId: number) {
  const target = workspace.customScheduleEvents.value.find(e => e.schedule_id === eventId)
  if (!target) return
  editingEventId.value = target.schedule_id
  eventForm.name = target.name
  eventForm.weekday = target.weekday ?? 1
  eventForm.start_time = target.start_time || '16:00'
  eventForm.end_time = target.end_time || '18:00'
  eventForm.location = target.location
  eventForm.schedule_type = target.schedule_type || 'other'
  eventForm.description = target.description
}

async function submitEvent() {
  if (!eventForm.name.trim() || eventPending.value) return

  eventPending.value = true
  eventError.value = ''
  try {
    if (editingEventId.value) {
      await workspace.updateCustomScheduleEvent(editingEventId.value, {
        name: eventForm.name.trim(),
        weekday: eventForm.weekday,
        start_time: eventForm.start_time,
        end_time: eventForm.end_time,
        location: eventForm.location.trim() || undefined,
        schedule_type: eventForm.schedule_type,
        description: eventForm.description.trim() || undefined,
      })
    } else {
      await workspace.createCustomScheduleEvent({
        name: eventForm.name.trim(),
        weekday: eventForm.weekday,
        start_time: eventForm.start_time,
        end_time: eventForm.end_time,
        location: eventForm.location.trim() || undefined,
        schedule_type: eventForm.schedule_type,
        description: eventForm.description.trim() || undefined,
      })
    }
    resetEventForm()
  } catch (error) {
    eventError.value = error instanceof Error ? error.message : 'Unable to save event.'
  } finally {
    eventPending.value = false
  }
}

async function deleteEvent(eventId: number) {
  if (eventPending.value) return
  eventPending.value = true
  eventError.value = ''
  try {
    await workspace.deleteCustomScheduleEvent(eventId)
    if (editingEventId.value === eventId) resetEventForm()
  } catch (error) {
    eventError.value = error instanceof Error ? error.message : 'Unable to delete event.'
  } finally {
    eventPending.value = false
  }
}

async function submitDeadline() {
  if (deadlinePending.value || !deadlineForm.title.trim() || !deadlineForm.dueAt.trim()) {
    return
  }

  deadlinePending.value = true
  deadlineError.value = ''
  try {
    const created = await workspace.createCalendarItem({
      title: deadlineForm.title.trim(),
      end: toBackendDeadlineEnd(deadlineForm.dueAt),
    })
    if (!created) {
      deadlineError.value = 'Unable to add deadline.'
      return
    }

    deadlineForm.title = ''
    deadlineForm.dueAt = defaultDeadlineDueAt()
  }
  catch (error) {
    deadlineError.value = error instanceof Error ? error.message : 'Unable to add deadline.'
  }
  finally {
    deadlinePending.value = false
  }
}

async function toggleDeadlineCompleted(deadline: ScheduleDeadline) {
  if (deadlineActionId.value) {
    return
  }

  deadlineActionId.value = deadline.id
  deadlineError.value = ''
  try {
    const updated = await workspace.toggleCalendarItemCompleted(deadline)
    if (!updated) {
      deadlineError.value = 'Unable to update deadline.'
    }
  }
  catch (error) {
    deadlineError.value = error instanceof Error ? error.message : 'Unable to update deadline.'
  }
  finally {
    deadlineActionId.value = null
  }
}

async function removeDeadline(deadlineId: string) {
  if (deadlineActionId.value) {
    return
  }

  deadlineActionId.value = deadlineId
  deadlineError.value = ''
  try {
    const deleted = await workspace.deleteCalendarItem(deadlineId)
    if (!deleted) {
      deadlineError.value = 'Unable to delete deadline.'
    }
  }
  catch (error) {
    deadlineError.value = error instanceof Error ? error.message : 'Unable to delete deadline.'
  }
  finally {
    deadlineActionId.value = null
  }
}

async function scrollToDeadlinesPanel() {
  await nextTick()
  document.getElementById('deadlines')?.scrollIntoView({
    behavior: reducedMotion.value === 'reduce' ? 'auto' : 'smooth',
    block: 'start',
  })
}

onMounted(async () => {
  void workspace.loadCalendarItems()
  void workspace.loadCustomScheduleEvents()
  if (route.hash === '#deadlines') {
    await scrollToDeadlinesPanel()
  }
})

watch(
  () => route.hash,
  (hash) => {
    if (hash === '#deadlines') {
      void scrollToDeadlinesPanel()
    }
  },
)
</script>

<template>
  <div class="w-full flex flex-col gap-4" :class="{ 'reduce-motion': reducedMotion === 'reduce' }">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <Button as-child variant="outline">
        <NuxtLink to="/assistant">
          <IconMessageCircle class="size-4" />
          Ask Assistant
        </NuxtLink>
      </Button>
    </div>

    <main class="@container/main grid gap-4 md:gap-6 @4xl/main:grid-cols-[1.1fr_0.9fr]">
      <div class="space-y-4">
        <Card class="border-border/70 shadow-sm">
          <CardHeader class="pb-3">
            <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <CardTitle>Schedule Table</CardTitle>
                <CardDescription>{{ displayLabel }}</CardDescription>
              </div>

              <div class="flex flex-wrap items-center gap-2">
                <div class="inline-flex rounded-lg border bg-muted/40 p-1">
                  <Button size="sm" :variant="viewMode === 'week' ? 'default' : 'ghost'" @click="setViewMode('week')">
                    Week
                  </Button>
                  <Button size="sm" :variant="viewMode === 'month' ? 'default' : 'ghost'" @click="setViewMode('month')">
                    Month
                  </Button>
                </div>

                <div class="inline-flex items-center gap-1">
                  <Button size="icon" variant="outline" @click="goToPrevious">
                    <IconChevronLeft class="size-4" />
                  </Button>
                  <Button size="sm" variant="outline" @click="goToToday">Today</Button>
                  <Button size="icon" variant="outline" @click="goToNext">
                    <IconChevronRight class="size-4" />
                  </Button>
                </div>
              </div>
            </div>
          </CardHeader>

          <CardContent class="pt-0">
            <Transition name="calendar-fade" mode="out-in">
              <div :key="viewTransitionKey" class="min-h-[560px]">
                <div v-if="viewMode === 'week'" class="space-y-3">
                  <EmptyState
                    v-if="!hasWeekItems"
                    title="No schedule items in this week"
                    description="No class blocks are mapped to the selected week window."
                  />

                  <div class="overflow-x-auto pb-2">
                    <div class="min-w-[900px]">
                      <div class="grid grid-cols-[88px_repeat(7,minmax(0,1fr))] gap-0 overflow-hidden rounded-xl border border-border/60 bg-background">
                        <div class="h-12 border-b border-border/60 bg-muted/25" />
                        <div
                          v-for="date in weekDates"
                          :key="`week-header-${formatDateKey(date)}`"
                          class="h-12 border-b border-l border-border/60 px-2 py-1"
                          :class="isToday(date) ? 'bg-primary/8' : 'bg-muted/20'
                          "
                        >
                          <p class="text-xs font-semibold">{{ getWeekdayLabel((date.getDay() + 6) % 7) }}</p>
                          <p class="text-[11px] text-muted-foreground">{{ formatWeekHeaderDate(date) }}</p>
                        </div>

                        <div class="border-b border-border/60 bg-muted/10">
                          <div
                            v-for="hour in 15"
                            :key="`time-${hour}`"
                            class="flex items-start justify-end border-t border-border/50 px-2 pt-1.5 first:border-t-0"
                            :style="{ height: `${60 * (32 / 50)}px` }"
                          >
                            <div class="text-right text-[11px] text-muted-foreground leading-tight">
                              <p class="font-medium text-foreground">{{ hour + 7 }}:00</p>
                            </div>
                          </div>
                        </div>

                        <div
                          v-for="date in weekDates"
                          :key="`week-column-${formatDateKey(date)}`"
                          class="border-b border-l border-border/60"
                          :class="isToday(date) ? 'bg-primary/5' : 'bg-card'"
                        >
                          <div class="relative" :style="{ height: `${15 * 60 * (32 / 50)}px` }">
                            <div
                              v-for="hour in 15"
                              :key="`slot-bg-${formatDateKey(date)}-${hour}`"
                              class="border-t border-border/45 first:border-t-0"
                              :style="{ height: `${60 * (32 / 50)}px` }"
                            />

                            <div
                              v-for="item in getWeekItems(date)"
                              :key="item.id"
                              class="schedule-item absolute rounded-2xl p-2.5 transition-all duration-150"
                              :class="[
                                scheduleToneClass(item.type),
                                item.type !== 'course' ? 'cursor-pointer hover:scale-[1.02] hover:brightness-105' : '',
                                selectedItem?.id === item.id ? 'ring-2 ring-primary/60 brightness-105 scale-[1.02]' : '',
                              ]"
                              :style="weekItemStyle(item)"
                              @mousedown.stop="handleItemClick(item, $event)"
                            >
                              <div class="flex items-start justify-between gap-1">
                                <p class="line-clamp-1 text-xs font-semibold leading-tight">{{ item.title }}</p>
                                <span v-if="item.type !== 'course'" class="schedule-kind-pill">
                                  {{ scheduleTypeLabel(item.type) }}
                                </span>
                              </div>
                              <p class="mt-1 line-clamp-1 text-[10px] text-muted-foreground">{{ item.startTime }}-{{ item.endTime }}</p>
                              <p v-if="item.location" class="mt-0.5 line-clamp-1 text-[10px] text-muted-foreground">{{ item.location }}</p>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <div v-else class="space-y-3">
                  <EmptyState
                    v-if="!hasMonthItems"
                    title="No schedule items in this month"
                    description="No class blocks are mapped to the selected month window."
                  />

                  <div class="overflow-x-auto pb-2">
                    <div class="min-w-[900px] overflow-hidden rounded-xl border border-border/60 bg-background">
                      <div class="grid grid-cols-7 border-b border-border/60 bg-muted/20">
                        <div
                          v-for="(label, index) in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']"
                          :key="`month-weekday-${label}-${index}`"
                          class="px-3 py-2 text-xs font-semibold"
                        >
                          {{ label }}
                        </div>
                      </div>

                      <div class="grid grid-cols-7">
                        <div
                          v-for="date in monthDates"
                          :key="`month-date-${formatDateKey(date)}`"
                          class="min-h-[140px] border-b border-r border-border/55 p-2 last:border-r-0"
                          :class="[
                            !isCurrentMonth(date) ? 'bg-muted/10 text-muted-foreground' : 'bg-card',
                            isToday(date) ? 'ring-1 ring-primary/40 ring-inset' : '',
                          ]"
                        >
                          <div class="flex items-center justify-between">
                            <p class="text-xs font-semibold">{{ formatMonthDay(date) }}</p>
                            <Badge v-if="isToday(date)" variant="outline" class="text-[10px]">Today</Badge>
                          </div>

                          <div class="mt-2 space-y-1">
                            <div
                              v-for="item in getMonthItems(date).slice(0, 2)"
                              :key="`month-item-${item.id}`"
                              class="schedule-pill rounded-md border px-2 py-1 transition-all duration-150"
                              :class="[
                                scheduleToneClass(item.type),
                                item.type !== 'course' ? 'cursor-pointer hover:brightness-105 hover:shadow-sm' : '',
                                selectedItem?.id === item.id ? 'ring-2 ring-primary/60 brightness-105' : '',
                              ]"
                              @mousedown.stop="handleItemClick(item, $event)"
                            >
                              <p class="line-clamp-1 text-[11px] font-semibold">{{ item.title }}</p>
                              <p class="line-clamp-1 text-[10px] text-muted-foreground">{{ item.startTime }}-{{ item.endTime }}</p>
                            </div>

                            <p
                              v-if="getMonthItems(date).length > 2"
                              class="text-[11px] font-medium text-muted-foreground"
                            >
                              +{{ getMonthItems(date).length - 2 }} more
                            </p>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </Transition>
          </CardContent>
        </Card>
      </div>

      <div class="space-y-4">
        <Card>
          <CardHeader>
            <div class="flex items-center gap-2">
              <IconTimelineEventText class="size-4 text-muted-foreground" />
              <CardTitle>Custom Events</CardTitle>
            </div>
          </CardHeader>
          <CardContent class="space-y-3">
            <form class="rounded-xl border bg-background p-3" @submit.prevent="submitEvent">
              <div class="grid gap-2.5">
                <label class="grid gap-1">
                  <span class="text-xs font-medium text-muted-foreground">Name</span>
                  <input
                    v-model="eventForm.name"
                    type="text"
                    class="input-soft h-9 px-3 text-sm"
                    placeholder="Event name"
                    required
                  >
                </label>
                <div class="grid grid-cols-2 gap-2">
                  <label class="grid gap-1">
                    <span class="text-xs font-medium text-muted-foreground">Weekday</span>
                    <select v-model.number="eventForm.weekday" class="input-soft h-9 px-2 text-sm">
                      <option v-for="opt in WEEKDAY_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                    </select>
                  </label>
                  <label class="grid gap-1">
                    <span class="text-xs font-medium text-muted-foreground">Type</span>
                    <select v-model="eventForm.schedule_type" class="input-soft h-9 px-2 text-sm">
                      <option v-for="opt in EVENT_TYPE_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                    </select>
                  </label>
                </div>
                <div class="grid grid-cols-2 gap-2">
                  <fieldset class="grid gap-1">
                    <span class="text-xs font-medium text-muted-foreground">Start</span>
                    <div class="flex gap-1">
                      <select :model-value="splitTime(eventForm.start_time).hour" class="input-soft h-9 flex-1 px-1 text-sm text-center" @change="eventForm.start_time = joinTime(Number(($event.target as HTMLSelectElement).value), splitTime(eventForm.start_time).minute)">
                        <option v-for="h in HOUR_OPTIONS" :key="h.value" :value="h.value">{{ h.label }}</option>
                      </select>
                      <select :model-value="splitTime(eventForm.start_time).minute" class="input-soft h-9 flex-1 px-1 text-sm text-center" @change="eventForm.start_time = joinTime(splitTime(eventForm.start_time).hour, Number(($event.target as HTMLSelectElement).value))">
                        <option v-for="m in MINUTE_OPTIONS" :key="m.value" :value="m.value">{{ m.label }}</option>
                      </select>
                    </div>
                  </fieldset>
                  <fieldset class="grid gap-1">
                    <span class="text-xs font-medium text-muted-foreground">End</span>
                    <div class="flex gap-1">
                      <select :model-value="splitTime(eventForm.end_time).hour" class="input-soft h-9 flex-1 px-1 text-sm text-center" @change="eventForm.end_time = joinTime(Number(($event.target as HTMLSelectElement).value), splitTime(eventForm.end_time).minute)">
                        <option v-for="h in HOUR_OPTIONS" :key="h.value" :value="h.value">{{ h.label }}</option>
                      </select>
                      <select :model-value="splitTime(eventForm.end_time).minute" class="input-soft h-9 flex-1 px-1 text-sm text-center" @change="eventForm.end_time = joinTime(splitTime(eventForm.end_time).hour, Number(($event.target as HTMLSelectElement).value))">
                        <option v-for="m in MINUTE_OPTIONS" :key="m.value" :value="m.value">{{ m.label }}</option>
                      </select>
                    </div>
                  </fieldset>
                </div>
                <label class="grid gap-1">
                  <span class="text-xs font-medium text-muted-foreground">Location (optional)</span>
                  <input v-model="eventForm.location" type="text" class="input-soft h-9 px-3 text-sm" placeholder="Location">
                </label>
                <div class="flex gap-2">
                  <Button type="submit" size="sm" class="flex-1 transition-all duration-200 active:scale-95" :disabled="eventPending || !eventForm.name.trim()">
                    <IconPlus v-if="!editingEventId" class="size-4" />
                    <IconCheck v-else class="size-4" />
                    {{ editingEventId ? 'Save Event' : 'Add Event' }}
                  </Button>
                  <Button v-if="editingEventId" type="button" size="sm" variant="outline" class="transition-all duration-200 active:scale-95" @click="resetEventForm">
                    Cancel
                  </Button>
                </div>
                <p v-if="eventError" class="text-xs text-destructive">{{ eventError }}</p>
              </div>
            </form>

          </CardContent>
        </Card>

        <Card id="deadlines">
          <CardHeader>
            <div class="flex items-center gap-2">
              <IconClockHour4 class="size-4 text-muted-foreground" />
              <CardTitle>Deadlines</CardTitle>
            </div>
          </CardHeader>
          <CardContent class="space-y-3">
            <form class="rounded-xl border bg-background p-3" @submit.prevent="submitDeadline">
              <div class="grid gap-2.5">
                <label class="grid gap-1">
                  <span class="text-xs font-medium text-muted-foreground">Title</span>
                  <input
                    v-model="deadlineForm.title"
                    type="text"
                    class="input-soft h-9 px-3 text-sm"
                    placeholder="Assignment due"
                    required
                  >
                </label>
                <label class="grid gap-1">
                  <span class="text-xs font-medium text-muted-foreground">Due</span>
                  <input
                    v-model="deadlineForm.dueAt"
                    type="datetime-local"
                    class="input-soft h-9 px-3 text-sm"
                    required
                  >
                </label>
                <Button type="submit" size="sm" class="w-full transition-all duration-200 active:scale-95" :disabled="deadlinePending || !deadlineForm.title.trim() || !deadlineForm.dueAt.trim()">
                  <IconPlus class="size-4" />
                  {{ deadlinePending ? 'Adding...' : 'Add Deadline' }}
                </Button>
                <p v-if="deadlineError" class="text-xs text-destructive">{{ deadlineError }}</p>
              </div>
            </form>

            <div v-if="sortedDeadlines.length > 0" class="max-h-72 space-y-2 overflow-y-auto pr-1">
              <div
                v-for="deadline in sortedDeadlines"
                :key="deadline.id"
                class="flex items-start gap-2 rounded-lg border bg-muted/40 p-3"
                :class="deadline.completed ? 'opacity-70' : ''"
              >
                <input
                  type="checkbox"
                  class="mt-1 size-4 shrink-0 rounded border-input"
                  :checked="deadline.completed"
                  :disabled="deadlineActionId === deadline.id"
                  @change="toggleDeadlineCompleted(deadline)"
                >
                <div class="min-w-0 flex-1">
                  <div class="flex flex-wrap items-center gap-2">
                    <p class="text-sm font-medium" :class="deadline.completed ? 'line-through text-muted-foreground' : ''">
                      {{ deadline.title }}
                    </p>
                    <Badge variant="outline">{{ deadline.eventType }}</Badge>
                  </div>
                  <p class="mt-1 text-xs text-muted-foreground">{{ deadline.calendarName }}</p>
                  <p class="mt-1 text-xs text-muted-foreground">{{ formatDeadlineDate(deadline.endTime) }}</p>
                </div>
                <button
                  type="button"
                  class="rounded p-1 text-muted-foreground transition hover:bg-accent hover:text-destructive"
                  :disabled="deadlineActionId === deadline.id"
                  aria-label="Delete deadline"
                  @click="removeDeadline(deadline.id)"
                >
                  <IconTrash class="size-3.5" />
                </button>
              </div>
            </div>

            <EmptyState
              v-else
              title="No upcoming deadlines"
              description="Add a due-date task here or sync Blackboard data from Sources."
            />
          </CardContent>
        </Card>
      </div>
    </main>

    <div
      v-if="selectedItem"
      class="fixed inset-0 z-50"
      @mousedown="onOverlayMousedown"
    >
      <!-- View mode -->
      <div
        v-if="popoverMode === 'view'"
        class="absolute w-48 rounded-lg border bg-card p-3 shadow-lg"
        :style="popoverStyle"
        @mousedown.stop
      >
        <p class="text-sm font-semibold truncate">{{ selectedItem.title }}</p>
        <p class="text-xs text-muted-foreground">{{ selectedItem.startTime }} - {{ selectedItem.endTime }}</p>
        <p v-if="selectedItem.location" class="text-xs text-muted-foreground truncate">{{ selectedItem.location }}</p>
        <div class="mt-3 flex gap-2">
          <Button type="button" size="sm" variant="outline" @click="openPopoverEdit">
            <IconEdit class="size-4" />
          </Button>
          <Button type="button" size="sm" variant="ghost" class="text-destructive" @click="popoverDelete">
            <IconTrash class="size-4" />
          </Button>
        </div>
      </div>

      <!-- Edit mode -->
      <div
        v-else
        class="absolute w-60 rounded-xl border bg-card p-3 shadow-lg"
        :style="popoverStyle"
        @mousedown.stop
      >
        <div class="grid gap-2">
          <input v-model="popoverEditForm.name" type="text" class="input-soft h-8 px-2 text-xs" placeholder="Event name">
          <div class="grid grid-cols-2 gap-1.5">
            <select v-model.number="popoverEditForm.weekday" class="input-soft h-8 px-1 text-xs">
              <option v-for="opt in WEEKDAY_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
            <select v-model="popoverEditForm.schedule_type" class="input-soft h-8 px-1 text-xs">
              <option v-for="opt in EVENT_TYPE_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </div>
          <div class="grid grid-cols-2 gap-1.5">
            <div class="flex gap-1">
              <select :model-value="splitTime(popoverEditForm.start_time).hour" class="input-soft h-8 flex-1 px-0 text-xs text-center" @change="popoverEditForm.start_time = joinTime(Number(($event.target as HTMLSelectElement).value), splitTime(popoverEditForm.start_time).minute)">
                <option v-for="h in HOUR_OPTIONS" :key="h.value" :value="h.value">{{ h.label }}</option>
              </select>
              <select :model-value="splitTime(popoverEditForm.start_time).minute" class="input-soft h-8 flex-1 px-0 text-xs text-center" @change="popoverEditForm.start_time = joinTime(splitTime(popoverEditForm.start_time).hour, Number(($event.target as HTMLSelectElement).value))">
                <option v-for="m in MINUTE_OPTIONS" :key="m.value" :value="m.value">{{ m.label }}</option>
              </select>
            </div>
            <div class="flex gap-1">
              <select :model-value="splitTime(popoverEditForm.end_time).hour" class="input-soft h-8 flex-1 px-0 text-xs text-center" @change="popoverEditForm.end_time = joinTime(Number(($event.target as HTMLSelectElement).value), splitTime(popoverEditForm.end_time).minute)">
                <option v-for="h in HOUR_OPTIONS" :key="h.value" :value="h.value">{{ h.label }}</option>
              </select>
              <select :model-value="splitTime(popoverEditForm.end_time).minute" class="input-soft h-8 flex-1 px-0 text-xs text-center" @change="popoverEditForm.end_time = joinTime(splitTime(popoverEditForm.end_time).hour, Number(($event.target as HTMLSelectElement).value))">
                <option v-for="m in MINUTE_OPTIONS" :key="m.value" :value="m.value">{{ m.label }}</option>
              </select>
            </div>
          </div>
          <input v-model="popoverEditForm.location" type="text" class="input-soft h-8 px-2 text-xs" placeholder="Location">
          <div class="flex gap-1.5">
            <Button type="button" size="sm" class="flex-1 transition-all duration-200 active:scale-95" :disabled="eventPending || !popoverEditForm.name.trim()" @click="submitPopoverEdit">Save</Button>
            <Button type="button" size="sm" variant="outline" class="transition-all duration-200 active:scale-95" @click="popoverMode = 'view'">Cancel</Button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.calendar-fade-enter-active,
.calendar-fade-leave-active {
  transition: opacity 220ms ease, transform 220ms ease;
}

.calendar-fade-enter-from,
.calendar-fade-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

.schedule-item,
.schedule-pill {
  background: #fdf6e3;
  border: none;
  color: hsl(var(--foreground));
}

.schedule-item {
  overflow: hidden;
}

.input-soft {
  border: 1px solid hsl(var(--border));
  border-radius: 0.75rem;
  background: hsl(var(--background));
  outline: none;
  transition: border-color 180ms ease, box-shadow 180ms ease;
  color: hsl(var(--foreground));
}

select.input-soft {
  appearance: none;
  -webkit-appearance: none;
  cursor: pointer;
  padding-right: 2rem;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23866b53' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 0.5rem center;
  transition: border-color 180ms ease, box-shadow 180ms ease, background-image 180ms ease;
}

select.input-soft:focus {
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23ec6c00' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");
}

select.input-soft option {
  background: #fffdf9;
  color: #1f1610;
  padding: 0.5rem;
}

.dark select.input-soft option {
  background: #3a2d22;
  color: #f8eee5;
}

.input-soft:focus {
  border-color: hsl(var(--ring));
  box-shadow: 0 0 0 3px hsl(var(--ring) / 0.15);
}

.input-soft:hover:not(:focus) {
  border-color: hsl(var(--ring) / 0.4);
}

.schedule-item::before,
.schedule-pill::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  border-radius: 999px;
  background: hsl(var(--primary) / 0.45);
}

.schedule-pill {
  position: relative;
  padding-left: 10px;
}

.schedule-tone-course::before {
  background: hsl(var(--primary) / 0.55);
}

.schedule-tone-sports::before {
  background: #81c784;
}

.schedule-tone-meeting::before {
  background: #64b5f6;
}

.schedule-tone-study::before {
  background: #ba68c8;
}

.schedule-tone-entertainment::before {
  background: #ffb74d;
}

.schedule-tone-custom::before {
  background: #b0bec5;
}

.schedule-kind-pill {
  border: 1px solid hsl(var(--border) / 0.8);
  border-radius: 999px;
  padding: 0 6px;
  line-height: 1.25rem;
  font-size: 10px;
  color: hsl(var(--muted-foreground));
  background: hsl(var(--muted) / 0.45);
}

.reduce-motion .calendar-fade-enter-active,
.reduce-motion .calendar-fade-leave-active {
  transition: opacity 160ms ease;
}

.reduce-motion .calendar-fade-enter-from,
.reduce-motion .calendar-fade-leave-to {
  transform: none;
}

@media (prefers-reduced-motion: reduce) {
  .calendar-fade-enter-active,
  .calendar-fade-leave-active {
    transition: opacity 160ms ease;
  }

  .calendar-fade-enter-from,
  .calendar-fade-leave-to {
    transform: none;
  }
}
</style>
