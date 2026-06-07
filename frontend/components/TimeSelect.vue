<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { ChevronDown } from 'lucide-vue-next'

const props = withDefaults(defineProps<{
  options: { value: number; label: string }[]
  modelValue: number
  size?: number
  class?: string
}>(), { size: 6 })

const emit = defineEmits<{
  'update:modelValue': [value: number]
}>()

const open = ref(false)
const root = ref<HTMLElement | null>(null)

const selectedLabel = computed(() => {
  const opt = props.options.find(o => o.value === props.modelValue)
  return opt ? opt.label : String(props.modelValue)
})

function select(value: number) {
  emit('update:modelValue', value)
  open.value = false
}

function onMousedown(e: MouseEvent) {
  e.preventDefault()
  open.value = !open.value
}

function onDocMousedown(e: MouseEvent) {
  if (root.value && !root.value.contains(e.target as Node)) {
    open.value = false
  }
}

watch(open, (val) => {
  if (val) {
    document.addEventListener('mousedown', onDocMousedown, true)
  } else {
    document.removeEventListener('mousedown', onDocMousedown, true)
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocMousedown, true)
})
</script>

<template>
  <div ref="root" class="relative">
    <button
      type="button"
      class="input-soft flex items-center justify-between gap-0.5"
      :class="props.class"
      @mousedown="onMousedown"
    >
      <span>{{ selectedLabel }}</span>
      <ChevronDown
        class="size-3 shrink-0 text-muted-foreground transition-transform duration-200"
        :class="open ? 'rotate-180' : ''"
      />
    </button>
    <div
      v-if="open"
      class="absolute left-0 z-20 mt-1 w-full rounded-xl border border-border bg-card py-1 shadow-lg"
      :style="{ maxHeight: `${props.size * 28}px`, overflowY: 'auto' }"
    >
      <button
        v-for="opt in options"
        :key="opt.value"
        type="button"
        class="flex h-7 w-full items-center justify-center text-sm transition-colors hover:bg-accent"
        :class="opt.value === modelValue ? 'bg-accent font-medium text-primary' : 'text-foreground'"
        @mousedown.prevent="select(opt.value)"
      >
        {{ opt.label }}
      </button>
    </div>
  </div>
</template>
