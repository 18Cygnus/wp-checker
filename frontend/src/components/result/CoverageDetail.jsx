import { Cpu } from "lucide-react";
import { getProfileText, getSectionName } from "@/utils/formatters";

// Per-tier display config — matches rTierA/B/C in pencil-new.pen
const TIER_CONFIG = {
    core: {
        eyebrow: "PRIORITAS UTAMA",
        eyebrowColor: "text-accent-primary",
    },
    supporting: {
        eyebrow: "SUPPORTING",
        eyebrowColor: "text-ink-secondary",
    },
    optional: {
        eyebrow: "OPTIONAL",
        eyebrowColor: "text-ink-muted",
    },
};

// Human-readable profile description (matches profileDesc in pencil-new.pen)
const PROFILE_DESCRIPTIONS = {
    technical_only:
        "Distribusi kategori dokumen ini paling mirip dengan prototipe teknikal (cosine similarity tertinggi). Prioritas dan bobot bagian disesuaikan terhadap profil ini.",
    investor_oriented:
        "Distribusi kategori dokumen ini paling mirip dengan prototipe berorientasi investor. Prioritas diberikan pada bagian tokenomics, use cases, dan project overview.",
    hybrid: "Dokumen menunjukkan distribusi campuran antara konten teknis dan konten yang berorientasi investor. Semua tier mendapat bobot seimbang.",
    undetermined:
        "Profil belum dapat ditentukan secara pasti. Sistem menggunakan distribusi tier standar sebagai acuan.",
};

// ─── TierCard ──────────────────────────────────────────────────────────────
function TierCard({ tierKey, tierData, labelDistribution }) {
    const config = TIER_CONFIG[tierKey] ?? TIER_CONFIG.optional;
    const sections = tierData?.sections ?? [];

    return (
        <article className="flex h-full flex-col gap-3 rounded-card border border-border-subtle bg-surface-card p-5 shadow-card">
            <p
                className={`font-mono text-[10px] font-semibold uppercase tracking-[0.14em] ${config.eyebrowColor}`}
            >
                {config.eyebrow}
            </p>
            <div className="h-px w-full bg-border-subtle" />

            <div className="flex-1">
                {sections.length > 0 ? (
                    sections.map((section, index) => {
                        const pct = Math.round(
                            (labelDistribution?.[section.label] ?? 0) * 100,
                        );
                        const isFound = Boolean(section.detected);
                        return (
                            <div key={`${section.label}-${index}`}>
                                <div className="flex items-center justify-between py-[6px]">
                                    <span
                                        className={
                                            isFound
                                                ? "text-[13px] text-ink-primary"
                                                : "text-[13px] text-ink-muted line-through"
                                        }
                                    >
                                        {isFound ? "✓\u2002" : "✗\u2002"}
                                        {getSectionName(section.label)}
                                    </span>
                                    <span className="ml-3 shrink-0 font-mono text-[11px] font-medium text-ink-muted">
                                        {pct > 0 ? `${pct}%` : "—"}
                                    </span>
                                </div>
                                {index < sections.length - 1 && (
                                    <div className="h-px bg-border-subtle" />
                                )}
                            </div>
                        );
                    })
                ) : (
                    <p className="py-2 text-[13px] text-ink-muted">
                        Tidak ada bagian dalam tier ini.
                    </p>
                )}
            </div>
        </article>
    );
}

// ─── CoverageDetail ────────────────────────────────────────────────────────
export default function CoverageDetail({
    coverageDetail,
    labelDistribution,
    sectionCount,
}) {
    const profileUsed = coverageDetail?.profile_used ?? "undetermined";
    const tiers = coverageDetail?.tiers ?? {};
    const profileDesc =
        PROFILE_DESCRIPTIONS[profileUsed] ?? PROFILE_DESCRIPTIONS.undetermined;

    const TOTAL_LABELS = 9;
    const detectedCount = Object.values(labelDistribution ?? {}).filter(
        (v) => v > 0,
    ).length;

    return (
        <section
            className="px-5 pb-8 sm:px-10 lg:px-20"
            style={{ paddingTop: 24 }}
        >
            <div className="mx-auto flex max-w-[1280px] flex-col gap-6">
                {/* ── Header (rCovHead) ─────────────────────────────────────────── */}
                <div className="flex flex-col gap-2">
                    <div className="flex flex-wrap items-center gap-[10px]">
                        <span className="font-mono text-[11px] font-medium uppercase tracking-eyebrow text-accent-primary">
                            C / PROFILE-AWARE COVERAGE
                        </span>
                        <span
                            className="h-px w-8 bg-border-strong"
                            aria-hidden
                        />
                        <span className="font-mono text-[10px] font-medium uppercase tracking-eyebrow text-ink-muted">
                            BERBASIS PROFIL DOKUMEN
                        </span>
                    </div>
                    <h2 className="font-heading text-[32px] font-normal leading-[1.2] tracking-[-0.022em] text-ink-primary">
                        Kesesuaian cakupan terhadap profil dokumen
                    </h2>
                </div>

                {/* ── Profile Card (rProfileCard) ───────────────────────────────── */}
                <div className="rounded-card border border-accent-primary bg-surface-card p-6 shadow-card">
                    <p className="mb-4 font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-accent-primary">
                        PROFIL TERDETEKSI
                    </p>
                    <div className="flex flex-wrap items-center gap-3">
                        <div className="flex items-center gap-1.5 rounded-md bg-accent-soft px-3.5 py-2">
                            <Cpu
                                className="h-3.5 w-3.5 text-accent-primary"
                                strokeWidth={2}
                            />
                            <span className="text-[13px] font-semibold text-accent-primary">
                                {getProfileText(profileUsed)}
                            </span>
                        </div>
                    </div>
                    <p className="mt-4 text-[13px] leading-[1.55] text-ink-secondary">
                        {profileDesc}
                    </p>
                </div>

                {/* ── Tiers Row (rTiersRow) ─────────────────────────────────────── */}
                <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                    {["core", "supporting", "optional"].map((tierKey) => (
                        <TierCard
                            key={tierKey}
                            tierKey={tierKey}
                            tierData={tiers[tierKey]}
                            labelDistribution={labelDistribution}
                        />
                    ))}
                </div>

                {/* ── Score Row (rScoreRow) ─────────────────────────────────────── */}
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-md bg-surface-muted px-5 py-4">
                    <span className="text-[13px] font-medium text-ink-secondary">
                        Label Presence
                    </span>
                    <span className="font-mono text-[14px] font-semibold text-ink-primary">
                        {detectedCount} / {TOTAL_LABELS} label terdeteksi
                    </span>
                </div>
            </div>
        </section>
    );
}
