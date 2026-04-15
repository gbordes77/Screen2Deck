'use client';

import { useEffect } from 'react';

export default function ResultError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.error('Result error boundary caught:', error);
  }, [error]);

  return (
    <main role="alert" className="p-8 text-red-400">
      <h2 className="text-xl font-semibold mb-2">Result error</h2>
      <p className="text-sm mb-4">{error.message || 'Unable to load this result.'}</p>
      <button
        type="button"
        onClick={reset}
        className="px-3 py-2 rounded-xl bg-white/10 hover:bg-white/20"
      >
        Retry
      </button>
    </main>
  );
}
