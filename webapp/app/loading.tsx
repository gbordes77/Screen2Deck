export default function Loading() {
  return (
    <div
      role="status"
      aria-live="polite"
      className="min-h-[60vh] flex items-center justify-center"
    >
      <div className="text-center space-y-3">
        <div className="w-10 h-10 mx-auto rounded-full border-2 border-mana-blue border-t-transparent animate-spin" />
        <span className="text-sm text-mtg-subtle">Loading…</span>
      </div>
    </div>
  );
}
