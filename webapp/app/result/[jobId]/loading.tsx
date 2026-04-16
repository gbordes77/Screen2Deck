export default function ResultLoading() {
  return (
    <div
      role="status"
      aria-live="polite"
      className="min-h-[60vh] flex items-center justify-center"
    >
      <div className="text-center space-y-4 animate-fade-in">
        <div className="relative w-16 h-16 mx-auto">
          <div className="absolute inset-0 rounded-full border-2 border-mtg-gold/20" />
          <div className="absolute inset-0 rounded-full border-2 border-mtg-gold border-t-transparent animate-spin" />
        </div>
        <p className="text-sm text-mtg-subtle">Loading result...</p>
      </div>
    </div>
  );
}
