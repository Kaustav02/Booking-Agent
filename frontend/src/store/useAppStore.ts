import { create } from "zustand";
import { persist } from "zustand/middleware";
import type {
  CallStatus,
  AgentState,
  TranscriptEntry,
  ToolCall,
  CallSummary,
} from "../types";

interface AppState {
  callStatus: CallStatus;
  agentState: AgentState;
  agentVolume: number;
  userVolume: number;
  transcript: TranscriptEntry[];
  toolCalls: ToolCall[];
  summary: CallSummary | null;
  roomToken: string;
  roomName: string;
  wsUrl: string;
  error: string;

  setCallStatus: (s: CallStatus) => void;
  setAgentState: (s: AgentState) => void;
  setAgentVolume: (v: number) => void;
  setUserVolume: (v: number) => void;
  addTranscript: (entry: TranscriptEntry) => void;
  addToolCall: (call: ToolCall) => void;
  updateToolCall: (id: string, update: Partial<ToolCall>) => void;
  setSummary: (s: CallSummary) => void;
  setRoom: (token: string, name: string, url: string) => void;
  setError: (e: string) => void;
  reset: () => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
  callStatus: "idle",
  agentState: "idle",
  agentVolume: 0,
  userVolume: 0,
  transcript: [],
  toolCalls: [],
  summary: null,
  roomToken: "",
  roomName: "",
  wsUrl: "",
  error: "",

  setCallStatus: (s) => set({ callStatus: s }),
  setAgentState: (s) => set({ agentState: s }),
  setAgentVolume: (v) => set({ agentVolume: v }),
  setUserVolume: (v) => set({ userVolume: v }),

  addTranscript: (entry) =>
    set((state) => ({
      transcript: [...state.transcript, entry],
    })),

  addToolCall: (call) =>
    set((state) => ({
      toolCalls: [call, ...state.toolCalls].slice(0, 20),
    })),

  updateToolCall: (id, update) =>
    set((state) => ({
      toolCalls: state.toolCalls.map((t) =>
        t.id === id ? { ...t, ...update } : t
      ),
    })),

  setSummary: (s) => set({ summary: s }),

  setRoom: (token, name, url) =>
    set({ roomToken: token, roomName: name, wsUrl: url }),

  setError: (e) => set({ error: e }),

  reset: () =>
    set({
      callStatus: "idle",
      agentState: "idle",
      agentVolume: 0,
      userVolume: 0,
      transcript: [],
      toolCalls: [],
      summary: null,
      roomToken: "",
      roomName: "",
      wsUrl: "",
      error: "",
    }),
    }),
    {
      name: "mykare-store",
      // Only persist conversation data — runtime state resets on refresh
      partialize: (state) => ({
        transcript: state.transcript,
        toolCalls: state.toolCalls,
        summary: state.summary,
      }),
    }
  )
);
