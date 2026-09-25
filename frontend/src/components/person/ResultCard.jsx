import { PersonCrop } from './PersonCrop'

export function ResultCard({ result, rank, onOpen }) {
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label={`Track ${result.track} · ${result.camName} · điểm ${result.scoreText}`}
      className="flex flex-col gap-2 rounded-md border-0 bg-surface p-2 text-left text-text shadow-sm transition-shadow hover:shadow-glow"
    >
      <PersonCrop result={result} rank={rank} />
      <div className="h-0.5 rounded-sm bg-neutral-800">
        <div
          className="h-0.5 rounded-sm bg-accent"
          style={{ width: `${Math.round(result.score * 100)}%` }}
        />
      </div>
      <div className="min-w-0">
        <div className="truncate text-xs">{result.camName}</div>
        <div className="text-[11px] text-neutral-400">{result.when}</div>
      </div>
    </button>
  )
}
