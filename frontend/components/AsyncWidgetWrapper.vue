<script setup lang="ts">
import { ref, watch, onBeforeUnmount } from 'vue'

const props = withDefaults(defineProps<{
  isLoading: boolean
  error?: string | null
  cancelTimeout?: number
}>(), {
  cancelTimeout: 3000
})

const emit = defineEmits<{
  (e: 'retry'): void
  (e: 'cancel'): void
}>()

const showCancelBtn = ref(false)
let timer: ReturnType<typeof setTimeout> | null = null

watch(() => props.isLoading, (loading) => {
  if (loading) {
    showCancelBtn.value = false
    timer = setTimeout(() => {
      showCancelBtn.value = true
    }, props.cancelTimeout)
  } else {
    if (timer) clearTimeout(timer)
    showCancelBtn.value = false
  }
}, { immediate: true })

onBeforeUnmount(() => {
  if (timer) clearTimeout(timer)
})
</script>

<template>
  <div class="relative w-full h-full min-h-[100px] flex flex-col pt-3">
    <!-- Error State -->
    <div v-if="error" class="flex flex-col items-center justify-center py-6 text-center space-y-3">
      <div class="text-sm text-destructive">{{ error }}</div>
      <UiButton variant="outline" size="sm" @click="emit('retry')">
        Retry
      </UiButton>
    </div>

    <!-- Loading State -->
    <div v-else-if="isLoading" class="flex flex-col items-center justify-center p-6 space-y-4">
      <slot name="skeleton">
        <div class="w-full space-y-2">
          <UiSkeleton class="h-4 w-full" />
          <UiSkeleton class="h-4 w-5/6" />
          <UiSkeleton class="h-4 w-4/6" />
        </div>
      </slot>
      <div v-show="showCancelBtn" class="mt-4 animate-in fade-in zoom-in duration-300">
        <UiButton variant="secondary" size="sm" @click="emit('cancel')">
          Cancel Request
        </UiButton>
      </div>
    </div>

    <!-- Content State -->
    <div v-else class="flex-1 w-full relative">
      <slot />
    </div>
  </div>
</template>
