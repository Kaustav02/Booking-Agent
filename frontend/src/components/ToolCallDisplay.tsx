import React from "react";
import {
  User, Calendar, BookOpen, List, XCircle, RefreshCw,
  PhoneOff, Loader2, CheckCircle2, AlertCircle
} from "lucide-react";
import type { ToolCall } from "../types";

const TOOL_META: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
  identify_user:        { label: "Identifying Patient",     icon: <User size={16} />,       color: "blue"   },
  fetch_slots:          { label: "Fetching Slots",          icon: <Calendar size={16} />,   color: "purple" },
  book_appointment:     { label: "Booking Appointment",     icon: <BookOpen size={16} />,   color: "green"  },
  retrieve_appointments:{ label: "Retrieving Appointments", icon: <List size={16} />,       color: "yellow" },
  cancel_appointment:   { label: "Cancelling Appointment",  icon: <XCircle size={16} />,    color: "red"    },
  modify_appointment:   { label: "Rescheduling",            icon: <RefreshCw size={16} />,  color: "orange" },
  end_conversation:     { label: "Ending Call",             icon: <PhoneOff size={16} />,   color: "gray"   },
};

const COLOR_MAP: Record<string, string> = {
  blue:   "border-blue-500/40 bg-blue-500/10 text-blue-300",
  purple: "border-purple-500/40 bg-purple-500/10 text-purple-300",
  green:  "border-green-500/40 bg-green-500/10 text-green-300",
  yellow: "border-yellow-500/40 bg-yellow-500/10 text-yellow-300",
  red:    "border-red-500/40 bg-red-500/10 text-red-300",
  orange: "border-orange-500/40 bg-orange-500/10 text-orange-300",
  gray:   "border-gray-500/40 bg-gray-500/10 text-gray-300",
};

interface Props {
  toolCalls: ToolCall[];
}

export const ToolCallDisplay: React.FC<Props> = ({ toolCalls }) => {
  if (toolCalls.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-600 text-sm gap-2">
        <Calendar size={28} className="opacity-40" />
        <span>Tool calls will appear here</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 overflow-y-auto scrollbar-thin max-h-full pr-1">
      {toolCalls.map((call) => {
        const meta = TOOL_META[call.tool] ?? {
          label: call.tool,
          icon: <BookOpen size={16} />,
          color: "gray",
        };
        const colorClass = COLOR_MAP[meta.color] ?? COLOR_MAP.gray;

        return (
          <div
            key={call.id}
            className={`flex items-start gap-3 border rounded-lg px-3 py-2.5 animate-fade-in ${colorClass}`}
          >
            <div className="mt-0.5 shrink-0">{meta.icon}</div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold">{meta.label}</span>
                {call.status === "in_progress" ? (
                  <Loader2 size={12} className="animate-spin opacity-70" />
                ) : call.status === "completed" ? (
                  <CheckCircle2 size={12} className="text-green-400" />
                ) : (
                  <AlertCircle size={12} className="text-red-400" />
                )}
              </div>
              <p className="text-xs opacity-75 mt-0.5 truncate">{call.message}</p>
              <p className="text-xs opacity-40 mt-0.5">
                {new Date(call.timestamp).toLocaleTimeString()}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
};
