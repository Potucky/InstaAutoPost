export type ContentStatus = 'draft' | 'approved' | 'archived';

export type MediaType = 'reel' | 'video' | 'carousel';

export type QueueStatus =
  | 'draft'
  | 'scheduled'
  | 'ready'
  | 'processing'
  | 'published'
  | 'failed'
  | 'cancelled'
  | 'retry_scheduled';

export type AttemptStatus = 'success' | 'failed' | 'dry_run';

export interface ContentItem {
  id: string;
  title: string;
  caption: string | null;
  video_url: string;
  thumbnail_url: string | null;
  hashtags: string[] | null;
  content_status: ContentStatus;
  media_type: MediaType;
  duration_seconds: number | null;
  file_size: number | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface QueueItem {
  id: string;
  content_id: string;
  queue_status: QueueStatus;
  scheduled_at: string | null;
  published_at: string | null;
  external_media_id: string | null;
  attempt_count: number;
  max_attempts: number;
  next_retry_at: string | null;
  failure_reason: string | null;
  ig_user_id: string | null;
  notes: string | null;
  locked_at: string | null;
  locked_by: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  ig_content_library?: ContentItem;
}

export type SlotStatus = 'empty' | 'assigned' | 'queued' | 'published' | 'failed' | 'cancelled';

export interface ScheduleSlot {
  id: string;
  // YYYY-MM-DD posting date in America/New_York; compare as string, never via new Date()
  slot_date: string;
  slot_window: 'morning' | 'lunch' | 'evening';
  // exact timestamptz/UTC publish instant; use for time display, filtering, and ordering
  scheduled_at: string;
  content_id: string | null;
  queue_id: string | null;
  slot_status: SlotStatus;
  notes: string | null;
  created_at: string;
  updated_at: string;
  ig_content_library?: {
    id: string;
    title: string;
    media_type: string;
    caption?: string | null;
  } | null;
}

export interface PublishAttempt {
  id: string;
  queue_id: string;
  attempt_number: number;
  status: AttemptStatus;
  response_data: Record<string, unknown> | null;
  error_message: string | null;
  container_id: string | null;
  media_id: string | null;
  duration_ms: number | null;
  dry_run: boolean;
  worker_version: string | null;
  created_at: string;
  ig_publishing_queue?: Pick<QueueItem, 'id' | 'content_id' | 'queue_status' | 'ig_content_library'>;
}
