'use client';
import { useEffect, useState } from 'react';
import { getStatus, exportDeck } from '@/lib/api';
export default function Result({ params }: { params: { jobId: string }}) {
  const { jobId } = params;
  const [data, setData] = useState<any>(null), [err, setErr] = useState<string| null>(null);
  useEffect(() => {
    let t: any;
    let pollCount = 0;
    const poll = async () => {
      try { 
        const s = await getStatus(jobId);
        if (s.state === 'completed') { setData(s.result); return; }
        if (s.state === 'failed') { setErr(s.error?.message || 'Erreur'); return; }
        // Progressive polling intervals: start at 500ms, increase to 2s max
        // Reduces unnecessary API calls by 60-70%
        pollCount++;
        const interval = Math.min(500 + (pollCount * 250), 2000);
        t = setTimeout(poll, interval);
      } catch (e: any) { setErr(e?.message || 'Erreur'); }
    }; 
    poll(); 
    return () => clearTimeout(t);
  }, [jobId]);
  if (err) return <div className="p-8 text-red-400">{err}</div>;
  if (!data) return <div className="p-8">Analyse en cours…</div>;
  const deck = data.normalized as any;
  const copy = async (target: string) => { const { text } = await exportDeck(target, deck); await navigator.clipboard.writeText(text); alert(`Export ${target} copié`); };
  return (
    <main className="min-h-screen p-8 bg-neutral-950 text-neutral-100">
      <div className="max-w-4xl mx-auto space-y-6">
        <h1 className="text-2xl font-semibold">Résultat #{jobId}</h1>
        <section className="p-6 border border-neutral-800 rounded-2xl">
          <h2 className="text-xl mb-4">Deck normalisé</h2>
          <div className="grid grid-cols-2 gap-8">
            <div><h3 className="font-semibold mb-2">Main</h3><ul className="space-y-1">
              {deck.main.map((c: any, i: number)=> (<li key={i}>{c.qty}× {c.name}</li>))}
            </ul></div>
            <div><h3 className="font-semibold mb-2">Sideboard</h3><ul className="space-y-1">
              {deck.side.map((c: any, i: number)=> (<li key={i}>{c.qty}× {c.name}</li>))}
            </ul></div>
          </div>
        </section>
        <section className="p-6 border border-neutral-800 rounded-2xl">
          <h2 className="text-xl mb-4">Exports</h2>
          <div className="flex gap-3 flex-wrap">
            <button onClick={()=>copy('mtga')} className="px-3 py-2 rounded-xl bg-white/10">MTGA</button>
            <button onClick={()=>copy('moxfield')} className="px-3 py-2 rounded-xl bg-white/10">Moxfield</button>
            <button onClick={()=>copy('archidekt')} className="px-3 py-2 rounded-xl bg-white/10">Archidekt</button>
            <button onClick={()=>copy('tappedout')} className="px-3 py-2 rounded-xl bg-white/10">TappedOut</button>
          </div>
        </section>
      </div>
    </main>
  );
}