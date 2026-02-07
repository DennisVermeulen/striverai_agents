import { useCallback, useEffect, useRef, useState } from "react";
import { api, connectWs, type BatchResponse, type TaskStatusResponse, type WsEvent } from "../api";
import TaskForm from "../components/TaskForm";
import TaskStatus from "../components/TaskStatus";
import ActionLog from "../components/ActionLog";
import BrowserView from "../components/BrowserView";
import Screenshot from "../components/Screenshot";
import RecordButton from "../components/RecordButton";
import WorkflowList from "../components/WorkflowList";
import BatchProgress from "../components/BatchProgress";

export default function Dashboard() {
  const [taskId, setTaskId] = useState<string | null>(null);
  const [task, setTask] = useState<TaskStatusResponse | null>(null);
  const [events, setEvents] = useState<WsEvent[]>([]);
  const [viewMode, setViewMode] = useState<"vnc" | "screenshot">("vnc");
  const [workflowRefresh, setWorkflowRefresh] = useState(0);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [batch, setBatch] = useState<BatchResponse | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const batchPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Connect WebSocket on mount
  useEffect(() => {
    const ws = connectWs((event) => {
      setEvents((prev) => [...prev, event]);

      // Auto-update task status from WS events
      if (event.type === "task_status" && event.task_id && event.status) {
        setTask((prev) =>
          prev && prev.task_id === event.task_id
            ? {
                ...prev,
                status: event.status as TaskStatusResponse["status"],
                steps_completed: event.step ?? prev.steps_completed,
                current_action: event.action ?? prev.current_action,
                result: event.result ?? prev.result,
                error: event.error ?? prev.error,
              }
            : prev
        );
      }

      // Auto-update batch from WS events
      if (event.type === "batch_progress" && event.batch_id) {
        setBatch((prev) => {
          if (!prev || prev.batch_id !== event.batch_id) return prev;
          return {
            ...prev,
            status: (event.status as string) ?? prev.status,
            current_index: event.current_index ?? prev.current_index,
            completed: event.completed ?? prev.completed,
            failed: event.failed ?? prev.failed,
          };
        });
      }
    });
    wsRef.current = ws;
    return () => ws.close();
  }, []);

  // Poll task status while running
  useEffect(() => {
    if (!taskId) return;

    const poll = async () => {
      try {
        const status = await api.getTask(taskId);
        setTask(status);
        if (status.status !== "running" && status.status !== "pending") {
          if (pollRef.current) clearInterval(pollRef.current);
        }
      } catch {
        // Task may not exist yet
      }
    };

    poll();
    pollRef.current = setInterval(poll, 1500);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [taskId]);

  // Poll batch status while running
  useEffect(() => {
    if (!batchId) return;

    const poll = async () => {
      try {
        const res = await api.getBatch(batchId);
        setBatch(res);
        if (res.status !== "running" && res.status !== "pending") {
          if (batchPollRef.current) clearInterval(batchPollRef.current);
        }
      } catch {
        // Batch may not exist yet
      }
    };

    poll();
    batchPollRef.current = setInterval(poll, 2000);
    return () => {
      if (batchPollRef.current) clearInterval(batchPollRef.current);
    };
  }, [batchId]);

  const handleTaskStarted = useCallback((id: string) => {
    setTaskId(id);
    setEvents([]);
    setTask(null);
  }, []);

  const handleBatchStarted = useCallback((id: string) => {
    setBatchId(id);
    setBatch(null);
    setEvents([]);
    setTask(null);
    setTaskId(null);
  }, []);

  const handleCancel = useCallback(async () => {
    if (taskId) {
      await api.cancelTask(taskId);
    }
  }, [taskId]);

  const handleBatchCancel = useCallback(async () => {
    if (batchId) {
      await api.cancelBatch(batchId);
    }
  }, [batchId]);

  const isRunning = task?.status === "running" || task?.status === "pending";
  const isBatchRunning = batch?.status === "running" || batch?.status === "pending";

  // Determine noVNC URL — same host, port 6080
  const noVncUrl = `${location.protocol}//${location.hostname}:6080`;

  return (
    <div className="h-full flex flex-col gap-6">
      {/* Top section: Form + Browser side by side */}
      <div className="flex gap-6 min-h-0 flex-1">
        {/* Left column: Task form + status */}
        <div className="w-96 shrink-0 space-y-4 overflow-y-auto">
          {/* Task Form */}
          <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
            <h2 className="text-sm font-medium text-gray-300 mb-3">New Task</h2>
            <TaskForm onTaskStarted={handleTaskStarted} disabled={isRunning || isBatchRunning} />
          </div>

          {/* Batch Progress */}
          {batch && (
            <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
              <h2 className="text-sm font-medium text-gray-300 mb-3">
                Batch Progress
              </h2>
              <BatchProgress batch={batch} onCancel={handleBatchCancel} />
            </div>
          )}

          {/* Task Status */}
          {task && (
            <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
              <h2 className="text-sm font-medium text-gray-300 mb-3">
                Task Status
              </h2>
              <TaskStatus task={task} onCancel={handleCancel} />
            </div>
          )}

          {/* Record Workflow */}
          <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
            <h2 className="text-sm font-medium text-gray-300 mb-3">
              Record &amp; Replay
            </h2>
            <RecordButton
              disabled={isRunning || isBatchRunning}
              onWorkflowSaved={() => setWorkflowRefresh((n) => n + 1)}
            />
          </div>

          {/* Saved Workflows */}
          <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
            <h2 className="text-sm font-medium text-gray-300 mb-3">
              Workflows
            </h2>
            <WorkflowList
              onTaskStarted={handleTaskStarted}
              onBatchStarted={handleBatchStarted}
              refreshTrigger={workflowRefresh}
            />
          </div>

        </div>

        {/* Right column: Browser view */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* View mode toggle */}
          <div className="flex items-center gap-2 mb-2">
            <button
              onClick={() => setViewMode("vnc")}
              className={`text-xs px-2 py-1 rounded transition-colors ${
                viewMode === "vnc"
                  ? "bg-blue-600/20 text-blue-400"
                  : "text-gray-500 hover:text-gray-300"
              }`}
            >
              Live Browser
            </button>
            <button
              onClick={() => setViewMode("screenshot")}
              className={`text-xs px-2 py-1 rounded transition-colors ${
                viewMode === "screenshot"
                  ? "bg-blue-600/20 text-blue-400"
                  : "text-gray-500 hover:text-gray-300"
              }`}
            >
              Screenshot
            </button>
          </div>

          {viewMode === "vnc" ? (
            <BrowserView noVncUrl={noVncUrl} />
          ) : (
            <div className="flex-1 bg-gray-900 rounded-lg border border-gray-800 p-4">
              <Screenshot />
            </div>
          )}
        </div>
      </div>

      {/* Bottom section: Action log */}
      <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
        <h2 className="text-sm font-medium text-gray-300 mb-3">Action Log</h2>
        <ActionLog events={events} />
      </div>
    </div>
  );
}
