import { ShieldCheck } from "lucide-react";

export default function TrustNote() {
  // trustNote from pencil-new.pen heroRight
  return (
    <div className="flex w-full items-center gap-2.5 px-1.5 py-3">
      <ShieldCheck
        className="h-3.5 w-3.5 shrink-0 text-ink-muted"
        strokeWidth={1.75}
      />
      <p className="font-body text-[12px] leading-[1.5] text-ink-muted">
        Dokumen Anda diproses untuk analisis sinyal dan tidak digunakan untuk
        rekomendasi finansial.
      </p>
    </div>
  );
}
