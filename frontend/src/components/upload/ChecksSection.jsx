import { Copy, LayoutList, Scale, Tag, TextQuote } from "lucide-react";

// Ordered by signal weight (signal hierarchy emphasis from PRD).
// Cards 1-2 = primary signals (border ink-primary, accent icon tile, accent-soft tag)
// Cards 3-5 = supporting (border subtle, muted icon tile, muted tag)
const CHECKS = [
    {
        number: "01",
        name: "Content Balance",
        icon: Scale,
        description:
            "Mengukur proporsi antar segmen — apakah teknis, tokenomics, dan tata kelola hadir dalam takaran yang sehat.",
        tag: "Sinyal Utama",
        primary: true,
    },
    {
        number: "02",
        name: "Profile-aware Coverage",
        icon: LayoutList,
        description:
            "Mengukur kelengkapan segmen dokumen dan membandingkan berdasarkan profil yang terdeteksi.",
        tag: "Sinyal Utama",
        primary: true,
    },
    {
        number: "03",
        name: "Sinyal Plagiarisme",
        icon: Copy,
        description:
            "Memantau indikasi plagiarisme atau penyalinan dari dokumen lain. Bisa netral pada beberapa whitepaper.",
        tag: "Pemantauan",
        primary: false,
    },
    {
        number: "04",
        name: "Kualitas Linguistik",
        icon: TextQuote,
        description:
            "Menilai keterbacaan, ketepatan istilah, dan kerapian penulisan sebagai indikator pendukung — bukan penentu utama.",
        tag: "Pendukung",
        primary: false,
    },
    {
        number: "05",
        name: "Ekstraksi Kata Kunci",
        icon: Tag,
        description:
            "Menyaring topik dan entitas utama untuk membantu interpretasi cepat. Konteks, bukan vonis.",
        tag: "Interpretif",
        primary: false,
    },
];

function CheckCard({ number, name, icon: Icon, description, tag, primary }) {
    return (
        <article
            className={
                primary
                    ? "flex h-full flex-col gap-[18px] rounded-card border border-ink-primary bg-surface-card p-6"
                    : "flex h-full flex-col gap-[18px] rounded-card border border-border-subtle bg-surface-card p-6"
            }
        >
            {/* Top row: icon tile + number */}
            <div className="flex items-start justify-between">
                <div
                    className={
                        primary
                            ? "flex h-10 w-10 items-center justify-center rounded-md bg-accent-primary"
                            : "flex h-10 w-10 items-center justify-center rounded-md bg-surface-muted"
                    }
                >
                    <Icon
                        className={
                            primary
                                ? "h-5 w-5 text-ink-inverse"
                                : "h-5 w-5 text-ink-primary"
                        }
                        strokeWidth={1.75}
                    />
                </div>
                <span className="font-mono text-[11px] font-medium uppercase tracking-[0.1em] text-ink-muted">
                    {number}
                </span>
            </div>

            <h3 className="font-heading text-display-check font-medium text-ink-primary">
                {name}
            </h3>

            <p className="flex-1 font-body text-[13px] leading-[1.55] text-ink-secondary">
                {description}
            </p>

            <span
                className={
                    primary
                        ? "inline-flex w-fit items-center rounded-pill bg-accent-soft px-2.5 py-1 font-mono text-[9px] font-medium uppercase tracking-[0.1em] text-accent-primary"
                        : "inline-flex w-fit items-center rounded-pill bg-surface-muted px-2.5 py-1 font-mono text-[9px] font-medium uppercase tracking-[0.1em] text-ink-secondary"
                }
            >
                {tag}
            </span>
        </article>
    );
}

export default function ChecksSection() {
    // checksSection from pencil-new.pen Frame 1 (2VwHc):
    // padding 60/80/40/80, gap 32. Header space-between with right-side priority pill.
    // checksGrid: vertical stack of 5 cards, gap 16.
    return (
        <section
            id="yang-dianalisis"
            className="px-5 py-15 sm:px-10 lg:px-20"
            style={{ paddingTop: 40, paddingBottom: 40 }}
        >
            <div className="mx-auto max-w-[1280px] flex flex-col gap-8">
                {/* checksHeader */}
                <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
                    <div className="flex max-w-[680px] flex-col gap-3.5">
                        {/* checksEyebrow */}
                        <div className="flex flex-wrap items-center gap-2.5">
                            <span className="font-mono text-[11px] font-medium uppercase tracking-eyebrow text-accent-primary">
                                02 / What We Extract
                            </span>
                            <span
                                className="h-px w-8 bg-border-strong"
                                aria-hidden
                            />
                            <span className="font-mono text-[11px] font-medium uppercase tracking-eyebrow text-ink-muted">
                                Five Document Signals
                            </span>
                        </div>
                        <h2 className="font-heading text-[28px] font-normal leading-[1.15] tracking-[-0.018em] text-ink-primary lg:text-display-section">
                            Yang diperiksa sistem dari setiap whitepaper
                        </h2>
                        <p className="font-body text-[15px] leading-[1.55] text-ink-secondary">
                            Bukan satu skor tunggal. Lima sinyal independen yang
                            digabung dengan hierarki — sinyal struktural
                            memimpin, sinyal pendukung memberi konteks.
                        </p>
                    </div>
                    <div className="flex flex-col items-start gap-2 lg:items-end">
                        <span className="inline-flex items-center gap-2 rounded-pill border border-border-subtle px-3 py-2">
                            <span className="h-1.5 w-1.5 rounded-full bg-accent-primary" />
                            <span className="font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-ink-secondary">
                                Diurutkan berdasarkan bobot
                            </span>
                        </span>
                    </div>
                </div>

                {/* checksGrid: horizontal 5-col grid (pencil: no layout = horizontal, fill_container per card) */}
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
                    {CHECKS.map((check) => (
                        <CheckCard key={check.number} {...check} />
                    ))}
                </div>
            </div>
        </section>
    );
}
