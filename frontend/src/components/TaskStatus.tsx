import type { TaskStatusResponse } from "../api";

interface Props {
  task: TaskStatusResponse;
  onCancel: () => void;
}

const statusColors: Record<string, string> = {
  pending: "text-yellow-400",
  running: "text-blue-400",
  completed: "text-green-400",
  failed: "text-red-400",
  cancelled: "text-gray-400",
};

const statusBg: Record<string, string> = {
  pending: "bg-yellow-400/10",
  running: "bg-blue-400/10",
  completed: "bg-green-400/10",
  failed: "bg-red-400/10",
  cancelled: "bg-gray-400/10",
};

export default function TaskStatus({ task, onCancel }: Props) {
  const maxSteps = 50; // default, could come from config
  const progress = Math.min((task.steps_completed / maxSteps) * 100, 100);
  const isRunning = task.status === "running" || task.status === "pending";

  return (
    <div className="space-y-3">
      {/* Status badge */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${statusColors[task.status]} ${statusBg[task.status]}`}
          >
            {isRunning && (
              <span className="w-1.5 h-1.5 bg-blue-400 rounded-full mr-1.5 animate-pulse" />
            )}
            {task.status}
          </span>
          <span className="text-sm text-gray-400">
            Step {task.steps_completed}/{maxSteps}
          </span>
        </div>
        {isRunning && (
          <button
            onClick={onCancel}
            className="text-xs text-red-400 hover:text-red-300 transition-colors"
          >
            Cancel
          </button>
        )}
      </div>

      {/* Progress bar */}
      <div className="w-full bg-gray-800 rounded-full h-1.5">
        <div
          className="bg-blue-500 h-1.5 rounded-full transition-all duration-300"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Current action */}
      {task.current_action && isRunning && (
        <p className="text-sm text-gray-400 truncate">
          <span className="text-gray-500">Action:</span> {task.current_action}
        </p>
      )}

      {/* Instruction */}
      <p className="text-sm text-gray-300 line-clamp-2">{task.instruction}</p>

      {/* Result */}
      {task.result && (
        <div className="p-3 bg-green-900/20 border border-green-800/30 rounded-lg">
          <p className="text-sm text-green-300">{task.result}</p>
        </div>
      )}

      {/* Error */}
      {task.error && (
        <div className="p-3 bg-red-900/20 border border-red-800/30 rounded-lg">
          <p className="text-sm text-red-300">{task.error}</p>
        </div>
      )}
    </div>
  );
}
