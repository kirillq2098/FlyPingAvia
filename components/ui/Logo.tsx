import Link from "next/link";
import { cn } from "@/lib/cn";
import { siteConfig } from "@/lib/site";

type LogoProps = {
  className?: string;
  tone?: "light" | "dark";
};

export function Logo({ className, tone = "light" }: LogoProps) {
  const ink = tone === "dark" ? "text-white" : "text-ink";
  const mark = tone === "dark" ? "stroke-white" : "stroke-blue";
  const fill = tone === "dark" ? "fill-white" : "fill-blue";

  return (
    <Link
      href="/#top"
      aria-label={`${siteConfig.name} — на главную`}
      className={cn("inline-flex items-center gap-2.5", ink, className)}
    >
      <svg
        width="22"
        height="22"
        viewBox="0 0 22 22"
        fill="none"
        aria-hidden
        className="shrink-0"
      >
        <circle cx="4" cy="18" r="2.2" className={fill} />
        <path
          d="M5.8 16.4 C9 12.2, 13.2 7.4, 18.5 4.2"
          className={mark}
          strokeWidth="1.6"
          strokeLinecap="round"
          fill="none"
        />
        <circle cx="18.5" cy="4.2" r="2.2" className={cn(fill, "opacity-90")} />
        <circle cx="18.5" cy="4.2" r="4.4" className={mark} strokeWidth="1" fill="none" opacity="0.35" />
      </svg>
      <span className="text-[1.05rem] font-semibold tracking-[-0.04em]">
        Fly<span className={tone === "dark" ? "text-white" : "text-blue"}>Ping</span>
      </span>
    </Link>
  );
}
