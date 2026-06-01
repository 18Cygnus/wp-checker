import { cn } from "@/lib/utils";

const colorClasses = {
  accent: "[&::-moz-progress-bar]:bg-accent-primary [&::-webkit-progress-value]:bg-accent-primary",
  positive: "[&::-moz-progress-bar]:bg-signal-positive [&::-webkit-progress-value]:bg-signal-positive",
  warn: "[&::-moz-progress-bar]:bg-signal-warn [&::-webkit-progress-value]:bg-signal-warn",
  alert: "[&::-moz-progress-bar]:bg-signal-alert [&::-webkit-progress-value]:bg-signal-alert",
  teal: "[&::-moz-progress-bar]:bg-accent-teal [&::-webkit-progress-value]:bg-accent-teal",
};

const heightClasses = {
  2: "h-0.5",
  4: "h-1",
  6: "h-1.5",
  8: "h-2",
};

export default function ProgressBar({
  value,
  color = "accent",
  height = 4,
  label,
  className,
}) {
  const clampedValue = Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : 0;

  return (
    <div className={cn("w-full", className)}>
      <progress
        className={cn(
          "w-full overflow-hidden rounded-full bg-surface-muted align-middle transition-all duration-700 ease-out [&::-webkit-progress-bar]:rounded-full [&::-webkit-progress-bar]:bg-surface-muted [&::-webkit-progress-value]:rounded-full [&::-webkit-progress-value]:transition-all [&::-webkit-progress-value]:duration-700 [&::-webkit-progress-value]:ease-out",
          heightClasses[height] ?? heightClasses[4],
          colorClasses[color] ?? colorClasses.accent
        )}
        max="100"
        value={clampedValue}
      />
      {label ? (
        <p className="mt-2 font-mono text-[11px] text-ink-muted">{label}</p>
      ) : null}
    </div>
  );
}
