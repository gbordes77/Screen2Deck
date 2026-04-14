export default function Loading() {
  return (
    <main
      role="status"
      aria-live="polite"
      className="min-h-screen p-8 bg-neutral-950 text-neutral-100 flex items-center justify-center"
    >
      <span className="text-neutral-400">Loading…</span>
    </main>
  );
}
