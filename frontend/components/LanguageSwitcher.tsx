"use client";

import { useTranslations } from "next-intl";
import { useInterfaceLocale } from "../i18n/LocaleProvider";
import { normalizeLocale } from "../i18n/messages";
export default function LanguageSwitcher() {
  const tr = useTranslations("common");
  const { locale, setLocale } = useInterfaceLocale();
  return (
    <select
      className="language-switcher"
      aria-label={tr("language")}
      value={locale}
      onChange={(e) => setLocale(normalizeLocale(e.target.value))}
    >
      <option value="en" lang="en">
        {tr("english")}
      </option>
      <option value="ar" lang="ar">
        {tr("arabic")}
      </option>
    </select>
  );
}
