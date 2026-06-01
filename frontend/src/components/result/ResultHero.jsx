import { FileText, Plus } from "lucide-react";
import { formatDuration, formatFileSize, formatScore } from "@/utils/formatters";

export default function ResultHero({ data, onReset }) {
  // rHero from pencil-new.pen Frame 2 (uhbk7):
  // padding 56/80/32/80, vertical layout
  // rEyebrowRow + rTopRow (file block on left, dark CTA on right)
  const filename = data?.filename ?? "Dokumen tanpa nama";
  const sizeText = formatFileSize(data?.file_size_bytes);
  const pages = Number(data?.page_count) || 0;

  return (
    <section
      className="px-5 sm:px-10 lg:px-20"
      style={{ paddingTop: 56, paddingBottom: 32 }}
    >
      <div className="mx-auto flex max-w-[1280px] flex-col gap-5">
        {/* rEyebrowRow */}
        <div className="flex flex-wrap items-center gap-2.5">
          <span className="font-mono text-[11px] font-medium uppercase tracking-eyebrow text-accent-primary">
            02 / Hasil Analisis
          </span>
          <span className="h-px w-8 bg-border-strong" aria-hidden />
          <span className="font-mono text-[10px] font-medium uppercase tracking-eyebrow text-signal-positive">
            Analisis Selesai · {formatDuration(data?.analysis_time_seconds)}
          </span>
        </div>

        {/* rTopRow */}
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex flex-1 flex-col gap-2.5">
            {/* rFileChip */}
            <div className="inline-flex w-fit items-center gap-2.5 rounded-button bg-surface-muted px-3 py-2">
              <FileText
                className="h-3.5 w-3.5 text-ink-secondary"
                strokeWidth={1.75}
              />
              <span className="font-mono text-[12px] font-medium text-ink-primary">
                {filename}
              </span>
              <span className="font-mono text-[11px] text-ink-muted">
                · {sizeText} · {pages} hlm
              </span>
            </div>

            <h1 className="font-heading text-[32px] font-normal leading-[1.12] tracking-[-0.024em] text-ink-primary lg:text-display-result">
              Telaah selesai. Berikut sinyal-sinyal yang ditemukan.
            </h1>

            <p className="max-w-[680px] font-body text-[15px] leading-[1.55] text-ink-secondary">
              Hasil ini adalah penilaian berbasis aturan terhadap sinyal-sinyal
              dokumen, bukan rekomendasi investasi. Telaah temuan secara
              keseluruhan sebelum mengambil keputusan.
            </p>
          </div>

          {/* rCTA: dark ink-primary button with plus icon */}
          <button
            type="button"
            onClick={onReset}
            className="inline-flex shrink-0 items-center gap-2 self-start rounded-button bg-ink-primary px-[18px] py-3 font-body text-[13px] font-medium text-ink-inverse transition-opacity hover:opacity-90"
          >
            <Plus className="h-3.5 w-3.5" strokeWidth={2.5} />
            <span>Analisis PDF lain</span>
          </button>
        </div>

        {/* Hidden score data passed to ExecutiveSummary; no separate ring here per design */}
        <span className="sr-only">
          Skor kredibilitas: {formatScore(data?.credibility_score)} dari 100
        </span>
      </div>
    </section>
  );
}
