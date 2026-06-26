import { useEffect, useRef, useCallback } from "react";
import {
  Room,
  RoomEvent,
  Track,
  RemoteParticipant,
  ParticipantEvent,
  LocalParticipant,
  DisconnectReason,
  Participant,
} from "livekit-client";
import { useAppStore } from "../store/useAppStore";
import type { AgentEvent, ToolCall, TranscriptEntry } from "../types";

const API_BASE = "/api";

export function useLiveKitRoom() {
  const roomRef = useRef<Room | null>(null);
  const agentAudioContextRef = useRef<AudioContext | null>(null);
  const agentAnalyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number>(0);
  const userAnalyserRef = useRef<AnalyserNode | null>(null);
  const userAnimFrameRef = useRef<number>(0);
  const agentAudioElementsRef = useRef<HTMLAudioElement[]>([]);

  const store = useAppStore();

  const cleanup = useCallback(() => {
    cancelAnimationFrame(animFrameRef.current);
    cancelAnimationFrame(userAnimFrameRef.current);
    agentAudioContextRef.current?.close();
    agentAudioContextRef.current = null;
    agentAnalyserRef.current = null;
    userAnalyserRef.current = null;
    agentAudioElementsRef.current.forEach((el) => { el.pause(); el.remove(); });
    agentAudioElementsRef.current = [];
  }, []);

  const trackAgentVolume = useCallback(
    (track: MediaStreamTrack) => {
      cleanup();
      const ctx = new AudioContext();
      agentAudioContextRef.current = ctx;

      const stream = new MediaStream([track]);
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.7;
      source.connect(analyser);
      source.connect(ctx.destination); // route to speakers
      agentAnalyserRef.current = analyser;

      const data = new Uint8Array(analyser.frequencyBinCount);

      const tick = () => {
        analyser.getByteFrequencyData(data);
        const rms = Math.sqrt(data.reduce((s, v) => s + v * v, 0) / data.length);
        const volume = Math.min(rms / 60, 1);
        store.setAgentVolume(volume);
        store.setAgentState(volume > 0.05 ? "speaking" : "idle");
        animFrameRef.current = requestAnimationFrame(tick);
      };
      tick();
    },
    [cleanup, store]
  );

  const trackUserVolume = useCallback(
    (track: MediaStreamTrack) => {
      cancelAnimationFrame(userAnimFrameRef.current);
      const ctx = agentAudioContextRef.current || new AudioContext();
      const stream = new MediaStream([track]);
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.7;
      source.connect(analyser);
      userAnalyserRef.current = analyser;

      const data = new Uint8Array(analyser.frequencyBinCount);
      const tick = () => {
        analyser.getByteFrequencyData(data);
        const rms = Math.sqrt(data.reduce((s, v) => s + v * v, 0) / data.length);
        store.setUserVolume(Math.min(rms / 60, 1));
        userAnimFrameRef.current = requestAnimationFrame(tick);
      };
      tick();
    },
    [store]
  );

  const handleAgentEvent = useCallback(
    (payload: Uint8Array) => {
      let event: AgentEvent;
      try {
        event = JSON.parse(new TextDecoder().decode(payload));
      } catch {
        return;
      }

      if (event.type === "tool_start") {
        const toolCall: ToolCall = {
          id: `${event.tool}-${Date.now()}`,
          tool: event.tool || "",
          status: "in_progress",
          message: event.message || "",
          data: event.data,
          timestamp: event.timestamp,
        };
        store.addToolCall(toolCall);
      } else if (event.type === "tool_result") {
        store.addToolCall({
          id: `${event.tool}-${Date.now()}`,
          tool: event.tool || "",
          status: "completed",
          message: event.message || "",
          data: event.data,
          timestamp: event.timestamp,
        });
      } else if (event.type === "summary") {
        const d = event.data as Record<string, unknown>;
        store.setSummary({
          session_id: d.session_id as string,
          patient_name: d.patient_name as string,
          phone: d.phone as string,
          summary: d.summary as string,
          appointments: (d.appointments as []) || [],
          preferences: d.preferences as string,
          intent: d.intent as string,
          timestamp: event.timestamp,
        });
      } else if (event.type === "call_ended") {
        store.setCallStatus("ended");
        store.setAgentState("idle");
      } else if (event.type === "transcript") {
        const d = event.data as Record<string, unknown>;
        const entry: TranscriptEntry = {
          id: Date.now().toString(),
          role: d.role as "user" | "assistant",
          text: d.text as string,
          timestamp: event.timestamp,
        };
        store.addTranscript(entry);
      }
    },
    [store]
  );

  const connectToRoom = useCallback(
    async (wsUrl: string, token: string) => {
      if (roomRef.current) {
        await roomRef.current.disconnect();
      }

      const room = new Room({
        adaptiveStream: true,
        dynacast: true,
        audioCaptureDefaults: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      roomRef.current = room;

      room.on(RoomEvent.Connected, () => {
        store.setCallStatus("connected");
        store.setAgentState("idle");
      });

      room.on(RoomEvent.Disconnected, (reason?: DisconnectReason) => {
        cleanup();
        if (reason !== DisconnectReason.CLIENT_INITIATED) {
          store.setCallStatus("ended");
        }
      });

      room.on(RoomEvent.DataReceived, (payload: Uint8Array, participant?: Participant) => {
        if (participant?.identity !== room.localParticipant.identity) {
          handleAgentEvent(payload);
        }
      });

      room.on(RoomEvent.TrackSubscribed, (track, _pub, participant: RemoteParticipant) => {
        if (track.kind === Track.Kind.Audio) {
          // Attach to an <audio> element so the browser actually plays it
          const audioEl = track.attach();
          audioEl.autoplay = true;
          document.body.appendChild(audioEl);
          agentAudioElementsRef.current.push(audioEl);

          // Also wire up AnalyserNode for avatar volume animation
          const mediaTrack = track.mediaStreamTrack;
          if (mediaTrack) {
            trackAgentVolume(mediaTrack);
          }

          track.on("ended", () => {
            track.detach(audioEl);
            audioEl.remove();
            agentAudioElementsRef.current = agentAudioElementsRef.current.filter(el => el !== audioEl);
            cleanup();
          });
        }
      });

      room.on(RoomEvent.TrackUnsubscribed, (track) => {
        if (track.kind === Track.Kind.Audio) {
          agentAudioElementsRef.current.forEach((el) => track.detach(el));
        }
        cleanup();
        store.setAgentVolume(0);
        store.setAgentState("idle");
      });

      room.on(RoomEvent.ParticipantConnected, (participant: RemoteParticipant) => {
        participant.on(ParticipantEvent.IsSpeakingChanged, (speaking: boolean) => {
          if (speaking) store.setAgentState("speaking");
        });
      });

      room.on(
        RoomEvent.ActiveSpeakersChanged,
        (speakers: Participant[]) => {
          const agentSpeaking = speakers.some(
            (s) => s.identity !== room.localParticipant.identity
          );
          const userSpeaking = speakers.some(
            (s) => s.identity === room.localParticipant.identity
          );
          if (agentSpeaking) store.setAgentState("speaking");
          else if (userSpeaking) store.setAgentState("listening");
          else store.setAgentState("idle");
        }
      );

      await room.connect(wsUrl, token);

      // Enable microphone
      await room.localParticipant.setMicrophoneEnabled(true);

      // Track user's mic volume
      const micPubs = Array.from(room.localParticipant.trackPublications.values());
      const micPub = micPubs.find((p) => p.track?.kind === Track.Kind.Audio);
      if (micPub?.track?.mediaStreamTrack) {
        trackUserVolume(micPub.track.mediaStreamTrack);
      }
    },
    [cleanup, handleAgentEvent, store, trackAgentVolume, trackUserVolume]
  );

  const startCall = useCallback(async () => {
    store.setCallStatus("connecting");
    store.setError("");

    try {
      const res = await fetch(`${API_BASE}/start-call`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_name: "Patient" }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to start call");
      }

      const { token, room_name, ws_url } = await res.json();
      store.setRoom(token, room_name, ws_url);

      await connectToRoom(ws_url, token);
    } catch (e) {
      store.setError(e instanceof Error ? e.message : "Unknown error");
      store.setCallStatus("idle");
    }
  }, [connectToRoom, store]);

  const endCall = useCallback(async () => {
    if (roomRef.current) {
      await roomRef.current.disconnect(true);
      roomRef.current = null;
    }
    cleanup();
    store.setCallStatus("ended");
    store.setAgentState("idle");
    store.setAgentVolume(0);
    store.setUserVolume(0);
  }, [cleanup, store]);

  const muteToggle = useCallback(async () => {
    const lp = roomRef.current?.localParticipant;
    if (!lp) return;
    const muted = lp.isMicrophoneEnabled;
    await lp.setMicrophoneEnabled(!muted);
  }, []);

  useEffect(() => {
    return () => {
      cleanup();
      roomRef.current?.disconnect();
    };
  }, [cleanup]);

  return { startCall, endCall, muteToggle };
}
