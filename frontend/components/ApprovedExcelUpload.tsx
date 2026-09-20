"use client";
import { useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { api, type Run } from "./api";
import FileInput from "./FileInput";
import { errorMessage } from "../i18n/errors";

type Issue = { cell: string; code: string; context: Record<string, string> };
type Preview = {
  id: string;
  valid_count: number;
  invalid_count: number;
  rows: {
    sheet: string;
    data: {
      title: string;
      description?: string;
      property_data?: Record<string, unknown>;
    };
    errors: Issue[];
    warnings: Issue[];
    source: Record<string, string>;
  }[];
};
export default function ApprovedExcelUpload({
  projectId,
  run,
  onDone,
}: {
  projectId: string;
  run: Run;
  onDone: () => void | Promise<void>;
}) {
  const t = useTranslations("excel");
  const tr = useTranslations();
  const [city, setCity] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const generation = useRef(0);
  const pending = useRef(false);
  const warnings = preview?.rows.some((row) => row.warnings.length) ?? false;
  const message = (issue: Issue) =>
    `${issue.cell ? `${issue.cell}: ` : ""}${t(`issues.${issue.code}`, issue.context)}`;
  return (
    <section className="panel form-panel">
      <h2>{t("title")}</h2>
      <p>{t("intro")}</p>
      <a className="secondary" href="/api/booklet-import-template" download>
        {t("download")}
      </a>
      <ol className="excel-instructions">
        <li>{t("step1")}</li>
        <li>{t("step2")}</li>
        <li>{t("step3")}</li>
      </ol>
      <details>
        <summary>{t("guide")}</summary>
        <p>{t("required")}</p>
        <p>{t("formats")}</p>
        <p>{t("links")}</p>
        <p>{t("missing")}</p>
      </details>
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          if (!file || pending.current) return;
          const version = ++generation.current;
          setPreview(null);
          setError("");
          setAcknowledged(false);
          if (!file.name.toLowerCase().endsWith(".xlsx")) {
            setError(t("wrongType"));
            return;
          }
          if (!file.size || file.size > 10 * 1024 * 1024) {
            setError(t("wrongSize"));
            return;
          }
          pending.current = true;
          setBusy(true);
          try {
            const form = new FormData();
            form.set("file", file);
            form.set("city", city);
            const result = await api<Preview>(
              `/projects/${projectId}/imports/approved/preview`,
              { method: "POST", body: form },
            );
            if (version === generation.current) setPreview(result);
          } catch (err) {
            if (version === generation.current) setError(errorMessage(err));
          } finally {
            pending.current = false;
            setBusy(false);
          }
        }}
      >
        <label>
          {t("city")}
          <input
            aria-label={t("city")}
            value={city}
            maxLength={100}
            disabled={busy}
            onChange={(event) => {
              setCity(event.target.value);
              generation.current++;
              setPreview(null);
              setAcknowledged(false);
            }}
          />
          <small className="muted">{t("cityHelp")}</small>
        </label>
        <label>
          {tr("ui.excel_workbook")}
          <FileInput
            name="file"
            accept=".xlsx"
            required
            disabled={busy}
            aria-label={tr("ui.excel_workbook")}
            onChange={(event) => {
              generation.current++;
              setPreview(null);
              setError("");
              setAcknowledged(false);
              setFile(event.target.files?.[0] ?? null);
            }}
          />
        </label>
        <button className="primary" disabled={busy || !file}>
          {busy ? t("checking") : tr("ui.preview_workbook")}
        </button>
      </form>
      {error && (
        <div className="notice error" role="alert">
          {error}
        </div>
      )}
      {preview && (
        <div aria-live="polite">
          <div className="notice">
            {t("summary", {
              valid: preview.valid_count,
              invalid: preview.invalid_count,
            })}
          </div>
          {!!preview.invalid_count && (
            <p className="notice error" role="alert">
              {t("blocked")}
            </p>
          )}
          {preview.rows.map((row, index) => {
            const property = row.data.property_data ?? {};
            return (
              <article className="excel-property" key={`${row.sheet}-${index}`}>
                <h3>
                  {row.sheet} — {row.data.title}
                </h3>
                <dl className="excel-facts">
                  {(
                    [
                      ["deed_number", "deed"],
                      ["area", "area"],
                      ["district", "district"],
                      ["auction_close_date", "date"],
                      ["auction_close_time", "time"],
                    ] as const
                  ).map(([field, label]) => (
                    <div key={field}>
                      <dt>{t(label)}</dt>
                      <dd>
                        <bdi>{String(property[field] ?? "—")}</bdi>
                      </dd>
                    </div>
                  ))}
                </dl>
                {!!row.errors.length && (
                  <ul className="error">
                    {row.errors.map((issue, n) => (
                      <li key={n}>{message(issue)}</li>
                    ))}
                  </ul>
                )}
                {!!row.warnings.length && (
                  <div className="notice">
                    <strong>{t("reviewWarnings")}</strong>
                    <ul>
                      {row.warnings.map((issue, n) => (
                        <li key={n}>{message(issue)}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <details>
                  <summary>{t("allCells")}</summary>
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>{t("cell")}</th>
                          <th>{t("source")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(row.source).map(([cell, value]) => (
                          <tr key={cell}>
                            <td>
                              <bdi>{cell}</bdi>
                            </td>
                            <td>{value || "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              </article>
            );
          })}
          {warnings && !preview.invalid_count && (
            <label className="excel-acknowledge">
              <input
                type="checkbox"
                checked={acknowledged}
                onChange={(event) => setAcknowledged(event.target.checked)}
              />
              {t("acknowledge")}
            </label>
          )}
          <button
            className="primary"
            disabled={
              busy ||
              !preview.valid_count ||
              !!preview.invalid_count ||
              (warnings && !acknowledged)
            }
            onClick={async () => {
              if (pending.current) return;
              pending.current = true;
              setBusy(true);
              setError("");
              try {
                await api(
                  `/projects/${projectId}/imports/${preview.id}/commit`,
                  { method: "POST" },
                );
                setPreview(null);
                await run(async () => {
                  await onDone();
                }, tr("ui.excel_records_imported"));
              } catch (err) {
                setError(errorMessage(err));
              } finally {
                pending.current = false;
                setBusy(false);
              }
            }}
          >
            {t("import", { count: preview.valid_count })}
          </button>
        </div>
      )}
    </section>
  );
}
