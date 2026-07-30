"use client";

import { useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { cn } from "@/lib/cn";

type SpotlightCardProps = {
  children: React.ReactNode;
  className?: string;
  hoverLift?: boolean;
};

export function SpotlightCard({
  children,
  className,
  hoverLift = true,
}: SpotlightCardProps) {
  const reduceMotion = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const [spot, setSpot] = useState({ x: 50, y: 40 });

  return (
    <motion.div
      ref={ref}
      whileHover={
        reduceMotion || !hoverLift
          ? undefined
          : { y: -6, scale: 1.012 }
      }
      transition={{ type: "spring", stiffness: 320, damping: 22 }}
      onMouseMove={(event) => {
        const node = ref.current;
        if (!node || reduceMotion) return;
        const rect = node.getBoundingClientRect();
        setSpot({
          x: ((event.clientX - rect.left) / rect.width) * 100,
          y: ((event.clientY - rect.top) / rect.height) * 100,
        });
      }}
      className={cn(
        "group relative overflow-hidden rounded-[24px] border border-slate-200/80 bg-white/80 shadow-[0_16px_40px_rgba(15,23,42,0.05)] backdrop-blur-xl transition-shadow duration-500 hover:shadow-[0_24px_60px_rgba(37,99,235,0.12)]",
        className,
      )}
      style={{
        backgroundImage: reduceMotion
          ? undefined
          : `radial-gradient(500px circle at ${spot.x}% ${spot.y}%, rgba(37,99,235,0.12), transparent 42%)`,
      }}
    >
      <div className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-500 group-hover:opacity-100">
        <div className="absolute -right-10 -top-10 h-32 w-32 rounded-full bg-sky-300/25 blur-3xl" />
        <div className="absolute -bottom-12 -left-8 h-28 w-28 rounded-full bg-brand-400/20 blur-3xl" />
      </div>
      <div className="relative h-full">{children}</div>
    </motion.div>
  );
}
