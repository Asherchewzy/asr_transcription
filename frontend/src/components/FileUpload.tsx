import { useState, useRef, useEffect, type DragEvent, type ChangeEvent } from 'react';
import { apiService } from '../services/api';
import { validateFiles } from '../services/validation';
import type { TaskResponse, TaskStatus } from '../types/transcription';

interface FileUploadProps {
  onUploadComplete: () => void;
}

interface UploadingFile {
  file: File;
  taskId?: string;
  status: 'pending' | 'uploading' | 'processing' | 'completed' | 'failed';
  error?: string;
}

export default function FileUpload({ onUploadComplete }: FileUploadProps) {
  const [uploadingFiles, setUploadingFiles] = useState<UploadingFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const timersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  // Cleanup timers on component unmount
  useEffect(() => {
    const timers = timersRef.current;
    return () => {
      timers.forEach(timer => clearTimeout(timer));
      timers.clear();
    };
  }, []);

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;

    const fileArray = Array.from(files);
    const validation = validateFiles(fileArray);

    if (!validation.valid) {
      setError(validation.error || 'Invalid files');
      return;
    }

    setError(null);

    // Add files to uploading list
    const newFiles: UploadingFile[] = fileArray.map(file => ({
      file,
      status: 'uploading'
    }));
    setUploadingFiles(prev => [...prev, ...newFiles]);

    try {
      // Upload files
      const tasks: TaskResponse[] = await apiService.uploadFiles(fileArray);

      // Update with task IDs
      setUploadingFiles(prev =>
        prev.map((uf) => {
          if (newFiles.includes(uf)) {
            const taskIdx = newFiles.indexOf(uf);
            return {
              ...uf,
              taskId: tasks[taskIdx].task_id,
              status: 'processing'
            };
          }
          return uf;
        })
      );

      // Poll for each task
      tasks.forEach((task) => {
        pollTaskStatus(task.task_id);
      });

    } catch (err) {
      const message = err instanceof Error ? err.message : 'Upload failed';
      setError(message);
      setUploadingFiles(prev =>
        prev.map(uf =>
          newFiles.includes(uf) ? { ...uf, status: 'failed', error: 'Upload failed' } : uf
        )
      );
    }
  };

  const pollTaskStatus = async (taskId: string) => {
    const maxAttempts = 60; // 60 attempts = 5 minutes (5s interval)
    let attempts = 0;

    const poll = async () => {
      try {
        const status: TaskStatus = await apiService.getTaskStatus(taskId);

        if (status.status === 'completed') {
          setUploadingFiles(prev =>
            prev.map(uf =>
              uf.taskId === taskId ? { ...uf, status: 'completed' } : uf
            )
          );
          timersRef.current.delete(taskId); // Clean up timer reference
          onUploadComplete();
          return;
        }

        if (status.status === 'failed') {
          setUploadingFiles(prev =>
            prev.map(uf =>
              uf.taskId === taskId ? { ...uf, status: 'failed', error: status.error } : uf
            )
          );
          timersRef.current.delete(taskId); // Clean up timer reference
          return;
        }

        // Still processing, poll again
        if (attempts < maxAttempts) {
          attempts++;
          const timerId = setTimeout(poll, 5000); // Poll every 5 seconds
          timersRef.current.set(taskId, timerId); // Track timer ID
        } else {
          setUploadingFiles(prev =>
            prev.map(uf =>
              uf.taskId === taskId ? { ...uf, status: 'failed', error: 'Timeout' } : uf
            )
          );
          timersRef.current.delete(taskId); // Clean up timer reference
        }
      } catch {
        setUploadingFiles(prev =>
          prev.map(uf =>
            uf.taskId === taskId ? { ...uf, status: 'failed', error: 'Status check failed' } : uf
          )
        );
        timersRef.current.delete(taskId); // Clean up timer reference
      }
    };

    poll();
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  const handleFileInput = (e: ChangeEvent<HTMLInputElement>) => {
    handleFiles(e.target.files);
  };

  const handleClick = () => {
    fileInputRef.current?.click();
  };

  const clearCompleted = () => {
    setUploadingFiles(prev =>
      prev.filter(uf => uf.status !== 'completed' && uf.status !== 'failed')
    );
  };

  return (
    <div className="file-upload">
      <div
        className={`drop-zone ${isDragging ? 'dragging' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleClick}
      >
        <p>Drag and drop MP3 files here or click to browse</p>
        <input
          ref={fileInputRef}
          type="file"
          accept="audio/mpeg,audio/mp3"
          multiple
          onChange={handleFileInput}
          style={{ display: 'none' }}
        />
      </div>

      {error && (
        <div className="error-message">
          {error}
        </div>
      )}

      {uploadingFiles.length > 0 && (
        <div className="upload-list">
          <div className="upload-list-header">
            <h3>Uploads</h3>
            <button onClick={clearCompleted} className="clear-button">
              Clear completed
            </button>
          </div>
          {uploadingFiles.map((uf, idx) => (
            <div key={idx} className={`upload-item ${uf.status}`}>
              <span className="filename">{uf.file.name}</span>
              <span className="status">{uf.status}</span>
              {uf.error && <span className="error">{uf.error}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
