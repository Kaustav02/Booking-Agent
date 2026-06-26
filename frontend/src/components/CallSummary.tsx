import React from "react";
import {
  FileText, Calendar, User, Phone, Clock, Tag, X
} from "lucide-react";
import type { CallSummary, Appointment } from "../types";

interface Props {
  summary: CallSummary;
  onClose: () => void;
  onNewCall: () => void;
}

function formatDate(dateStr: string) {
  try {
    return new Date(dateStr + "T00:00:00").toLocaleDateString(undefined, {
      weekday: "short", month: "short", day: "numeric", year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

function formatTimestamp(ts: string) {
  try {
    return new Date(ts).toLocaleString(undefined, {
      month: "short", day: "numeric", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return ts;
  }
}

export const CallSummaryPanel: React.FC<Props> = ({ summary, onClose, onNewCall }) => {
  const activeAppts = summary.appointments.filter(
    (a: Appointment) => a.status === "booked"
  );

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-fade-in">
      <div className="bg-gray-800 border border-gray-700 rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto scrollbar-thin animate-slide-up">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-gray-700">
          <div className="flex items-center gap-3">
            <div className="bg-green-500/20 p-2 rounded-lg">
              <FileText size={20} className="text-green-400" />
            </div>
            <div>
              <h2 className="font-bold text-white text-lg">Call Summary</h2>
              <p className="text-xs text-gray-400">{formatTimestamp(summary.timestamp)}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors p-1 rounded-lg hover:bg-gray-700"
          >
            <X size={20} />
          </button>
        </div>

        <div className="p-5 flex flex-col gap-5">
          {/* Patient Info */}
          <div className="bg-gray-700/50 rounded-xl p-4 flex flex-col gap-2">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">
              Patient
            </h3>
            <div className="flex items-center gap-2 text-sm text-white">
              <User size={14} className="text-blue-400" />
              <span>{summary.patient_name || "—"}</span>
            </div>
            <div className="flex items-center gap-2 text-sm text-white">
              <Phone size={14} className="text-blue-400" />
              <span>{summary.phone || "—"}</span>
            </div>
            {summary.intent && (
              <div className="flex items-center gap-2 text-sm text-white">
                <Tag size={14} className="text-purple-400" />
                <span className="capitalize">{summary.intent}</span>
              </div>
            )}
          </div>

          {/* Summary */}
          <div>
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
              Conversation Summary
            </h3>
            <p className="text-sm text-gray-200 leading-relaxed bg-gray-700/30 rounded-xl p-4 border border-gray-600/40">
              {summary.summary || "No summary available."}
            </p>
          </div>

          {/* Appointments */}
          <div>
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
              Appointments ({activeAppts.length})
            </h3>
            {activeAppts.length === 0 ? (
              <p className="text-sm text-gray-500 italic">No appointments booked.</p>
            ) : (
              <div className="flex flex-col gap-2">
                {activeAppts.map((appt: Appointment) => (
                  <div
                    key={appt.id}
                    className="flex items-center gap-3 bg-green-500/10 border border-green-500/30 rounded-xl px-4 py-3"
                  >
                    <Calendar size={16} className="text-green-400 shrink-0" />
                    <div>
                      <p className="text-sm font-medium text-white">
                        {formatDate(appt.date)}
                      </p>
                      <div className="flex items-center gap-1 text-xs text-gray-400 mt-0.5">
                        <Clock size={11} />
                        <span>{appt.time_slot}</span>
                        {appt.notes && (
                          <span className="ml-2 text-gray-500">· {appt.notes}</span>
                        )}
                      </div>
                    </div>
                    <span className="ml-auto text-xs bg-green-500/20 text-green-300 px-2 py-0.5 rounded-full">
                      Confirmed
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Preferences */}
          {summary.preferences && (
            <div>
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                Patient Preferences
              </h3>
              <p className="text-sm text-gray-200 bg-gray-700/30 rounded-xl p-4 border border-gray-600/40">
                {summary.preferences}
              </p>
            </div>
          )}

          {/* Session ID */}
          <p className="text-xs text-gray-600 text-center">
            Session: {summary.session_id}
          </p>
        </div>

        {/* Footer */}
        <div className="flex gap-3 p-5 pt-0">
          <button
            onClick={onClose}
            className="flex-1 py-2.5 rounded-xl border border-gray-600 text-gray-300 text-sm font-medium hover:bg-gray-700 transition-colors"
          >
            Close
          </button>
          <button
            onClick={onNewCall}
            className="flex-1 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold transition-colors"
          >
            New Call
          </button>
        </div>
      </div>
    </div>
  );
};
