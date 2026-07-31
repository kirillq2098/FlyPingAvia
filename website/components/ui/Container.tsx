import { cn } from "@/lib/cn";

type ContainerProps = {
  children: React.ReactNode;
  className?: string;
  as?: "div" | "section" | "footer" | "header" | "nav";
  id?: string;
  wide?: boolean;
};

export function Container({
  children,
  className,
  as: Tag = "div",
  id,
  wide = false,
}: ContainerProps) {
  return (
    <Tag
      id={id}
      className={cn(
        "mx-auto w-full px-5 sm:px-6 lg:px-8",
        wide ? "max-w-[1400px]" : "max-w-[1400px]",
        className,
      )}
    >
      {children}
    </Tag>
  );
}
