import type { Metadata, Viewport } from "next";
import { cookies } from "next/headers";
import "./globals.css";
import { Providers } from "@/components/providers";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import type { Lang } from "@/lib/types";

export const metadata: Metadata = {
  title: { default: "WasteWise · AI waste classification", template: "%s · WasteWise" },
  description: "Classify household waste from a photo, see Grad-CAM explanations and get Indian segregation guidance in English and Hindi.",
  icons: { icon: "/icon.svg" },
};

export const viewport: Viewport = {
  themeColor: [{ media: "(prefers-color-scheme: light)", color: "#F6F8F5" }, { media: "(prefers-color-scheme: dark)", color: "#0B1A16" }],
  width: "device-width",
  initialScale: 1,
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const c = (await cookies()).get("ww-lang")?.value;
  const lang: Lang = c === "hi" ? "hi" : "en";
  return (
    <html lang={lang} suppressHydrationWarning>
      <body className="min-h-dvh antialiased">
        <Providers initialLang={lang}>
          <div className="flex min-h-dvh flex-col">
            <SiteHeader />
            <main id="main" className="flex-1">{children}</main>
            <SiteFooter />
          </div>
        </Providers>
      </body>
    </html>
  );
}
