import Link from "next/link";
import { cn } from "@/lib/cn";

type ButtonVariant = "primary" | "secondary" | "ghost" | "on-dark";
type ButtonSize = "md" | "lg";

type CommonProps = {
  children: React.ReactNode;
  className?: string;
  variant?: ButtonVariant;
  size?: ButtonSize;
};

type ButtonAsButton = CommonProps &
  React.ButtonHTMLAttributes<HTMLButtonElement> & {
    href?: undefined;
  };

type ButtonAsLink = CommonProps & {
  href: string;
  target?: string;
  rel?: string;
  onClick?: React.MouseEventHandler<HTMLAnchorElement>;
};

type ButtonProps = ButtonAsButton | ButtonAsLink;

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-brand text-white hover:bg-brand-hover focus-visible:ring-brand",
  secondary:
    "bg-transparent text-ink underline-offset-4 hover:underline focus-visible:ring-brand",
  ghost:
    "bg-transparent text-ink ring-1 ring-line hover:bg-surface-raised focus-visible:ring-brand",
  "on-dark":
    "bg-white text-night hover:bg-[#f3f1ec] focus-visible:ring-white",
};

const sizeClasses: Record<ButtonSize, string> = {
  md: "h-11 px-5 text-sm",
  lg: "h-12 px-6 text-[0.95rem] sm:h-[3.25rem] sm:px-7",
};

export function Button(props: ButtonProps) {
  const { children, className, variant = "primary", size = "md" } = props;

  const classes = cn(
    "inline-flex items-center justify-center gap-2 rounded-[var(--radius)] font-medium tracking-[-0.01em] transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
    variant !== "secondary" && sizeClasses[size],
    variantClasses[variant],
    className,
  );

  if ("href" in props && props.href) {
    const { href, target, rel, onClick } = props;
    return (
      <Link href={href} target={target} rel={rel} onClick={onClick} className={classes}>
        {children}
      </Link>
    );
  }

  const { type = "button", ...rest } = props as ButtonAsButton;
  return (
    <button type={type} className={classes} {...rest}>
      {children}
    </button>
  );
}
