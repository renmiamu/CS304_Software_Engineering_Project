<script setup lang="ts">
import { VisArea, VisAxis, VisLine, VisXYContainer } from '@unovis/vue'
import type { SyncJob } from '~/types/app'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

const props = defineProps<{
  syncJobs: SyncJob[]
}>()

type RangeOption = '90d' | '30d' | '7d'

const timeRange = ref<RangeOption>('30d')

const rangeDays = computed(() => {
  if (timeRange.value === '7d') {
    return 7
  }

  if (timeRange.value === '30d') {
    return 30
  }

  return 90
})

const trendData = computed(() => {
  const days = rangeDays.value
  const now = new Date()
  const dayMap = new Map<string, { date: Date, total: number, issues: number }>()

  for (let offset = days - 1; offset >= 0; offset--) {
    const date = new Date(now)
    date.setHours(0, 0, 0, 0)
    date.setDate(date.getDate() - offset)
    const key = date.toISOString().slice(0, 10)
    dayMap.set(key, { date, total: 0, issues: 0 })
  }

  for (const job of props.syncJobs) {
    const runAt = new Date(job.runAt)
    runAt.setHours(0, 0, 0, 0)
    const key = runAt.toISOString().slice(0, 10)
    const slot = dayMap.get(key)

    if (!slot) {
      continue
    }

    slot.total += 1
    if (job.status !== 'success') {
      slot.issues += 1
    }
  }

  return [...dayMap.values()]
})

const maxY = computed(() => {
  const max = Math.max(...trendData.value.map(item => Math.max(item.total, item.issues)), 1)
  return Math.max(2, max + 1)
})

const svgDefs = `
  <linearGradient id="syncTotalFill" x1="0" y1="0" x2="0" y2="1">
    <stop offset="5%" stop-color="var(--color-chart-2)" stop-opacity="0.8" />
    <stop offset="95%" stop-color="var(--color-chart-2)" stop-opacity="0.05" />
  </linearGradient>
`

type DataPoint = { date: Date, total: number, issues: number }
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between gap-3">
      <div>
        <p class="text-sm font-medium">Source Sync Trend</p>
      </div>
      <Select v-model="timeRange">
        <SelectTrigger class="w-[140px]" size="sm" aria-label="Select range">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="90d">Last 90 days</SelectItem>
          <SelectItem value="30d">Last 30 days</SelectItem>
          <SelectItem value="7d">Last 7 days</SelectItem>
        </SelectContent>
      </Select>
    </div>

    <div class="h-[260px] w-full">
      <VisXYContainer
        :data="trendData"
        :svg-defs="svgDefs"
        :y-domain="[0, maxY]"
        :margin="{ left: 6, right: 12, top: 10, bottom: 22 }"
      >
        <VisArea
          :x="(d: DataPoint) => d.date"
          :y="(d: DataPoint) => d.total"
          color="url(#syncTotalFill)"
        />
        <VisLine
          :x="(d: DataPoint) => d.date"
          :y="(d: DataPoint) => d.total"
          color="var(--color-chart-2)"
          :line-width="2"
        />
        <VisLine
          :x="(d: DataPoint) => d.date"
          :y="(d: DataPoint) => d.issues"
          color="var(--color-destructive)"
          :line-width="2"
        />
        <VisAxis
          type="x"
          :x="(d: DataPoint) => d.date"
          :tick-line="false"
          :domain-line="false"
          :grid-line="false"
          :num-ticks="6"
          :tick-format="(value: number) => new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })"
        />
        <VisAxis
          type="y"
          :num-ticks="4"
          :tick-line="false"
          :domain-line="false"
        />
      </VisXYContainer>
    </div>
  </div>
</template>
