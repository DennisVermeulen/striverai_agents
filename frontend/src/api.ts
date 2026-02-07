const BASE = "/api";

export interface TaskResponse {
  task_id: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  instruction: string;
}

export interface TaskStatusResponse extends TaskResponse {
  steps_completed: number;
  current_action: string | null;
  result: string | null;
  error: string | null;
}

export interface HealthResponse {
  status: string;
  browser_ready: boolean;
}

export interface ConfigResponse {
  llm_provider: string;
  llm_model: string;
  ollama_model: string;
  ollama_base_url: string;
  agent_max_steps: number;
  agent_step_delay: number;
}

export interface ConfigUpdate {
  llm_provider?: string;
  llm_model?: string;
  ollama_model?: string;
  agent_max_steps?: number;
  agent_step_delay?: number;
}

export interface WorkflowStep {
  action: string;
  description: string;
  coordinates?: number[];
  text?: string;
  key?: string;
  url?: string;
  element?: Record<string, string>;
}

export interface WorkflowParameter {
  name: string;
  label: string;
  default: string;
}

export interface WorkflowResponse {
  name: string;
  description: string;
  start_url: string;
  recorded_at: string;
  parameters: WorkflowParameter[];
  steps: WorkflowStep[];
}

export interface WorkflowListResponse {
  workflows: WorkflowResponse[];
}

export interface BatchRowResponse {
  index: number;
  parameters: Record<string, string>;
  status: string;
  task_id: string;
  error: string;
}

export interface BatchResponse {
  batch_id: string;
  workflow_name: string;
  status: string;
  total: number;
  completed: number;
  failed: number;
  current_index: number;
  rows: BatchRowResponse[];
}

export interface WsEvent {
  type: string;
  task_id?: string;
  step?: number;
  action?: string;
  status?: string;
  result?: string;
  error?: string;
  // Batch events
  batch_id?: string;
  workflow_name?: string;
  current_index?: number;
  total?: number;
  completed?: number;
  failed?: number;
  current_row?: Record<string, string>;
  [key: string]: unknown;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

export const api = {
  health: () => request<HealthResponse>("/health"),

  screenshot: () => `${BASE}/screenshot?t=${Date.now()}`,

  createTask: (instruction: string, url?: string, maxSteps?: number) =>
    request<TaskResponse>("/task", {
      method: "POST",
      body: JSON.stringify({
        instruction,
        url: url || undefined,
        max_steps: maxSteps || undefined,
      }),
    }),

  getTask: (taskId: string) => request<TaskStatusResponse>(`/task/${taskId}`),

  cancelTask: (taskId: string) =>
    request<{ status: string }>(`/task/${taskId}/cancel`, { method: "POST" }),

  getConfig: () => request<ConfigResponse>("/config"),

  updateConfig: (update: ConfigUpdate) =>
    request<ConfigResponse>("/config", {
      method: "POST",
      body: JSON.stringify(update),
    }),

  saveSession: () =>
    request<{ status: string; path: string }>("/session/save", {
      method: "POST",
    }),

  // Recording
  startRecording: () =>
    request<{ status: string }>("/recording/start", { method: "POST" }),

  stopRecording: (name: string, description?: string) =>
    request<WorkflowResponse>("/recording/stop", {
      method: "POST",
      body: JSON.stringify({ name, description: description || "" }),
    }),

  // Workflows
  listWorkflows: () => request<WorkflowListResponse>("/workflows"),

  getWorkflow: (name: string) => request<WorkflowResponse>(`/workflows/${name}`),

  runWorkflow: (
    name: string,
    mode: "direct" | "ai" = "direct",
    parameters: Record<string, string> = {},
  ) =>
    request<TaskResponse>(`/workflows/${name}/run`, {
      method: "POST",
      body: JSON.stringify({ mode, parameters }),
    }),

  deleteWorkflow: (name: string) =>
    request<{ status: string }>(`/workflows/${name}`, { method: "DELETE" }),

  // Batch
  startBatch: (
    name: string,
    mode: "direct" | "ai" = "direct",
    rows: Record<string, string>[],
  ) =>
    request<BatchResponse>(`/workflows/${name}/batch`, {
      method: "POST",
      body: JSON.stringify({ mode, rows }),
    }),

  getBatch: (batchId: string) => request<BatchResponse>(`/batch/${batchId}`),

  cancelBatch: (batchId: string) =>
    request<{ status: string }>(`/batch/${batchId}/cancel`, { method: "POST" }),
};

export function connectWs(onMessage: (event: WsEvent) => void): WebSocket {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${proto}//${location.host}/api/ws`);
  ws.onmessage = (e) => {
    try {
      onMessage(JSON.parse(e.data));
    } catch {
      // ignore non-JSON messages
    }
  };
  return ws;
}
