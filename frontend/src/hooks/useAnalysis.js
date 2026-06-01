import { useCallback, useRef, useState } from "react";
import { analyzeWhitepaper } from "@/services/api";

/**
 * Custom hook managing the full analysis lifecycle.
 *
 * States: idle → uploading → analyzing → result | error
 *
 * @returns {{
 *   appState: "idle" | "uploading" | "analyzing" | "result" | "error",
 *   result: object | null,
 *   error: string | null,
 *   progress: { step: number, totalSteps: number, stepName: string } | null,
 *   startAnalysis: (file: File) => void,
 *   reset: () => void
 * }}
 */
export function useAnalysis() {
  const [appState, setAppState] = useState("idle");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [progress, setProgress] = useState(null);
  const abortRef = useRef(null);

  const cleanup = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
  }, []);

  const reset = useCallback(() => {
    cleanup();
    setAppState("idle");
    setResult(null);
    setError(null);
    setProgress(null);
  }, [cleanup]);

  const startAnalysis = useCallback(
    async (file) => {
      cleanup();
      setResult(null);
      setError(null);
      setProgress({ step: 0, totalSteps: 9, stepName: "Mengunggah file..." });
      setAppState("uploading");

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const analysisResult = await analyzeWhitepaper(
          file,
          (step, totalSteps, stepName) => {
            setAppState("analyzing");
            setProgress({ step, totalSteps, stepName });
          },
          controller.signal,
        );

        setResult(analysisResult);
        setAppState("result");
        setProgress(null);
      } catch (err) {
        if (err.name === "AbortError") return;
        setError(err.message || "Terjadi kesalahan yang tidak diketahui.");
        setAppState("error");
        setProgress(null);
      }
    },
    [cleanup],
  );

  return { appState, result, error, progress, startAnalysis, reset };
}
