"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { MascotState } from "@/components/student/BuddyMascot";

interface UseVoiceBuddyOptions {
  onTranscriptUpdate: (text: string) => void;
  onAutoSend?: (text: string) => void;
  autoSend?: boolean;
  subject?: string;
}

export function useVoiceBuddy({
  onTranscriptUpdate,
  onAutoSend,
  autoSend = false,
  subject,
}: UseVoiceBuddyOptions) {
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [audioLevel, setAudioLevel] = useState(0);
  const [voiceError, setVoiceError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const recognitionRef = useRef<any>(null);
  const livePreviewRef = useRef<string>("");
  const cancelledRef = useRef<boolean>(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const rafRef = useRef<number | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const playbackSourceRef = useRef<AudioBufferSourceNode | null>(null);

  const stopAudioMeter = useCallback(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    setAudioLevel(0);
  }, []);

  const stopSpeaking = useCallback(() => {
    if (playbackSourceRef.current) {
      try {
        playbackSourceRef.current.stop();
      } catch {
        // ignore
      }
      playbackSourceRef.current = null;
    }
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    stopAudioMeter();
    setIsSpeaking(false);
  }, [stopAudioMeter]);

  const startRecording = useCallback(async () => {
    setVoiceError(null);
    stopSpeaking();
    cancelledRef.current = false;
    livePreviewRef.current = "";
    chunksRef.current = [];

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/mp4")
        ? "audio/mp4"
        : "";

      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (ev) => {
        if (ev.data.size > 0) chunksRef.current.push(ev.data);
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        if (timerRef.current) clearInterval(timerRef.current);
        stopAudioMeter();
        setIsRecording(false);

        if (recognitionRef.current) {
          try {
            recognitionRef.current.stop();
          } catch {
            // ignore
          }
        }

        if (cancelledRef.current || chunksRef.current.length === 0) {
          return;
        }

        setIsTranscribing(true);
        try {
          const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
          const form = new FormData();
          form.append("audio", blob, "recording.webm");
          if (subject) form.append("subject", subject);

          const res = await fetch("/api/voice/transcribe", {
            method: "POST",
            body: form,
          });
          if (res.ok) {
            const data = await res.json();
            const cleaned = (data.transcript || "").trim() || livePreviewRef.current;
            if (cleaned) {
              onTranscriptUpdate(cleaned);
              if (autoSend && onAutoSend) onAutoSend(cleaned);
            }
          } else if (livePreviewRef.current) {
            onTranscriptUpdate(livePreviewRef.current);
          }
        } catch {
          if (livePreviewRef.current) {
            onTranscriptUpdate(livePreviewRef.current);
          }
        } finally {
          setIsTranscribing(false);
        }
      };

      // Mic volume meter
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      if (AudioCtx) {
        const ctx = new AudioCtx();
        audioCtxRef.current = ctx;
        const src = ctx.createMediaStreamSource(stream);
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 256;
        src.connect(analyser);
        const buf = new Uint8Array(analyser.frequencyBinCount);
        const tick = () => {
          analyser.getByteFrequencyData(buf);
          const avg = buf.reduce((a, b) => a + b, 0) / buf.length;
          setAudioLevel(Math.min(1, avg / 90));
          rafRef.current = requestAnimationFrame(tick);
        };
        tick();
      }

      // Layer 1: Web Speech API live preview
      const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (SpeechRec) {
        const rec = new SpeechRec();
        rec.lang = "bn-BD";
        rec.interimResults = true;
        rec.continuous = true;
        rec.onresult = (event: any) => {
          let combined = "";
          for (let i = 0; i < event.results.length; i++) {
            combined += event.results[i][0].transcript;
          }
          livePreviewRef.current = combined.trim();
          onTranscriptUpdate(livePreviewRef.current);
        };
        try {
          rec.start();
          recognitionRef.current = rec;
        } catch {
          // ignore if unsupported
        }
      }

      recorder.start(250);
      setIsRecording(true);
      setRecordingSeconds(0);
      timerRef.current = setInterval(() => {
        setRecordingSeconds((s) => s + 1);
      }, 1000);
    } catch {
      setVoiceError("mic_denied");
      setIsRecording(false);
    }
  }, [autoSend, onAutoSend, onTranscriptUpdate, stopAudioMeter, stopSpeaking, subject]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
  }, []);

  const cancelRecording = useCallback(() => {
    cancelledRef.current = true;
    livePreviewRef.current = "";
    onTranscriptUpdate("");
    stopRecording();
  }, [onTranscriptUpdate, stopRecording]);

  const speakText = useCallback(
    async (
      text: string,
      mood: "friendly" | "encouraging" | "curious" | "celebrating" = "friendly",
      language: "bn" | "en" | "mixed" = "bn"
    ) => {
      if (!text.trim()) return;
      stopSpeaking();
      setIsSpeaking(true);

      try {
        const res = await fetch("/api/voice/speak", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, mood, language }),
        });

        if (res.ok) {
          const arrayBuf = await res.arrayBuffer();
          const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
          const ctx = new AudioCtx();
          const audioBuf = await ctx.decodeAudioData(arrayBuf);
          const src = ctx.createBufferSource();
          src.buffer = audioBuf;
          const analyser = ctx.createAnalyser();
          analyser.fftSize = 256;
          src.connect(analyser);
          analyser.connect(ctx.destination);

          const buf = new Uint8Array(analyser.frequencyBinCount);
          const tick = () => {
            analyser.getByteFrequencyData(buf);
            const avg = buf.reduce((a, b) => a + b, 0) / buf.length;
            setAudioLevel(Math.min(1, avg / 90));
            rafRef.current = requestAnimationFrame(tick);
          };
          tick();

          src.onended = () => {
            stopAudioMeter();
            setIsSpeaking(false);
            ctx.close().catch(() => {});
          };
          playbackSourceRef.current = src;
          src.start(0);
          return;
        }
      } catch {
        // Fall through to browser speechSynthesis
      }

      // Browser SpeechSynthesis fallback
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        const utter = new SpeechSynthesisUtterance(text.slice(0, 600));
        utter.lang = language === "en" ? "en-US" : "bn-BD";
        const simTimer = setInterval(() => {
          setAudioLevel(0.25 + Math.random() * 0.55);
        }, 120);
        utter.onend = () => {
          clearInterval(simTimer);
          setAudioLevel(0);
          setIsSpeaking(false);
        };
        utter.onerror = () => {
          clearInterval(simTimer);
          setAudioLevel(0);
          setIsSpeaking(false);
        };
        window.speechSynthesis.speak(utter);
      } else {
        setIsSpeaking(false);
      }
    },
    [stopAudioMeter, stopSpeaking]
  );

  useEffect(() => {
    return () => {
      stopSpeaking();
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [stopSpeaking]);

  const deriveMascotState = useCallback(
    (isStreaming: boolean, toolStatus: string | null, justCompleted: boolean): MascotState => {
      if (voiceError) return "confused";
      if (isRecording) return "listening";
      if (isTranscribing) return "transcribing";
      if (isStreaming || toolStatus) return "thinking";
      if (isSpeaking) return "speaking";
      if (justCompleted) return "celebrating";
      return "idle";
    },
    [isRecording, isSpeaking, isTranscribing, voiceError]
  );

  return {
    isRecording,
    isTranscribing,
    isSpeaking,
    recordingSeconds,
    audioLevel,
    voiceError,
    startRecording,
    stopRecording,
    cancelRecording,
    speakText,
    stopSpeaking,
    deriveMascotState,
  };
}
