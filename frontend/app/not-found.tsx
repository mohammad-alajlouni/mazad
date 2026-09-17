"use client";
import { useTranslations } from "next-intl";
export default function NotFound() {
  const tr = useTranslations("common");
  return (
    <main className="startup">
      <h1>{tr("notFound")}</h1>
      <a className="primary" href="/">
        {tr("returnHome")}
      </a>
    </main>
  );
}
