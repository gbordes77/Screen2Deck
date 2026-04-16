"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, upload } from "@/lib/api";

function Spinner() {
  return (
    <svg
      className="animate-spin h-5 w-5"
      viewBox="0 0 24 24"
      aria-hidden="true"
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
  );
}

const FORMATS = [
  { label: "MTGA", desc: "Arena import" },
  { label: "Moxfield", desc: "Deck builder" },
  { label: "Archidekt", desc: "Analysis" },
  { label: "TappedOut", desc: "Community" },
];

export default function Page() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  const handleFile = useCallback((f: File | null) => {
    setFile(f);
    setError("");
    if (f) {
      const url = URL.createObjectURL(f);
      setPreview(url);
    } else {
      setPreview(null);
    }
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const f = e.dataTransfer.files[0];
      if (f && f.type.startsWith("image/")) handleFile(f);
    },
    [handleFile],
  );

  const onSubmit = async () => {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const jobId = await upload(file);
      router.push(`/result/${jobId}`);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`Upload failed (${err.status}): ${err.body || err.message}`);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Upload failed. Please try again.");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="bg-dark-gradient min-h-[calc(100vh-8rem)]">
      {/* Hero */}
      <section className="max-w-4xl mx-auto px-4 sm:px-6 pt-12 pb-8 text-center">
        <h1 className="text-4xl sm:text-5xl font-bold tracking-tight mb-3">
          <span className="text-mtg-gold">Screenshot</span> to{" "}
          <span className="text-mtg-gold">Deck List</span>
        </h1>
        <p className="text-mtg-subtle text-lg max-w-2xl mx-auto">
          Upload a screenshot of your Magic: The Gathering deck and get a
          Scryfall-validated, exportable list in seconds.
        </p>
      </section>

      {/* Upload zone */}
      <section className="max-w-3xl mx-auto px-4 sm:px-6 pb-16">
        <div className="mtg-card p-6 sm:p-8 space-y-6 animate-fade-in">
          {/* Drop zone */}
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
            }}
            aria-label="Upload deck screenshot"
            className={`
              relative rounded-lg border-2 border-dashed p-8 sm:p-12
              text-center cursor-pointer transition-all duration-200
              ${
                dragOver
                  ? "border-mtg-gold bg-mtg-gold/5 shadow-gold"
                  : preview
                    ? "border-mtg-gold/40 bg-mtg-gold/5"
                    : "border-mtg-border hover:border-mtg-gold/40 hover:bg-mtg-surface"
              }
            `}
          >
            <input
              ref={inputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => handleFile(e.target.files?.[0] ?? null)}
            />

            {preview ? (
              <div className="space-y-4">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={preview}
                  alt="Deck screenshot preview"
                  className="max-h-64 mx-auto rounded-lg shadow-card object-contain"
                />
                <div className="text-sm text-mtg-subtle">
                  <span className="font-medium text-mtg-text">
                    {file?.name}
                  </span>{" "}
                  &mdash;{" "}
                  {file ? (file.size / 1024 / 1024).toFixed(2) : "0"} MB
                </div>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleFile(null);
                    if (inputRef.current) inputRef.current.value = "";
                  }}
                  className="text-sm text-mtg-subtle hover:text-mtg-red transition-colors"
                >
                  Remove
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="w-16 h-16 mx-auto rounded-full bg-mtg-gold/10 flex items-center justify-center">
                  <svg
                    className="w-8 h-8 text-mtg-gold"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth="1.5"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
                    />
                  </svg>
                </div>
                <div>
                  <p className="text-mtg-text font-medium">
                    Drop your deck screenshot here
                  </p>
                  <p className="text-sm text-mtg-subtle mt-1">
                    or click to browse &mdash; PNG / JPG, up to 8 MB
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Error */}
          <div aria-live="polite" role="status">
            {error && (
              <div className="p-4 bg-mtg-red/10 border border-mtg-red/20 rounded-lg text-red-400 text-sm animate-fade-in">
                {error}
              </div>
            )}
          </div>

          {/* Analyze button */}
          <button
            type="button"
            disabled={!file || busy}
            onClick={onSubmit}
            aria-busy={busy}
            className="mtg-btn-gold w-full flex items-center justify-center gap-3 text-lg"
          >
            {busy ? (
              <>
                <Spinner />
                Analyzing deck...
              </>
            ) : (
              <>
                <svg
                  className="w-5 h-5"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
                  />
                </svg>
                Analyze Deck
              </>
            )}
          </button>

          {/* Processing info */}
          {busy && (
            <div
              role="status"
              aria-live="polite"
              className="p-4 bg-mtg-blue/10 border border-mtg-blue/20 rounded-lg text-blue-300 text-sm animate-slide-up"
            >
              <strong>Vision AI is processing your image.</strong> This
              typically takes 3&ndash;5 seconds. On first run, EasyOCR models
              (~64&nbsp;MB) may need to download.
            </div>
          )}
        </div>

        {/* Features grid */}
        <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="mtg-card p-5 animate-slide-up">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-lg bg-mtg-gold/10 flex items-center justify-center flex-shrink-0">
                <svg
                  className="w-5 h-5 text-mtg-gold"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth="1.5"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                  />
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-sm text-mtg-text">
                  Vision AI Primary
                </h3>
                <p className="text-xs text-mtg-subtle mt-1">
                  Gemini 2.5 Flash with typed JSON output. EasyOCR as fallback.
                </p>
              </div>
            </div>
          </div>

          <div className="mtg-card p-5 animate-slide-up">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-lg bg-mtg-green/10 flex items-center justify-center flex-shrink-0">
                <svg
                  className="w-5 h-5 text-mtg-green"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth="1.5"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-sm text-mtg-text">
                  Scryfall Validated
                </h3>
                <p className="text-xs text-mtg-subtle mt-1">
                  Every card verified via Scryfall batch API. Split, DFC, and
                  Adventure cards supported.
                </p>
              </div>
            </div>
          </div>

          <div className="mtg-card p-5 animate-slide-up">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-lg bg-mtg-blue/10 flex items-center justify-center flex-shrink-0">
                <svg
                  className="w-5 h-5 text-mtg-blue"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth="1.5"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3"
                  />
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-sm text-mtg-text">
                  Multi-Format Export
                </h3>
                <p className="text-xs text-mtg-subtle mt-1">
                  One-click copy to MTGA, Moxfield, Archidekt, or TappedOut.
                </p>
              </div>
            </div>
          </div>

          <div className="mtg-card p-5 animate-slide-up">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-lg bg-mtg-red/10 flex items-center justify-center flex-shrink-0">
                <svg
                  className="w-5 h-5 text-mtg-red"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth="1.5"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z"
                  />
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-sm text-mtg-text">
                  Fast Processing
                </h3>
                <p className="text-xs text-mtg-subtle mt-1">
                  ~3s typical. Idempotent caching via image hash for instant
                  re-uploads.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Supported formats */}
        <div className="mt-8 text-center">
          <p className="text-xs text-mtg-muted mb-3">EXPORT FORMATS</p>
          <div className="flex justify-center gap-3 flex-wrap">
            {FORMATS.map((f) => (
              <span
                key={f.label}
                className="px-3 py-1.5 text-xs rounded-full border border-mtg-border text-mtg-subtle"
              >
                {f.label}
              </span>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
