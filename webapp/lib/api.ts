export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8080";
export async function upload(file: File): Promise<string> {
  const fd = new FormData(); fd.append("file", file);
  const res = await fetch(`${API_BASE}/api/ocr/upload`, { method: 'POST', body: fd });
  if (!res.ok) throw new Error(await res.text());
  const j = await res.json(); return j.jobId as string;
}
export async function getStatus(jobId: string) {
  const res = await fetch(`${API_BASE}/api/ocr/status/${jobId}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(await res.text()); return res.json();
}
export async function exportDeck(target: string, deck: any) {
  const res = await fetch(`${API_BASE}/api/export/${target}`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(deck)});
  if (!res.ok) throw new Error(await res.text()); return res.json();
}