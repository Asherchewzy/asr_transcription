import { useState, useEffect, useCallback } from 'react';
import FileUpload from './components/FileUpload';
import TranscriptionList from './components/TranscriptionList';
import SearchBar from './components/SearchBar';
import { apiService } from './services/api';
import type { Transcription } from './types/transcription';
import './App.css';

function App() {
  const [transcriptions, setTranscriptions] = useState<Transcription[]>([]);
  const [searchResults, setSearchResults] = useState<Transcription[]>([]);
  const [loading, setLoading] = useState(false);
  const [isSearching, setIsSearching] = useState(false);

  const fetchTranscriptions = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiService.listTranscriptions();
      setTranscriptions(data);
    } catch (err) {
      console.error('Failed to fetch transcriptions:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTranscriptions();
  }, [fetchTranscriptions]);

  const handleUploadComplete = () => {
    fetchTranscriptions();
  };

  const handleSearch = async (query: string) => {
    if (!query) {
      setSearchResults([]);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    try {
      const results = await apiService.searchTranscriptions(query);
      setSearchResults(results);
    } catch (err) {
      console.error('Search failed:', err);
      setSearchResults([]);
    }
  };

  return (
    <div className="app">
      <header>
        <h1>Audio Transcription</h1>
      </header>

      <main>
        <FileUpload onUploadComplete={handleUploadComplete} />

        <SearchBar onSearch={handleSearch} />

        <TranscriptionList
          transcriptions={isSearching ? searchResults : transcriptions}
          loading={loading}
        />
      </main>
    </div>
  );
}

export default App;
