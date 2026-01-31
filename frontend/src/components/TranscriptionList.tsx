import type { Transcription } from '../types/transcription';

interface TranscriptionListProps {
  transcriptions: Transcription[];
  loading?: boolean;
}

export default function TranscriptionList({ transcriptions, loading }: TranscriptionListProps) {
  if (loading) {
    return (
      <div className="transcription-list-container">
        <h2>Transcriptions</h2>
        <div className="loading">Loading transcriptions...</div>
      </div>
    );
  }

  if (transcriptions.length === 0) {
    return (
      <div className="transcription-list-container">
        <h2>Transcriptions</h2>
        <div className="empty-state">No transcriptions found.</div>
      </div>
    );
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  return (
    <div className="transcription-list-container">
      <h2>Transcriptions ({transcriptions.length})</h2>
      <div className="transcription-list">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Filename</th>
              <th>Status</th>
              <th>Transcribed Text</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {transcriptions.map(t => (
              <tr key={t.id} className={`status-${t.status}`}>
                <td>{t.id}</td>
                <td className="filename-cell">{t.audio_filename}</td>
                <td>
                  <span className={`status-badge ${t.status}`}>
                    {t.status}
                  </span>
                </td>
                <td className="text-cell">
                  {t.status === 'completed' && t.transcribed_text ? (
                    <div className="transcribed-text">{t.transcribed_text}</div>
                  ) : t.status === 'failed' && t.error_message ? (
                    <div className="error-text">{t.error_message}</div>
                  ) : (
                    <div className="no-text">-</div>
                  )}
                </td>
                <td className="date-cell">{formatDate(t.created_timestamp)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
