"use client";

import Script from "next/script";
import { siteConfig } from "@/lib/config";

/**
 * Подключает аналитику только при наличии ID в env.
 * Не блокирует основной рендер (afterInteractive).
 */
export function Analytics() {
  const { gaId, yandexMetricaId } = siteConfig.analytics;
  const hasGa = Boolean(gaId);
  const hasYm = Boolean(yandexMetricaId);

  if (!hasGa && !hasYm) {
    return null;
  }

  return (
    <>
      {hasGa ? (
        <>
          <Script
            src={`https://www.googletagmanager.com/gtag/js?id=${gaId}`}
            strategy="afterInteractive"
          />
          <Script id="ga4-init" strategy="afterInteractive">
            {`
              window.dataLayer = window.dataLayer || [];
              function gtag(){dataLayer.push(arguments);}
              window.gtag = gtag;
              gtag('js', new Date());
              gtag('config', '${gaId}', { anonymize_ip: true });
            `}
          </Script>
        </>
      ) : null}

      {hasYm ? (
        <Script id="yandex-metrica" strategy="afterInteractive">
          {`
            (function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};
            m[i].l=1*new Date();
            for (var j = 0; j < document.scripts.length; j++) {if (document.scripts[j].src === r) { return; }}
            k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)})
            (window, document, "script", "https://mc.yandex.ru/metrika/tag.js", "ym");
            ym(${Number(yandexMetricaId)}, "init", {
              clickmap:true,
              trackLinks:true,
              accurateTrackBounce:true,
              webvisor:false
            });
          `}
        </Script>
      ) : null}
    </>
  );
}
