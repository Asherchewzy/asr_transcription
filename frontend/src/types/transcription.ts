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
