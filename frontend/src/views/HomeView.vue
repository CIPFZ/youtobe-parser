<script setup lang="ts">
import { ref, computed } from 'vue'
import { useAnalyze } from '../composables/useAnalyze'
import ProgressBar from '../components/ProgressBar.vue'
import VideoCard from '../components/VideoCard.vue'
import FormatTable from '../components/FormatTable.vue'
import type { VideoFormat } from '../types'

const urlInput = ref('')
const {
  submitUrl,
  reset,
  isSubmitting,
  taskStatus,
  progress,
  videoInfo,
  taskError,
  submitError,
  isLoading,
} = useAnalyze()

// Active format tab
type TabKey = 'muxed' | 'video_only' | 'audio_only'
const activeTab = ref<TabKey>('muxed')

const tabs: { key: TabKey; label: string; icon: string }[] = [
  { key: 'muxed', label: '音画合一', icon: '🎬' },
  { key: 'video_only', label: '仅视频', icon: '🎥' },
  { key: 'audio_only', label: '仅音频', icon: '🎵' },
]

const filteredFormats = computed<VideoFormat[]>(() => {
  if (!videoInfo.value) return []
  return videoInfo.value.formats.filter((f) => f.category === activeTab.value)
})

const formatCounts = computed(() => {
  if (!videoInfo.value) return { muxed: 0, video_only: 0, audio_only: 0 }
  const fmts = videoInfo.value.formats
  return {
    muxed: fmts.filter((f) => f.category === 'muxed').length,
    video_only: fmts.filter((f) => f.category === 'video_only').length,
    audio_only: fmts.filter((f) => f.category === 'audio_only').length,
  }
})

function handleSubmit() {
  const url = urlInput.value.trim()
  if (!url) return
  submitUrl(url)
}

function handleReset() {
  urlInput.value = ''
  reset()
}

const showResults = computed(() => taskStatus.value === 'completed' && videoInfo.value)
const showProgress = computed(() => isLoading.value || taskStatus.value === 'failed')
const errorMessage = computed(() => taskError.value || submitError.value?.message || null)
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <!-- Background blobs -->
    <div class="fixed inset-0 pointer-events-none overflow-hidden -z-10">
      <div class="absolute -top-40 -left-40 w-96 h-96 bg-accent/8 rounded-full blur-3xl" />
      <div class="absolute top-1/3 -right-32 w-80 h-80 bg-purple-600/6 rounded-full blur-3xl" />
      <div class="absolute -bottom-32 left-1/3 w-72 h-72 bg-blue-600/6 rounded-full blur-3xl" />
    </div>

    <!-- Header -->
    <header class="pt-12 pb-6 text-center">
      <h1 class="text-3xl md:text-4xl font-bold tracking-tight">
        <span class="gradient-text">YouTube</span>
        <span class="text-text-primary ml-1">Parser</span>
      </h1>
      <p class="mt-2 text-text-muted text-sm">高性能视频解析 · 全格式信息提取</p>
    </header>

    <!-- Main Content -->
    <main class="flex-1 w-full max-w-4xl mx-auto px-4 pb-16 space-y-6">

      <!-- URL Input Card -->
      <div class="glass p-6">
        <form @submit.prevent="handleSubmit" class="flex gap-3">
          <div class="relative flex-1">
            <div class="absolute inset-y-0 left-0 flex items-center pl-4 pointer-events-none">
              <svg class="w-5 h-5 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
              </svg>
            </div>
            <input
              v-model="urlInput"
              type="url"
              placeholder="粘贴 YouTube 视频链接…"
              class="w-full pl-12 pr-4 py-3.5 rounded-xl bg-surface-700/80 border border-surface-500/40
                     text-text-primary placeholder:text-text-muted
                     focus:outline-none focus:border-accent/60 focus:ring-2 focus:ring-accent/20
                     transition-all duration-200 text-sm"
              :disabled="isSubmitting || isLoading"
            />
          </div>

          <button
            v-if="!showResults && !showProgress"
            type="submit"
            :disabled="!urlInput.trim() || isSubmitting"
            class="px-6 py-3.5 rounded-xl font-semibold text-sm text-white
                   gradient-accent
                   hover:opacity-90 hover:shadow-lg hover:shadow-accent/20
                   disabled:opacity-40 disabled:cursor-not-allowed
                   transition-all duration-200 whitespace-nowrap"
          >
            <span v-if="isSubmitting" class="flex items-center gap-2">
              <svg class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              提交中
            </span>
            <span v-else>开始解析</span>
          </button>

          <button
            v-else
            type="button"
            @click="handleReset"
            class="px-6 py-3.5 rounded-xl font-semibold text-sm
                   bg-surface-600 text-text-secondary hover:bg-surface-500 hover:text-text-primary
                   transition-all duration-200 whitespace-nowrap"
          >
            重新解析
          </button>
        </form>
      </div>

      <!-- Error -->
      <transition name="fade">
        <div
          v-if="errorMessage"
          class="glass-sm p-4 border-danger/30 border text-danger text-sm flex items-start gap-3"
        >
          <svg class="w-5 h-5 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
          <p>{{ errorMessage }}</p>
        </div>
      </transition>

      <!-- Progress -->
      <transition name="slide-up">
        <div v-if="showProgress" class="glass p-6">
          <ProgressBar :progress="progress" :status="taskStatus" />
        </div>
      </transition>

      <!-- Results -->
      <transition name="slide-up">
        <div v-if="showResults && videoInfo" class="space-y-6">
          <!-- Video Card -->
          <VideoCard :info="videoInfo" />

          <!-- Format Tabs -->
          <div class="glass overflow-hidden">
            <!-- Tab bar -->
            <div class="flex border-b border-surface-500/30">
              <button
                v-for="tab in tabs"
                :key="tab.key"
                @click="activeTab = tab.key"
                class="flex-1 py-3.5 text-sm font-medium transition-all duration-200 relative"
                :class="activeTab === tab.key
                  ? 'text-accent-light'
                  : 'text-text-muted hover:text-text-secondary'"
              >
                <span>{{ tab.icon }} {{ tab.label }}</span>
                <span class="ml-1.5 text-xs opacity-60">({{ formatCounts[tab.key] }})</span>
                <!-- Active indicator -->
                <div
                  v-if="activeTab === tab.key"
                  class="absolute bottom-0 left-1/4 right-1/4 h-0.5 gradient-accent rounded-full"
                />
              </button>
            </div>

            <!-- Table -->
            <FormatTable
              :formats="filteredFormats"
            />
          </div>
        </div>
      </transition>
    </main>

    <!-- Footer -->
    <footer class="text-center py-6 text-text-muted text-xs">
      Powered by yt-dlp & FastAPI
    </footer>
  </div>
</template>
