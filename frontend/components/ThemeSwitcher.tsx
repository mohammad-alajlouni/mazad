"use client";

import { useTranslations } from "next-intl";
import { Moon, Sun } from "lucide-react";

// Day or night for the whole site. Day is the default; the device's setting
// is never followed. The choice lives on <html data-theme> (which the styles
// read, and which shows the right icon) and in a cookie the server reads.
export default function ThemeSwitcher() {
  const tr = useTranslations("common");
  const toggle = () => {
    const root = document.documentElement;
    const night = root.dataset.theme !== "dark";
    if (night) root.dataset.theme = "dark";
    else delete root.dataset.theme;
    document.cookie = `atlas_theme=${night ? "dark" : "light"}; Path=/; Max-Age=31536000; SameSite=Lax${location.protocol === "https:" ? "; Secure" : ""}`;
  };
  return (
    <button
      type="button"
      className="theme-switcher"
      onClick={toggle}
      aria-label={tr("theme")}
      title={tr("theme")}
    >
      <Moon size={17} className="to-night" aria-hidden="true" />
      <Sun size={17} className="to-day" aria-hidden="true" />
    </button>
  );
}
