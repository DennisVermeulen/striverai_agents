import { useEffect, useRef } from "react";
import type { WsEvent } from "../api";

interface Props {
  events: WsEvent[];
}

export default function ActionLog({ events }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events.length]);

  if (events.length === 0) {
    return (
      <div className="text-sm text-gray-600 italic py-4 text-center">
        No actions yet. Start a task to see live updates.
      </div>
    );
  }

  return (
    <div className="space-y-1 max-h-64 overflow-y-auto">
      {events.map((event, i) => (
        <div
          key={i}
          className="flex items-start gap-2 text-sm py-1 px-2 rounded hover:bg-gray-800/50"
        >
          <span className="text-gray-600 font-mono text-xs mt-0.5 shrink-0 w-5 text-right">
            {i + 1}
          </span>
          <EventContent event={event} />
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}

function EventContent({ event }: { event: WsEvent }) {
  switch (event.type) {
    case "step":
      return (
        <span className="text-gray-300">
          <span className="text-blue-400">{event.action}</span>
        </span>
      );
    case "task_started":
      return <span className="text-yellow-400">Task started</span>;
    case "task_completed":
      return (
        <span className="text-green-400">
          Completed: {event.result}
        </span>
      );
    case "task_failed":
      return <span className="text-red-400">Failed: {event.error}</span>;
    case "task_cancelled":
      return <span className="text-gray-400">Task cancelled</span>;
    default:
      return (
        <span className="text-gray-500">
          {event.type}: {JSON.stringify(event)}
        </span>
      );
  }
}
