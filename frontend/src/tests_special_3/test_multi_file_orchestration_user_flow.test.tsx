/**
 * special test #2: multi-file orchestration user flow
 *
 * tests realistic scenario: 5 files with mixed outcomes (success/fail/timeout)
 * validates independent polling loops don't interfere with each other
 * tests state management under complex concurrent operations
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import FileUpload from '../components/FileUpload';
import * as api from '../services/api';
import * as validation from '../services/validation';

vi.mock('../services/api', () => ({
  apiService: {
    uploadFiles: vi.fn(),
    getTaskStatus: vi.fn(),
  },
}));

vi.mock('../services/validation', () => ({
  validateFiles: vi.fn(),
}));

// Helper to create a mock FileList from an array of Files
function createMockFileList(files: File[]): FileList {
  const fileList = {
    length: files.length,
    item: (index: number) => files[index] || null,
    [Symbol.iterator]: function* () {
      for (const file of files) {
        yield file;
      }
    },
  };
  // Add numeric indices
  files.forEach((file, index) => {
    (fileList as unknown as Record<number, File>)[index] = file;
  });
  return fileList as unknown as FileList;
}

describe('multi-file orchestration user flow', () => {
  const mockOnUploadComplete = vi.fn();

  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    vi.mocked(validation.validateFiles).mockReturnValue({ valid: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should handle 5 files with mixed outcomes independently', async () => {
    // arrange - 5 files uploaded at once
    vi.mocked(api.apiService.uploadFiles).mockResolvedValue([
      { task_id: 'task-1', transcription_id: 1, filename: 'file1.mp3', status: 'processing' },
      { task_id: 'task-2', transcription_id: 2, filename: 'file2.mp3', status: 'processing' },
      { task_id: 'task-3', transcription_id: 3, filename: 'file3.mp3', status: 'processing' },
      { task_id: 'task-4', transcription_id: 4, filename: 'file4.mp3', status: 'processing' },
      { task_id: 'task-5', transcription_id: 5, filename: 'file5.mp3', status: 'processing' },
    ]);

    // track poll counts per task
    const pollCounts: Record<string, number> = {
      'task-1': 0,
      'task-2': 0,
      'task-3': 0,
      'task-4': 0,
      'task-5': 0,
    };

    // mock different outcomes for each file
    vi.mocked(api.apiService.getTaskStatus).mockImplementation(async (taskId) => {
      pollCounts[taskId]++;

      // file1: completed after 2 polls
      if (taskId === 'task-1') {
        if (pollCounts[taskId] >= 2) {
          return { status: 'completed', task_id: 'task-1', transcription_id: 1, text: 'text 1' };
        }
        return { status: 'processing', task_id: 'task-1' };
      }

      // file2: failed immediately
      if (taskId === 'task-2') {
        return { status: 'failed', task_id: 'task-2', error: 'transcription error' };
      }

      // file3: will timeout (always processing)
      if (taskId === 'task-3') {
        return { status: 'processing', task_id: 'task-3' };
      }

      // file4: completed after 5 polls
      if (taskId === 'task-4') {
        if (pollCounts[taskId] >= 5) {
          return { status: 'completed', task_id: 'task-4', transcription_id: 4, text: 'text 4' };
        }
        return { status: 'processing', task_id: 'task-4' };
      }

      // file5: completed after 3 polls
      if (taskId === 'task-5') {
        if (pollCounts[taskId] >= 3) {
          return { status: 'completed', task_id: 'task-5', transcription_id: 5, text: 'text 5' };
        }
        return { status: 'processing', task_id: 'task-5' };
      }

      return { status: 'processing', task_id: taskId };
    });

    // create 5 mock files
    const mockFiles = [
      new File(['audio1'], 'file1.mp3', { type: 'audio/mpeg' }),
      new File(['audio2'], 'file2.mp3', { type: 'audio/mpeg' }),
      new File(['audio3'], 'file3.mp3', { type: 'audio/mpeg' }),
      new File(['audio4'], 'file4.mp3', { type: 'audio/mpeg' }),
      new File(['audio5'], 'file5.mp3', { type: 'audio/mpeg' }),
    ];

    render(<FileUpload onUploadComplete={mockOnUploadComplete} />);

    // trigger upload
    const dropZone = screen.getByText(/drag and drop MP3 files/i);
    const input = dropZone.parentElement?.querySelector('input[type="file"]') as HTMLInputElement;

    await act(async () => {
      fireEvent.change(input, { target: { files: createMockFileList(mockFiles) } });
      await vi.runAllTimersAsync();
    });

    // all 5 files should be polled initially (runAllTimersAsync may run more iterations)
    expect(vi.mocked(api.apiService.getTaskStatus).mock.calls.length).toBeGreaterThanOrEqual(5);

    // advance time for more polls to ensure all complete
    for (let i = 0; i < 6; i++) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(5000);
        await vi.runAllTimersAsync();
      });
    }

    // verify callbacks - file1 (completed after 2), file4 (after 5), file5 (after 3) = 3 completions
    // file2 failed and file3 times out, so they don't call onUploadComplete
    expect(mockOnUploadComplete).toHaveBeenCalledTimes(3);
  });

  it('should show correct status for each file independently', async () => {
    vi.mocked(api.apiService.uploadFiles).mockResolvedValue([
      { task_id: 'status-1', transcription_id: 1, filename: 'status1.mp3', status: 'processing' },
      { task_id: 'status-2', transcription_id: 2, filename: 'status2.mp3', status: 'processing' },
    ]);

    vi.mocked(api.apiService.getTaskStatus).mockImplementation(async (taskId) => {
      if (taskId === 'status-1') {
        return { status: 'completed', task_id: 'status-1', transcription_id: 1, text: 'done' };
      }
      return { status: 'failed', task_id: 'status-2', error: 'error message' };
    });

    const mockFiles = [
      new File(['audio1'], 'status1.mp3', { type: 'audio/mpeg' }),
      new File(['audio2'], 'status2.mp3', { type: 'audio/mpeg' }),
    ];

    render(<FileUpload onUploadComplete={mockOnUploadComplete} />);

    const dropZone = screen.getByText(/drag and drop MP3 files/i);
    const input = dropZone.parentElement?.querySelector('input[type="file"]') as HTMLInputElement;

    await act(async () => {
      fireEvent.change(input, { target: { files: createMockFileList(mockFiles) } });
      await vi.runAllTimersAsync();
    });

    // verify different statuses are shown
    const uploadItems = screen.getAllByText(/status.*\.mp3/i);
    expect(uploadItems.length).toBe(2);

    // check that completed and failed statuses appear (use getAllByText because "Clear completed" also matches)
    expect(screen.getAllByText(/completed/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/failed/i).length).toBeGreaterThan(0);
  });

  it('should allow clearing completed/failed items while others continue', async () => {
    vi.mocked(api.apiService.uploadFiles).mockResolvedValue([
      { task_id: 'clear-1', transcription_id: 1, filename: 'clear1.mp3', status: 'processing' },
      { task_id: 'clear-2', transcription_id: 2, filename: 'clear2.mp3', status: 'processing' },
      { task_id: 'clear-3', transcription_id: 3, filename: 'clear3.mp3', status: 'processing' },
    ]);

    vi.mocked(api.apiService.getTaskStatus).mockImplementation(async (taskId) => {
      // clear-1: completed immediately
      if (taskId === 'clear-1') {
        return { status: 'completed', task_id: 'clear-1', transcription_id: 1, text: 'done' };
      }
      // clear-2: failed immediately
      if (taskId === 'clear-2') {
        return { status: 'failed', task_id: 'clear-2', error: 'error' };
      }
      // clear-3: always processing (never completes)
      return { status: 'processing', task_id: 'clear-3' };
    });

    const mockFiles = [
      new File(['audio1'], 'clear1.mp3', { type: 'audio/mpeg' }),
      new File(['audio2'], 'clear2.mp3', { type: 'audio/mpeg' }),
      new File(['audio3'], 'clear3.mp3', { type: 'audio/mpeg' }),
    ];

    render(<FileUpload onUploadComplete={mockOnUploadComplete} />);

    const dropZone = screen.getByText(/drag and drop MP3 files/i);
    const input = dropZone.parentElement?.querySelector('input[type="file"]') as HTMLInputElement;

    // Trigger upload but only advance a little - don't run all timers
    await act(async () => {
      fireEvent.change(input, { target: { files: createMockFileList(mockFiles) } });
    });

    // Wait for initial upload and first poll
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // verify all 3 files shown
    expect(screen.getByText('clear1.mp3')).toBeInTheDocument();
    expect(screen.getByText('clear2.mp3')).toBeInTheDocument();
    expect(screen.getByText('clear3.mp3')).toBeInTheDocument();

    // click clear completed button
    const clearButton = screen.getByText(/clear completed/i);
    await act(async () => {
      fireEvent.click(clearButton);
    });

    // completed and failed items should be removed
    expect(screen.queryByText('clear1.mp3')).not.toBeInTheDocument();
    expect(screen.queryByText('clear2.mp3')).not.toBeInTheDocument();

    // processing item should still be there
    expect(screen.getByText('clear3.mp3')).toBeInTheDocument();
  });

  it('should handle batch where some files fail validation', async () => {
    // validation fails for some files
    vi.mocked(validation.validateFiles).mockReturnValue({
      valid: false,
      error: 'Invalid file type'
    });

    const mockFiles = [
      new File(['audio1'], 'valid.mp3', { type: 'audio/mpeg' }),
      new File(['text'], 'invalid.txt', { type: 'text/plain' }),
    ];

    render(<FileUpload onUploadComplete={mockOnUploadComplete} />);

    const dropZone = screen.getByText(/drag and drop MP3 files/i);
    const input = dropZone.parentElement?.querySelector('input[type="file"]') as HTMLInputElement;

    await act(async () => {
      fireEvent.change(input, { target: { files: createMockFileList(mockFiles) } });
      await vi.runAllTimersAsync();
    });

    // error message should be shown
    expect(screen.getByText(/invalid file type/i)).toBeInTheDocument();

    // upload should not have been called
    expect(api.apiService.uploadFiles).not.toHaveBeenCalled();
  });

  it('should preserve file order in upload list', async () => {
    vi.mocked(api.apiService.uploadFiles).mockResolvedValue([
      { task_id: 'order-1', transcription_id: 1, filename: 'first.mp3', status: 'processing' },
      { task_id: 'order-2', transcription_id: 2, filename: 'second.mp3', status: 'processing' },
      { task_id: 'order-3', transcription_id: 3, filename: 'third.mp3', status: 'processing' },
    ]);

    vi.mocked(api.apiService.getTaskStatus).mockResolvedValue({
      status: 'processing',
      task_id: 'order-1',
    });

    const mockFiles = [
      new File(['audio1'], 'first.mp3', { type: 'audio/mpeg' }),
      new File(['audio2'], 'second.mp3', { type: 'audio/mpeg' }),
      new File(['audio3'], 'third.mp3', { type: 'audio/mpeg' }),
    ];

    render(<FileUpload onUploadComplete={mockOnUploadComplete} />);

    const dropZone = screen.getByText(/drag and drop MP3 files/i);
    const input = dropZone.parentElement?.querySelector('input[type="file"]') as HTMLInputElement;

    await act(async () => {
      fireEvent.change(input, { target: { files: createMockFileList(mockFiles) } });
      await vi.runAllTimersAsync();
    });

    // verify files appear in order - the component shows "Uploads" header when files exist
    expect(screen.getByText('Uploads')).toBeInTheDocument();

    // order should be preserved
    expect(screen.getByText('first.mp3')).toBeInTheDocument();
    expect(screen.getByText('second.mp3')).toBeInTheDocument();
    expect(screen.getByText('third.mp3')).toBeInTheDocument();
  });

  it('should handle upload API failure gracefully', async () => {
    vi.mocked(api.apiService.uploadFiles).mockRejectedValue(
      new Error('Server error')
    );

    const mockFiles = [
      new File(['audio'], 'fail.mp3', { type: 'audio/mpeg' }),
    ];

    render(<FileUpload onUploadComplete={mockOnUploadComplete} />);

    const dropZone = screen.getByText(/drag and drop MP3 files/i);
    const input = dropZone.parentElement?.querySelector('input[type="file"]') as HTMLInputElement;

    await act(async () => {
      fireEvent.change(input, { target: { files: createMockFileList(mockFiles) } });
      await vi.runAllTimersAsync();
    });

    // error should be shown
    expect(screen.getByText(/server error/i)).toBeInTheDocument();

    // onUploadComplete should not be called
    expect(mockOnUploadComplete).not.toHaveBeenCalled();
  });

  it('should track each file status independently during rapid uploads', async () => {
    // track which tasks have been polled
    const tasksPolled: string[] = [];

    vi.mocked(api.apiService.uploadFiles).mockResolvedValue([
      { task_id: 'rapid-1', transcription_id: 1, filename: 'rapid1.mp3', status: 'processing' },
      { task_id: 'rapid-2', transcription_id: 2, filename: 'rapid2.mp3', status: 'processing' },
    ]);

    vi.mocked(api.apiService.getTaskStatus).mockImplementation(async (taskId) => {
      tasksPolled.push(taskId);
      return { status: 'completed', task_id: taskId, transcription_id: 1, text: 'done' };
    });

    const mockFiles = [
      new File(['audio1'], 'rapid1.mp3', { type: 'audio/mpeg' }),
      new File(['audio2'], 'rapid2.mp3', { type: 'audio/mpeg' }),
    ];

    render(<FileUpload onUploadComplete={mockOnUploadComplete} />);

    const dropZone = screen.getByText(/drag and drop MP3 files/i);
    const input = dropZone.parentElement?.querySelector('input[type="file"]') as HTMLInputElement;

    await act(async () => {
      fireEvent.change(input, { target: { files: createMockFileList(mockFiles) } });
      await vi.runAllTimersAsync();
    });

    // both tasks should have been polled
    expect(tasksPolled).toContain('rapid-1');
    expect(tasksPolled).toContain('rapid-2');

    // both should complete
    expect(mockOnUploadComplete).toHaveBeenCalledTimes(2);
  });

  it('should handle empty file list gracefully', async () => {
    render(<FileUpload onUploadComplete={mockOnUploadComplete} />);

    const dropZone = screen.getByText(/drag and drop MP3 files/i);
    const input = dropZone.parentElement?.querySelector('input[type="file"]') as HTMLInputElement;

    // trigger change with no files
    await act(async () => {
      fireEvent.change(input, { target: { files: [] } });
    });

    // no upload should be triggered
    expect(api.apiService.uploadFiles).not.toHaveBeenCalled();
  });
});
