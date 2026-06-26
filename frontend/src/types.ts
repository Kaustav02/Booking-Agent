export type CallStatus = "idle" | "connecting" | "connected" | "ended";

export type AgentState = "idle" | "listening" | "thinking" | "speaking";

export interface TranscriptEntry {
  id: string;
  role: "user" | "assistant";
  text: string;
  timestamp: string;
}

export interface ToolCall {
  id: string;
  tool: string;
  status: "in_progress" | "completed" | "error";
  message: string;
  data?: Record<string, unknown>;
  timestamp: string;
}

export interface Appointment {
  id: number;
  date: string;
  time_slot: string;
  status: string;
  notes?: string;
  created_at?: string;
}

export interface CallSummary {
  session_id: string;
  patient_name: string;
  phone: string;
  summary: string;
  appointments: Appointment[];
  preferences: string;
  intent: string;
  timestamp: string;
}

export interface AgentEvent {
  type: "tool_start" | "tool_result" | "summary" | "call_ended" | "transcript";
  tool?: string;
  message?: string;
  data?: Record<string, unknown>;
  timestamp: string;
}
