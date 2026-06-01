import { useState } from "react";
import { Menu, X } from "lucide-react";
import { cn } from "@/lib/utils";

const navLinks = [
    { href: "#yang-dianalisis", label: "Yang Dianalisis" },
    { href: "#cara-kerja", label: "Cara Kerja" },
    { href: "#catatan", label: "Catatan" },
];

function BrandMark() {
    // brandMarkBox + brandMarkInner + 3 stripes (bml1, bml2, bml3)
    return (
        <div className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-surface-inverse">
            <div className="relative h-[22px] w-[18px] rounded-[2px] bg-ink-inverse">
                <span className="absolute left-[3px] right-[3px] top-[5px] h-[2px] rounded-sm bg-surface-inverse" />
                <span className="absolute left-[3px] right-[3px] top-[10px] h-[2px] rounded-sm bg-surface-inverse" />
                <span className="absolute left-[3px] right-[7px] top-[15px] h-[2px] rounded-sm bg-accent-primary" />
            </div>
        </div>
    );
}

function ResearchTag() {
    return (
        <span className="inline-flex items-center gap-2 rounded-pill border border-border-subtle px-3 py-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-accent-teal" />
            <span className="font-mono text-[10px] font-medium uppercase tracking-mono-meta text-ink-secondary">
                Riset Skripsi · v0.9
            </span>
        </span>
    );
}

export default function NavBar({ onReset }) {
    const [isOpen, setIsOpen] = useState(false);

    const handleBrandClick = (e) => {
        if (onReset) {
            e.preventDefault();
            onReset();
        }
    };

    return (
        <header className="sticky top-0 z-50 border-b border-border-subtle bg-surface-primary/95 backdrop-blur">
            <div className="mx-auto flex h-[72px] max-w-[1280px] items-center justify-between gap-4 px-5 sm:px-10 lg:px-20">
                {/* Brand group */}
                <a href="#beranda" onClick={handleBrandClick} className="flex min-w-0 items-center gap-3">
                    <BrandMark />
                    <div className="flex min-w-0 flex-col leading-tight">
                        <span className="font-heading text-[18px] font-medium tracking-[-0.011em] text-ink-primary">
                            Whitepaper Checker
                        </span>
                        <span className="mt-0.5 font-mono text-[9px] font-medium uppercase tracking-[0.156em] text-ink-muted">
                            Document Intelligence for Investors
                        </span>
                    </div>
                </a>

                {/* Right nav (desktop) */}
                <nav className="hidden items-center gap-8 md:flex">
                    {navLinks.map((link) => (
                        <a
                            key={link.href}
                            href={link.href}
                            className="font-body text-[13px] font-medium text-ink-secondary transition-colors hover:text-ink-primary"
                        >
                            {link.label}
                        </a>
                    ))}
                    <ResearchTag />
                </nav>

                {/* Mobile menu trigger */}
                <button
                    type="button"
                    aria-expanded={isOpen}
                    aria-label={
                        isOpen ? "Tutup menu navigasi" : "Buka menu navigasi"
                    }
                    onClick={() => setIsOpen((prev) => !prev)}
                    className="inline-flex h-9 w-9 items-center justify-center rounded-button text-ink-primary md:hidden"
                >
                    {isOpen ? (
                        <X className="h-5 w-5" />
                    ) : (
                        <Menu className="h-5 w-5" />
                    )}
                </button>
            </div>

            {/* Mobile menu drawer */}
            <div
                className={cn(
                    "border-t border-border-subtle bg-surface-primary md:hidden",
                    isOpen ? "block" : "hidden",
                )}
            >
                <div className="mx-auto flex max-w-[1280px] flex-col gap-3 px-5 py-4 sm:px-10">
                    {navLinks.map((link) => (
                        <a
                            key={link.href}
                            href={link.href}
                            onClick={() => setIsOpen(false)}
                            className="font-body text-sm font-medium text-ink-secondary transition-colors hover:text-ink-primary"
                        >
                            {link.label}
                        </a>
                    ))}
                    <div className="pt-1">
                        <ResearchTag />
                    </div>
                </div>
            </div>
        </header>
    );
}
