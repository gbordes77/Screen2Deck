'use client';
import { useState } from 'react';
import { upload } from '@/lib/api';
import { useRouter } from 'next/navigation';

export default function Page() {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>('');
  const router = useRouter();
  
  const onSubmit = async () => {
    if (!file) return;
    setBusy(true);
    setError('');
    
    try {
      const jobId = await upload(file);
      router.push(`/result/${jobId}`);
    } catch (err: any) {
      setError(err?.message || 'Upload failed. Please try again.');
    } finally {
      setBusy(false);
    }
  };
  
  return (
    <main className="min-h-screen p-8 bg-neutral-950 text-neutral-100">
      <div className="max-w-3xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">MTG Deck Scanner</h1>
        
        <div className="p-6 border border-neutral-800 rounded-2xl space-y-4">
          {/* File input with preview */}
          <div>
            <input 
              type="file" 
              accept="image/*" 
              onChange={e => {
                setFile(e.target.files?.[0] || null);
                setError('');
              }} 
              className="mb-2 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-white/10 file:text-neutral-100 hover:file:bg-white/20"
            />
            {file && (
              <p className="text-sm text-neutral-400">
                Selected: {file.name} ({(file.size / 1024 / 1024).toFixed(2)} MB)
              </p>
            )}
          </div>
          
          {/* Error display */}
          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400">
              {error}
            </div>
          )}
          
          {/* Submit button with loading state */}
          <button 
            disabled={!file || busy} 
            onClick={onSubmit} 
            className="px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          >
            {busy ? (
              <>
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Processing...
              </>
            ) : (
              'Analyze Deck'
            )}
          </button>
        </div>
        
        {/* Instructions */}
        <div className="mt-6 p-4 bg-white/5 rounded-xl">
          <h2 className="font-semibold mb-2">How to use:</h2>
          <ol className="text-sm text-neutral-400 space-y-1 list-decimal list-inside">
            <li>Take a screenshot of your MTG deck list</li>
            <li>Upload the image using the file selector above</li>
            <li>Wait for OCR processing (typically 2-5 seconds)</li>
            <li>Export to your preferred format (MTGA, Moxfield, etc.)</li>
          </ol>
        </div>
      </div>
    </main>
  );
}