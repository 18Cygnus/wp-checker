import { useEffect, useId, useRef, useState } from "react";
import { ArrowUp, Check, FileText, FolderOpen } from "lucide-react";
import ErrorCard from "@/components/shared/ErrorCard";
import { cn } from "@/lib/utils";

const MAX_FILE_SIZE = 25 * 1024 * 1024;

const CAPABILITY_ITEMS = [
  "Extract key information dari whitepaper",
  "Deteksi profile-aware coverage dan content balance",
  "Sinyal plagiarisme dan peringatan kualitas linguistik",
  "Ringkasan sinyal untuk ditelaah calon investor",
];

const META_ITEMS = ["PDF", "Maks. 25 MB", "Satu dokumen"];

function formatFileSize(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 KB";
  const mb = bytes / (1024 * 1024);
  if (mb >= 1) return `${mb.toFixed(mb >= 10 ? 0 : 1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function validateFiles(fileList) {
  if (!fileList?.length) return "Pilih satu file PDF untuk memulai analisis.";
  if (fileList.length > 1) return "Hanya satu file yang dapat diunggah dalam satu waktu.";
  const [file] = fileList;
  if (!file.name.toLowerCase().endsWith(".pdf")) return "Format file harus PDF.";
  if (file.size > MAX_FILE_SIZE) return "Ukuran file melebihi batas 25 MB.";
  return null;
}

// Composed document icon from pencil-new.pen (NaeWC + lrXwX + Ah6uU stack)
function DocIcon() {
  return (
    <div className="relative h-20 w-16">
      {/* docIconBg: 56x72 white card with dark stroke */}
      <div className="absolute left-1 top-1 h-[72px] w-14 rounded-[4px] border border-ink-primary bg-surface-card">
        <span className="absolute left-2 right-2 top-3 h-[2px] rounded bg-ink-primary" />
        <span className="absolute left-2 right-3 top-[22px] h-[2px] rounded bg-ink-primary" />
        <span className="absolute left-2 right-4 top-[32px] h-[2px] rounded bg-border-strong" />
        <span className="absolute left-2 right-2 top-[42px] h-[2px] rounded bg-border-strong" />
        <span className="absolute left-2 right-5 top-[52px] h-[2px] rounded bg-border-strong" />
      </div>
      {/* docIconCorner: 14x14 fold */}
      <div className="absolute right-1 top-1 h-[14px] w-[14px] rounded-bl-[2px] border-b border-l border-ink-primary bg-surface-tinted" />
      {/* docIconAccent: 18x18 blue circle with arrow-up */}
      <div className="absolute -bottom-0 -right-0 flex h-[18px] w-[18px] items-center justify-center rounded-full bg-accent-primary">
        <ArrowUp className="h-3 w-3 text-ink-inverse" strokeWidth={2.5} />
      </div>
    </div>
  );
}

export default function UploadCard({ onFileSelect, uploadState, progress, error }) {
  const inputId = useId();
  const inputRef = useRef(null);
  const dragDepthRef = useRef(0);
  const [isDragging, setIsDragging] = useState(false);
  const [inlineError, setInlineError] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);

  useEffect(() => {
    if (uploadState === "idle") {
      dragDepthRef.current = 0;
      setIsDragging(false);
    }
  }, [uploadState]);

  const handleValidFile = (file) => {
    setInlineError(null);
    setSelectedFile(file);
    onFileSelect(file);
  };

  const handleFiles = (fileList) => {
    const msg = validateFiles(fileList);
    if (msg) {
      setInlineError(msg);
      return;
    }
    handleValidFile(fileList[0]);
  };

  const handleInputChange = (e) => {
    handleFiles(e.target.files);
    e.target.value = "";
  };

  const handleDragEnter = (e) => {
    e.preventDefault();
    dragDepthRef.current += 1;
    setIsDragging(true);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
    if (!isDragging) setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
    if (dragDepthRef.current === 0) setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    dragDepthRef.current = 0;
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  const progressValue = progress
    ? Math.round((progress.step / Math.max(progress.totalSteps, 1)) * 100)
    : 0;
  const isBusy = uploadState === "uploading" || uploadState === "analyzing";

  return (
    <section className="w-full rounded-card border border-border-subtle bg-surface-card p-7 shadow-card">
      {/* upTopRow: header with title + step badge */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h2 className="font-heading text-display-card font-medium text-ink-primary">
            Unggah Whitepaper
          </h2>
          <p className="font-body text-[12px] text-ink-muted">
            Satu PDF · alur dokumen tunggal
          </p>
        </div>
        <span className="inline-flex shrink-0 items-center rounded-pill bg-accent-soft px-3 py-1.5 font-mono text-[10px] font-medium uppercase tracking-mono-meta text-accent-primary">
          Langkah 1 / 2
        </span>
      </div>

      {uploadState === "error" && error ? (
        <ErrorCard className="mt-6" message={error} />
      ) : null}

      {isBusy ? (
        <div className="mt-6 space-y-4">
          {selectedFile ? (
            <div className="flex items-center gap-3 rounded-input border border-border-subtle bg-surface-tinted px-4 py-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-surface-card text-accent-primary">
                <FileText className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <p className="truncate font-body text-sm font-medium text-ink-primary">
                  {selectedFile.name}
                </p>
                <p className="font-mono text-[11px] text-ink-muted">
                  {formatFileSize(selectedFile.size)}
                </p>
              </div>
            </div>
          ) : null}

          {/* progressSection from pencil-new.pen */}
          <div className="space-y-2 pt-3">
            <div className="border-t border-border-subtle pt-3">
              <div className="flex items-center justify-between">
                <span className="font-body text-[13px] font-medium text-ink-primary">
                  {uploadState === "uploading"
                    ? "Mengunggah dokumen..."
                    : "Menganalisis dokumen..."}
                </span>
                <span className="font-mono text-[13px] font-semibold text-accent-primary">
                  {progressValue}%
                </span>
              </div>
              <div className="mt-2 h-1.5 w-full overflow-hidden rounded-bar bg-surface-muted">
                <div
                  className="h-full rounded-bar bg-accent-primary transition-all duration-300"
                  style={{ width: `${progressValue}%` }}
                />
              </div>
              {progress ? (
                <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.04em] text-ink-muted">
                  Langkah {progress.step}/{progress.totalSteps} ·{" "}
                  {progress.stepName}
                </p>
              ) : null}
            </div>
          </div>
        </div>
      ) : (
        <>
          {/* dropZone */}
          <div
            className={cn(
              "mt-6 flex flex-col items-center gap-5 rounded-input border-[1.5px] bg-surface-tinted px-7 py-11 text-center transition-colors",
              isDragging
                ? "border-accent-primary bg-accent-soft/40"
                : "border-border-strong"
            )}
            onDragEnter={handleDragEnter}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <DocIcon />

            <div className="flex flex-col items-center gap-1.5">
              <p className="font-body text-[15px] font-medium text-ink-primary">
                {isDragging
                  ? "Lepaskan PDF di sini"
                  : "Tarik & lepas PDF whitepaper di sini"}
              </p>
              <p className="font-body text-[12px] text-ink-muted">atau</p>
            </div>

            {/* browseBtn: dark surface.inverse button */}
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="inline-flex items-center gap-2 rounded-button bg-surface-inverse px-[22px] py-3 font-body text-[13px] font-medium text-ink-inverse transition-opacity hover:opacity-90"
            >
              <FolderOpen className="h-[14px] w-[14px]" strokeWidth={2} />
              <span>Pilih file PDF</span>
            </button>

            {/* metaRow: dot-separated mono */}
            <div className="flex flex-wrap items-center justify-center gap-x-[18px] gap-y-2">
              {META_ITEMS.map((item, idx) => (
                <span key={item} className="flex items-center gap-[18px]">
                  <span className="font-mono text-[10px] font-medium uppercase tracking-[0.1em] text-ink-muted">
                    {item}
                  </span>
                  {idx < META_ITEMS.length - 1 ? (
                    <span
                      className="h-1 w-1 rounded-full bg-ink-muted/60"
                      aria-hidden
                    />
                  ) : null}
                </span>
              ))}
            </div>

            <input
              id={inputId}
              ref={inputRef}
              type="file"
              accept=".pdf"
              className="sr-only"
              onChange={handleInputChange}
            />
          </div>

          {inlineError ? (
            <p className="mt-3 font-body text-[13px] text-signal-alert">
              {inlineError}
            </p>
          ) : null}

          {/* capList: 4 capability rows inside the card */}
          <ul className="mt-6 space-y-2.5 px-1 pt-2">
            {CAPABILITY_ITEMS.map((item) => (
              <li
                key={item}
                className="flex items-start gap-2.5 font-body text-[13px] text-ink-secondary"
              >
                <Check
                  className="mt-[3px] h-[14px] w-[14px] shrink-0 text-signal-positive"
                  strokeWidth={2.5}
                />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
