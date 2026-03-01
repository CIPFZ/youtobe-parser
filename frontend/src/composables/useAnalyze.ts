import { ref, computed, watch } from 'vue'
import { useMutation, useQuery } from '@tanstack/vue-query'
import type {
    AnalyzeRequest,
    TaskResponse,
    TaskStatusResponse,
} from '../types'

const API_BASE = '/v1'

async function postAnalyze(body: AnalyzeRequest): Promise<TaskResponse> {
    const res = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    })
    if (!res.ok) throw new Error(`Analyze failed: ${res.status}`)
    return res.json()
}

async function fetchTaskStatus(taskId: string): Promise<TaskStatusResponse> {
    const res = await fetch(`${API_BASE}/tasks/${taskId}`)
    if (!res.ok) throw new Error(`Task poll failed: ${res.status}`)
    return res.json()
}

export function useAnalyze() {
    const taskId = ref<string | null>(null)
    const isPolling = ref(false)

    // Mutation: submit URL
    const analyzeMutation = useMutation({
        mutationFn: postAnalyze,
        onSuccess: (data) => {
            taskId.value = data.task_id
            isPolling.value = true
        },
    })

    // Query: poll task status (enabled only when we have a task ID and it's still in progress)
    const taskQuery = useQuery({
        queryKey: computed(() => ['task', taskId.value]),
        queryFn: () => fetchTaskStatus(taskId.value!),
        enabled: computed(() => !!taskId.value && isPolling.value),
        refetchInterval: computed(() => (isPolling.value ? 1000 : false)),
    })

    // Stop polling when task is done
    watch(
        () => taskQuery.data.value?.status,
        (status) => {
            if (status === 'completed' || status === 'failed') {
                isPolling.value = false
            }
        },
    )

    function submitUrl(url: string) {
        taskId.value = null
        isPolling.value = false
        analyzeMutation.mutate({ url })
    }

    function reset() {
        taskId.value = null
        isPolling.value = false
        analyzeMutation.reset()
    }

    return {
        taskId,
        submitUrl,
        reset,
        isSubmitting: computed(() => analyzeMutation.isPending.value),
        submitError: computed(() => analyzeMutation.error.value),
        taskData: computed(() => taskQuery.data.value ?? null),
        taskStatus: computed(() => taskQuery.data.value?.status ?? null),
        progress: computed(() => taskQuery.data.value?.progress ?? 0),
        videoInfo: computed(() => taskQuery.data.value?.result ?? null),
        taskError: computed(() => taskQuery.data.value?.error ?? null),
        isLoading: computed(() => {
            const s = taskQuery.data.value?.status
            return s === 'pending' || s === 'processing'
        }),
    }
}
