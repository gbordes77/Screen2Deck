'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ApiError, upload } from '@/lib/api';

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
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`Upload failed (${err.status}): ${err.body || err.message}`);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Upload failed. Please try again.');
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="min-h-screen p-8 bg-neutral-950 text-neutral-100">
      <div className="max-w-3xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">Screen2Deck</h1>

        <div className="p-6 border border-neutral-800 rounded-2xl space-y-4">
          <div>
            <label
              htmlFor="deck-image"
              className="block text-sm font-medium mb-2"
            >
              Deck screenshot
              <span className="block text-xs text-neutral-400 font-normal mt-1">
                PNG or JPG, up to 8 MB.
              </span>
            </label>
            <input
              id="deck-image"
              type="file"
              accept="image/*"
              aria-describedby="file-hint"
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null);
                setError('');
              }}
              className="mb-2 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-white/10 file:text-neutral-100 hover:file:bg-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
            />
            {file && (
              <p id="file-hint" className="text-sm text-neutral-400">
                Selected: {file.name} ({(file.size / 1024 / 1024).toFixed(2)} MB)
              </p>
            )}
          </div>

          <div aria-live="polite" role="status" className="contents">
            {error && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400">
                {error}
              </div>
            )}
          </div>

          <button
            type="button"
            disabled={!file || busy}
            onClick={onSubmit}
            aria-busy={busy}
            className="px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
          >
            {busy ? (
              <>
                <svg
                  className="animate-spin h-4 w-4"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                  focusable="false"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                    fill="none"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Processing…
              </>
            ) : (
              'Analyze Deck'
            )}
          </button>

          {busy && (
            <div
              role="status"
              aria-live="polite"
              className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg text-blue-400 text-sm"
            >
              <strong>First-time setup:</strong> If this is your first upload,
              EasyOCR is downloading models (~64&nbsp;MB). This takes 2–3
              minutes but only happens once. Subsequent scans will be fast
              (3–5&nbsp;seconds).
            </div>
          )}
        </div>

        <div className="mt-6 p-4 bg-white/5 rounded-xl">
          <h2 className="font-semibold mb-2">How to use</h2>
          <ol className="text-sm text-neutral-400 space-y-1 list-decimal list-inside">
            <li>Take a screenshot of your MTG deck list.</li>
            <li>Upload the image using the file selector above.</li>
            <li>Wait for OCR processing (typically 2–5 seconds).</li>
            <li>Export to your preferred format (MTGA, Moxfield, etc.).</li>
          </ol>
        </div>
      </div>
    </main>
  );
}
