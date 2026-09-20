"use client";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api, Detail, Output, Run, send } from "./api";

type Review = {
  valid: boolean;
  config?: { format?: string; size?: string; headline?: string };
  missing: { field: string; section: string }[];
};
export default function GenerateProject({
  detail,
  busy,
  dirty,
  run,
  onDone,
  onFix,
}: {
  detail: Detail;
  busy: boolean;
  dirty: boolean;
  run: Run;
  onDone: () => Promise<void>;
  onFix: (section: "data" | "banner" | "social", step?: string) => void;
}) {
  const t = useTranslations("projectGeneration");
  const a = useTranslations("auction");
  const [reviews, setReviews] = useState<Review[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let current = true;
    setReviews(null);
    setFailed(false);
    void Promise.all([
      api<Review>(`/projects/${detail.project.id}/banner-review`),
      api<Review>(`/projects/${detail.project.id}/social-review`),
    ])
      .then((r) => {
        if (current) setReviews(r);
      })
      .catch(() => {
        if (current) setFailed(true);
      });
    return () => {
      current = false;
    };
  }, [detail, retry]);
  const stage = Object.entries(detail.workflow?.stages || {}).find(
    ([, value]) => !value.valid,
  )?.[0];
  const ready = !stage && reviews?.every((r) => r.valid) && !dirty;
  return (
    <section
      className="panel form-panel project-generation"
      aria-label={t("title")}
    >
      <h2>{t("title")}</h2>
      <p>{t("help")}</p>
      <div className="publication-summary">
        <span>{t("booklet")}</span>
        <span>
          {t("banner")} · {reviews?.[0].config?.size || "4x2"} m
        </span>
        <span>
          {t("social")} · {reviews?.[1].config?.format || "instagram"}
        </span>
      </div>
      {!ready && (
        <p className="muted">
          {dirty
            ? t("save")
            : stage
              ? t("missing")
              : failed
                ? t("failed")
                : !reviews
                  ? t("checking")
                  : t("settings")}
        </p>
      )}
      {stage && (
        <button
          type="button"
          className="text-button"
          onClick={() => onFix("data", stage)}
        >
          {t("fix")}
        </button>
      )}
      {!stage &&
        reviews?.map(
          (r, index) =>
            !r.valid && (
              <div key={index} className="notice error">
                <ul>
                  {r.missing.map((m, i) => (
                    <li key={i}>{a.has(m.field) ? a(m.field) : m.field}</li>
                  ))}
                </ul>
                <button
                  type="button"
                  onClick={() => onFix(index === 0 ? "banner" : "social")}
                >
                  {t("settings")}
                </button>
              </div>
            ),
        )}
      {failed && (
        <button type="button" onClick={() => setRetry((v) => v + 1)}>
          {t("retry")}
        </button>
      )}
      <button
        type="button"
        className="primary"
        disabled={!ready || busy}
        onClick={() =>
          void run(async () => {
            await api<Output[]>(`/projects/${detail.project.id}/generate`, {
              method: "POST",
              body: send({
                types: ["project_booklet", "banners", "social_content"],
                output_language:
                  detail.project.auction?.document_language || "ar",
              }),
            });
            await onDone();
          }, t("done"))
        }
      >
        {busy ? t("generating") : t("generate")}
      </button>
    </section>
  );
}
