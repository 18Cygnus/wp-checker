export default function Footer() {
    // footer (nizCN) from pencil-new.pen Frame 1:
    // padding 24/80, horizontal space-between, mono labels at 0.6 letter-spacing
    return (
        <footer className="border-t border-border-subtle bg-surface-primary">
            <div className="mx-auto flex max-w-[1280px] flex-col gap-3 px-5 py-6 sm:px-10 md:flex-row md:items-center md:justify-between lg:px-20">
                <p className="font-mono text-[10px] font-medium uppercase tracking-mono-meta text-ink-muted">
                    © Whitepaper Checker · Riset Skripsi
                </p>
            </div>
        </footer>
    );
}
