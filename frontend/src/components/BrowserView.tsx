import { useState } from "react";

interface Props {
  noVncUrl: string;
}

export default function BrowserView({ noVncUrl }: Props) {
  const [loaded, setLoaded] = useState(false);

  return (
    <div className="relative w-full h-full min-h-[400px] bg-gray-900 rounded-lg overflow-hidden border border-gray-800">
      {!loaded && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="text-center">
            <div className="w-8 h-8 border-2 border-gray-600 border-t-blue-500 rounded-full animate-spin mx-auto mb-2" />
            <p className="text-sm text-gray-500">Connecting to browser...</p>
          </div>
        </div>
      )}
      <iframe
        src={`${noVncUrl}/vnc.html?autoconnect=true&resize=scale`}
        className="w-full h-full"
        style={{ opacity: loaded ? 1 : 0 }}
        onLoad={() => setLoaded(true)}
        title="Browser View"
      />
    </div>
  );
}
