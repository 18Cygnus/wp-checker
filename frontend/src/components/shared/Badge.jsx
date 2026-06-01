import { cn } from "@/lib/utils";

const variantClasses = {
  positive: "bg-signal-positive-soft text-signal-positive border-signal-positive/20",
  warn: "bg-signal-warn-soft text-signal-warn border-signal-warn/20",
  alert: "bg-signal-alert-soft text-signal-alert border-signal-alert/20",
  accent: "bg-accent-soft text-accent-primary border-accent-primary/15",
  muted: "bg-surface-muted text-ink-secondary border-border-subtle",
};

export default function Badge({ label, variant = "muted", icon, className }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-pill border px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.2em]",
        variantClasses[variant] ?? variantClasses.muted,
        className
      )}
    >
      {icon ? <span className="flex items-center">{icon}</span> : null}
      <span>{label}</span>
    </span>
  );
}
