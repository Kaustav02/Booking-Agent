import React, { useState } from "react";
import {
  Phone, PhoneOff, Mic, MicOff, Activity
} from "lucide-react";
import { Avatar } from "./Avatar";
import { ToolCallDisplay } from "./ToolCallDisplay";
import { Transcript } from "./Transcript";
import { useAppStore } from "../store/useAppStore";
import { useLiveKitRoom } from "../hooks/useLiveKitRoom";

export const CallInterface: React.FC = () => {
  const {
    callStatus, agentState, agentVolume, userVolume,
    transcript, toolCalls, error,
  } = useAppStore();

  const { startCall, endCall, muteToggle } = useLiveKitRoom();
  const [isMuted, setIsMuted] = useState(false);
  const [activeTab, setActiveTab] = useState<"tools" | "transcript">("tools");

  const isConnecting = callStatus === "connecting";
  const isConnected = callStatus === "connected";
  const isIdle = callStatus === "idle";
  const isEnded = callStatus === "ended";

  const handleMute = async () => {
    await muteToggle();
    setIsMuted((m) => !m);
  };

  const callDurationRef = React.useRef<number>(0);
  const [callDuration, setCallDuration] = React.useState("00:00");

  React.useEffect(() => {
    if (!isConnected) {
      callDurationRef.current = 0;
      setCallDuration("00:00");
      return;
    }
    const interval = setInterval(() => {
      callDurationRef.current += 1;
      const m = Math.floor(callDurationRef.current / 60)
        .toString()
        .padStart(2, "0");
      const s = (callDurationRef.current % 60).toString().padStart(2, "0");
      setCallDuration(`${m}:${s}`);
    }, 1000);
    return () => clearInterval(interval);
  }, [isConnected]);

  return (
    <div className="flex flex-col h-full min-h-screen bg-gray-900">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm shrink-0">
        <div className="flex items-center gap-3">
          <div className="bg-blue-600 rounded-xl p-2">
            <Activity size={20} className="text-white" />
          </div>
          <div>
            <h1 className="font-bold text-white text-lg leading-tight">Mykare Health</h1>
            <p className="text-xs text-gray-400">AI Voice Reception</p>
          </div>
        </div>

        {isConnected && (
          <div className="flex items-center gap-2 text-green-400 text-sm">
            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            <span className="font-mono">{callDuration}</span>
          </div>
        )}
      </header>

      {/* Main layout */}
      <div className="flex flex-1 overflow-hidden gap-0">
        {/* Left: Avatar + Controls */}
        <div className="flex flex-col items-center justify-between w-80 shrink-0 p-6 border-r border-gray-800 bg-gray-900">
          {/* Avatar section */}
          <div className="flex flex-col items-center gap-6 flex-1 justify-center">
            <Avatar agentState={agentState} volume={agentVolume} />

            {/* User speaking indicator */}
            {isConnected && userVolume > 0.05 && (
              <div className="flex items-center gap-1.5 text-xs text-blue-400">
                <div className="flex gap-0.5 items-end h-4">
                  {[1, 2, 3, 4, 5].map((i) => (
                    <div
                      key={i}
                      className="wave-bar w-1 rounded-full bg-blue-400"
                      style={{ height: `${30 + Math.random() * 70}%` }}
                    />
                  ))}
                </div>
                <span>You are speaking</span>
              </div>
            )}
          </div>

          {/* Error message */}
          {error && (
            <div className="w-full mb-4 bg-red-500/10 border border-red-500/30 text-red-300 text-xs rounded-xl px-4 py-3">
              {error}
            </div>
          )}

          {/* Call controls */}
          <div className="flex flex-col items-center gap-4 w-full">
            {isIdle && (
              <button
                onClick={startCall}
                className="flex items-center justify-center gap-2 w-full py-3.5 bg-green-500 hover:bg-green-400 text-white font-semibold rounded-2xl transition-all duration-200 shadow-lg shadow-green-500/25 active:scale-95"
              >
                <Phone size={20} />
                Start Call with Aria
              </button>
            )}

            {isConnecting && (
              <button
                disabled
                className="flex items-center justify-center gap-2 w-full py-3.5 bg-yellow-500/20 text-yellow-300 font-semibold rounded-2xl border border-yellow-500/30 cursor-not-allowed"
              >
                <span className="w-4 h-4 border-2 border-yellow-400 border-t-transparent rounded-full animate-spin" />
                Connecting…
              </button>
            )}

            {isConnected && (
              <div className="flex gap-3 w-full">
                <button
                  onClick={handleMute}
                  className={`flex-1 flex items-center justify-center gap-2 py-3 rounded-xl font-medium text-sm transition-all ${
                    isMuted
                      ? "bg-red-500/20 border border-red-500/40 text-red-300"
                      : "bg-gray-700 hover:bg-gray-600 text-gray-200"
                  }`}
                >
                  {isMuted ? <MicOff size={16} /> : <Mic size={16} />}
                  {isMuted ? "Unmute" : "Mute"}
                </button>
                <button
                  onClick={endCall}
                  className="flex-1 flex items-center justify-center gap-2 py-3 bg-red-600 hover:bg-red-500 text-white font-semibold rounded-xl text-sm transition-all active:scale-95"
                >
                  <PhoneOff size={16} />
                  End Call
                </button>
              </div>
            )}

            {isEnded && (
              <button
                onClick={() => useAppStore.getState().reset()}
                className="flex items-center justify-center gap-2 w-full py-3.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-2xl transition-all"
              >
                <Phone size={20} />
                New Call
              </button>
            )}
          </div>

          {/* Clinic info */}
          <p className="mt-4 text-xs text-gray-600 text-center">
            Mon–Sat · 9 AM – 5 PM
          </p>
        </div>

        {/* Right: Tabs */}
        <div className="flex-1 flex flex-col overflow-hidden bg-gray-900">
          {/* Tab bar */}
          <div className="flex border-b border-gray-800 shrink-0">
            {(["tools", "transcript"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`flex-1 py-3 text-sm font-medium transition-colors capitalize ${
                  activeTab === tab
                    ? "text-white border-b-2 border-blue-500 bg-gray-800/50"
                    : "text-gray-500 hover:text-gray-300"
                }`}
              >
                {tab === "tools" ? "Tool Activity" : "Conversation"}
                {tab === "tools" && toolCalls.length > 0 && (
                  <span className="ml-2 bg-blue-600 text-white text-xs rounded-full px-1.5 py-0.5">
                    {toolCalls.length}
                  </span>
                )}
                {tab === "transcript" && transcript.length > 0 && (
                  <span className="ml-2 bg-gray-600 text-white text-xs rounded-full px-1.5 py-0.5">
                    {transcript.length}
                  </span>
                )}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div className="flex-1 overflow-hidden p-4">
            {activeTab === "tools" ? (
              <ToolCallDisplay toolCalls={toolCalls} />
            ) : (
              <Transcript entries={transcript} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
