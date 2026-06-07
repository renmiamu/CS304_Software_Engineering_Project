<script setup lang="ts">
defineProps<{
  title: string
  description: string
}>()
</script>

<template>
  <div class="rounded-3xl border border-dashed border-border bg-muted/60 p-8 text-center">
    <p class="text-base font-medium text-foreground">{{ title }}</p>
    <p class="mt-2 text-sm leading-6 text-muted-foreground">{{ description }}</p>
  </div>
</template>
