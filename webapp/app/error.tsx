"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Root error boundary caught:", error);
  }, [error]);

  return (
    <div className="min-h-[60vh] flex items-center justify-center p-8">
      <div className="mtg-card p-8 max-w-md w-full text-center space-y-4 animate-fade-in">
        <div className="w-14 h-14 mx-auto rounded-full bg-mtg-red/10 flex items-center justify-center">
          <svg
            className="w-7 h-7 text-mtg-red"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126z"
            />
          </svg>
        </div>
        <h1 className="text-xl font-semibold text-mtg-text">
          Something went wrong
        </h1>
        <p className="text-sm text-mtg-subtle">
          {error.message || "An unexpected error occurred."}
        </p>
        <button type="button" onClick={reset} className="mtg-btn-ghost">
          Try again
        </button>
      </div>
    </div>
  );
}
