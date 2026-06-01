import { Cpu } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatDuration, formatScore } from "@/utils/formatters";

function getCredibilityTone(score) {
  if (score >= 88) {
    return {
      tagBg: "bg-signal-positive-soft",
      tagText: "text-signal-positive",
      tagDot: "bg-signal-positive",
      gaugeStroke: "stroke-signal-positive",
      label: "Indikasi Positif · Telaah Lanjut Dianjurkan",
    };
  }
  if (score >= 80) {
    return {
      tagBg: "bg-signal-warn-soft",
      tagText: "text-signal-warn",
      tagDot: "bg-signal-warn",
      gaugeStroke: "stroke-signal-warn",
      label: "Cukup Kredibel · Telaah Lebih Lanjut",
    };
  }
  return {
    tagBg: "bg-signal-alert-soft",
    tagText: "text-signal-alert",
    tagDot: "bg-signal-alert",
    gaugeStroke: "stroke-signal-alert",
    label: "Sinyal Lemah · Verifikasi Manual Diperlukan",
  };
}

const PROFILE_TONE = {
  technical_only: { icon: Cpu, label: "Cenderung Technical" },
  investor_oriented: { icon: Cpu, label: "Cenderung Investor-Oriented" },
  hybrid: { icon: Cpu, label: "Hybrid" },
  undetermined: { icon: Cpu, label: "Profil Belum Pasti" },
};

// ─── gauge ───────────────────────────────────────────────────────────────────
// rGauge: full-circle donut, 180×180, innerRadius 0.72 → strokeWidth ≈25px
// At score X: fill sweeps X/100 × 360° starting at 12 o'clock

function Gauge({ score, strokeClass }) {
  const size = 180;
  const strokeWidth = 25;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const normalized = Math.max(0, Math.min(100, score));
  const offset = circumference - (normalized / 100) * circumference;

  return (
    <div className="relative h-[180px] w-[180px] shrink-0">
      <svg className="h-[180px] w-[180px] -rotate-90" viewBox={`0 0 ${size} ${size}`} aria-hidden>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={strokeWidth}
          className="stroke-surface-muted"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={strokeWidth}
          strokeLinecap="butt"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className={cn(strokeClass, "transition-all duration-1000 ease-out")}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-[2px]">
        <span className="font-heading text-display-gauge font-normal leading-none text-ink-primary">
          {Math.round(normalized)}
        </span>
        <span className="font-mono text-[9px] font-medium tracking-[1.6px] text-ink-muted">DARI 100</span>
      </div>
    </div>
  );
}

// ─── meta stat item ───────────────────────────────────────────────────────────

function MetaStat({ value, label }) {
  return (
    <div className="flex flex-col gap-[2px]">
      <span className="font-heading text-[20px] font-normal leading-none tracking-[-0.3px] text-ink-primary">
        {value}
      </span>
      <span className="font-mono text-[9px] font-normal tracking-[1.4px] text-ink-muted">{label}</span>
    </div>
  );
}

// ─── main component ───────────────────────────────────────────────────────────

export default function ExecutiveSummary({ headline, paragraph, profileType, score, labelDistribution, analysisTime }) {
  const headlineText = headline || "Ringkasan analisis belum tersedia.";
  const paragraphText = paragraph || "";
  const numericScore = formatScore(score);
  const tone = getCredibilityTone(numericScore);
  const profileMeta = PROFILE_TONE[profileType] ?? PROFILE_TONE.undetermined;
  const ProfileIcon = profileMeta.icon;
  const detectedCategories = Object.keys(labelDistribution ?? {}).filter(
    (k) => (labelDistribution[k] ?? 0) > 0
  ).length;
  const durationText = analysisTime ? formatDuration(analysisTime) : "—";

  return (
    <section className="px-5 pb-8 sm:px-10 lg:px-20" style={{ paddingTop: 16 }}>
      <div className="mx-auto max-w-[1280px]">
        {/* rExec card */}
        <div className="flex flex-col items-start gap-8 rounded-[8px] border border-border-subtle bg-surface-card p-8 shadow-[0_1px_3px_#0F162008,0_12px_32px_#0F16200D] lg:flex-row">

          {/* rGaugeWrap — 200px */}
          <div className="flex w-full shrink-0 flex-col items-center gap-3 lg:w-[200px] lg:self-start">
            <Gauge score={numericScore} strokeClass={tone.gaugeStroke} />
          </div>

          {/* rExecBody — fill */}
          <div className="flex min-w-0 flex-1 flex-col gap-[14px]">

            {/* rExecTagRow */}
            <div className="flex flex-wrap items-center gap-2">
              {/* credibility tag */}
              <span className={cn("inline-flex items-center gap-2 rounded-full px-3 py-[6px]", tone.tagBg)}>
                <span className={cn("h-2 w-2 rounded-full", tone.tagDot)} />
                <span className={cn("font-mono text-[10px] font-semibold tracking-[1.4px]", tone.tagText)}>
                  {tone.label}
                </span>
              </span>

              {/* profile badge */}
              <span className="inline-flex items-center gap-2 rounded-full bg-accent-soft px-3 py-[6px]">
                <ProfileIcon className="h-3 w-3 text-accent-primary" strokeWidth={2} />
                <span className="font-mono text-[10px] font-semibold tracking-[1.4px] text-accent-primary">
                  {profileMeta.label}
                </span>
              </span>
            </div>

            {/* rExecHead */}
            <h2 className="font-heading text-[22px] font-normal leading-[1.3] tracking-[-0.3px] text-ink-primary">
              {headlineText}
            </h2>

            {/* rExecP */}
            {paragraphText && (
              <p className="text-[14px] leading-[1.6] text-ink-secondary">{paragraphText}</p>
            )}

            {/* rExecMeta — stat row */}
            <div className="flex flex-wrap gap-6 pt-3">
              <MetaStat value={`${detectedCategories} / 9`} label="KATEGORI TERDETEKSI" />
              <MetaStat value="5" label="SINYAL DIPERIKSA" />
              <MetaStat value={durationText} label="DURASI ANALISIS" />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

