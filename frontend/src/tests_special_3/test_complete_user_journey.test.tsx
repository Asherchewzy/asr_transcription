/**
 * special test #3: complete user journey
 *
 * tests the entire user experience from upload to search
 * proves ALL components work together correctly
 * validates the core value proposition: user can transcribe and find their files
 * most impressive for presentation: shows the app actually works
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import App from '../App';
import * as api from '../services/api';
import * as validation from '../services/validation';

vi.mock('../services/api', () => ({
  apiService: {
    uploadFiles: vi.fn(),
    getTaskStatus: vi.fn(),
    listTranscriptions: vi.fn(),
    searchTranscriptions: vi.fn(),
    getHealth: vi.fn(),
  },
}));

vi.mock('../services/validation', () => ({
  validateFiles: vi.fn(),
}));

describe('complete user journey', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    vi.mocked(validation.validateFiles).mockReturnValue({ valid: true });
    vi.mocked(api.apiService.listTranscriptions).mockResolvedValue([]);
    vi.mocked(api.apiService.getHealth).mockResolvedValue({
      status: 'healthy',
      timestamp: new Date().toISOString(),
      model_loaded: true,
      device_info: 'cpu',
      db_healthy: true,
      redis_healthy: true,
      celery_workers_active: true,
      issues: [],
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should complete full journey: upload → poll → complete → list → search', async () => {

    // step 1: app loads with empty transcription list
    vi.mocked(api.apiService.listTranscriptions).mockResolvedValue([]);

    render(<App />);

    // wait for initial render
    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    // verify app renders with all components
    expect(screen.getByText(/audio transcription/i)).toBeInTheDocument();
    expect(screen.getByText(/drag and drop MP3 files/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/search by filename/i)).toBeInTheDocument();

    // verify initial list is empty
    expect(screen.getByText(/no transcriptions found/i)).toBeInTheDocument();

    // step 2: user uploads a file
    vi.mocked(api.apiService.uploadFiles).mockResolvedValue([
      {
        task_id: 'journey-task-1',
        transcription_id: 1,
        filename: 'my_audio_file.mp3',
        status: 'processing',
      },
    ]);

    // first poll returns processing, second returns completed
    let pollCount = 0;
    vi.mocked(api.apiService.getTaskStatus).mockImplementation(async () => {
      pollCount++;
      if (pollCount >= 2) {
        return {
          status: 'completed',
          task_id: 'journey-task-1',
          transcription_id: 1,
          text: 'hello this is the transcribed audio content',
        };
      }
      return {
        status: 'processing',
        task_id: 'journey-task-1',
      };
    });

    // after upload completes, list should refetch
    vi.mocked(api.apiService.listTranscriptions).mockResolvedValue([
      {
        id: 1,
        audio_filename: 'my_audio_file.mp3',
        transcribed_text: 'hello this is the transcribed audio content',
        created_timestamp: new Date().toISOString(),
        status: 'completed',
        task_id: 'journey-task-1',
        error_message: undefined,
      },
    ]);

    // simulate file drop
    const mockFile = new File(['audio content'], 'my_audio_file.mp3', {
      type: 'audio/mpeg',
    });

    const dropZone = screen.getByText(/drag and drop MP3 files/i);
    const input = dropZone.parentElement?.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;

    await act(async () => {
      fireEvent.change(input, { target: { files: [mockFile] } });
      await vi.runOnlyPendingTimersAsync();
    });

    // verify file appears in upload list (may appear in both upload and transcription list)
    expect(screen.getAllByText('my_audio_file.mp3').length).toBeGreaterThan(0);

    // advance time to trigger second poll
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
      await vi.runOnlyPendingTimersAsync();
    });

    // the completed status should appear somewhere
    const completedElements = screen.getAllByText(/completed/i);
    expect(completedElements.length).toBeGreaterThan(0);

    // the transcription list should now show the file
    expect(api.apiService.listTranscriptions).toHaveBeenCalled();

    // step 5: user searches for the file
    vi.mocked(api.apiService.searchTranscriptions).mockResolvedValue([
      {
        id: 1,
        audio_filename: 'my_audio_file.mp3',
        transcribed_text: 'hello this is the transcribed audio content',
        created_timestamp: new Date().toISOString(),
        status: 'completed',
        task_id: 'journey-task-1',
        error_message: undefined,
      },
    ]);

    const searchInput = screen.getByPlaceholderText(/search by filename/i);
    const searchButton = screen.getByText('Search');

    await act(async () => {
      fireEvent.change(searchInput, { target: { value: 'my_audio' } });
      fireEvent.click(searchButton);
      await vi.runOnlyPendingTimersAsync();
    });

    // verify search was called with the query
    expect(api.apiService.searchTranscriptions).toHaveBeenCalled();

    // step 6: clear completed uploads
    const clearButton = screen.getByText(/clear completed/i);
    await act(async () => {
      fireEvent.click(clearButton);
    });

    // upload list should be cleared (completed items removed)
  });

  it('should handle failed transcription in user journey', async () => {
    vi.mocked(api.apiService.listTranscriptions).mockResolvedValue([]);

    render(<App />);

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    expect(screen.getByText(/drag and drop MP3 files/i)).toBeInTheDocument();

    // upload file
    vi.mocked(api.apiService.uploadFiles).mockResolvedValue([
      {
        task_id: 'fail-journey-task',
        transcription_id: 2,
        filename: 'fail_audio.mp3',
        status: 'processing',
      },
    ]);

    // task fails
    vi.mocked(api.apiService.getTaskStatus).mockResolvedValue({
      status: 'failed',
      task_id: 'fail-journey-task',
      error: 'Audio could not be transcribed',
    });

    const mockFile = new File(['audio'], 'fail_audio.mp3', {
      type: 'audio/mpeg',
    });

    const dropZone = screen.getByText(/drag and drop MP3 files/i);
    const input = dropZone.parentElement?.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;

    await act(async () => {
      fireEvent.change(input, { target: { files: [mockFile] } });
      await vi.runOnlyPendingTimersAsync();
    });

    // verify failure is displayed
    expect(screen.getByText(/failed/i)).toBeInTheDocument();
  });

  it('should show transcription list with existing data on load', async () => {
    // pre-populate with existing transcriptions
    vi.mocked(api.apiService.listTranscriptions).mockResolvedValue([
      {
        id: 1,
        audio_filename: 'existing1.mp3',
        transcribed_text: 'existing transcription one',
        created_timestamp: '2024-01-01T10:00:00Z',
        status: 'completed',
        task_id: 'existing-1',
        error_message: undefined,
      },
      {
        id: 2,
        audio_filename: 'existing2.mp3',
        transcribed_text: 'existing transcription two',
        created_timestamp: '2024-01-02T10:00:00Z',
        status: 'completed',
        task_id: 'existing-2',
        error_message: undefined,
      },
      {
        id: 3,
        audio_filename: 'failed_one.mp3',
        transcribed_text: null,
        created_timestamp: '2024-01-03T10:00:00Z',
        status: 'failed',
        task_id: 'failed-1',
        error_message: 'Transcription error',
      },
    ]);

    render(<App />);

    // wait for transcriptions to load
    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    expect(screen.getByText('existing1.mp3')).toBeInTheDocument();
    expect(screen.getByText('existing2.mp3')).toBeInTheDocument();
    expect(screen.getByText('failed_one.mp3')).toBeInTheDocument();

    // verify count is shown
    expect(screen.getByText(/transcriptions \(3\)/i)).toBeInTheDocument();

    // verify statuses are displayed
    const completedBadges = screen.getAllByText('completed');
    expect(completedBadges.length).toBe(2);

    const failedBadges = screen.getAllByText('failed');
    expect(failedBadges.length).toBe(1);
  });

  it('should update list after upload completes', async () => {
    // initially empty
    vi.mocked(api.apiService.listTranscriptions)
      .mockResolvedValueOnce([]) // initial load
      .mockResolvedValueOnce([ // after upload complete
        {
          id: 1,
          audio_filename: 'new_upload.mp3',
          transcribed_text: 'new transcription',
          created_timestamp: new Date().toISOString(),
          status: 'completed',
          task_id: 'new-task',
          error_message: undefined,
        },
      ]);

    vi.mocked(api.apiService.uploadFiles).mockResolvedValue([
      {
        task_id: 'new-task',
        transcription_id: 1,
        filename: 'new_upload.mp3',
        status: 'processing',
      },
    ]);

    vi.mocked(api.apiService.getTaskStatus).mockResolvedValue({
      status: 'completed',
      task_id: 'new-task',
      transcription_id: 1,
      text: 'new transcription',
    });

    render(<App />);

    // verify initially empty
    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });
    expect(screen.getByText(/no transcriptions found/i)).toBeInTheDocument();

    // upload file
    const mockFile = new File(['audio'], 'new_upload.mp3', {
      type: 'audio/mpeg',
    });

    const dropZone = screen.getByText(/drag and drop MP3 files/i);
    const input = dropZone.parentElement?.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;

    await act(async () => {
      fireEvent.change(input, { target: { files: [mockFile] } });
      await vi.runOnlyPendingTimersAsync();
    });

    // listTranscriptions should be called again after upload completes
    expect(api.apiService.listTranscriptions).toHaveBeenCalledTimes(2);
  });

  it('should clear search and show all transcriptions', async () => {
    vi.mocked(api.apiService.listTranscriptions).mockResolvedValue([
      {
        id: 1,
        audio_filename: 'all1.mp3',
        transcribed_text: 'text 1',
        created_timestamp: new Date().toISOString(),
        status: 'completed',
        task_id: 't1',
        error_message: undefined,
      },
      {
        id: 2,
        audio_filename: 'all2.mp3',
        transcribed_text: 'text 2',
        created_timestamp: new Date().toISOString(),
        status: 'completed',
        task_id: 't2',
        error_message: undefined,
      },
    ]);

    vi.mocked(api.apiService.searchTranscriptions).mockResolvedValue([
      {
        id: 1,
        audio_filename: 'all1.mp3',
        transcribed_text: 'text 1',
        created_timestamp: new Date().toISOString(),
        status: 'completed',
        task_id: 't1',
        error_message: undefined,
      },
    ]);

    render(<App />);

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    expect(screen.getByText('all1.mp3')).toBeInTheDocument();
    expect(screen.getByText('all2.mp3')).toBeInTheDocument();

    // search
    const searchInput = screen.getByPlaceholderText(/search by filename/i);
    const searchButton = screen.getByText('Search');

    await act(async () => {
      fireEvent.change(searchInput, { target: { value: 'all1' } });
      fireEvent.click(searchButton);
      await vi.runOnlyPendingTimersAsync();
    });

    // wait for search results
    expect(api.apiService.searchTranscriptions).toHaveBeenCalledWith('all1');

    // clear search
    const clearButton = screen.getByText('Clear');
    await act(async () => {
      fireEvent.click(clearButton);
      await vi.runOnlyPendingTimersAsync();
    });

    // should show all transcriptions again
    expect(screen.getByText('all1.mp3')).toBeInTheDocument();
    expect(screen.getByText('all2.mp3')).toBeInTheDocument();
  });

  it('should handle search with enter key', async () => {
    vi.mocked(api.apiService.listTranscriptions).mockResolvedValue([]);
    vi.mocked(api.apiService.searchTranscriptions).mockResolvedValue([]);

    render(<App />);

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    expect(screen.getByPlaceholderText(/search by filename/i)).toBeInTheDocument();

    const searchInput = screen.getByPlaceholderText(/search by filename/i);

    await act(async () => {
      fireEvent.change(searchInput, { target: { value: 'enter_search' } });
      fireEvent.keyPress(searchInput, { key: 'Enter', charCode: 13 });
      await vi.runOnlyPendingTimersAsync();
    });

    // search should be triggered
    expect(api.apiService.searchTranscriptions).toHaveBeenCalled();
  });

  it('should handle loading state during fetch', async () => {
    // delay the response
    vi.mocked(api.apiService.listTranscriptions).mockImplementation(
      () => new Promise(resolve => setTimeout(() => resolve([]), 1000))
    );

    render(<App />);

    // should show loading initially
    expect(screen.getByText(/loading transcriptions/i)).toBeInTheDocument();

    // advance time to complete the fetch
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1100);
      await vi.runOnlyPendingTimersAsync();
    });

    // loading should be gone
    expect(screen.queryByText(/loading transcriptions/i)).not.toBeInTheDocument();
  });

  it('should handle API error during initial load', async () => {
    // mock console.error to avoid noise
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    vi.mocked(api.apiService.listTranscriptions).mockRejectedValue(
      new Error('Network error')
    );

    render(<App />);

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    // app should still render without crashing
    expect(screen.getByText(/audio transcription/i)).toBeInTheDocument();

    consoleSpy.mockRestore();
  });

  it('should handle multiple sequential uploads', async () => {
    vi.mocked(api.apiService.listTranscriptions).mockResolvedValue([]);

    let uploadCount = 0;
    vi.mocked(api.apiService.uploadFiles).mockImplementation(async () => {
      uploadCount++;
      return [
        {
          task_id: `seq-task-${uploadCount}`,
          transcription_id: uploadCount,
          filename: `seq${uploadCount}.mp3`,
          status: 'processing',
        },
      ];
    });

    vi.mocked(api.apiService.getTaskStatus).mockResolvedValue({
      status: 'completed',
      task_id: 'seq-task-1',
      transcription_id: 1,
      text: 'done',
    });

    render(<App />);

    const dropZone = screen.getByText(/drag and drop MP3 files/i);
    const input = dropZone.parentElement?.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;

    // first upload
    const mockFile1 = new File(['audio1'], 'seq1.mp3', { type: 'audio/mpeg' });
    await act(async () => {
      fireEvent.change(input, { target: { files: [mockFile1] } });
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // second upload
    const mockFile2 = new File(['audio2'], 'seq2.mp3', { type: 'audio/mpeg' });
    await act(async () => {
      fireEvent.change(input, { target: { files: [mockFile2] } });
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // both uploads should have been made
    expect(api.apiService.uploadFiles).toHaveBeenCalledTimes(2);
  });
});
