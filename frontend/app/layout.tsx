import "./globals.css";
import "./landing.css";
import "./identity.css";
import "./theme.css";
import { cookies } from "next/headers";
import LocaleProvider from "../i18n/LocaleProvider";
import { messages, normalizeLocale } from "../i18n/messages";
async function requestLocale() {
  return normalizeLocale((await cookies()).get("atlas_locale")?.value);
}
export async function generateMetadata() {
  const locale = await requestLocale();
  return {
    title: messages[locale].common.metaTitle,
    description: messages[locale].common.metaDescription,
  };
}
export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const locale = await requestLocale();
  // Day unless the visitor chose night (see theme.css).
  const night = (await cookies()).get("atlas_theme")?.value === "dark";
  return (
    <html
      lang={locale}
      dir={locale === "ar" ? "rtl" : "ltr"}
      data-theme={night ? "dark" : undefined}
    >
      <body>
        <LocaleProvider initialLocale={locale}>{children}</LocaleProvider>
      </body>
    </html>
  );
}
