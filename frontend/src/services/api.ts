import type { HealthResponse, Transcription, TaskResponse, TaskStatus } from '../types/transcription';

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
      if (response.status === 429) {
        let detail = '';
        let limit: string | undefined;
        const headerLimit =
          response.headers.get('x-ratelimit-limit') ||
          response.headers.get('ratelimit-limit') ||
          response.headers.get('X-RateLimit-Limit') ||
          undefined;

        const errorBody = await response.json().catch(() => null);
        if (typeof errorBody?.detail === 'string') {
          detail = errorBody.detail;
        }
        if (typeof errorBody?.limit === 'string') {
          limit = errorBody.limit;
        }

        if (!limit && detail) {
          const match = detail.match(/rate limit exceeded:?\s*(.*)$/i);
          if (match?.[1]) {
            limit = match[1].trim();
          } else {
            const inline = detail.match(/(\d+\s*\/\s*\w+|\d+\s+per\s+\d+\s+\w+)/i);
            if (inline?.[0]) {
              limit = inline[0];
            }
          }
        }

        if (!limit && headerLimit) {
          limit = headerLimit;
        }

        const message = limit
          ? `Rate limit has been hit. Limit: ${limit}`
          : 'Rate limit has been hit. Please try again later.';
        throw new Error(message);
      }

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

  async getHealth(): Promise<HealthResponse> {
    const response = await fetch(`${this.baseURL}/api/v1/health`);
    const data = await response.json().catch(() => null);

    if (!data) {
      throw new Error('Health check failed');
    }

    return data as HealthResponse;
  }
}

export const apiService = new ApiService();
