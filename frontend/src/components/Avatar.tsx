import React, { useEffect, useRef } from "react";
import type { AgentState } from "../types";

interface AvatarProps {
  agentState: AgentState;
  volume: number;
}

export const Avatar: React.FC<AvatarProps> = ({ agentState, volume }) => {
  const mouthRef = useRef<SVGPathElement>(null);
  const leftEyeRef = useRef<SVGEllipseElement>(null);
  const rightEyeRef = useRef<SVGEllipseElement>(null);
  const rafRef = useRef<number>(0);
  const blinkTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const isSpeaking = agentState === "speaking";
  const isListening = agentState === "listening";

  // Animate mouth based on volume
  useEffect(() => {
    cancelAnimationFrame(rafRef.current);

    if (!isSpeaking) {
      // Reset mouth to gentle smile
      if (mouthRef.current) {
        mouthRef.current.setAttribute(
          "d",
          "M 60 88 Q 80 96 100 88"
        );
      }
      return;
    }

    const animate = () => {
      if (!mouthRef.current) return;
      const v = Math.max(0, Math.min(1, volume));
      // Upper lip stays, lower jaw drops proportionally to volume
      const openness = v * 18;
      const curve = 8 + v * 10;
      mouthRef.current.setAttribute(
        "d",
        `M 60 88 Q 80 ${88 + curve} 100 88 Q 80 ${88 + openness} 60 88`
      );
      rafRef.current = requestAnimationFrame(animate);
    };

    rafRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(rafRef.current);
  }, [isSpeaking, volume]);

  // Blink animation
  useEffect(() => {
    const blink = () => {
      [leftEyeRef, rightEyeRef].forEach((ref) => {
        if (!ref.current) return;
        ref.current.setAttribute("ry", "1");
        setTimeout(() => ref.current?.setAttribute("ry", "10"), 120);
      });
    };

    blinkTimerRef.current = setInterval(blink, 3500 + Math.random() * 1500);
    return () => {
      if (blinkTimerRef.current) clearInterval(blinkTimerRef.current);
    };
  }, []);

  const ringColors = isSpeaking
    ? ["rgba(14,159,110,0.5)", "rgba(14,159,110,0.3)", "rgba(14,159,110,0.15)"]
    : isListening
    ? ["rgba(26,86,219,0.5)", "rgba(26,86,219,0.3)", "rgba(26,86,219,0.15)"]
    : ["rgba(55,65,81,0)", "rgba(55,65,81,0)", "rgba(55,65,81,0)"];

  const ringScale = 1 + volume * 0.12;

  return (
    <div className="flex flex-col items-center gap-4">
      {/* Outer animated rings */}
      <div className="relative flex items-center justify-center">
        {/* Ring 3 */}
        <div
          className="absolute rounded-full transition-all duration-150"
          style={{
            width: 240,
            height: 240,
            background: ringColors[2],
            transform: isSpeaking ? `scale(${ringScale + 0.08})` : "scale(1)",
            transition: "transform 0.08s ease, background 0.3s ease",
          }}
        />
        {/* Ring 2 */}
        <div
          className="absolute rounded-full transition-all duration-150"
          style={{
            width: 210,
            height: 210,
            background: ringColors[1],
            transform: isSpeaking ? `scale(${ringScale + 0.04})` : "scale(1)",
            transition: "transform 0.08s ease, background 0.3s ease",
          }}
        />
        {/* Ring 1 */}
        <div
          className="absolute rounded-full transition-all duration-150"
          style={{
            width: 184,
            height: 184,
            background: ringColors[0],
            transform: isSpeaking ? `scale(${ringScale})` : "scale(1)",
            transition: "transform 0.08s ease, background 0.3s ease",
          }}
        />

        {/* Face SVG */}
        <svg
          width="160"
          height="180"
          viewBox="0 0 160 180"
          className="relative z-10 drop-shadow-2xl"
          style={{ filter: "drop-shadow(0 8px 24px rgba(0,0,0,0.4))" }}
        >
          {/* Hair */}
          <ellipse cx="80" cy="48" rx="55" ry="50" fill="#1a1a2e" />
          <ellipse cx="80" cy="44" rx="50" ry="44" fill="#2d2b55" />
          {/* Side hair */}
          <ellipse cx="30" cy="90" rx="16" ry="30" fill="#1a1a2e" />
          <ellipse cx="130" cy="90" rx="16" ry="30" fill="#1a1a2e" />

          {/* Face / skin */}
          <ellipse cx="80" cy="100" rx="52" ry="62" fill="#FDDBB4" />

          {/* Ears */}
          <ellipse cx="28" cy="100" rx="10" ry="14" fill="#FBBF7A" />
          <ellipse cx="132" cy="100" rx="10" ry="14" fill="#FBBF7A" />
          <ellipse cx="28" cy="100" rx="6" ry="9" fill="#F5A877" />
          <ellipse cx="132" cy="100" rx="6" ry="9" fill="#F5A877" />

          {/* Forehead / hairline curve */}
          <ellipse cx="80" cy="56" rx="42" ry="20" fill="#FDDBB4" />

          {/* Eyebrows */}
          <path
            d="M 52 74 Q 64 70 72 73"
            stroke="#5C4033"
            strokeWidth="3"
            strokeLinecap="round"
            fill="none"
          />
          <path
            d="M 88 73 Q 96 70 108 74"
            stroke="#5C4033"
            strokeWidth="3"
            strokeLinecap="round"
            fill="none"
          />

          {/* Eye whites */}
          <ellipse cx="64" cy="84" rx="13" ry="12" fill="white" />
          <ellipse cx="96" cy="84" rx="13" ry="12" fill="white" />

          {/* Irises */}
          <ellipse cx="64" cy="85" rx="8" ry="9" fill="#3B82F6" />
          <ellipse cx="96" cy="85" rx="8" ry="9" fill="#3B82F6" />

          {/* Pupils */}
          <ellipse cx="65" cy="85" rx="4.5" ry="5" fill="#111" />
          <ellipse cx="97" cy="85" rx="4.5" ry="5" fill="#111" />

          {/* Eye highlights */}
          <ellipse cx="67" cy="82" rx="2" ry="2" fill="white" opacity="0.9" />
          <ellipse cx="99" cy="82" rx="2" ry="2" fill="white" opacity="0.9" />

          {/* Animated eyelids */}
          <ellipse ref={leftEyeRef} cx="64" cy="84" rx="13" ry="10" fill="#FDDBB4" opacity="0" />
          <ellipse ref={rightEyeRef} cx="96" cy="84" rx="13" ry="10" fill="#FDDBB4" opacity="0" />

          {/* Nose */}
          <path
            d="M 80 95 Q 75 106 74 112 Q 80 115 86 112 Q 85 106 80 95"
            fill="#F5A877"
            opacity="0.6"
          />

          {/* Mouth — animated */}
          <path
            ref={mouthRef}
            d="M 60 88 Q 80 96 100 88"
            stroke="#C75B7A"
            strokeWidth="2.5"
            strokeLinecap="round"
            fill="none"
            style={{ transform: "translateY(36px)" }}
          />

          {/* Cheek blush */}
          <ellipse cx="52" cy="110" rx="10" ry="6" fill="#F87171" opacity="0.25" />
          <ellipse cx="108" cy="110" rx="10" ry="6" fill="#F87171" opacity="0.25" />

          {/* Stethoscope / collar */}
          <rect x="55" y="158" width="50" height="20" rx="4" fill="#1A56DB" />
          <text x="80" y="172" textAnchor="middle" fill="white" fontSize="8" fontWeight="bold">
            MYKARE
          </text>

          {/* Stethoscope earpiece */}
          <circle cx="48" cy="152" r="4" fill="#9CA3AF" />
          <path d="M 48 152 Q 60 148 70 155" stroke="#9CA3AF" strokeWidth="2" fill="none" />
          <circle cx="100" cy="155" r="6" fill="#6B7280" stroke="#9CA3AF" strokeWidth="1.5" />
        </svg>
      </div>

      {/* Status label */}
      <div className="flex items-center gap-2">
        <div
          className={`w-2.5 h-2.5 rounded-full transition-colors duration-300 ${
            isSpeaking
              ? "bg-green-400 animate-pulse"
              : isListening
              ? "bg-blue-400 animate-pulse"
              : "bg-gray-500"
          }`}
        />
        <span className="text-sm font-medium text-gray-300">
          {isSpeaking
            ? "Aria is speaking"
            : isListening
            ? "Aria is listening"
            : "Aria"}
        </span>
      </div>
    </div>
  );
};
