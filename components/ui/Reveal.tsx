"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";

type RevealProps = {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  y?: number;
};

export function Reveal({
  children,
  className,
  delay = 0,
  y = 18,
}: RevealProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (media.matches) {
      setVisible(true);
      return;
    }

    // Start hidden only after mount, then reveal on intersect (or fallback timer).
    setVisible(false);

    const fallback = window.setTimeout(() => setVisible(true), 900 + delay * 1000);

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          window.setTimeout(() => setVisible(true), delay * 1000);
          observer.disconnect();
          window.clearTimeout(fallback);
        }
      },
      { threshold: 0.08, rootMargin: "100px 0px" },
    );

    observer.observe(node);

    return () => {
      observer.disconnect();
      window.clearTimeout(fallback);
    };
  }, [delay]);

  return (
    <div
      ref={ref}
      className={cn(
        "transition-[opacity,transform] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]",
        visible ? "translate-y-0 opacity-100" : "opacity-0",
        className,
      )}
      style={visible ? undefined : { transform: `translateY(${y}px)` }}
    >
      {children}
    </div>
  );
}
