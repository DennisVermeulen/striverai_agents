import { useState } from "react";
import { api } from "../api";

interface Props {
  disabled?: boolean;
  onWorkflowSaved?: () => void;
}

export default function RecordButton({ disabled, onWorkflowSaved }: Props) {
  const [recording, setRecording] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleStart = async () => {
    setError("");
    setLoading(true);
    try {
      await api.startRecording();
      setRecording(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start recording");
    } finally {
      setLoading(false);
    }
  };

  const handleStop = () => {
    setShowModal(true);
    setName("");
    setDescription("");
  };

  const handleSave = async () => {
    if (!name.trim()) return;
    setError("");
    setLoading(true);
    try {
      await api.stopRecording(
        name.trim().replace(/\s+/g, "-").toLowerCase(),
        description.trim()
      );
      setRecording(false);
      setShowModal(false);
      onWorkflowSaved?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save workflow");
    } finally {
      setLoading(false);
    }
  };

  const handleDiscard = async () => {
    setLoading(true);
    try {
      await api.stopRecording("_discard_" + Date.now());
      // Delete the discarded workflow
      try {
        await api.deleteWorkflow("_discard_" + Date.now());
      } catch {
        // Ignore — may not exist
      }
    } catch {
      // Ignore errors on discard
    }
    setRecording(false);
    setShowModal(false);
    setLoading(false);
  };

  return (
    <>
      <button
        onClick={recording ? handleStop : handleStart}
        disabled={disabled || loading}
        className={`w-full py-2 px-4 text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-2 ${
          recording
            ? "bg-red-600/20 text-red-400 hover:bg-red-600/30 border border-red-800"
            : "bg-gray-800 text-gray-300 hover:bg-gray-700 border border-gray-700"
        } disabled:opacity-50`}
      >
        {recording && (
          <span className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
          </span>
        )}
        {loading ? "..." : recording ? "Stop Recording" : "Record Workflow"}
      </button>

      {/* Save modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-6 w-96 space-y-4">
            <h3 className="text-sm font-medium text-gray-200">Save Workflow</h3>

            <div>
              <label className="block text-sm text-gray-400 mb-1">Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. send-email-gmail"
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === "Enter" && name.trim()) handleSave();
                }}
              />
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Description <span className="text-gray-600">(optional)</span>
              </label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What does this workflow do?"
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {error && <p className="text-sm text-red-400">{error}</p>}

            <div className="flex gap-2">
              <button
                onClick={handleSave}
                disabled={!name.trim() || loading}
                className="flex-1 py-2 px-4 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors"
              >
                {loading ? "Saving..." : "Save"}
              </button>
              <button
                onClick={handleDiscard}
                disabled={loading}
                className="py-2 px-4 bg-gray-800 hover:bg-gray-700 text-gray-400 text-sm rounded-lg transition-colors border border-gray-700"
              >
                Discard
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
