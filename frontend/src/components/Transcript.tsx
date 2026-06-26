import React, { useEffect, useRef } from "react";
import { MessageSquare } from "lucide-react";
import type { TranscriptEntry } from "../types";

interface Props {
  entries: TranscriptEntry[];
}

export const Transcript: React.FC<Props> = ({ entries }) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries]);

  if (entries.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-600 text-sm gap-2">
        <MessageSquare size={28} className="opacity-40" />
        <span>Conversation will appear here</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 overflow-y-auto scrollbar-thin max-h-full pr-1">
      {entries.map((entry) => (
        <div
          key={entry.id}
          className={`flex animate-fade-in ${
            entry.role === "user" ? "justify-end" : "justify-start"
          }`}
        >
          <div
            className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
              entry.role === "user"
                ? "bg-blue-600 text-white rounded-br-sm"
                : "bg-gray-700 text-gray-100 rounded-bl-sm"
            }`}
          >
            <p>{entry.text}</p>
            <p
              className={`text-xs mt-1 ${
                entry.role === "user" ? "text-blue-200" : "text-gray-500"
              }`}
            >
              {new Date(entry.timestamp).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </p>
          </div>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
};
