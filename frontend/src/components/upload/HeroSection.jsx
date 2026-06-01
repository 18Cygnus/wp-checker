import UploadCard from "@/components/upload/UploadCard";
import TrustNote from "@/components/upload/TrustNote";

const META_STATS = [
    { value: "5", label: "sinyal dokumen" },
    { value: "9", label: "kategori bagian" },
    { value: "PDF", label: "format dokumen" },
];

export default function HeroSection({
    onUpload,
    uploadState,
    progress,
    error,
}) {
    // hero from pencil-new.pen Frame 1 (aj39R):
    // padding 64/80/40/80, gap 48px, horizontal layout
    // heroLeft (fill_container, vertical, gap 28) + heroRight (520px, vertical, gap 16)
    return (
        <section className="px-5 pb-10 pt-16 sm:px-10 lg:px-20 lg:pb-10 lg:pt-16">
            <div className="mx-auto flex max-w-[1280px] flex-col gap-12 lg:flex-row lg:items-start lg:gap-12">
                {/* heroLeft */}
                <div className="flex flex-1 flex-col gap-7">
                    {/* eyebrow: accent label + 32x1 rule + muted label */}
                    <div className="flex flex-wrap items-center gap-2.5">
                        <span className="font-mono text-[11px] font-medium uppercase tracking-eyebrow text-accent-primary">
                            01 / Whitepaper Review
                        </span>
                        <span
                            className="h-px w-8 bg-border-strong"
                            aria-hidden
                        />
                        <span className="font-mono text-[11px] font-medium uppercase tracking-eyebrow text-ink-muted">
                            Document-First · Rule-Based
                        </span>
                    </div>

                    {/* heroTitle: 62px Newsreader, -1.2 letter-spacing, lineHeight 1.05 */}
                    <h1 className="font-heading text-[40px] font-normal leading-[1.05] tracking-[-0.025em] text-ink-primary sm:text-[52px] lg:text-[62px]">
                        Periksa whitepaper kripto sebelum Anda mempercayainya.
                    </h1>

                    {/* heroSub: 17px Geist, lineHeight 1.6 */}
                    <p className="max-w-[560px] font-body text-[15px] leading-[1.6] text-ink-secondary lg:text-[17px]">
                        Unggah satu PDF whitepaper dan dapatkan sinyal yang
                        diekstrak, profil whitepaper, dan ringkasan berorientasi
                        kredibilitas untuk membantu telaah investor awal.
                    </p>

                    {/* heroMetaRow: 3 stats with 30px Newsreader numerals */}
                    <dl className="mt-2 flex flex-wrap gap-x-10 gap-y-5">
                        {META_STATS.map((stat) => (
                            <div
                                key={stat.label}
                                className="flex flex-col gap-1.5"
                            >
                                <dt className="font-heading text-[26px] font-medium leading-none tracking-[-0.01em] text-ink-primary lg:text-[30px]">
                                    {stat.value}
                                </dt>
                                <dd className="font-body text-[12px] text-ink-muted">
                                    {stat.label}
                                </dd>
                            </div>
                        ))}
                    </dl>
                </div>

                {/* heroRight: 520px upload column */}
                <div className="flex w-full flex-col gap-4 lg:w-[520px] lg:shrink-0">
                    <UploadCard
                        onFileSelect={onUpload}
                        uploadState={uploadState}
                        progress={progress}
                        error={error}
                    />
                    <TrustNote />
                </div>
            </div>
        </section>
    );
}
