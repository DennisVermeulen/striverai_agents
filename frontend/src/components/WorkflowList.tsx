import { useCallback, useEffect, useState } from "react";
import { api, type WorkflowResponse } from "../api";

interface Props {
  onTaskStarted?: (taskId: string) => void;
  refreshTrigger?: number;
}

export default function WorkflowList({ onTaskStarted, refreshTrigger }: Props) {
  const [workflows, setWorkflows] = useState<WorkflowResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [runningName, setRunningName] = useState<string | null>(null);
  const [error, setError] = useState("");

  const fetchWorkflows = useCallback(async () => {
    try {
      const res = await api.listWorkflows();
      setWorkflows(res.workflows);
    } catch {
      // Ignore — workflows dir may not exist yet
    }
  }, []);

  useEffect(() => {
    fetchWorkflows();
  }, [fetchWorkflows, refreshTrigger]);

  const handleRun = async (name: string, mode: "direct" | "ai" = "direct") => {
    setError("");
    setRunningName(name);
    try {
      const res = await api.runWorkflow(name, mode);
      onTaskStarted?.(res.task_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run workflow");
    } finally {
      setRunningName(null);
    }
  };

  const handleDelete = async (name: string) => {
    try {
      await api.deleteWorkflow(name);
      setWorkflows((prev) => prev.filter((w) => w.name !== name));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete workflow");
    }
  };

  if (workflows.length === 0) {
    return (
      <p className="text-sm text-gray-500 italic">
        No workflows recorded yet. Click "Record Workflow" to start.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {error && <p className="text-sm text-red-400">{error}</p>}

      {workflows.map((w) => (
        <div
          key={w.name}
          className="flex items-center justify-between p-3 bg-gray-800 rounded-lg border border-gray-700"
        >
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-gray-200 truncate">
              {w.name}
            </p>
            <p className="text-xs text-gray-500 truncate">
              {w.description || `${w.steps.length} steps`}
              {w.start_url && ` — ${w.start_url}`}
            </p>
          </div>

          <div className="flex items-center gap-1 ml-3 shrink-0">
            <button
              onClick={() => handleRun(w.name, "direct")}
              disabled={runningName !== null}
              className="px-3 py-1 text-xs font-medium bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 rounded transition-colors disabled:opacity-50"
            >
              {runningName === w.name ? "..." : "Run"}
            </button>
            <button
              onClick={() => handleRun(w.name, "ai")}
              disabled={runningName !== null}
              className="px-3 py-1 text-xs font-medium bg-purple-600/20 text-purple-400 hover:bg-purple-600/30 rounded transition-colors disabled:opacity-50"
              title="Run with AI (uses LLM credits)"
            >
              AI
            </button>
            <button
              onClick={() => handleDelete(w.name)}
              className="px-2 py-1 text-xs text-gray-500 hover:text-red-400 hover:bg-red-600/10 rounded transition-colors"
              title="Delete workflow"
            >
              &times;
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
