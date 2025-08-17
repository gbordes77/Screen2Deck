'use client';
import { useState } from 'react';
import { upload } from '@/lib/api';
import { useRouter } from 'next/navigation';
export default function Page() {
  const [file, setFile] = useState<File| null>(null);
  const [busy, setBusy] = useState(false);
  const router = useRouter();
  const onSubmit = async () => {
    if (!file) return;
    setBusy(true);
    try { const jobId = await upload(file); router.push(`/result/${jobId}`); }
    catch { alert('Upload failed'); }
    finally { setBusy(false); }
  };
  return (
    <main className="min-h-screen p-8 bg-neutral-950 text-neutral-100">
      <div className="max-w-3xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">MTG Deck Scanner</h1>
        <div className="p-6 border border-neutral-800 rounded-2xl">
          <input type="file" accept="image/*" onChange={e=> setFile(e.target.files?.[0]||null)} className="mb-4" />
          <button disabled={!file||busy} onClick={onSubmit} className="px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 disabled:opacity-50">Analyser</button>
        </div>
      </div>
    </main>
  );
}