import { useState } from "react";
import { api } from "../api";

export default function Screenshot() {
  const [src, setSrc] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const capture = () => {
    setLoading(true);
    setSrc(api.screenshot());
    // Image onLoad will clear loading state
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium text-gray-300">Screenshot</h3>
        <button
          onClick={capture}
          className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
        >
          Capture
        </button>
      </div>
      {src ? (
        <div className="relative">
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-900/50 rounded-lg">
              <div className="w-5 h-5 border-2 border-gray-600 border-t-blue-500 rounded-full animate-spin" />
            </div>
          )}
          <img
            src={src}
            alt="Browser screenshot"
            className="w-full rounded-lg border border-gray-800"
            onLoad={() => setLoading(false)}
            onError={() => setLoading(false)}
          />
        </div>
      ) : (
        <div className="h-32 bg-gray-900 rounded-lg border border-gray-800 flex items-center justify-center">
          <p className="text-sm text-gray-600">Click "Capture" to take a screenshot</p>
        </div>
      )}
    </div>
  );
}
