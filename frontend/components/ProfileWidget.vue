<script setup lang="ts">
import { computed } from 'vue'
import { WORKSPACE_QUERY_KEYS } from '~/composables/useWorkspaceStore'

const workspace = useWorkspaceStore()

const queryMeta = computed(() => workspace.readQueryMetaForActiveUser(WORKSPACE_QUERY_KEYS.academicSnapshot))
const grade = computed(() => workspace.academicProfile.value.grade ?? {})
const credit = computed(() => workspace.academicProfile.value.credit ?? {
  total_credit: 0,
  category_credit: {},
})

function retry() {
  void workspace.refreshWorkspaceQuery(WORKSPACE_QUERY_KEYS.academicSnapshot)
}

function cancel() {
  workspace.cancelWorkspaceQuery(WORKSPACE_QUERY_KEYS.academicSnapshot)
}
</script>

<template>
  <UiCard class="flex flex-col h-full overflow-hidden">
    <div class="px-6 pt-6 pb-2 border-b">
      <h3 class="font-semibold text-lg">Academic Profile</h3>
    </div>

    <AsyncWidgetWrapper
      :is-loading="queryMeta.isLoading"
      :error="queryMeta.error"
      @retry="retry"
      @cancel="cancel"
      class="p-6"
    >
      <div class="grid grid-cols-2 gap-4 text-sm">
        <div class="bg-muted w-full rounded-md flex flex-col p-4">
          <div class="text-muted-foreground text-xs font-semibold tracking-wider">GPA</div>
          <div class="font-bold text-xl mt-1">{{ grade.GPA ?? 'N/A' }}</div>
        </div>
        <div class="bg-muted rounded-md flex flex-col p-4 w-full">
          <div class="text-muted-foreground text-xs font-semibold tracking-wider">RANK</div>
          <div class="font-bold text-xl mt-1">{{ grade.Rank ?? 'N/A' }}</div>
        </div>
        <div class="bg-muted rounded-md flex flex-col p-4 w-full col-span-2">
          <div class="text-muted-foreground text-xs font-semibold tracking-wider">TOTAL CREDITS</div>
          <div class="font-bold text-xl mt-1">{{ credit.total_credit || 0 }}</div>
          <div class="text-xs text-muted-foreground mt-2 grid grid-cols-2 lg:grid-cols-3 gap-2">
            <div v-for="(v, k) in credit.category_credit" :key="k" class="bg-background px-2 py-1 rounded">
              {{ k }}: {{ v }}
            </div>
          </div>
        </div>
      </div>
    </AsyncWidgetWrapper>
  </UiCard>
</template>
