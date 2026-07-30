import { Header } from "@/components/Header";
import { Hero } from "@/components/Hero";
import { HowItWorks } from "@/components/HowItWorks";
import { Features } from "@/components/Features";
import { Comparison } from "@/components/Comparison";
import { Gallery } from "@/components/Gallery";
import { FAQ } from "@/components/FAQ";
import { CTA } from "@/components/CTA";
import { Footer } from "@/components/Footer";

export default function HomePage() {
  return (
    <>
      <div id="top" />
      <Header />
      <main>
        <Hero />
        <HowItWorks />
        <Features />
        <Comparison />
        <Gallery />
        <FAQ />
        <CTA />
      </main>
      <Footer />
    </>
  );
}
