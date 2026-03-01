<script setup lang="ts">
import type { VideoInfo } from '../types'

const props = defineProps<{
  info: VideoInfo
}>()

function formatDuration(sec: number | null): string {
  if (!sec) return '--:--'
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = Math.floor(sec % 60)
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}

function formatViews(n: number | null): string {
  if (!n) return ''
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M 次播放`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K 次播放`
  return `${n} 次播放`
}

function formatDate(d: string | null): string {
  if (!d || d.length !== 8) return ''
  return `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}`
}
</script>

<template>
  <div class="glass-sm overflow-hidden">
    <!-- Thumbnail -->
    <div class="relative aspect-video bg-surface-700 overflow-hidden">
      <img
        v-if="props.info.thumbnail"
        :src="props.info.thumbnail"
        :alt="props.info.title"
        class="w-full h-full object-cover"
        loading="lazy"
      />
      <div
        v-if="props.info.duration"
        class="absolute bottom-3 right-3 px-2 py-0.5 rounded bg-black/70 text-xs font-mono text-white/90 backdrop-blur-sm"
      >
        {{ formatDuration(props.info.duration) }}
      </div>
    </div>

    <!-- Info -->
    <div class="p-5 space-y-3">
      <h2 class="text-lg font-semibold leading-snug text-text-primary line-clamp-2">
        {{ props.info.title }}
      </h2>

      <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-text-secondary">
        <a
          v-if="props.info.channel"
          :href="props.info.channel_url || '#'"
          target="_blank"
          class="hover:text-accent-light transition-colors duration-200 flex items-center gap-1"
        >
          <svg class="w-4 h-4 opacity-60" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
          </svg>
          {{ props.info.channel }}
        </a>
        <span v-if="props.info.view_count" class="flex items-center gap-1">
          <svg class="w-4 h-4 opacity-60" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path stroke-linecap="round" stroke-linejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
          </svg>
          {{ formatViews(props.info.view_count) }}
        </span>
        <span v-if="props.info.upload_date" class="flex items-center gap-1">
          <svg class="w-4 h-4 opacity-60" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          {{ formatDate(props.info.upload_date) }}
        </span>
      </div>
    </div>
  </div>
</template>
