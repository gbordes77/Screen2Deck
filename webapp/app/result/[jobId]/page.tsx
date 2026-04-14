'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ApiError,
  DeckResult,
  JobStatus,
  NormalizedDeck,
  exportDeck,
  getStatus,
} from '@/lib/api';

const EXPORT_TARGETS = ['mtga', 'moxfield', 'archidekt', 'tappedout'] as const;
type ExportTarget = (typeof EXPORT_TARGETS)[number];

interface PageProps {
  params: { jobId: string };
}

export default function Result({ params }: PageProps) {
  const { jobId } = params;
  const [data, setData] = useState<DeckResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [copiedFormat, setCopiedFormat] = useState<ExportTarget | null>(null);
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

        if (status.state === 'completed') {
          setData(status.result);
          return;
        }
        if (status.state === 'failed') {
          setErr(status.error?.message ?? 'OCR failed');
          return;
        }

        pollCount += 1;
        const interval = Math.min(500 + pollCount * 250, 2000);
        timeoutId = setTimeout(poll, interval);
      } catch (e) {
        if (cancelled || (e instanceof DOMException && e.name === 'AbortError')) {
          return;
        }
        setErr(
          e instanceof ApiError
            ? `Status check failed (${e.status})`
            : e instanceof Error
            ? e.message
            : 'Unexpected error',
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
            : 'Export failed',
        );
      }
    },
    [deck],
  );

  if (err) {
    return (
      <main className="p-8 text-red-400" role="alert">
        {err}
      </main>
    );
  }

  if (!deck) {
    return (
      <main className="p-8" role="status" aria-live="polite">
        Analyzing deck…
      </main>
    );
  }

  return (
    <main className="min-h-screen p-8 bg-neutral-950 text-neutral-100">
      <div className="max-w-4xl mx-auto space-y-6">
        <h1 className="text-2xl font-semibold">Result #{jobId}</h1>
        <section className="p-6 border border-neutral-800 rounded-2xl">
          <h2 className="text-xl mb-4">Normalized deck</h2>
          <div className="grid grid-cols-2 gap-8">
            <div>
              <h3 className="font-semibold mb-2">Mainboard</h3>
              <ul className="space-y-1">
                {deck.main.map((c, i) => (
                  <li key={`${c.scryfall_id ?? c.name}-${i}`}>
                    {c.qty}× {c.name}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="font-semibold mb-2">Sideboard</h3>
              <ul className="space-y-1">
                {deck.side.map((c, i) => (
                  <li key={`${c.scryfall_id ?? c.name}-${i}`}>
                    {c.qty}× {c.name}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>
        <section className="p-6 border border-neutral-800 rounded-2xl">
          <h2 className="text-xl mb-4">Exports</h2>
          <div className="flex gap-3 flex-wrap">
            {EXPORT_TARGETS.map((target) => (
              <button
                key={target}
                type="button"
                onClick={() => copy(target)}
                aria-label={`Copy deck to ${target} format`}
                className="px-3 py-2 rounded-xl bg-white/10 hover:bg-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
              >
                {target.toUpperCase()}
              </button>
            ))}
          </div>
          <div aria-live="polite" role="status" className="mt-3 h-5 text-sm text-green-400">
            {copiedFormat && `${copiedFormat.toUpperCase()} copied to clipboard`}
          </div>
        </section>
      </div>
    </main>
  );
}
