"use client";

import { ThemeProvider } from "next-themes";
import { Toaster } from "sonner";
import { I18nProvider } from "@/lib/i18n/provider";
import { AuthProvider } from "@/components/auth-provider";
import type { Lang } from "@/lib/types";

export function Providers({ children, initialLang }: { children: React.ReactNode; initialLang: Lang }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <I18nProvider initialLang={initialLang}>
        <AuthProvider>
          {children}
          <Toaster richColors closeButton position="top-center" />
        </AuthProvider>
      </I18nProvider>
    </ThemeProvider>
  );
}
