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
  { id: "mtga", label: "MTGA", chip: "export-chip--gold" },
  { id: "moxfield", label: "Moxfield", chip: "export-chip--blue" },
  { id: "archidekt", label: "Archidekt", chip: "export-chip--green" },
  { id: "tappedout", label: "TappedOut", chip: "export-chip--red" },
] as const;

type ExportTarget = (typeof EXPORT_TARGETS)[number]["id"];

interface PageProps {
  params: { jobId: string };
}

function CardRow({ card }: { card: NormalizedCard }) {
  return (
    <li className="flex items-center justify-between py-1.5 px-3 rounded-md hover:bg-mana-blue-soft/40 transition-colors group">
      <span className="flex items-center gap-3 min-w-0">
        <span className="font-mono text-xs text-mana-blue w-6 text-right flex-shrink-0 font-semibold">
          {card.qty}
        </span>
        <span className="text-mtg-text truncate">{card.name}</span>
      </span>
      {card.scryfall_id && (
        <a
          href={`https://scryfall.com/card/${card.scryfall_id}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-mtg-muted hover:text-mana-blue opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 ml-3"
          aria-label={`View ${card.name} on Scryfall`}
        >
          Scryfall ↗
        </a>
      )}
    </li>
  );
}

function DeckSection({
  title,
  cards,
  accentClass,
  icon,
}: {
  title: string;
  cards: NormalizedCard[];
  accentClass: string;
  icon: React.ReactNode;
}) {
  const total = cards.reduce((s, c) => s + c.qty, 0);
  return (
    <div className="mtg-card mtg-card--hover p-6 animate-slide-up">
      <div className="flex items-center justify-between mb-4">
        <h3 className="flex items-center gap-2.5 font-heading font-semibold text-lg text-mtg-text">
          <span className={accentClass}>{icon}</span>
          {title}
        </h3>
        <span className="font-mono text-xs text-mtg-subtle bg-mtg-bg-soft px-2.5 py-1 rounded-full border border-mtg-border">
          {total} · {cards.length} unique
        </span>
      </div>
      <ul className="space-y-0.5">
        {cards.map((c, i) => (
          <CardRow key={`${c.scryfall_id ?? c.name}-${i}`} card={c} />
        ))}
      </ul>
      {cards.length === 0 && (
        <p className="text-sm text-mtg-muted py-6 text-center italic">
          No cards
        </p>
      )}
    </div>
  );
}

function ProcessingState() {
  return (
    <div className="min-h-[60vh] flex items-center justify-center px-4">
      <div className="text-center space-y-6 animate-fade-in">
        <div className="relative w-20 h-20 mx-auto">
          <div className="absolute inset-0 rounded-full border-2 border-mana-blue/20" />
          <div className="absolute inset-0 rounded-full border-2 border-mana-blue border-t-transparent animate-spin" />
          <div className="absolute inset-3 rounded-full bg-mana-blue-soft flex items-center justify-center">
            <svg
              className="w-8 h-8 text-mana-blue"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth="1.5"
              aria-hidden="true"
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
          <p className="font-heading text-xl text-mtg-text">
            Analyzing your deck…
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
        setTimeout(() => setCopiedFormat(null), 2200);
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
      <div className="min-h-[60vh] flex items-center justify-center px-4">
        <div
          role="alert"
          className="mtg-card p-8 max-w-md text-center space-y-4 animate-fade-in"
        >
          <div className="w-14 h-14 mx-auto rounded-full bg-mana-red-soft border border-mana-red/20 flex items-center justify-center">
            <svg
              className="w-7 h-7 text-mana-red"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth="1.5"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
              />
            </svg>
          </div>
          <h2 className="font-heading text-lg text-mtg-text">
            Something broke
          </h2>
          <p className="text-sm text-mtg-subtle">{err}</p>
          <Link href="/" className="mtg-btn-ghost">
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
  const validated =
    deck.main.filter((c) => c.scryfall_id).length +
    deck.side.filter((c) => c.scryfall_id).length;
  const totalCards = deck.main.length + deck.side.length;

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 animate-fade-in">
        <div>
          <h1 className="brand-title font-heading text-3xl sm:text-4xl">
            Deck Analysis
          </h1>
          <p className="text-sm text-mtg-subtle mt-2">
            {mainTotal + sideTotal} cards total · {totalCards} unique ·{" "}
            <span className="font-mono text-xs text-mtg-muted">
              job {jobId.slice(0, 8)}
            </span>
          </p>
        </div>
        <Link href="/" className="mtg-btn-ghost">
          <svg
            className="w-4 h-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 4.5v15m7.5-7.5h-15"
            />
          </svg>
          New scan
        </Link>
      </div>

      {/* Stats bar */}
      <div
        className="grid grid-cols-2 sm:grid-cols-4 gap-3 animate-slide-up"
        style={{ animationDelay: "80ms" }}
      >
        {[
          {
            label: "Mainboard",
            value: mainTotal,
            sub: `${deck.main.length} unique`,
            color: "text-mana-white",
          },
          {
            label: "Sideboard",
            value: sideTotal,
            sub: `${deck.side.length} unique`,
            color: "text-mtg-subtle",
          },
          {
            label: "Total",
            value: mainTotal + sideTotal,
            sub: "cards",
            color: "text-mana-blue",
          },
          {
            label: "Validated",
            value: `${validated}/${totalCards}`,
            sub: "Scryfall",
            color:
              validated === totalCards ? "text-mana-green" : "text-mana-white",
          },
        ].map((stat) => (
          <div key={stat.label} className="mtg-card p-4 text-center">
            <div
              className={`font-heading font-bold text-2xl ${stat.color}`}
            >
              {stat.value}
            </div>
            <div className="text-xs text-mtg-subtle mt-1 uppercase tracking-wider font-medium">
              {stat.label}
            </div>
            <div className="text-[10px] text-mtg-muted mt-0.5 font-mono">
              {stat.sub}
            </div>
          </div>
        ))}
      </div>

      {/* Deck lists */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <DeckSection
          title="Mainboard"
          cards={deck.main}
          accentClass="text-mana-white"
          icon={
            <svg
              className="w-5 h-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth="1.5"
              aria-hidden="true"
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
          accentClass="text-mtg-subtle"
          icon={
            <svg
              className="w-5 h-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth="1.5"
              aria-hidden="true"
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
      <div
        className="mtg-card p-6 animate-slide-up"
        style={{ animationDelay: "160ms" }}
      >
        <h2 className="font-heading font-semibold text-xl text-mtg-text mb-4 flex items-center gap-2">
          <span aria-hidden="true">📋</span>
          Export to clipboard
        </h2>
        <div className="flex flex-wrap gap-3">
          {EXPORT_TARGETS.map((target) => {
            const isCopied = copiedFormat === target.id;
            return (
              <button
                key={target.id}
                type="button"
                onClick={() => copy(target.id)}
                aria-label={`Copy deck in ${target.label} format`}
                className={`export-chip ${isCopied ? "export-chip--copied" : target.chip}`}
              >
                {isCopied ? (
                  <>
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth="2.4"
                      aria-hidden="true"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M4.5 12.75l6 6 9-13.5"
                      />
                    </svg>
                    Copied
                  </>
                ) : (
                  target.label
                )}
              </button>
            );
          })}
        </div>
        <p className="text-xs text-mtg-muted mt-4">
          Click a format to copy the full deck list to your clipboard. MTGA uses
          front-face only for DFC / split / adventure cards.
        </p>
      </div>
    </div>
  );
}
