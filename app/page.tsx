import { Header } from "@/components/Header";
import { Hero } from "@/components/Hero";
import { SocialProof } from "@/components/SocialProof";
import { HowItWorks } from "@/components/HowItWorks";
import { PriceDrop } from "@/components/PriceDrop";
import { Features } from "@/components/Features";
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
        <SocialProof />
        <HowItWorks />
        <PriceDrop />
        <Features />
        <Gallery />
        <FAQ />
        <CTA />
      </main>
      <Footer />
    </>
  );
}
