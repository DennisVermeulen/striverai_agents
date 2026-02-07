import { useState } from "react";
import { api } from "../api";

interface Props {
  onTaskStarted: (taskId: string) => void;
  disabled?: boolean;
}

export default function TaskForm({ onTaskStarted, disabled }: Props) {
  const [instruction, setInstruction] = useState("");
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!instruction.trim()) return;

    setError("");
    setSubmitting(true);
    try {
      const res = await api.createTask(instruction.trim(), url.trim() || undefined);
      onTaskStarted(res.task_id);
      setInstruction("");
      setUrl("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start task");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1">
          Instruction
        </label>
        <textarea
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          placeholder="What should the agent do?"
          rows={3}
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
          disabled={disabled || submitting}
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1">
          URL <span className="text-gray-500">(optional)</span>
        </label>
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://..."
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          disabled={disabled || submitting}
        />
      </div>

      {error && (
        <p className="text-sm text-red-400">{error}</p>
      )}

      <button
        type="submit"
        disabled={disabled || submitting || !instruction.trim()}
        className="w-full py-2 px-4 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors"
      >
        {submitting ? "Starting..." : "Start Task"}
      </button>
    </form>
  );
}
