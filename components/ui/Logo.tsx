import { Plane } from "lucide-react";
import { cn } from "@/lib/cn";
import { siteConfig } from "@/lib/site";

type LogoProps = {
  className?: string;
  showWordmark?: boolean;
};

export function Logo({ className, showWordmark = true }: LogoProps) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <span className="relative flex h-9 w-9 items-center justify-center rounded-[14px] bg-gradient-to-br from-brand-500 to-sky-400 shadow-[0_8px_20px_rgba(37,99,235,0.35)] ring-1 ring-white/40">
        <span className="absolute inset-0 rounded-[14px] bg-white/15 opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
        <Plane className="relative h-4 w-4 text-white" strokeWidth={2.4} />
      </span>
      {showWordmark ? (
        <span className="text-lg font-bold tracking-[-0.03em] text-ink">
          {siteConfig.name}
        </span>
      ) : null}
    </span>
  );
}
