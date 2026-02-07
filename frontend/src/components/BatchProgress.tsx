import type { BatchResponse } from "../api";

interface Props {
  batch: BatchResponse;
  onCancel: () => void;
}

const STATUS_ICONS: Record<string, { icon: string; color: string }> = {
  completed: { icon: "\u2713", color: "text-green-400" },
  failed: { icon: "\u2717", color: "text-red-400" },
  running: { icon: "\u25C9", color: "text-blue-400" },
  pending: { icon: "\u25CB", color: "text-gray-600" },
  skipped: { icon: "\u2014", color: "text-gray-600" },
};

export default function BatchProgress({ batch, onCancel }: Props) {
  const pct = batch.total > 0
    ? Math.round(((batch.completed + batch.failed) / batch.total) * 100)
    : 0;

  const isDone = batch.status === "completed" || batch.status === "cancelled" || batch.status === "failed";

  // Show first few param values for the current row
  const currentRow = batch.rows[batch.current_index];
  const currentLabel = currentRow
    ? Object.values(currentRow.parameters).slice(0, 3).join(" — ")
    : "";

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-200">
            Batch: {batch.workflow_name}
          </p>
          <p className="text-xs text-gray-500">
            {batch.completed + batch.failed} / {batch.total}
            {batch.failed > 0 && (
              <span className="text-red-400 ml-1">({batch.failed} failed)</span>
            )}
          </p>
        </div>
        {!isDone && (
          <button
            onClick={onCancel}
            className="px-3 py-1 text-xs text-red-400 hover:text-red-300 bg-red-600/10 hover:bg-red-600/20 rounded transition-colors"
          >
            Cancel
          </button>
        )}
        {isDone && (
          <span className={`text-xs font-medium ${
            batch.status === "completed" ? "text-green-400" : "text-gray-400"
          }`}>
            {batch.status === "completed" ? "Done" : batch.status}
          </span>
        )}
      </div>

      {/* Progress bar */}
      <div className="w-full h-2 bg-gray-700 rounded-full overflow-hidden">
        <div
          className="h-full bg-blue-500 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Current row */}
      {!isDone && currentLabel && (
        <p className="text-xs text-gray-400 truncate">
          Running: {currentLabel}
        </p>
      )}

      {/* Row list */}
      <div className="max-h-40 overflow-y-auto space-y-0.5">
        {batch.rows.map((row) => {
          const st = STATUS_ICONS[row.status] || STATUS_ICONS.pending;
          const label = Object.values(row.parameters).slice(0, 3).join(", ");
          return (
            <div
              key={row.index}
              className={`flex items-center gap-2 px-2 py-1 rounded text-xs ${
                row.status === "running" ? "bg-blue-600/10" : ""
              }`}
            >
              <span className={`${st.color} w-3 text-center`}>{st.icon}</span>
              <span className="text-gray-400 w-5 text-right shrink-0">
                {row.index + 1}
              </span>
              <span className="text-gray-300 truncate flex-1">{label}</span>
              {row.error && (
                <span className="text-red-400 truncate max-w-[150px]" title={row.error}>
                  {row.error}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
