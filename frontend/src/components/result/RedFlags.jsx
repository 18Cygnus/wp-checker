import { AlertTriangle } from "lucide-react";

export default function RedFlags({ flags }) {
  if (!Array.isArray(flags) || !flags.length) {
    return null;
  }

  return (
    <section className="px-5 pb-8 sm:px-10 lg:px-20" style={{ paddingTop: 16 }}>
      <div className="mx-auto max-w-[1280px]">
        <div className="mb-6 flex items-center gap-3">
          <span className="font-mono text-[11px] font-semibold uppercase tracking-eyebrow text-signal-alert">
            PERHATIAN
          </span>
          <span className="h-px w-8 bg-signal-alert/30" />
          <span className="font-mono text-[11px] uppercase tracking-eyebrow text-ink-muted">
            {flags.length} temuan
          </span>
        </div>

        <div className="rounded-card border border-signal-alert/20 bg-signal-alert/5 p-6 shadow-card">
          <div className="flex items-center gap-3">
            <AlertTriangle className="h-5 w-5 text-signal-alert" />
            <h2 className="font-heading text-lg text-signal-alert">Temuan Penting</h2>
          </div>

          <ul className="mt-4 space-y-3">
            {flags.map((flag) => (
              <li key={flag} className="flex gap-3 text-sm text-ink-primary">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-signal-alert" aria-hidden="true" />
                <span>{flag}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
