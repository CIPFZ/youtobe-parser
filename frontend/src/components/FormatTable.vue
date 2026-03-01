<script setup lang="ts">
import { ref } from 'vue'
import type { VideoFormat } from '../types'

const props = defineProps<{
  formats: VideoFormat[]
}>()

const copiedId = ref<string | null>(null)

async function copyLink(url: string, formatId: string) {
  try {
    await navigator.clipboard.writeText(url)
  } catch {
    const input = document.createElement('input')
    input.value = url
    document.body.appendChild(input)
    input.select()
    document.execCommand('copy')
    document.body.removeChild(input)
  }
  copiedId.value = formatId
  setTimeout(() => { copiedId.value = null }, 1500)
}

function formatSize(bytes: number | null): string {
  if (!bytes) return '—'
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

function formatBitrate(tbr: number | null): string {
  if (!tbr) return '—'
  if (tbr < 1000) return `${tbr.toFixed(0)} kbps`
  return `${(tbr / 1000).toFixed(1)} Mbps`
}

function codecLabel(vcodec: string | null, acodec: string | null): string {
  const parts: string[] = []
  if (vcodec && vcodec !== 'none') parts.push(vcodec.split('.')[0] ?? vcodec)
  if (acodec && acodec !== 'none') parts.push(acodec.split('.')[0] ?? acodec)
  return parts.join(' + ') || '—'
}
</script>

<template>
  <div class="overflow-x-auto">
    <table class="w-full text-sm">
      <thead>
        <tr class="text-text-secondary text-xs uppercase tracking-wider border-b border-surface-500/40">
          <th class="py-3 px-4 text-left font-medium">格式</th>
          <th class="py-3 px-4 text-left font-medium">分辨率</th>
          <th class="py-3 px-4 text-left font-medium">编码</th>
          <th class="py-3 px-4 text-left font-medium">大小</th>
          <th class="py-3 px-4 text-left font-medium">码率</th>
          <th class="py-3 px-4 text-right font-medium">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="fmt in props.formats"
          :key="fmt.format_id"
          class="border-b border-surface-500/20 hover:bg-surface-600/40 transition-colors duration-150"
        >
          <td class="py-3 px-4">
            <span class="inline-flex items-center gap-1.5">
              <span
                class="inline-block px-2 py-0.5 rounded text-[11px] font-semibold uppercase tracking-wide"
                :class="{
                  'bg-accent/20 text-accent-light': fmt.ext === 'webm',
                  'bg-success/20 text-success': fmt.ext === 'mp4',
                  'bg-warning/20 text-warning': fmt.ext === 'm4a' || fmt.ext === 'opus',
                  'bg-surface-500/50 text-text-secondary': !['webm', 'mp4', 'm4a', 'opus'].includes(fmt.ext),
                }"
              >
                {{ fmt.ext }}
              </span>
              <span v-if="fmt.format_note" class="text-text-muted text-xs">{{ fmt.format_note }}</span>
            </span>
          </td>
          <td class="py-3 px-4 text-text-primary font-medium">
            {{ fmt.resolution || '—' }}
            <span v-if="fmt.fps" class="text-text-muted text-xs ml-1">{{ fmt.fps }}fps</span>
          </td>
          <td class="py-3 px-4 text-text-secondary text-xs font-mono">
            {{ codecLabel(fmt.vcodec, fmt.acodec) }}
          </td>
          <td class="py-3 px-4 text-text-secondary">
            {{ formatSize(fmt.filesize || fmt.filesize_approx) }}
          </td>
          <td class="py-3 px-4 text-text-secondary">
            {{ formatBitrate(fmt.tbr) }}
          </td>
          <td class="py-3 px-4 text-right">
            <button
              v-if="fmt.url"
              @click="copyLink(fmt.url, fmt.format_id)"
              class="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold
                     bg-accent/15 text-accent-light hover:bg-accent/30
                     transition-all duration-200 cursor-pointer
                     hover:shadow-[0_0_12px_rgba(108,92,231,0.3)]"
            >
              <svg v-if="copiedId !== fmt.format_id" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
              </svg>
              <svg v-else class="w-3.5 h-3.5 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              {{ copiedId === fmt.format_id ? '已复制' : '复制链接' }}
            </button>
            <span v-else class="text-text-muted text-xs">—</span>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-if="!props.formats.length" class="text-center text-text-muted py-6 text-sm">
      此分类下暂无可用格式
    </p>
  </div>
</template>
