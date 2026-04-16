"use client";

import { useEffect } from "react";
import Link from "next/link";

export default function ResultError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Result error boundary caught:", error);
  }, [error]);

  return (
    <div className="min-h-[60vh] flex items-center justify-center p-8">
      <div
        role="alert"
        className="mtg-card p-8 max-w-md text-center space-y-4 animate-fade-in"
      >
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
              d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
            />
          </svg>
        </div>
        <h2 className="text-lg font-semibold text-mtg-text">
          Failed to load result
        </h2>
        <p className="text-sm text-mtg-subtle">
          {error.message || "Unable to load this result."}
        </p>
        <div className="flex justify-center gap-3">
          <button type="button" onClick={reset} className="mtg-btn-ghost">
            Retry
          </button>
          <Link href="/" className="mtg-btn-ghost">
            New scan
          </Link>
        </div>
      </div>
    </div>
  );
}
