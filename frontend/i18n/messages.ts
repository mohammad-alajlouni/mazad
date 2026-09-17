import en from "../messages/en.json";
import ar from "../messages/ar.json";
export type Locale = "en" | "ar";
export const messages = { en, ar };
export const normalizeLocale = (value?: string): Locale =>
  value === "ar" ? "ar" : "en";
