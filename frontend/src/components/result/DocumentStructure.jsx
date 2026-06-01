import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";
import { getSectionName } from "@/utils/formatters";

// ─── Category styles — pill colors per section type ────────────────────────────
const categoryStyles = {
    introduction: {
        color: "text-accent-primary",
        bgColor: "bg-accent-soft",
        border: "",
    },
    problem_statement: {
        color: "text-signal-warn",
        bgColor: "bg-signal-warn-soft",
        border: "",
    },
    solution_proposal: {
        color: "text-signal-positive",
        bgColor: "bg-signal-positive-soft",
        border: "",
    },
    technical_architecture: {
        color: "text-accent-primary",
        bgColor: "bg-accent-soft",
        border: "",
    },
    tokenomics: {
        color: "text-signal-warn",
        bgColor: "bg-signal-warn-soft",
        border: "",
    },
    roadmap: {
        color: "text-accent-primary",
        bgColor: "bg-accent-soft",
        border: "",
    },
    team_and_partnerships: {
        color: "text-accent-teal",
        bgColor: "bg-accent-soft",
        border: "",
    },
    governance: {
        color: "text-ink-secondary",
        bgColor: "bg-surface-muted",
        border: "border border-border-subtle",
    },
    risks_and_compliance: {
        color: "text-signal-alert",
        bgColor: "bg-signal-alert-soft",
        border: "",
    },
};

// ─── Confidence helpers ────────────────────────────────────────────────────────
function confColor(c) {
    if (c >= 0.8) return "text-signal-positive";
    if (c >= 0.6) return "text-signal-warn";
    return "text-signal-alert";
}
function confBarFill(c) {
    if (c >= 0.8) return "bg-signal-positive";
    if (c >= 0.6) return "bg-signal-warn";
    return "bg-signal-alert";
}

// ─── SrPill — inline category badge (sr1C) ────────────────────────────────────
function SrPill({ label, styles }) {
    return (
        <span
            className={cn(
                "inline-block rounded-full px-[9px] py-[3px] font-mono text-[10px] tracking-[0.4px]",
                styles.bgColor,
                styles.color,
                styles.border,
            )}
        >
            {label}
        </span>
    );
}

// ─── SrBar — mini progress bar (sr1Dbar: w-[60px] h-[4px]) ───────────────────
function SrBar({ value }) {
    return (
        <div className="h-[4px] w-[60px] shrink-0 rounded-full bg-border-subtle">
            <div
                className={cn("h-[4px] rounded-full", confBarFill(value))}
                style={{ width: `${Math.round(value * 100)}%` }}
            />
        </div>
    );
}

// ─── renderBody — parse markdown subset to JSX ────────────────────────────────
// Handles: ## heading, · bullet list, plain paragraphs separated by blank lines
function renderBody(raw) {
    if (!raw) return null;
    const lines = raw.split("\n");
    const nodes = [];
    let listItems = [];

    const flushList = () => {
        if (listItems.length === 0) return;
        nodes.push(
            <ul key={`ul-${nodes.length}`} className="mt-2 space-y-[3px]">
                {listItems.map((item, i) => (
                    <li
                        key={i}
                        className="flex items-start gap-[6px] text-[13px] leading-[1.55] text-ink-secondary"
                    >
                        <span className="mt-[4px] h-[4px] w-[4px] shrink-0 rounded-full bg-ink-muted" />
                        <span>{item}</span>
                    </li>
                ))}
            </ul>,
        );
        listItems = [];
    };

    lines.forEach((line, i) => {
        if (line.startsWith("## ")) {
            flushList();
            nodes.push(
                <p
                    key={i}
                    className="mt-3 font-sans text-[12px] font-semibold uppercase tracking-[0.5px] text-ink-primary first:mt-0"
                >
                    {line.slice(3)}
                </p>,
            );
        } else if (line.startsWith("· ") || line.startsWith("- ")) {
            listItems.push(line.slice(2));
        } else if (line.trim() === "") {
            flushList();
        } else {
            flushList();
            nodes.push(
                <p
                    key={i}
                    className="text-[13px] leading-[1.65] text-ink-secondary"
                >
                    {line}
                </p>,
            );
        }
    });
    flushList();
    return nodes;
}

// ─── MdPanel — expanded body panel (sr1Expanded) ─────────────────────────────
// outer: bg-surface-muted, border-top subtle, px-5 py-4
// inner card: bg-surface-card, border border-subtle, rounded-[6px], px-4 py-[14px]
// left-offset to align with heading column (skip index w-8 + gap-4 = 48px)
function MdPanel({ body }) {
    return (
        <div className=" border-border-subtle bg-surface-muted px-5 pb-4">
            <div className="rounded-[6px] border border-border-subtle bg-surface-card px-4 py-[14px] shadow-[0_1px_2px_#0F16200A]">
                <div className="space-y-[6px]">{renderBody(body)}</div>
            </div>
        </div>
    );
}

// ─── SectionRow — single row + optional expanded panel ────────────────────────
function SectionRow({ section, isExpanded, onToggle }) {
    const styles = categoryStyles[section.label] ?? categoryStyles.governance;
    const hasBody = Boolean(section.body);

    return (
        <div className="border-b border-border-subtle last:border-b-0">
            {/* sr1Row */}
            <div
                onClick={hasBody ? onToggle : undefined}
                className={cn(
                    "flex items-center gap-4 px-5 py-[14px] transition-colors",
                    isExpanded
                        ? "bg-surface-muted"
                        : hasBody && "hover:bg-surface-muted/60",
                    hasBody && "cursor-pointer",
                )}
            >
                {/* sr1A — index w-8 */}
                <span className="w-8 shrink-0 font-mono text-[11px] text-ink-muted">
                    {String(section.index).padStart(2, "0")}
                </span>

                {/* sr1B — heading w-[340px] */}
                <span className="w-[340px] shrink-0 truncate font-sans text-[13px] font-medium text-ink-primary">
                    {section.heading}
                </span>

                {/* sr1Cw — pill, fill remaining */}
                <div className="min-w-0 flex-1">
                    <SrPill
                        label={getSectionName(section.label)}
                        styles={styles}
                    />
                </div>

                {/* sr1Dw — confidence value + bar, w-[120px] right-aligned */}
                <div className="flex w-[120px] shrink-0 items-center justify-end gap-2">
                    <span
                        className={cn(
                            "font-mono text-[11px] font-medium",
                            confColor(section.confidence),
                        )}
                    >
                        {section.confidence.toFixed(2)}
                    </span>
                    <SrBar value={section.confidence} />
                </div>

                {/* chevron — 14×14, accent.primary (lucide), only if has body */}
                <div className="w-[14px] shrink-0">
                    {hasBody ? (
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                onToggle();
                            }}
                            aria-label={
                                isExpanded
                                    ? "Tutup isi segmen"
                                    : "Lihat isi segmen"
                            }
                            className="text-accent-primary transition-opacity hover:opacity-60"
                        >
                            {isExpanded ? (
                                <ChevronUp className="h-[14px] w-[14px]" />
                            ) : (
                                <ChevronDown className="h-[14px] w-[14px]" />
                            )}
                        </button>
                    ) : null}
                </div>
            </div>

            {/* sr1MdPanel */}
            {isExpanded && hasBody && <MdPanel body={section.body} />}
        </div>
    );
}

// ─── DocumentStructure ────────────────────────────────────────────────────────
const INITIAL_SHOW = 10;
const INCREMENT = 15;

export default function DocumentStructure({ sections }) {
    const [expandedId, setExpandedId] = useState(null);
    const [visibleCount, setVisibleCount] = useState(INITIAL_SHOW);

    const normalized = (sections ?? []).map((section, index) => ({
        id: section?.id ?? `section-${index}`,
        index: section?.index ?? index + 1,
        heading: section?.heading ?? section?.title ?? "Tanpa Judul",
        label: section?.label ?? section?.classified_label ?? "introduction",
        confidence: Number(section?.confidence) || 0,
        body: section?.body ?? null,
    }));

    const total = normalized.length;
    const visible = normalized.slice(0, visibleCount);
    const hidden = total - visibleCount;

    return (
        <section
            className="px-5 pb-8 sm:px-10 lg:px-20"
            style={{ paddingTop: 16 }}
        >
            <div className="mx-auto max-w-[1280px]">
                {/* secStrHead — eyebrow + title */}
                <div className="mb-6 flex flex-col gap-2">
                    <div className="flex items-center gap-[10px]">
                        <span className="font-mono text-[11px] font-medium uppercase tracking-eyebrow text-accent-primary">
                            D / STRUKTUR DOKUMEN
                        </span>
                        <span
                            className="h-px w-8 bg-border-strong"
                            aria-hidden
                        />
                        <span className="font-mono text-[10px] uppercase tracking-eyebrow text-ink-muted">
                            {total} BAGIAN TERIDENTIFIKASI · KLASIFIKASI ROBERTA
                        </span>
                    </div>
                    <h2 className="font-heading text-[32px] font-normal leading-[1.2] tracking-[-0.022em] text-ink-primary">
                        Bagaimana model membaca struktur dokumen
                    </h2>
                </div>

                {/* secStrCard */}
                <div className="overflow-hidden rounded-[8px] border border-border-subtle bg-surface-card shadow-card">
                    {/* secStrHdrRow */}
                    <div className="flex items-center gap-4 border-b border-border-subtle bg-surface-muted px-5 py-[14px]">
                        <span className="w-8 shrink-0 font-mono text-[10px] uppercase tracking-[1.2px] text-ink-muted">
                            #
                        </span>
                        <span className="w-[340px] shrink-0 font-mono text-[10px] uppercase tracking-[1.2px] text-ink-muted">
                            JUDUL BAGIAN
                        </span>
                        <span className="min-w-0 flex-1 font-mono text-[10px] uppercase tracking-[1.2px] text-ink-muted">
                            KATEGORI TERDETEKSI
                        </span>
                        <span className="w-[120px] shrink-0 text-right font-mono text-[10px] uppercase tracking-[1.2px] text-ink-muted">
                            KEYAKINAN
                        </span>
                        <span className="w-[14px] shrink-0" aria-hidden />
                    </div>

                    {/* secStrList */}
                    {visible.length ? (
                        visible.map((section) => (
                            <SectionRow
                                key={section.id}
                                section={section}
                                isExpanded={expandedId === section.id}
                                onToggle={() =>
                                    setExpandedId(
                                        expandedId === section.id
                                            ? null
                                            : section.id,
                                    )
                                }
                            />
                        ))
                    ) : (
                        <p className="px-5 py-6 text-center text-sm text-ink-muted">
                            Struktur dokumen belum tersedia.
                        </p>
                    )}

                    {/* srMore footer */}
                    {(hidden > 0 || visibleCount > INITIAL_SHOW) && (
                        <div className="flex items-center justify-center gap-3 border-t border-border-subtle bg-surface-muted px-5 py-[14px]">
                            {hidden > 0 && (
                                <button
                                    onClick={() =>
                                        setVisibleCount((c) => c + INCREMENT)
                                    }
                                    className="flex items-center gap-2 font-mono text-[11px] tracking-[0.6px] text-accent-primary transition-opacity hover:opacity-70"
                                >
                                    <span>
                                        Tampilkan {Math.min(hidden, INCREMENT)}{" "}
                                        bagian lainnya
                                    </span>
                                    <ChevronDown className="h-[14px] w-[14px]" />
                                </button>
                            )}
                            {hidden > 0 && visibleCount > INITIAL_SHOW && (
                                <span
                                    className="font-mono text-[10px] text-border-strong"
                                    aria-hidden
                                >
                                    ·
                                </span>
                            )}
                            {visibleCount > INITIAL_SHOW && (
                                <button
                                    onClick={() => {
                                        setVisibleCount(INITIAL_SHOW);
                                        setExpandedId(null);
                                    }}
                                    className="flex items-center gap-2 font-mono text-[11px] tracking-[0.6px] text-ink-muted transition-opacity hover:opacity-70"
                                >
                                    <ChevronUp className="h-[14px] w-[14px]" />
                                    <span>Tampilkan lebih sedikit</span>
                                </button>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </section>
    );
}
