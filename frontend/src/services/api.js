const API_BASE = import.meta.env.VITE_API_URL || "/api";

/**
 * Parse SSE lines from a text chunk.
 * Each SSE message is `data: <json>\n\n`.
 */
function parseSSELines(text) {
  const events = [];
  const lines = text.split("\n");

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("data: ")) {
      try {
        events.push(JSON.parse(trimmed.slice(6)));
      } catch {
        // skip malformed JSON
      }
    }
  }

  return events;
}

/**
 * Upload a PDF and stream analysis progress via SSE.
 *
 * @param {File} file - PDF file to analyze
 * @param {(step: number, totalSteps: number, stepName: string) => void} onProgress
 * @param {AbortSignal} [signal] - optional abort signal for cleanup
 * @returns {Promise<object>} - analysis result from backend
 */
export async function analyzeWhitepaper(file, onProgress, signal) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    headers: { Accept: "text/event-stream" },
    body: formData,
    signal,
  });

  if (!response.ok) {
    let errorMessage = "Terjadi kesalahan saat mengunggah file.";
    try {
      const body = await response.json();
      if (body.error) errorMessage = body.error;
    } catch {
      // use default message
    }

    if (response.status === 429) {
      errorMessage = "Terlalu banyak permintaan. Silakan coba lagi dalam beberapa saat.";
    }

    throw new Error(errorMessage);
  }

  const contentType = response.headers.get("Content-Type") || "";

  // Non-SSE JSON response (fallback if backend doesn't stream)
  if (contentType.includes("application/json")) {
    const result = await response.json();
    if (result.error) throw new Error(result.error);
    return result;
  }

  // SSE streaming response
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();

    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const events = parseSSELines(buffer);

    // Keep only the last incomplete line in buffer
    const lastNewline = buffer.lastIndexOf("\n");
    buffer = lastNewline >= 0 ? buffer.slice(lastNewline + 1) : buffer;

    for (const event of events) {
      if (event.status === "error") {
        throw new Error(event.error || "Terjadi kesalahan saat memproses dokumen.");
      }

      if (event.status === "complete") {
        return event.result;
      }

      // Progress event
      if (event.step != null) {
        onProgress(event.step, event.total_steps, event.step_name);
      }
    }
  }

  throw new Error("Koneksi terputus sebelum analisis selesai.");
}
