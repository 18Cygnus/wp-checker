import { AlertCircle, RefreshCcw } from "lucide-react";
import { cn } from "@/lib/utils";

export default function ErrorCard({ message, onRetry, className }) {
  return (
    <div
      className={cn(
        "rounded-lg border border-signal-alert bg-signal-alert-soft p-4",
        className
      )}
    >
      <div className="flex items-start gap-3">
        <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-signal-alert" />
        <div className="flex-1 space-y-3">
          <div>
            <p className="font-body text-sm font-medium text-ink-primary">Terjadi kendala analisis</p>
            <p className="mt-1 text-sm text-ink-secondary">{message}</p>
          </div>
          {onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              className="inline-flex items-center gap-2 rounded-button border border-signal-alert px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.16em] text-signal-alert transition-colors hover:bg-signal-alert hover:text-ink-inverse"
            >
              <RefreshCcw className="h-3.5 w-3.5" />
              Coba Lagi
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
