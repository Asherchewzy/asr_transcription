export interface Transcription {
  id: number;
  audio_filename: string;
  transcribed_text: string | null;
  created_timestamp: string;
  status: 'processing' | 'completed' | 'failed';
  task_id?: string;
  error_message?: string;
}

export interface TaskResponse {
  task_id: string;
  transcription_id: number;
  filename: string;
  status: string;
}

export interface TaskStatus {
  status: string;
  task_id: string;
  transcription_id?: number;
  text?: string;
  error?: string;
}

export interface HealthResponse {
  status: 'healthy' | 'degraded';
  timestamp: string;
  model_loaded: boolean;
  device_info: string;
  db_healthy: boolean;
  redis_healthy: boolean;
  celery_workers_active: boolean;
  issues: string[];
}
