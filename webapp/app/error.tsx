'use client';

import { useEffect } from 'react';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.error('Root error boundary caught:', error);
  }, [error]);

  return (
    <main
      role="alert"
      className="min-h-screen p-8 bg-neutral-950 text-neutral-100 flex items-center justify-center"
    >
      <div className="max-w-md w-full space-y-4">
        <h1 className="text-2xl font-semibold">Something went wrong</h1>
        <p className="text-sm text-neutral-400">
          {error.message || 'An unexpected error occurred while rendering this page.'}
        </p>
        <button
          type="button"
          onClick={reset}
          className="px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
        >
          Try again
        </button>
      </div>
    </main>
  );
}
