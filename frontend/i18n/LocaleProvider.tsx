"use client";
import { ConfirmationProvider } from "../components/Confirmation";
import { createContext, useContext, useState, useEffect } from "react";
import { NextIntlClientProvider, useTranslations } from "next-intl";
import { messages, Locale } from "./messages";
const Context = createContext<{
  locale: Locale;
  setLocale: (locale: Locale) => void;
}>({ locale: "ar", setLocale: () => {} });
export function useInterfaceLocale() {
  return useContext(Context);
}
export default function LocaleProvider({
  initialLocale,
  children,
}: {
  initialLocale: Locale;
  children: React.ReactNode;
}) {
  const [locale, setState] = useState(initialLocale);
  const setLocale = (next: Locale) => {
    document.cookie = `atlas_locale=${next}; Path=/; Max-Age=31536000; SameSite=Lax${location.protocol === "https:" ? "; Secure" : ""}`;
    document.documentElement.lang = next;
    document.documentElement.dir = next === "ar" ? "rtl" : "ltr";
    setState(next);
  };
  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir = locale === "ar" ? "rtl" : "ltr";
    document.title = messages[locale].common.metaTitle;
    document
      .querySelector('meta[name="description"]')
      ?.setAttribute("content", messages[locale].common.metaDescription);
    // Clear stale browser validation text when the interface language changes.
    document
      .querySelectorAll<HTMLInputElement>("input,select,textarea")
      .forEach((input) => input.setCustomValidity(""));
  }, [locale]);
  return (
    <Context.Provider value={{ locale, setLocale }}>
      <NextIntlClientProvider
        locale={locale}
        messages={messages[locale]}
        timeZone="Asia/Amman"
      >
        <ConfirmationProvider>
          <LocalizedValidation>{children}</LocalizedValidation>
        </ConfirmationProvider>
      </NextIntlClientProvider>
    </Context.Provider>
  );
}
function LocalizedValidation({ children }: { children: React.ReactNode }) {
  const tr = useTranslations("common");
  return (
    <div
      className="locale-root"
      onInputCapture={(event) => {
        const el = event.target;
        if (
          el instanceof HTMLInputElement ||
          el instanceof HTMLTextAreaElement ||
          el instanceof HTMLSelectElement
        )
          el.setCustomValidity("");
      }}
      onInvalidCapture={(event) => {
        const el = event.target;
        if (
          el instanceof HTMLInputElement ||
          el instanceof HTMLTextAreaElement ||
          el instanceof HTMLSelectElement
        ) {
          el.setCustomValidity(
            tr(
              el.validity.valueMissing
                ? "required"
                : el instanceof HTMLInputElement && el.type === "email"
                  ? "invalidEmail"
                  : "invalidNumber",
            ),
          );
        }
      }}
    >
      {children}
    </div>
  );
}
