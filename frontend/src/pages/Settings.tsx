import { useEffect, useState } from "react";
import { api, type ConfigResponse, type HealthResponse } from "../api";

export default function Settings() {
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  // Draft state for editable fields
  const [provider, setProvider] = useState("anthropic");
  const [llmModel, setLlmModel] = useState("");
  const [ollamaModel, setOllamaModel] = useState("");
  const [maxSteps, setMaxSteps] = useState(50);
  const [stepDelay, setStepDelay] = useState(0.5);

  // Load config and health on mount
  useEffect(() => {
    api.getConfig().then((cfg) => {
      setConfig(cfg);
      setProvider(cfg.llm_provider);
      setLlmModel(cfg.llm_model);
      setOllamaModel(cfg.ollama_model);
      setMaxSteps(cfg.agent_max_steps);
      setStepDelay(cfg.agent_step_delay);
    });
    api.health().then(setHealth);
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setMessage("");
    try {
      const updated = await api.updateConfig({
        llm_provider: provider,
        llm_model: llmModel,
        ollama_model: ollamaModel,
        agent_max_steps: maxSteps,
        agent_step_delay: stepDelay,
      });
      setConfig(updated);
      setMessage("Settings saved");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveSession = async () => {
    try {
      await api.saveSession();
      setMessage("Session saved");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to save session");
    }
  };

  if (!config) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-6 h-6 border-2 border-gray-600 border-t-blue-500 rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-xl font-bold text-white">Settings</h1>

      {/* Health status */}
      <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
        <h2 className="text-sm font-medium text-gray-300 mb-3">System Status</h2>
        <div className="flex items-center gap-3">
          <span
            className={`w-2 h-2 rounded-full ${
              health?.browser_ready ? "bg-green-400" : "bg-red-400"
            }`}
          />
          <span className="text-sm text-gray-300">
            Browser: {health?.browser_ready ? "Ready" : "Not ready"}
          </span>
        </div>
      </div>

      {/* LLM Provider */}
      <div className="bg-gray-900 rounded-lg border border-gray-800 p-4 space-y-4">
        <h2 className="text-sm font-medium text-gray-300">LLM Provider</h2>

        {/* Provider toggle */}
        <div className="flex gap-2">
          {["anthropic", "ollama"].map((p) => (
            <button
              key={p}
              onClick={() => setProvider(p)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                provider === p
                  ? "bg-blue-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:text-gray-200"
              }`}
            >
              {p.charAt(0).toUpperCase() + p.slice(1)}
            </button>
          ))}
        </div>

        {/* Model selection */}
        {provider === "anthropic" ? (
          <div>
            <label className="block text-sm text-gray-400 mb-1">
              Anthropic Model
            </label>
            <select
              value={llmModel}
              onChange={(e) => setLlmModel(e.target.value)}
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="claude-sonnet-4-5-20250929">Claude Sonnet 4.5</option>
              <option value="claude-opus-4-6">Claude Opus 4.6</option>
            </select>
          </div>
        ) : (
          <div>
            <label className="block text-sm text-gray-400 mb-1">
              Ollama Model
            </label>
            <input
              type="text"
              value={ollamaModel}
              onChange={(e) => setOllamaModel(e.target.value)}
              placeholder="e.g. gemma3:4b"
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="text-xs text-gray-600 mt-1">
              Ollama endpoint: {config.ollama_base_url}
            </p>
          </div>
        )}
      </div>

      {/* Agent settings */}
      <div className="bg-gray-900 rounded-lg border border-gray-800 p-4 space-y-4">
        <h2 className="text-sm font-medium text-gray-300">Agent Settings</h2>

        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-sm text-gray-400">Max Steps</label>
            <span className="text-sm text-gray-300 font-mono">{maxSteps}</span>
          </div>
          <input
            type="range"
            min={1}
            max={200}
            value={maxSteps}
            onChange={(e) => setMaxSteps(Number(e.target.value))}
            className="w-full accent-blue-500"
          />
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-sm text-gray-400">Step Delay (seconds)</label>
            <span className="text-sm text-gray-300 font-mono">
              {stepDelay.toFixed(1)}s
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={5}
            step={0.1}
            value={stepDelay}
            onChange={(e) => setStepDelay(Number(e.target.value))}
            className="w-full accent-blue-500"
          />
        </div>
      </div>

      {/* Browser session */}
      <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
        <h2 className="text-sm font-medium text-gray-300 mb-3">
          Browser Session
        </h2>
        <button
          onClick={handleSaveSession}
          className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm rounded-lg transition-colors"
        >
          Save Session (cookies)
        </button>
      </div>

      {/* Save button + message */}
      <div className="flex items-center gap-4">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-6 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors"
        >
          {saving ? "Saving..." : "Save Settings"}
        </button>
        {message && (
          <span
            className={`text-sm ${
              message.includes("Failed") ? "text-red-400" : "text-green-400"
            }`}
          >
            {message}
          </span>
        )}
      </div>
    </div>
  );
}
