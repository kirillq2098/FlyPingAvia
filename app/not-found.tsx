import type { Metadata } from "next";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import { Logo } from "@/components/ui/Logo";

export const metadata: Metadata = {
  title: "Страница не найдена",
  robots: { index: false, follow: false },
};

export default function NotFound() {
  return (
    <main id="main" className="flex min-h-screen flex-col">
      <div className="border-b border-line">
        <Container className="flex h-16 items-center">
          <Logo />
        </Container>
      </div>

      <Container className="flex flex-1 flex-col justify-center py-20">
        <p className="mono text-[11px] uppercase tracking-[0.18em] text-mute">
          error 404
        </p>
        <h1 className="mt-4 text-4xl font-semibold tracking-[-0.045em] text-ink sm:text-5xl">
          Маршрут не найден
        </h1>
        <p className="mt-4 max-w-md text-base leading-7 text-mute">
          Похоже, такой страницы нет. Вернитесь на главную и продолжите
          путешествие.
        </p>
        <div className="mt-8 flex items-center gap-6">
          <Button href="/" size="lg">
            Вернуться на главную
          </Button>
          <Link href="/#faq" className="text-sm text-mute hover:text-ink">
            FAQ
          </Link>
        </div>
        <div className="mt-16 flex max-w-sm items-center gap-4 border-t border-line pt-6">
          <p className="airport-code text-2xl text-ink">OVB</p>
          <span className="h-px flex-1 bg-line-strong" />
          <p className="airport-code text-2xl text-ink">LED</p>
        </div>
      </Container>
    </main>
  );
}
