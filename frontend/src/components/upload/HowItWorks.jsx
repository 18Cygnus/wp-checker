import { FileSearch, ScanLine, Upload } from "lucide-react";

const STEPS = [
    {
        number: "01",
        title: "Unggah PDF",
        description: "Pilih satu whitepaper kripto. Sistem hanya menerima PDF.",
        icon: Upload,
    },
    {
        number: "02",
        title: "Analisis dokumen",
        description:
            "Sistem mengekstrak struktur, mengukur cakupan bagian, dan menghitung sinyal pendukung.",
        icon: ScanLine,
    },
    {
        number: "03",
        title: "Telaah temuan",
        description:
            "Briefing investor: skor, sinyal, peta cakupan, kata kunci, dan catatan keterbatasan.",
        icon: FileSearch,
    },
];

function Step({ number, title, description, icon: Icon }) {
    return (
        <div className="flex flex-1 flex-col gap-3 px-8 py-7">
            {/* step top: large number + icon */}
            <div className="flex items-center justify-between">
                <span className="font-heading text-[42px] font-normal leading-none tracking-[-0.024em] text-ink-primary">
                    {number}
                </span>
                <Icon
                    className="h-[22px] w-[22px] text-ink-muted"
                    strokeWidth={1.5}
                />
            </div>
            <h3 className="mt-3 font-heading text-display-card font-medium text-ink-primary">
                {title}
            </h3>
            <p className="font-body text-[13px] leading-[1.55] text-ink-secondary">
                {description}
            </p>
        </div>
    );
}

export default function HowItWorks() {
    // howSection from pencil-new.pen Frame 1 (IDhXP):
    // padding 40/80/80/80, gap 32. Header eyebrow + 34px title.
    // howSteps: single bordered card with 3 sections + vertical dividers
    return (
        <section
            id="cara-kerja"
            className="px-5 sm:px-10 lg:px-20"
            style={{ paddingTop: 40, paddingBottom: 40 }}
        >
            <div className="mx-auto flex max-w-[1280px] flex-col gap-8">
                {/* howHeader */}
                <div className="flex max-w-[680px] flex-col gap-3.5">
                    <div className="flex flex-wrap items-center gap-2.5">
                        <span className="font-mono text-[11px] font-medium uppercase tracking-eyebrow text-accent-primary">
                            03 / Workflow
                        </span>
                        <span
                            className="h-px w-8 bg-border-strong"
                            aria-hidden
                        />
                        <span className="font-mono text-[11px] font-medium uppercase tracking-eyebrow text-ink-muted">
                            Three Steps · One Page
                        </span>
                    </div>
                    <h2 className="font-heading text-[28px] font-normal leading-[1.15] tracking-[-0.018em] text-ink-primary lg:text-display-section">
                        Cara kerjanya
                    </h2>
                </div>

                {/* howSteps: single card with vertical dividers between steps */}
                <div className="flex flex-col divide-y divide-border-subtle rounded-card border border-border-subtle bg-surface-card md:flex-row md:divide-x md:divide-y-0">
                    {STEPS.map((step) => (
                        <Step key={step.number} {...step} />
                    ))}
                </div>
            </div>
        </section>
    );
}
