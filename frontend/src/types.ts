/* API types matching the backend Pydantic models */

export interface AnalyzeRequest {
    url: string
}

export interface TaskResponse {
    task_id: string
    status: string
}

export interface VideoFormat {
    format_id: string
    ext: string
    resolution: string | null
    fps: number | null
    vcodec: string | null
    acodec: string | null
    filesize: number | null
    filesize_approx: number | null
    tbr: number | null
    url: string | null
    format_note: string | null
    category: 'muxed' | 'video_only' | 'audio_only' | 'unknown'
}

export interface VideoInfo {
    title: string
    thumbnail: string | null
    duration: number | null
    channel: string | null
    channel_url: string | null
    view_count: number | null
    upload_date: string | null
    webpage_url: string
    formats: VideoFormat[]
}

export interface TaskStatusResponse {
    task_id: string
    status: 'pending' | 'processing' | 'completed' | 'failed'
    progress: number
    result: VideoInfo | null
    error: string | null
}
