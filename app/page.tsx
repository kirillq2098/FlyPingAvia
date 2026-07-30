import { Header } from "@/components/Header";
import { Hero } from "@/components/Hero";
import { ProductFlow } from "@/components/ProductFlow";
import { InterfaceShowcase } from "@/components/InterfaceShowcase";
import { TravelEditorial } from "@/components/TravelEditorial";
import { Principles } from "@/components/Principles";
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
        <ProductFlow />
        <InterfaceShowcase />
        <TravelEditorial />
        <Principles />
        <FAQ />
        <CTA />
      </main>
      <Footer />
    </>
  );
}
