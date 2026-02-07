import { useCallback, useEffect, useRef, useState } from "react";
import { api, type WorkflowParameter, type WorkflowResponse } from "../api";

interface Props {
  onTaskStarted?: (taskId: string) => void;
  onBatchStarted?: (batchId: string) => void;
  refreshTrigger?: number;
}

interface ModalState {
  workflowName: string;
  mode: "direct" | "ai";
  parameters: WorkflowParameter[];
  values: Record<string, string>;
  tab: "single" | "batch";
  csvText: string;
  parsedRows: Record<string, string>[];
  csvError: string;
}

function parseCsv(text: string): { rows: Record<string, string>[]; error: string } {
  const lines = text.trim().split("\n").filter((l) => l.trim());
  if (lines.length < 2) return { rows: [], error: "Needs at least a header row and one data row" };

  // Detect separator: tab or comma
  const sep = lines[0].includes("\t") ? "\t" : ",";
  const headers = lines[0].split(sep).map((h) => h.trim());

  if (headers.some((h) => !h)) {
    return { rows: [], error: "Header row has empty column names" };
  }

  const rows: Record<string, string>[] = [];
  for (let i = 1; i < lines.length; i++) {
    const vals = lines[i].split(sep).map((v) => v.trim());
    const row: Record<string, string> = {};
    for (let j = 0; j < headers.length; j++) {
      row[headers[j]] = vals[j] || "";
    }
    rows.push(row);
  }

  return { rows, error: "" };
}

export default function WorkflowList({ onTaskStarted, onBatchStarted, refreshTrigger }: Props) {
  const [workflows, setWorkflows] = useState<WorkflowResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [runningName, setRunningName] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [modal, setModal] = useState<ModalState | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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

  const handleRunClick = (w: WorkflowResponse, mode: "direct" | "ai") => {
    if (w.parameters && w.parameters.length > 0) {
      const initial: Record<string, string> = {};
      for (const p of w.parameters) {
        initial[p.name] = p.default || "";
      }
      setModal({
        workflowName: w.name,
        mode,
        parameters: w.parameters,
        values: initial,
        tab: "single",
        csvText: "",
        parsedRows: [],
        csvError: "",
      });
    } else {
      executeRun(w.name, mode, {});
    }
  };

  const executeRun = async (
    name: string,
    mode: "direct" | "ai",
    parameters: Record<string, string>,
  ) => {
    setError("");
    setRunningName(name);
    setModal(null);
    try {
      const res = await api.runWorkflow(name, mode, parameters);
      onTaskStarted?.(res.task_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run workflow");
    } finally {
      setRunningName(null);
    }
  };

  const executeBatch = async (
    name: string,
    mode: "direct" | "ai",
    rows: Record<string, string>[],
  ) => {
    setError("");
    setRunningName(name);
    setModal(null);
    try {
      const res = await api.startBatch(name, mode, rows);
      onBatchStarted?.(res.batch_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start batch");
    } finally {
      setRunningName(null);
    }
  };

  const handleCsvChange = (text: string) => {
    if (!modal) return;
    const { rows, error } = parseCsv(text);
    setModal({ ...modal, csvText: text, parsedRows: rows, csvError: error });
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const text = reader.result as string;
      handleCsvChange(text);
    };
    reader.readAsText(file);
    // Reset input so same file can be re-selected
    e.target.value = "";
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
              {w.parameters && w.parameters.length > 0 && (
                <span className="ml-2 text-xs text-yellow-500/70" title="Has parameters">
                  {"{{"}&hellip;{"}}"}
                </span>
              )}
            </p>
            <p className="text-xs text-gray-500 truncate">
              {w.description || `${w.steps.length} steps`}
              {w.start_url && ` — ${w.start_url}`}
            </p>
          </div>

          <div className="flex items-center gap-1 ml-3 shrink-0">
            <button
              onClick={() => handleRunClick(w, "direct")}
              disabled={runningName !== null}
              className="px-3 py-1 text-xs font-medium bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 rounded transition-colors disabled:opacity-50"
            >
              {runningName === w.name ? "..." : "Run"}
            </button>
            <button
              onClick={() => handleRunClick(w, "ai")}
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

      {/* Parameter modal with Single/Batch tabs */}
      {modal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-gray-800 border border-gray-600 rounded-xl p-5 w-full max-w-lg shadow-2xl">
            <h3 className="text-sm font-semibold text-gray-200 mb-3">
              {modal.workflowName}
              <span className="ml-2 text-xs font-normal text-gray-500">
                {modal.mode === "ai" ? "AI replay" : "Direct replay"}
              </span>
            </h3>

            {/* Tab switch */}
            <div className="flex gap-1 mb-4">
              <button
                onClick={() => setModal({ ...modal, tab: "single" })}
                className={`px-3 py-1 text-xs rounded transition-colors ${
                  modal.tab === "single"
                    ? "bg-gray-700 text-gray-200"
                    : "text-gray-500 hover:text-gray-300"
                }`}
              >
                Single
              </button>
              <button
                onClick={() => setModal({ ...modal, tab: "batch" })}
                className={`px-3 py-1 text-xs rounded transition-colors ${
                  modal.tab === "batch"
                    ? "bg-gray-700 text-gray-200"
                    : "text-gray-500 hover:text-gray-300"
                }`}
              >
                Batch
              </button>
            </div>

            {modal.tab === "single" ? (
              /* Single parameter inputs */
              <>
                <div className="space-y-3">
                  {modal.parameters.map((p) => (
                    <div key={p.name}>
                      <label className="block text-xs text-gray-400 mb-1">
                        {p.label || p.name}
                        {!p.default && <span className="text-red-400 ml-1">*</span>}
                      </label>
                      <input
                        type="text"
                        value={modal.values[p.name] || ""}
                        onChange={(e) =>
                          setModal((prev) =>
                            prev
                              ? { ...prev, values: { ...prev.values, [p.name]: e.target.value } }
                              : null,
                          )
                        }
                        placeholder={p.default || p.label || p.name}
                        className="w-full px-3 py-1.5 text-sm bg-gray-900 border border-gray-600 rounded text-gray-200 placeholder-gray-600 focus:border-blue-500 focus:outline-none"
                      />
                    </div>
                  ))}
                </div>

                <div className="flex justify-end gap-2 mt-5">
                  <button
                    onClick={() => setModal(null)}
                    className="px-4 py-1.5 text-xs text-gray-400 hover:text-gray-200 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => executeRun(modal.workflowName, modal.mode, modal.values)}
                    className={`px-4 py-1.5 text-xs font-medium rounded transition-colors ${
                      modal.mode === "ai"
                        ? "bg-purple-600/30 text-purple-300 hover:bg-purple-600/50"
                        : "bg-blue-600/30 text-blue-300 hover:bg-blue-600/50"
                    }`}
                  >
                    {modal.mode === "ai" ? "Run with AI" : "Run"}
                  </button>
                </div>
              </>
            ) : (
              /* Batch CSV input */
              <>
                <div className="space-y-3">
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-xs text-gray-400">
                        Paste CSV (columns: {modal.parameters.map((p) => p.name).join(", ")})
                      </label>
                      <button
                        onClick={() => fileInputRef.current?.click()}
                        className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                      >
                        Upload file
                      </button>
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept=".csv,.tsv,.txt"
                        onChange={handleFileUpload}
                        className="hidden"
                      />
                    </div>
                    <textarea
                      value={modal.csvText}
                      onChange={(e) => handleCsvChange(e.target.value)}
                      placeholder={`${modal.parameters.map((p) => p.name).join(",")}\nvalue1,value2,...\nvalue3,value4,...`}
                      rows={6}
                      className="w-full px-3 py-2 text-xs font-mono bg-gray-900 border border-gray-600 rounded text-gray-200 placeholder-gray-600 focus:border-blue-500 focus:outline-none resize-y"
                    />
                  </div>

                  {modal.csvError && (
                    <p className="text-xs text-red-400">{modal.csvError}</p>
                  )}

                  {/* Preview table */}
                  {modal.parsedRows.length > 0 && (
                    <div className="border border-gray-700 rounded overflow-hidden">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="bg-gray-700/50">
                            <th className="px-2 py-1 text-left text-gray-400 font-medium">#</th>
                            {modal.parameters.map((p) => (
                              <th key={p.name} className="px-2 py-1 text-left text-gray-400 font-medium">
                                {p.name}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {modal.parsedRows.slice(0, 5).map((row, i) => (
                            <tr key={i} className="border-t border-gray-700/50">
                              <td className="px-2 py-1 text-gray-500">{i + 1}</td>
                              {modal.parameters.map((p) => (
                                <td key={p.name} className="px-2 py-1 text-gray-300 truncate max-w-[150px]">
                                  {row[p.name] || <span className="text-gray-600">—</span>}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {modal.parsedRows.length > 5 && (
                        <p className="px-2 py-1 text-xs text-gray-500 bg-gray-700/30">
                          ... and {modal.parsedRows.length - 5} more rows
                        </p>
                      )}
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-between mt-5">
                  <span className="text-xs text-gray-500">
                    {modal.parsedRows.length > 0 && `${modal.parsedRows.length} rows`}
                  </span>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setModal(null)}
                      className="px-4 py-1.5 text-xs text-gray-400 hover:text-gray-200 transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => executeBatch(modal.workflowName, modal.mode, modal.parsedRows)}
                      disabled={modal.parsedRows.length === 0}
                      className={`px-4 py-1.5 text-xs font-medium rounded transition-colors disabled:opacity-30 ${
                        modal.mode === "ai"
                          ? "bg-purple-600/30 text-purple-300 hover:bg-purple-600/50"
                          : "bg-blue-600/30 text-blue-300 hover:bg-blue-600/50"
                      }`}
                    >
                      Start Batch ({modal.parsedRows.length})
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
