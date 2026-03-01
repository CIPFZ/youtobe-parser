<script setup lang="ts">
const props = defineProps<{
  progress: number
  status: string | null
}>()

const statusLabels: Record<string, string> = {
  pending: '⏳ 排队等待中…',
  processing: '🔍 正在解析视频信息…',
  completed: '✅ 解析完成',
  failed: '❌ 解析失败',
}
</script>

<template>
  <div class="space-y-3">
    <!-- Label -->
    <div class="flex items-center justify-between text-sm">
      <span class="text-text-secondary">
        {{ statusLabels[props.status || ''] || '准备中…' }}
      </span>
      <span class="font-mono text-accent-light text-xs">
        {{ props.progress.toFixed(0) }}%
      </span>
    </div>

    <!-- Track -->
    <div class="relative h-2 rounded-full bg-surface-600 overflow-hidden">
      <!-- Fill -->
      <div
        class="absolute inset-y-0 left-0 rounded-full transition-all duration-500 ease-out"
        :class="{
          'gradient-accent': props.status !== 'failed',
          'bg-danger': props.status === 'failed',
        }"
        :style="{ width: `${Math.max(props.progress, props.status === 'pending' ? 5 : 0)}%` }"
      />
      <!-- Shimmer overlay when active -->
      <div
        v-if="props.status === 'processing' || props.status === 'pending'"
        class="absolute inset-0 shimmer rounded-full"
      />
    </div>
  </div>
</template>
