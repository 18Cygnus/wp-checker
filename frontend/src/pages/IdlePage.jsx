import ChecksSection from "@/components/upload/ChecksSection";
import HeroSection from "@/components/upload/HeroSection";
import HowItWorks from "@/components/upload/HowItWorks";

export default function IdlePage({ onUpload, uploadState, progress, error }) {
    // Frame 1 (Desktop · Idle Upload State) section order from pencil-new.pen:
    // navBar → divider → hero → checksSection → howSection → disclaimerBand → footer
    // (NavBar/Disclaimer/Footer are rendered at App level)
    return (
        <>
            <div className="border-b border-border-subtle">
                <HeroSection
                    onUpload={onUpload}
                    uploadState={uploadState}
                    progress={progress}
                    error={error}
                />
            </div>

            <ChecksSection />
            <HowItWorks />

            <section
                id="catatan"
                className="px-5 pt-10 pb-16 sm:px-10 lg:px-20"
            >
                <div className="mx-auto flex max-w-[1280px] flex-col gap-3.5">
                    <div className="flex flex-wrap items-center gap-2.5">
                        <span className="font-mono text-[11px] font-medium uppercase tracking-eyebrow text-accent-primary">
                            04 / Notes
                        </span>
                        <span
                            className="h-px w-8 bg-border-strong"
                            aria-hidden
                        />
                        <span className="font-mono text-[11px] font-medium uppercase tracking-eyebrow text-ink-muted">
                            Document-First · Interpretive
                        </span>
                    </div>
                    <h2 className="font-heading text-[28px] font-normal leading-[1.15] tracking-[-0.018em] text-ink-primary lg:text-display-section">
                        Dibangun untuk membaca dokumen, bukan memberi vonis
                        investasi
                    </h2>
                    <p className="max-w-[760px] font-body text-[15px] leading-[1.55] text-ink-secondary">
                        Whitepaper Checker menyusun asesmen dari lima sinyal
                        dokumen: keseimbangan konten, cakupan bagian penting
                        berbasis profil, kemiripan dengan sumber publik,
                        kualitas linguistik, dan ekstraksi kata kunci. Sinyal
                        struktural memimpin; sinyal pendukung memberi konteks.
                        Hasilnya dirancang sebagai alat bantu telaah awal —
                        bukan rekomendasi investasi.
                    </p>
                </div>
            </section>
        </>
    );
}
