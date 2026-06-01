import { Info } from "lucide-react";

export default function DisclaimerBand() {
    // disclaimerBand from pencil-new.pen Frame 1 (cdRvo):
    // surface.tinted bg, padding 28/80, horizontal layout with icon box + text
    return (
        <section className="w-full bg-surface-tinted">
            <div className="mx-auto flex max-w-[1280px] items-center gap-6 px-5 py-7 sm:px-10 lg:px-20">
                {/* discIcon: 44x44 box with info icon */}
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md border border-border-subtle bg-surface-card">
                    <Info
                        className="h-5 w-5 text-ink-primary"
                        strokeWidth={1.75}
                    />
                </div>

                {/* discText: eyebrow + body */}
                <div className="flex min-w-0 flex-1 flex-col gap-1">
                    <p className="font-mono text-[10px] font-medium uppercase tracking-[0.14em] text-ink-muted">
                        Bukan Nasihat Finansial
                    </p>
                    <p className="font-body text-[13px] leading-[1.55] text-ink-secondary">
                        Alat ini mendukung telaah dokumen awal dan bukan
                        merupakan rekomendasi investasi. Hasil bersifat
                        heuristik berbasis aturan dari sinyal dokumen.
                    </p>
                </div>
            </div>
        </section>
    );
}
