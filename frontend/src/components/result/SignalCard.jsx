import { ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

// ─── helpers ────────────────────────────────────────────────────────────────

function getSimilarityPct(score) {
    // signal.score is 0–100 inverted: 100 = no plagiarism, 0 = fully plagiarised
    return Math.round(100 - (Number(score) || 0));
}

function getLinguisticLabel(score) {
    const s = Number(score) || 0;
    if (s >= 88) return "Baik";
    if (s >= 70) return "Cukup";
    return "Perlu Perhatian";
}

function getPrimaryScoreLabel(signal) {
    const s = Number(signal?.score) || 0;
    const level = s >= 88 ? "KUAT" : s >= 80 ? "CUKUP" : "LEMAH";
    return signal?.name === "content_balance"
        ? `DISTRIBUSI ${level}`
        : `SINYAL ${level}`;
}

function getPrimaryLabelColor(score) {
    const s = Number(score) || 0;
    if (s >= 88) return "text-signal-positive";
    if (s >= 80) return "text-signal-warn";
    return "text-signal-alert";
}

function getPrimaryBarColor(score) {
    const s = Number(score) || 0;
    if (s >= 88) return "bg-accent-primary";
    if (s >= 80) return "bg-signal-warn";
    return "bg-signal-alert";
}

const SIGNAL_DESCRIPTIONS = {
    content_balance:
        "Distribusi pembahasan antar kategori — apakah dokumen seimbang atau berat sebelah pada hype/marketing.",
    profile_aware_coverage:
        "Mengukur kelengkapan bagian-bagian penting dokumen berdasarkan profil yang terdeteksi.",
};

// ─── primary card (rSigA / rSigB) ────────────────────────────────────────────

function PrimaryCard({ signal }) {
    const score = Number(signal?.score) || 0;
    const weight = Math.round((Number(signal?.weight) || 0) * 100);
    const description = SIGNAL_DESCRIPTIONS[signal?.name] ?? "";
    const scoreLabel = getPrimaryScoreLabel(signal);
    const labelColor = getPrimaryLabelColor(score);
    const barColor = getPrimaryBarColor(score);

    return (
        <article className="flex w-full gap-6 rounded-[8px] border border-ink-primary bg-surface-card p-6">
            {/* left 280px */}
            <div className="flex w-[280px] shrink-0 flex-col gap-2">
                <div className="flex items-center gap-2">
                    <span className="inline-flex items-center rounded-full bg-ink-primary px-[10px] py-1">
                        <span className="font-mono text-[9px] font-semibold tracking-[1.4px] text-ink-inverse">
                            SINYAL UTAMA
                        </span>
                    </span>
                    <span className="font-mono text-[9px] text-ink-muted">
                        Bobot {weight}%
                    </span>
                </div>
                <h3 className="font-heading text-[22px] font-normal leading-tight tracking-[-0.3px] text-ink-primary">
                    {signal?.label ?? "Sinyal"}
                </h3>
                {description && (
                    <p className="text-[13px] leading-[1.5] text-ink-secondary">
                        {description}
                    </p>
                )}
            </div>

            {/* right fill */}
            <div className="flex flex-1 flex-col gap-[14px]">
                <div className="flex w-full items-end justify-between">
                    <span className="font-heading text-[48px] leading-none tracking-[-1.2px] text-ink-primary">
                        {score}
                    </span>
                    <span
                        className={cn(
                            "font-mono text-[10px] font-semibold tracking-[1.4px]",
                            labelColor,
                        )}
                    >
                        {scoreLabel}
                    </span>
                </div>
                <div className="h-[10px] w-full overflow-hidden rounded-full bg-surface-muted">
                    <div
                        className={cn(
                            "h-[10px] rounded-full transition-all duration-500",
                            barColor,
                        )}
                        style={{ width: `${score}%` }}
                    />
                </div>
            </div>
        </article>
    );
}

// ─── monitoring card (rSigC) ─────────────────────────────────────────────────

function MonitoringCard({ signal }) {
    const score = Number(signal?.score) || 0;
    const similarity = getSimilarityPct(score);
    const weight = Math.round((Number(signal?.weight) || 0) * 100);
    const neutralLabel =
        similarity <= 25
            ? "NETRAL · MINIM PLAGIARISME"
            : similarity <= 55
              ? "NETRAL · PERLU DITELAAH"
              : "TINGGI · PERLU PERHATIAN";

    return (
        <article className="flex w-full items-center gap-6 rounded-[8px] border border-border-subtle bg-surface-card p-5">
            {/* left 280px */}
            <div className="flex w-[280px] shrink-0 flex-col gap-[6px]">
                <div className="flex items-center gap-2">
                    <span className="inline-flex items-center rounded-full bg-surface-muted px-[10px] py-1">
                        <span className="font-mono text-[9px] font-medium tracking-[1.4px] text-ink-muted">
                            PEMANTAUAN
                        </span>
                    </span>
                    <span className="font-mono text-[9px] text-ink-muted">
                        Bobot {weight}%
                    </span>
                </div>
                <h3 className="text-[16px] font-semibold text-ink-primary">
                    {signal?.label ?? "Sinyal"}
                </h3>
                <p className="text-[12px] leading-[1.5] text-ink-muted">
                    Kemiripan tinggi tidak otomatis berarti negatif — telaah
                    konteks rujukan.
                </p>
            </div>

            {/* right fill */}
            <div className="flex flex-1 flex-col gap-[10px]">
                <div className="flex w-full items-end justify-between">
                    <span className="text-[28px] font-semibold leading-none text-ink-primary">
                        {similarity}%
                    </span>
                    <span className="font-mono text-[10px] font-medium tracking-[1.4px] text-ink-secondary">
                        {neutralLabel}
                    </span>
                </div>
                <div className="h-[6px] w-full overflow-hidden rounded-full bg-surface-muted">
                    <div
                        className="h-[6px] rounded-full bg-ink-muted transition-all duration-500"
                        style={{ width: `${similarity}%` }}
                    />
                </div>
            </div>
        </article>
    );
}

// ─── supporting card (rSigD) ──────────────────────────────────────────────────

function SupportingCard({ signal }) {
    const score = Number(signal?.score) || 0;
    const weight = Math.round((Number(signal?.weight) || 0) * 100);
    const qualityLabel = getLinguisticLabel(score);

    return (
        <article className="flex w-full items-center gap-6 rounded-[8px] border border-border-subtle bg-surface-card px-[18px] py-[18px]">
            {/* left 280px */}
            <div className="flex w-[280px] shrink-0 flex-col gap-1">
                <div className="flex items-center gap-2">
                    <span className="inline-flex items-center rounded-full bg-surface-muted px-[10px] py-[3px]">
                        <span className="font-mono text-[9px] font-medium tracking-[1.4px] text-ink-muted">
                            PENDUKUNG
                        </span>
                    </span>
                    <span className="font-mono text-[9px] text-ink-muted">
                        Bobot {weight}%
                    </span>
                </div>
                <h3 className="text-[14px] font-medium text-ink-secondary">
                    {signal?.label ?? "Sinyal"}
                </h3>
            </div>

            {/* right fill */}
            <div className="flex flex-1 items-center gap-4">
                <div className="h-[5px] flex-1 overflow-hidden rounded-full bg-surface-muted">
                    <div
                        className="h-[5px] rounded-full bg-ink-muted transition-all duration-500"
                        style={{ width: `${score}%` }}
                    />
                </div>
                <span className="shrink-0 font-mono text-[11px] font-medium tracking-[0.6px] text-ink-secondary">
                    {qualityLabel}
                </span>
            </div>
        </article>
    );
}

// ─── keyword card (sigE) ──────────────────────────────────────────────────────

function normaliseScores(keywords) {
    if (!keywords.length) return [];
    const scores = keywords.map((kw) =>
        Number(typeof kw === "string" ? 0 : (kw?.score ?? 0)),
    );
    const max = Math.max(...scores, 0.0001);
    return keywords.map((kw, i) => ({
        ...(typeof kw === "string" ? { term: kw, score: 0 } : kw),
        normScore: scores[i] / max,
    }));
}

// Design spec (sigEExpanded): 3 tiers of plain Geist text, no pills, rows centered.
// Tier 1 (~top 4): 22→16px font-semibold, ink.primary / accent.primary
// Tier 2 (~next 5): 14px font-medium, ink.secondary
// Tier 3 (rest):   11px font-normal, ink.muted
function buildWordCloudRows(keywords) {
    const t1 = keywords.slice(0, 4);
    const t2 = keywords.slice(4, 9);
    const t3 = keywords.slice(9);
    return { t1, t2, t3 };
}

// Tier-1 words get descending sizes: 22, 20, 18, 16px (matching design wk1–wk4)
const T1_SIZES = [22, 20, 18, 16];
// Tier-1 colors: first two ink.primary, third accent.primary, fourth ink.secondary
const T1_COLORS = [
    "text-ink-primary",
    "text-ink-primary",
    "text-accent-primary",
    "text-ink-secondary",
];

function KeywordCard({ signal }) {
    const [expanded, setExpanded] = useState(false);
    const raw = signal?.details?.topKeywords ?? [];
    const topKeywords = normaliseScores(raw);
    const preview = topKeywords.slice(0, 4);
    const remaining = Math.max(0, topKeywords.length - 4);
    const { t1, t2, t3 } = buildWordCloudRows(topKeywords);

    return (
        <article className="w-full overflow-hidden rounded-[8px] border border-border-subtle bg-surface-muted">
            <button
                type="button"
                onClick={() => setExpanded((v) => !v)}
                className="flex w-full items-center justify-between gap-4 px-5 py-5 text-left"
            >
                {/* header left */}
                <div className="flex flex-col gap-1">
                    <div className="flex items-center gap-2">
                        <span className="font-mono text-[11px] tracking-[1.4px] text-ink-muted">
                            E
                        </span>
                        <span className="text-[14px] font-medium text-ink-secondary">
                            Kata Kunci Diekstrak
                        </span>
                    </div>
                    <span className="font-mono text-[9px] tracking-[1.2px] text-ink-muted">
                        PENDUKUNG · TIDAK MEMPENGARUHI SKOR
                    </span>
                </div>

                {/* pills preview row */}
                <div className="flex flex-1 items-center justify-end gap-2 overflow-hidden">
                    {preview.map((kw) => (
                        <span
                            key={kw.term}
                            className="inline-flex shrink-0 items-center rounded-full border border-border-subtle bg-surface-card px-[10px] py-[5px]"
                        >
                            <span className="font-mono text-[10px] text-ink-secondary">
                                {kw.term}
                            </span>
                        </span>
                    ))}
                    {remaining > 0 && (
                        <span className="shrink-0 font-mono text-[10px] tracking-[0.4px] text-ink-muted">
                            +{remaining} lainnya
                        </span>
                    )}
                    {topKeywords.length === 0 && (
                        <span className="font-mono text-[10px] text-ink-muted">
                            Tidak ada kata kunci
                        </span>
                    )}
                </div>

                <span className="ml-2 shrink-0 text-ink-muted">
                    {expanded ? (
                        <ChevronUp size={16} />
                    ) : (
                        <ChevronDown size={16} />
                    )}
                </span>
            </button>

            {expanded && (
                <div className="flex flex-col gap-[14px] border-t border-border-subtle px-5 pb-6 pt-5">
                    {topKeywords.length ? (
                        <>
                            {/* section label */}
                            <span className="font-mono text-[9px] tracking-[1.2px] text-ink-muted">
                                FREKUENSI KATA KUNCI DALAM DOKUMEN
                            </span>

                            {/* tier 1 — largest, bold */}
                            {t1.length > 0 && (
                                <div className="flex items-center justify-center gap-4">
                                    {t1.map((kw, i) => (
                                        <span
                                            key={kw.term}
                                            className={cn(
                                                "font-semibold leading-none",
                                                T1_COLORS[i] ??
                                                    "text-ink-secondary",
                                            )}
                                            style={{
                                                fontSize: T1_SIZES[i] ?? 16,
                                            }}
                                        >
                                            {kw.term}
                                        </span>
                                    ))}
                                </div>
                            )}

                            {/* tier 2 — medium */}
                            {t2.length > 0 && (
                                <div className="flex items-center justify-center gap-[14px]">
                                    {t2.map((kw) => (
                                        <span
                                            key={kw.term}
                                            className="text-[14px] font-medium leading-none text-ink-secondary"
                                        >
                                            {kw.term}
                                        </span>
                                    ))}
                                </div>
                            )}

                            {/* tier 3 — small, muted */}
                            {t3.length > 0 && (
                                <div className="flex flex-wrap items-center justify-center gap-[12px]">
                                    {t3.map((kw) => (
                                        <span
                                            key={kw.term}
                                            className="text-[11px] font-normal leading-none text-ink-muted"
                                        >
                                            {kw.term}
                                        </span>
                                    ))}
                                </div>
                            )}
                        </>
                    ) : (
                        <p className="text-center font-mono text-[11px] text-ink-muted">
                            Tidak ada kata kunci untuk ditampilkan.
                        </p>
                    )}
                </div>
            )}
        </article>
    );
}

// ─── router ──────────────────────────────────────────────────────────────────

export default function SignalCard({ signal }) {
    const tier = signal?.tier;
    if (tier === "primary") return <PrimaryCard signal={signal} />;
    if (tier === "monitoring") return <MonitoringCard signal={signal} />;
    if (tier === "supporting") return <SupportingCard signal={signal} />;
    return <KeywordCard signal={signal} />;
}
