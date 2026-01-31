import type { Transcription, TaskResponse, TaskStatus } from '../types/transcription';

class ApiService {
  private baseURL: string;

  constructor() {
    this.baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  }

  async uploadFiles(files: File[]): Promise<TaskResponse[]> {
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });

    const response = await fetch(`${this.baseURL}/api/v1/transcribe`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(error.detail || 'Upload failed');
    }

    const data = await response.json();
    return data.tasks;
  }

  async getTaskStatus(taskId: string): Promise<TaskStatus> {
    const response = await fetch(`${this.baseURL}/api/v1/status/${taskId}`);

    if (!response.ok) {
      throw new Error('Failed to fetch task status');
    }

    return response.json();
  }

  async listTranscriptions(status?: string): Promise<Transcription[]> {
    const params = new URLSearchParams();
    if (status) {
      params.append('status', status);
    }

    const url = `${this.baseURL}/api/v1/transcriptions${params.toString() ? `?${params.toString()}` : ''}`;
    const response = await fetch(url);

    if (!response.ok) {
      throw new Error('Failed to fetch transcriptions');
    }

    return response.json();
  }

  async searchTranscriptions(query: string): Promise<Transcription[]> {
    const params = new URLSearchParams({ filename: query });
    const response = await fetch(`${this.baseURL}/api/v1/search?${params.toString()}`);

    if (!response.ok) {
      throw new Error('Search failed');
    }

    const data = await response.json();
    return data.results;
  }
}

export const apiService = new ApiService();
