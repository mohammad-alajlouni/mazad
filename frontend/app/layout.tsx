import "./globals.css";
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
  return (
    <html lang={locale} dir={locale === "ar" ? "rtl" : "ltr"}>
      <body>
        <LocaleProvider initialLocale={locale}>{children}</LocaleProvider>
      </body>
    </html>
  );
}
