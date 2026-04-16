"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  ApiError,
  DeckResult,
  JobStatus,
  NormalizedCard,
  NormalizedDeck,
  exportDeck,
  getStatus,
} from "@/lib/api";

const EXPORT_TARGETS = [
  { id: "mtga", label: "MTGA", color: "bg-mtg-gold/20 text-mtg-gold border-mtg-gold/30" },
  { id: "moxfield", label: "Moxfield", color: "bg-mtg-blue/20 text-blue-300 border-mtg-blue/30" },
  { id: "archidekt", label: "Archidekt", color: "bg-mtg-green/20 text-green-300 border-mtg-green/30" },
  { id: "tappedout", label: "TappedOut", color: "bg-mtg-red/20 text-red-300 border-mtg-red/30" },
] as const;

type ExportTarget = (typeof EXPORT_TARGETS)[number]["id"];

interface PageProps {
  params: { jobId: string };
}

function CardRow({ card }: { card: NormalizedCard }) {
  return (
    <li className="flex items-center justify-between py-1.5 px-3 rounded-lg hover:bg-mtg-surface/80 transition-colors group">
      <span className="flex items-center gap-2 min-w-0">
        <span className="text-mtg-gold font-mono text-sm w-6 text-right flex-shrink-0">
          {card.qty}
        </span>
        <span className="text-mtg-text truncate">{card.name}</span>
      </span>
      {card.scryfall_id && (
        <a
          href={`https://scryfall.com/card/${card.scryfall_id}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-mtg-muted hover:text-mtg-gold opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 ml-2"
          aria-label={`View ${card.name} on Scryfall`}
        >
          Scryfall
        </a>
      )}
    </li>
  );
}

function DeckSection({
  title,
  cards,
  icon,
}: {
  title: string;
  cards: NormalizedCard[];
  icon: React.ReactNode;
}) {
  const total = cards.reduce((s, c) => s + c.qty, 0);
  return (
    <div className="mtg-card p-5 animate-slide-up">
      <div className="flex items-center justify-between mb-3">
        <h3 className="flex items-center gap-2 font-semibold text-mtg-text">
          {icon}
          {title}
        </h3>
        <span className="text-xs px-2 py-0.5 rounded-full bg-mtg-gold/10 text-mtg-gold font-mono">
          {total} cards &middot; {cards.length} unique
        </span>
      </div>
      <ul className="space-y-0.5">
        {cards.map((c, i) => (
          <CardRow key={`${c.scryfall_id ?? c.name}-${i}`} card={c} />
        ))}
      </ul>
      {cards.length === 0 && (
        <p className="text-sm text-mtg-muted py-4 text-center">No cards</p>
      )}
    </div>
  );
}

function ProcessingState() {
  return (
    <div className="min-h-[60vh] flex items-center justify-center">
      <div className="text-center space-y-6 animate-fade-in">
        <div className="relative w-20 h-20 mx-auto">
          <div className="absolute inset-0 rounded-full border-2 border-mtg-gold/20" />
          <div className="absolute inset-0 rounded-full border-2 border-mtg-gold border-t-transparent animate-spin" />
          <div className="absolute inset-3 rounded-full bg-mtg-gold/10 flex items-center justify-center">
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
                d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
          </div>
        </div>
        <div>
          <p className="text-lg font-medium text-mtg-text">
            Analyzing your deck...
          </p>
          <p className="text-sm text-mtg-subtle mt-1">
            Vision AI is reading card names and quantities
          </p>
        </div>
      </div>
    </div>
  );
}

export default function Result({ params }: PageProps) {
  const { jobId } = params;
  const [data, setData] = useState<DeckResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [copiedFormat, setCopiedFormat] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const abort = new AbortController();
    abortRef.current = abort;
    let timeoutId: ReturnType<typeof setTimeout> | undefined;
    let pollCount = 0;
    let cancelled = false;

    const poll = async () => {
      if (cancelled) return;
      try {
        const status: JobStatus = await getStatus(jobId, abort.signal);
        if (cancelled) return;

        if (status.state === "completed") {
          setData(status.result);
          return;
        }
        if (status.state === "failed") {
          setErr(status.error?.message ?? "OCR processing failed");
          return;
        }

        pollCount += 1;
        const interval = Math.min(500 + pollCount * 250, 2000);
        timeoutId = setTimeout(poll, interval);
      } catch (e) {
        if (
          cancelled ||
          (e instanceof DOMException && e.name === "AbortError")
        ) {
          return;
        }
        setErr(
          e instanceof ApiError
            ? `Status check failed (${e.status})`
            : e instanceof Error
              ? e.message
              : "Unexpected error",
        );
      }
    };

    poll();

    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
      abort.abort();
    };
  }, [jobId]);

  const deck: NormalizedDeck | null = data?.normalized ?? null;

  const copy = useCallback(
    async (target: ExportTarget) => {
      if (!deck) return;
      try {
        const { text } = await exportDeck(target, deck);
        await navigator.clipboard.writeText(text);
        setCopiedFormat(target);
        setTimeout(() => setCopiedFormat(null), 2500);
      } catch (e) {
        setErr(
          e instanceof ApiError
            ? `Export failed (${e.status})`
            : e instanceof Error
              ? e.message
              : "Export failed",
        );
      }
    },
    [deck],
  );

  if (err) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
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
          <p className="text-red-400">{err}</p>
          <Link href="/" className="mtg-btn-ghost inline-block">
            Try another image
          </Link>
        </div>
      </div>
    );
  }

  if (!deck) {
    return <ProcessingState />;
  }

  const mainTotal = deck.main.reduce((s, c) => s + c.qty, 0);
  const sideTotal = deck.side.reduce((s, c) => s + c.qty, 0);

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 animate-fade-in">
        <div>
          <h1 className="text-2xl font-bold text-mtg-text">Deck Analysis</h1>
          <p className="text-sm text-mtg-subtle mt-1">
            {mainTotal + sideTotal} cards total &middot;{" "}
            {deck.main.length + deck.side.length} unique &middot; Job{" "}
            <span className="font-mono text-xs">{jobId.slice(0, 8)}</span>
          </p>
        </div>
        <Link href="/" className="mtg-btn-ghost flex items-center gap-2">
          <svg
            className="w-4 h-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 4.5v15m7.5-7.5h-15"
            />
          </svg>
          New Scan
        </Link>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 animate-slide-up">
        {[
          { label: "Mainboard", value: mainTotal, sub: `${deck.main.length} unique` },
          { label: "Sideboard", value: sideTotal, sub: `${deck.side.length} unique` },
          { label: "Total", value: mainTotal + sideTotal, sub: "cards" },
          {
            label: "Validated",
            value: `${deck.main.filter((c) => c.scryfall_id).length + deck.side.filter((c) => c.scryfall_id).length}/${deck.main.length + deck.side.length}`,
            sub: "Scryfall",
          },
        ].map((stat) => (
          <div
            key={stat.label}
            className="mtg-card p-4 text-center"
          >
            <div className="text-2xl font-bold text-mtg-gold">
              {stat.value}
            </div>
            <div className="text-xs text-mtg-subtle mt-0.5">
              {stat.label}
            </div>
          </div>
        ))}
      </div>

      {/* Deck lists */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <DeckSection
          title="Mainboard"
          cards={deck.main}
          icon={
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
                d="M6.429 9.75L2.25 12l4.179 2.25m0-4.5l5.571 3 5.571-3m-11.142 0L2.25 7.5 12 2.25l9.75 5.25-4.179 2.25m0 0L21.75 12l-4.179 2.25m0 0l4.179 2.25L12 21.75 2.25 16.5l4.179-2.25m11.142 0l-5.571 3-5.571-3"
              />
            </svg>
          }
        />
        <DeckSection
          title="Sideboard"
          cards={deck.side}
          icon={
            <svg
              className="w-5 h-5 text-mtg-subtle"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth="1.5"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125"
              />
            </svg>
          }
        />
      </div>

      {/* Export section */}
      <div className="mtg-card p-6 animate-slide-up">
        <h2 className="font-semibold text-mtg-text mb-4 flex items-center gap-2">
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
              d="M15.75 17.25v3.375c0 .621-.504 1.125-1.125 1.125h-9.75a1.125 1.125 0 01-1.125-1.125V7.875c0-.621.504-1.125 1.125-1.125H6.75a9.06 9.06 0 011.5.124m7.5 10.376h3.375c.621 0 1.125-.504 1.125-1.125V11.25c0-4.46-3.243-8.161-7.5-8.876a9.06 9.06 0 00-1.5-.124H9.375c-.621 0-1.125.504-1.125 1.125v3.5m7.5 10.375H9.375a1.125 1.125 0 01-1.125-1.125v-9.25m12 6.625v-1.875a3.375 3.375 0 00-3.375-3.375h-1.5a1.125 1.125 0 01-1.125-1.125v-1.5a3.375 3.375 0 00-3.375-3.375H9.75"
            />
          </svg>
          Export to Clipboard
        </h2>
        <div className="flex flex-wrap gap-3">
          {EXPORT_TARGETS.map((target) => (
            <button
              key={target.id}
              type="button"
              onClick={() => copy(target.id)}
              aria-label={`Copy deck in ${target.label} format`}
              className={`
                px-5 py-2.5 rounded-lg border text-sm font-medium
                transition-all duration-200
                hover:brightness-125 hover:shadow-gold
                focus-visible:ring-2 focus-visible:ring-mtg-gold/60
                ${target.color}
                ${copiedFormat === target.id ? "ring-2 ring-green-400/60" : ""}
              `}
            >
              {copiedFormat === target.id ? (
                <span className="flex items-center gap-1.5">
                  <svg
                    className="w-4 h-4 text-green-400"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M4.5 12.75l6 6 9-13.5"
                    />
                  </svg>
                  Copied!
                </span>
              ) : (
                target.label
              )}
            </button>
          ))}
        </div>
        <div
          aria-live="polite"
          role="status"
          className="mt-3 h-5 text-xs text-mtg-subtle"
        >
          {copiedFormat &&
            `${EXPORT_TARGETS.find((t) => t.id === copiedFormat)?.label} format copied to clipboard`}
        </div>
      </div>
    </div>
  );
}
