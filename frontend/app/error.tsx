"use client";
import { useTranslations } from "next-intl";
export default function ErrorPage({ reset }: { reset: () => void }) {
  const tr = useTranslations("common");
  return (
    <main className="startup">
      <h1>{tr("unexpectedError")}</h1>
      <button className="primary" onClick={reset}>
        {tr("retry")}
      </button>
    </main>
  );
}
