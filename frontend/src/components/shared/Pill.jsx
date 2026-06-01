import { cn } from "@/lib/utils";

export default function Pill({
  label,
  color = "text-ink-secondary",
  bgColor = "bg-surface-muted",
  className,
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border border-border-subtle px-3 py-1 font-mono text-[11px]",
        color,
        bgColor,
        className
      )}
    >
      {label}
    </span>
  );
}
