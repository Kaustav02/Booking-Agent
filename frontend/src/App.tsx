import React from "react";
import { CallInterface } from "./components/CallInterface";
import { CallSummaryPanel } from "./components/CallSummary";
import { useAppStore } from "./store/useAppStore";

export default function App() {
  const { summary, callStatus, reset } = useAppStore();

  // Show summary overlay when call ends with a summary
  const showSummary = summary !== null && callStatus === "ended";

  return (
    <div className="h-screen overflow-hidden">
      <CallInterface />
      {showSummary && (
        <CallSummaryPanel
          summary={summary!}
          onClose={() => useAppStore.setState({ summary: null })}
          onNewCall={() => reset()}
        />
      )}
    </div>
  );
}
