import SignalCard from "@/components/result/SignalCard";

export default function SignalBreakdown({ signals }) {
    const TIER_ORDER = {
        primary: 0,
        monitoring: 1,
        supporting: 2,
        interpretive: 3,
    };
    const sortedSignals = [...(signals ?? [])].sort(
        (left, right) =>
            (TIER_ORDER[left?.tier] ?? 99) - (TIER_ORDER[right?.tier] ?? 99),
    );

    return (
        <section
            className="px-5 pb-8 sm:px-10 lg:px-20"
            style={{ paddingTop: 24 }}
        >
            <div className="mx-auto max-w-[1280px]">
                {/* header */}
                <div className="mb-6 flex flex-col gap-2">
                    <div className="flex items-center gap-[10px]">
                        <span className="font-mono text-[11px] font-medium tracking-[1.6px] text-accent-primary">
                            B / RINCIAN SINYAL
                        </span>
                        <span className="h-px w-8 bg-border-strong" />
                        <span className="font-mono text-[10px] font-medium tracking-[1.6px] text-ink-muted">
                            SUSUNAN BERDASARKAN PRIORITAS
                        </span>
                    </div>
                    <h2 className="font-heading text-[32px] font-normal tracking-[-0.6px] text-ink-primary">
                        5 sinyal yang dipertimbangkan
                    </h2>
                    <p className="max-w-[760px] text-[14px] leading-[1.55] text-ink-secondary">
                        Keseimbangan konten & cakupan berbasis profil adalah
                        sinyal utama. Kemiripan bersifat netral. Linguistik &
                        kata kunci hanya pendukung.
                    </p>
                </div>

                {/* cards */}
                <div className="flex flex-col gap-[14px]">
                    {sortedSignals.length ? (
                        sortedSignals.map((signal) => (
                            <SignalCard key={signal.name} signal={signal} />
                        ))
                    ) : (
                        <div className="rounded-[8px] border border-border-subtle bg-surface-card p-6 text-sm text-ink-muted">
                            Belum ada rincian sinyal untuk ditampilkan.
                        </div>
                    )}
                </div>
            </div>
        </section>
    );
}
