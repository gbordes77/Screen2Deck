"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, upload } from "@/lib/api";

function Spinner() {
  return (
    <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24" aria-hidden="true">
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

/* ------------------------------------------------------------------------ */
/* Mana symbols — 5 circles of WUBRG, rendered as styled SVGs              */
/* ------------------------------------------------------------------------ */

function ManaSymbolRow() {
  return (
    <div
      className="flex items-center justify-center gap-2.5 mb-10 animate-fade-in"
      role="presentation"
      aria-hidden="true"
    >
      <span className="mana-circle mana-circle--white">
        {/* Sun (white) */}
        <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
          <path d="M12 5a7 7 0 100 14 7 7 0 000-14zm0 2a5 5 0 110 10 5 5 0 010-10z" />
          <g stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            <line x1="12" y1="1" x2="12" y2="3" />
            <line x1="12" y1="21" x2="12" y2="23" />
            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
            <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
            <line x1="1" y1="12" x2="3" y2="12" />
            <line x1="21" y1="12" x2="23" y2="12" />
            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
            <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
          </g>
        </svg>
      </span>
      <span className="mana-circle mana-circle--blue">
        {/* Water drop (blue) */}
        <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
          <path d="M12 2c-1 2.5-6 8-6 13a6 6 0 1012 0c0-5-5-10.5-6-13z" />
        </svg>
      </span>
      <span className="mana-circle mana-circle--black">
        {/* Skull (black) */}
        <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
          <path d="M12 3a7 7 0 00-7 7v3.5l-1 2v1.5a1 1 0 001 1h2v1.5a1.5 1.5 0 001.5 1.5h7A1.5 1.5 0 0017 18.5V17h2a1 1 0 001-1v-1.5l-1-2V10a7 7 0 00-7-7zm-2.5 7a1.5 1.5 0 11.001 2.999A1.5 1.5 0 019.5 10zm5 0a1.5 1.5 0 110 3 1.5 1.5 0 010-3z" />
        </svg>
      </span>
      <span className="mana-circle mana-circle--red">
        {/* Fire/flame (red) */}
        <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
          <path d="M13.5 2c.2 3.6-2.5 5.5-4 7.5C8 11.5 7 13 7 15a5 5 0 0010 0c0-2.5-1.8-4.5-3-6 1.5-1 2-2.5 2-4 0-1-.5-2-2.5-3z" />
        </svg>
      </span>
      <span className="mana-circle mana-circle--green">
        {/* Tree (green) */}
        <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
          <path d="M12 2L7 9h3l-3 5h3l-3 5h10l-3-5h3l-3-5h3L12 2zm-1 18h2v2h-2z" />
        </svg>
      </span>
    </div>
  );
}

/* ------------------------------------------------------------------------ */
/* Background decorative mana symbol glyph (faded corners)                 */
/* ------------------------------------------------------------------------ */

function BgCornerSun() {
  return (
    <svg
      viewBox="0 0 120 120"
      className="bg-mana-corner top-24 left-4 sm:left-16 w-20 sm:w-28"
      fill="#E0B23A"
      aria-hidden="true"
    >
      <circle cx="60" cy="60" r="22" />
      <g stroke="#E0B23A" strokeWidth="3" strokeLinecap="round">
        <line x1="60" y1="18" x2="60" y2="30" />
        <line x1="60" y1="90" x2="60" y2="102" />
        <line x1="18" y1="60" x2="30" y2="60" />
        <line x1="90" y1="60" x2="102" y2="60" />
        <line x1="30" y1="30" x2="38" y2="38" />
        <line x1="82" y1="82" x2="90" y2="90" />
        <line x1="30" y1="90" x2="38" y2="82" />
        <line x1="82" y1="38" x2="90" y2="30" />
      </g>
    </svg>
  );
}

function BgCornerDrop() {
  return (
    <svg
      viewBox="0 0 120 120"
      className="bg-mana-corner top-60 right-4 sm:right-16 w-20 sm:w-28"
      fill="#2F5BA8"
      aria-hidden="true"
    >
      <path d="M60 10c-6 14-30 42-30 66a30 30 0 0060 0c0-24-24-52-30-66z" />
    </svg>
  );
}

/* ------------------------------------------------------------------------ */

export default function Page() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const uploadCardRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  const handleFile = useCallback((f: File | null) => {
    setFile(f);
    setError("");
    if (f) {
      setPreview(URL.createObjectURL(f));
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

  const scrollToUpload = () => {
    uploadCardRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    setTimeout(() => inputRef.current?.focus(), 400);
  };

  return (
    <div className="relative overflow-hidden">
      <BgCornerSun />
      <BgCornerDrop />

      {/* ---------- Hero ---------- */}
      <section className="relative z-10 max-w-4xl mx-auto px-4 sm:px-6 pt-12 sm:pt-16 pb-10 text-center">
        <ManaSymbolRow />

        <h1 className="brand-title font-heading animate-fade-in mb-6">
          The Scryfall-Validated
          <br />
          MTG Deck Scanner
        </h1>

        <p
          className="text-mtg-text text-lg sm:text-xl max-w-2xl mx-auto leading-relaxed animate-fade-in"
          style={{ animationDelay: "120ms" }}
        >
          Stop typing decks by hand. Upload a screenshot and get an{" "}
          <strong className="font-semibold">exportable deck list</strong> in{" "}
          <strong className="font-semibold">under 5 seconds</strong>.
        </p>

        <p
          className="text-mtg-subtle italic mt-4 animate-fade-in"
          style={{ animationDelay: "200ms" }}
        >
          Works with MTGA, MTGO, Moxfield, Archidekt, and paper card photos.
        </p>

        {/* Info callout */}
        <div
          className="info-callout max-w-2xl mx-auto mt-8 text-left animate-slide-up"
          style={{ animationDelay: "280ms" }}
        >
          <p className="flex items-start gap-2 text-mtg-text text-sm sm:text-base">
            <span aria-hidden="true" className="text-lg">🔮</span>
            <span>
              <strong className="font-semibold">Vision AI + Scryfall.</strong>{" "}
              Gemini 2.5 Flash reads your screenshot with typed JSON output, then
              every card name is validated against the official Scryfall
              database — split, DFC and Adventure cards included.
            </span>
          </p>
        </div>

        {/* Feature chips */}
        <div
          className="flex flex-wrap justify-center gap-2 mt-8 animate-slide-up"
          style={{ animationDelay: "360ms" }}
        >
          <span className="feature-chip feature-chip--blue">
            <span aria-hidden="true">💧</span> Vision-First OCR
          </span>
          <span className="feature-chip feature-chip--green">
            <span aria-hidden="true">✅</span> Scryfall Validated
          </span>
          <span className="feature-chip feature-chip--pink">
            <span aria-hidden="true">⚡</span> 4-Format Export
          </span>
        </div>

        {/* CTAs */}
        <div
          className="flex flex-col sm:flex-row justify-center gap-3 mt-10 animate-slide-up"
          style={{ animationDelay: "440ms" }}
        >
          <button
            type="button"
            onClick={scrollToUpload}
            className="cta-pill cta-pill--gold"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
              />
            </svg>
            Scan My Deck
          </button>
          <a
            href="https://github.com/gbordes77/Screen2Deck"
            target="_blank"
            rel="noopener noreferrer"
            className="cta-pill cta-pill--navy"
          >
            <svg
              className="w-5 h-5"
              fill="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61-.546-1.385-1.335-1.755-1.335-1.755-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
            </svg>
            View on GitHub
          </a>
        </div>

        <p className="mt-4 text-xs text-mtg-muted animate-fade-in" style={{ animationDelay: "560ms" }}>
          v2.4.0 · Gemini 2.5 Flash · 100% open source (MIT)
        </p>
      </section>

      {/* ---------- Upload card ---------- */}
      <section
        ref={uploadCardRef}
        className="relative z-10 max-w-3xl mx-auto px-4 sm:px-6 pb-20 scroll-mt-20"
      >
        <div className="mtg-card p-6 sm:p-10 animate-slide-up">
          <div className="text-center mb-6">
            <h2 className="font-heading text-2xl text-mtg-text mb-2">
              Upload Your Deck
            </h2>
            <p className="text-sm text-mtg-subtle">
              PNG or JPG, up to 8 MB — paper, MTGA, MTGO, or websites.
            </p>
          </div>

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
              relative rounded-xl border-2 border-dashed p-8 sm:p-12 bg-mtg-bg-soft
              text-center cursor-pointer transition-all duration-300 ease-signature
              ${
                dragOver
                  ? "border-mana-blue bg-mana-blue-soft scale-[1.01]"
                  : preview
                    ? "border-mana-green/60 bg-mana-green-soft/40"
                    : "border-mtg-border hover:border-mana-blue/50 hover:bg-white"
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
                  className="max-h-72 mx-auto rounded-lg shadow-md object-contain"
                />
                <div className="text-sm text-mtg-subtle">
                  <span className="font-medium text-mtg-text">{file?.name}</span>
                  <span className="text-mtg-muted"> · </span>
                  <span className="font-mono text-xs">
                    {file ? (file.size / 1024 / 1024).toFixed(2) : "0"} MB
                  </span>
                </div>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleFile(null);
                    if (inputRef.current) inputRef.current.value = "";
                  }}
                  className="text-sm text-mana-red hover:underline underline-offset-4"
                >
                  Remove image
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="w-16 h-16 mx-auto rounded-full bg-gradient-to-br from-mana-blue-soft via-white to-mana-green-soft border border-mtg-border flex items-center justify-center shadow-sm">
                  <svg
                    className="w-8 h-8 text-mana-blue"
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
                  <p className="font-heading text-lg text-mtg-text">
                    Drop your deck screenshot
                  </p>
                  <p className="text-sm text-mtg-subtle mt-1">
                    or click to browse
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Error */}
          <div aria-live="polite" role="status" className="mt-4">
            {error && (
              <div className="p-4 bg-mana-red-soft border border-mana-red/30 rounded-lg text-mana-red text-sm animate-fade-in">
                {error}
              </div>
            )}
          </div>

          {/* Submit */}
          <button
            type="button"
            disabled={!file || busy}
            onClick={onSubmit}
            aria-busy={busy}
            className="cta-pill cta-pill--gold w-full mt-6 text-base"
          >
            {busy ? (
              <>
                <Spinner />
                <span>Analyzing deck…</span>
              </>
            ) : (
              <>
                <svg
                  className="w-5 h-5"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth="2"
                  aria-hidden="true"
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

          {busy && (
            <div
              role="status"
              aria-live="polite"
              className="mt-4 p-4 bg-mana-blue-soft border border-mana-blue/30 rounded-lg text-mana-blue text-sm animate-slide-up"
            >
              <strong className="font-semibold">
                Vision AI is reading your image.
              </strong>{" "}
              Typical latency is 3–5&nbsp;seconds.
            </div>
          )}
        </div>

        {/* How it works */}
        <div className="mt-16 text-center">
          <h2 className="font-heading text-3xl text-mtg-text mb-2">
            How it works
          </h2>
          <p className="text-mtg-subtle max-w-2xl mx-auto mb-10">
            Three steps, no account required. All data stays temporary — images
            are deleted after processing.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5 text-left">
            {[
              {
                n: "1",
                title: "Upload",
                desc: "Drop a screenshot (PNG / JPG, ≤ 8 MB). Works with MTGA, MTGO, Moxfield, Archidekt, or a photo of paper cards.",
                color: "feature-chip--blue",
                num: "bg-mana-blue text-white",
              },
              {
                n: "2",
                title: "Vision AI reads it",
                desc: "Gemini 2.5 Flash extracts card names + quantities as typed JSON. EasyOCR is the fallback.",
                color: "feature-chip--pink",
                num: "bg-mana-black text-white",
              },
              {
                n: "3",
                title: "Scryfall validates",
                desc: "Every name is checked against Scryfall's live API. Split, DFC and Adventure cards are correctly reconciled.",
                color: "feature-chip--green",
                num: "bg-mana-green text-white",
              },
            ].map((step, i) => (
              <div
                key={step.n}
                className="mtg-card mtg-card--hover p-6 animate-slide-up"
                style={{ animationDelay: `${i * 80}ms` }}
              >
                <div className="flex items-center gap-3 mb-3">
                  <span
                    className={`flex items-center justify-center w-8 h-8 rounded-full font-heading font-bold text-sm ${step.num}`}
                  >
                    {step.n}
                  </span>
                  <h3 className="font-heading font-semibold text-lg text-mtg-text">
                    {step.title}
                  </h3>
                </div>
                <p className="text-sm text-mtg-subtle leading-relaxed">
                  {step.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
