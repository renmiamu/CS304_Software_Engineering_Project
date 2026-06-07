<script setup lang="ts">
import { AccordionRoot } from 'reka-ui'

const props = defineProps<{
  type?: 'single' | 'multiple'
  collapsible?: boolean
  defaultValue?: string | string[]
  modelValue?: string | string[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string | string[]]
}>()
</script>

<template>
  <AccordionRoot
    :type="type ?? 'single'"
    :collapsible="collapsible ?? true"
    :default-value="defaultValue"
    :model-value="modelValue"
    class="w-full"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <slot />
  </AccordionRoot>
</template>
