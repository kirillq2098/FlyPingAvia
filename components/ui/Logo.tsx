import { cn } from "@/lib/cn";
import { siteConfig } from "@/lib/site";

type LogoProps = {
  className?: string;
  tone?: "light" | "dark";
};

export function Logo({ className, tone = "light" }: LogoProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2.5 text-[1.05rem] font-semibold tracking-[-0.03em]",
        tone === "dark" ? "text-white" : "text-ink",
        className,
      )}
    >
      <span
        className={cn(
          "inline-flex h-7 w-7 items-center justify-center rounded-[8px] text-[11px] font-bold tracking-normal",
          tone === "dark"
            ? "bg-white text-night"
            : "bg-brand text-white",
        )}
        aria-hidden
      >
        FP
      </span>
      {siteConfig.name}
    </span>
  );
}
