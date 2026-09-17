import { createTranslator } from "next-intl";
import { messages, normalizeLocale } from "./messages";
export const currentLocale = () =>
  normalizeLocale(
    typeof document === "undefined" ? "ar" : document.documentElement.lang,
  );
export function translate(
  key: string,
  values?: Record<string, string | number>,
) {
  const locale = currentLocale();
  const translator = createTranslator({ locale, messages: messages[locale] });
  return (
    translator as (
      key: string,
      values?: Record<string, string | number>,
    ) => string
  )(key, values);
}
export function systemLabel(value: string) {
  const key = value.replaceAll(" ", "_");
  return Object.hasOwn(messages.en.labels, key)
    ? translate("labels." + key)
    : translate("common.unknownLabel");
}
export function formatNumber(
  value: number | string,
  options: Intl.NumberFormatOptions = {},
) {
  return new Intl.NumberFormat(currentLocale(), {
    maximumFractionDigits: 4,
    ...options,
  }).format(Number(value));
}
export function formatDate(value: string) {
  return new Intl.DateTimeFormat(currentLocale(), {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "Asia/Amman",
  }).format(new Date(value.length === 10 ? value + "T12:00:00" : value));
}
export function formatTime(value: string) {
  return new Intl.DateTimeFormat(currentLocale(), {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Amman",
  }).format(new Date(value));
}
export function localizeKnownMessage(value: string): string {
  for (const ns of ["ui", "common"] as const)
    for (const [key, en] of Object.entries(messages.en[ns])) {
      const ar = (messages.ar[ns] as Record<string, string>)[key];
      if (value === en || value === ar) return translate(ns + "." + key);
    }
  return value;
}
export function activityLabel(action: string) {
  const key = action.replaceAll(" ", "_");
  return Object.hasOwn(messages.en.activity, key)
    ? translate("activity." + key)
    : translate("ui.recent_activity");
}
export function activityDetail(action: string, detail: string) {
  if (action === "Settings updated")
    return translate("ui.organization_branding");
  if (action === "Output generated" || action === "Output approved") {
    const [kind, ...name] = detail.split(" · ");
    const key = kind.toLowerCase().replaceAll(" ", "_");
    const aliases: Record<string, string> = {
      marketing_banners: "banners",
      social_media_content: "social_content",
    };
    return systemLabel(aliases[key] || key) + " · " + name.join(" · ");
  }
  if (action === "Excel preview" || action === "Excel imported") {
    const match = detail.match(/^(\d+) (?:valid )?rows for ([\s\S]*)$/);
    if (match)
      return translate(
        action === "Excel preview" ? "common.rowsFor" : "common.validRowsFor",
        { count: Number(match[1]), name: match[2] },
      );
  }
  return detail;
}
