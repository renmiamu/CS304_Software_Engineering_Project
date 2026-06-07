<script setup lang="ts">
import { computed } from 'vue'
import { WORKSPACE_QUERY_KEYS } from '~/composables/useWorkspaceStore'

const workspace = useWorkspaceStore()
const queryMeta = computed(() => workspace.readQueryMetaForActiveUser(WORKSPACE_QUERY_KEYS.scheduleToday))

const todaySchedule = computed(() => {
  const schedule = workspace.tisScheduleCourses.value || []
  const currentDay = new Date().getDay() || 7 // 1 to 7

  return schedule.filter(course => {
    const weekday = course.weekday?.toString() || ''
    if (String(currentDay) === weekday) return true
    
    const zhDays = ['日', '一', '二', '三', '四', '五', '六', '日']
    const dayString = zhDays[currentDay]
    if (weekday.includes(dayString)) return true

    return false
  })
})

function retry() {
  void workspace.refreshWorkspaceQuery(WORKSPACE_QUERY_KEYS.scheduleToday)
}

function cancel() {
  workspace.cancelWorkspaceQuery(WORKSPACE_QUERY_KEYS.scheduleToday)
}
</script>

<template>
  <UiCard class="flex flex-col h-full overflow-hidden">
    <div class="px-6 pt-6 pb-2 border-b">
      <h3 class="font-semibold text-lg">Today's Schedule</h3>
    </div>

    <AsyncWidgetWrapper
      :is-loading="queryMeta.isLoading"
      :error="queryMeta.error"
      @retry="retry"
      @cancel="cancel"
      class="flex-1 overflow-y-auto px-6 py-4"
    >
      <div v-if="todaySchedule.length === 0" class="text-sm text-muted-foreground py-4 text-center">
        No expected courses configured or none found for today
      </div>
      <div v-else class="space-y-4">
        <div v-for="(course, index) in todaySchedule" :key="index" class="border rounded-md p-3">
          <div class="font-medium text-sm">{{ course.course_name }}</div>
          <div class="text-xs text-muted-foreground flex justify-between mt-1">
            <span>{{ course.teacher || 'TBA' }}</span>
            <span class="font-medium bg-muted px-1.5 py-0.5 rounded">{{ course.location || 'TBA' }}</span>
          </div>
          <div class="text-xs text-muted-foreground mt-1">
            {{ course.weekday }} &middot; {{ course.time_slots }} (Weeks: {{ course.weeks }})
          </div>
        </div>
      </div>
    </AsyncWidgetWrapper>
  </UiCard>
</template>
