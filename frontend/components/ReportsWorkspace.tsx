"use client";
// The Real Estate General Authority's reports, after the auction: the auction
// closing form and the outputs report, for the auction project chosen first.
// The project gives the auction's name, dates, properties and selling agent;
// what happened at the auction is entered here once and fills both reports.
import React, { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { ArrowRight, FileCheck2, ImagePlus, Trash2 } from "lucide-react";
import { api, send, Detail, Output, Run } from "./api";
import ReportPreview from "./ReportPreview";
import { OutputList } from "./shared";

type Result = {
  status: "" | "sold" | "unsold";
  reason: string;
  winner: string;
  value: string;
  opening_price: string;
};
type Channel = { content: string; views: string };
type Entries = {
  closing: { date: string | null; approval_number: string };
  report: Record<string, unknown> & {
    boards: string[];
    channels: Record<string, Channel>;
  };
  properties: Record<string, Result>;
};
type View = {
  reports: Entries;
  images: { id: string; category: string }[];
  limits: Record<string, number>;
  shared: {
    auction_name: string;
    agent_name: string;
    agent_phone: string;
    properties: {
      id: string;
      title: string;
      deed: string;
      property_type: string;
      usage: string;
      district: string;
    }[];
  };
};
export const REPORTS = ["auction_closing", "outputs_report"] as const;
type Report = (typeof REPORTS)[number];
const CHANNELS = ["x", "tiktok", "whatsapp", "sms"];
const EMPTY: Result = {
  status: "",
  reason: "",
  winner: "",
  value: "",
  opening_price: "",
};

export default function ReportsWorkspace({
  detail,
  busy,
  run,
  reloadProject,
  setReview,
  onChangeProject,
}: {
  detail: Detail;
  busy: boolean;
  run: Run;
  reloadProject: () => Promise<void>;
  setReview: (output: Output) => void;
  onChangeProject: () => void;
}) {
  const t = useTranslations("authorityReports");
  const [view, setView] = useState<View | null>(null);
  const [entries, setEntries] = useState<Entries | null>(null);
  const [report, setReport] = useState<Report>("auction_closing");
  const [images, setImages] = useState(0);
  const id = detail.project.id;
  useEffect(() => {
    void run(async () => {
      const loaded = await api<View>(`/projects/${id}/reports`);
      setView(loaded);
      setEntries(loaded.reports);
    });
  }, [id]);
  if (!view || !entries) return <section className="panel form-panel" />;
  const shared = view.shared;
  const r = entries.report;
  const setReportValue = (key: string, value: unknown) =>
    setEntries({ ...entries, report: { ...r, [key]: value } });
  const result = (item: string) => entries.properties[item] || EMPTY;
  const setResult = (item: string, key: keyof Result, value: string) =>
    setEntries({
      ...entries,
      properties: {
        ...entries.properties,
        [item]: { ...result(item), [key]: value },
      },
    });
  const text = (value: unknown) =>
    value === null || value === undefined ? "" : String(value);
  const field = (
    label: string,
    value: unknown,
    change: (value: string) => void,
    props: React.InputHTMLAttributes<HTMLInputElement> = {},
  ) => (
    <label>
      <span className="label-text">{label}</span>
      <input
        value={text(value)}
        onChange={(e) => change(e.target.value)}
        {...props}
      />
    </label>
  );
  const count = (key: string) =>
    field(t(`fields.${key}`), r[key], (v) => setReportValue(key, v), {
      type: "number",
      min: 0,
      inputMode: "numeric",
      dir: "ltr",
    });
  const save = (then?: () => Promise<void>) =>
    void run(async () => {
      const saved = await api<View>(`/projects/${id}/reports`, {
        method: "PUT",
        body: send(entries),
      });
      setView(saved);
      setEntries(saved.reports);
      if (then) await then();
    }, t("saved"));
  const issue = () =>
    save(async () => {
      const [output] = await api<Output[]>(`/projects/${id}/generate`, {
        method: "POST",
        body: send({ types: [report], output_language: "ar" }),
      });
      await reloadProject();
      setReview(output);
    });
  // Report images are stored at once (the entries keep their unsaved values).
  const upload = (category: string, files: FileList | null) =>
    void run(async () => {
      for (const file of Array.from(files || [])) {
        const body = new FormData();
        body.append("file", file);
        body.append("category", category);
        const next = await api<View>(`/projects/${id}/report-images`, {
          method: "POST",
          body,
        });
        setView({ ...next, reports: view.reports });
      }
      setImages((v) => v + 1);
    });
  const remove = (image: string) =>
    void run(async () => {
      const next = await api<View>(`/projects/${id}/report-images/${image}`, {
        method: "DELETE",
      });
      setView({ ...next, reports: view.reports });
      setImages((v) => v + 1);
    });
  const gallery = (category: string) => {
    const own = view.images.filter((i) => i.category === category);
    const limit = view.limits[category];
    return (
      <div className="report-images" data-category={category}>
        <span className="label-text">
          {t(`images.${category}`)}{" "}
          <small className="muted">
            {t("imageCount", { count: own.length, limit })}
          </small>
        </span>
        <ul>
          {own.map((image) => (
            <li key={image.id}>
              <img
                src={`/api/projects/${id}/report-images/${image.id}`}
                alt={t(`images.${category}`)}
              />
              <button
                type="button"
                className="icon-button"
                aria-label={t("removeImage")}
                title={t("removeImage")}
                onClick={() => remove(image.id)}
              >
                <Trash2 size={15} />
              </button>
            </li>
          ))}
          {(own.length < limit || limit === 1) && (
            <li>
              <label className="report-image-add">
                <ImagePlus size={18} />
                <span>
                  {own.length && limit === 1 ? t("replace") : t("add")}
                </span>
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  multiple={limit > 1}
                  aria-label={t(`images.${category}`)}
                  onChange={(e) => {
                    upload(category, e.target.files);
                    e.target.value = "";
                  }}
                />
              </label>
            </li>
          )}
        </ul>
      </div>
    );
  };
  const given = (label: string, value: string) => (
    <div className="form-given">
      <span className="label-text">{label}</span>
      <span className="given-value">{value || <em>{t("notEntered")}</em>}</span>
      <small>{t("fromProject")}</small>
    </div>
  );
  return (
    <div className="reports-workspace">
      <section className="project-hub">
        <div className="hub-heading">
          <span className="hub-icon">
            <FileCheck2 size={22} />
          </span>
          <div>
            <h2>{shared.auction_name || detail.project.name}</h2>
            <p>{t("projectHelp")}</p>
          </div>
          <button
            type="button"
            className="text-button"
            onClick={onChangeProject}
          >
            <ArrowRight size={16} />
            {t("changeProject")}
          </button>
        </div>
        <nav className="project-sections segmented" aria-label={t("title")}>
          {REPORTS.map((key) => (
            <button
              key={key}
              type="button"
              disabled={busy}
              className={report === key ? "selected" : ""}
              aria-current={report === key ? "page" : undefined}
              onClick={() => setReport(key)}
            >
              {t(key)}
            </button>
          ))}
        </nav>
      </section>
      <div className="live-booklet-layout">
        <form
          className="live-booklet-fields panel form-panel reports-form"
          onSubmit={(e) => {
            e.preventDefault();
            save();
          }}
        >
          <h2>{t(report)}</h2>
          <p className="muted">{t(`${report}Help`)}</p>
          <div className="form-grid">
            {given(t("fields.auction_name"), shared.auction_name)}
            {given(t("fields.agent_name"), shared.agent_name)}
          </div>
          {report === "auction_closing" && (
            <>
              <div className="form-grid">
                {field(
                  t("fields.closing_date"),
                  entries.closing.date,
                  (v) =>
                    setEntries({
                      ...entries,
                      closing: { ...entries.closing, date: v || null },
                    }),
                  { type: "date", dir: "ltr" },
                )}
                {field(
                  t("fields.approval_number"),
                  entries.closing.approval_number,
                  (v) =>
                    setEntries({
                      ...entries,
                      closing: { ...entries.closing, approval_number: v },
                    }),
                  { dir: "ltr" },
                )}
              </div>
              <h3>{t("results")}</h3>
              <p className="muted">{t("resultsHelp")}</p>
              {!shared.properties.length && (
                <p className="notice error">{t("noProperties")}</p>
              )}
              {shared.properties.map((p, n) => {
                const own = result(p.id);
                return (
                  <fieldset
                    key={p.id}
                    className="report-result"
                    data-item={p.id}
                  >
                    <legend>
                      {n + 1}. {p.title || p.property_type}
                      <small className="muted">
                        {" "}
                        · {p.deed} · {p.property_type}
                        {p.usage ? ` · ${p.usage}` : ""}
                      </small>
                    </legend>
                    <div className="segmented form-choice" role="radiogroup">
                      {(["sold", "unsold"] as const).map((key) => (
                        <button
                          type="button"
                          key={key}
                          role="radio"
                          aria-checked={own.status === key}
                          aria-label={`${p.title || p.deed}: ${t(key)}`}
                          className={own.status === key ? "selected" : ""}
                          onClick={() =>
                            setResult(
                              p.id,
                              "status",
                              own.status === key ? "" : key,
                            )
                          }
                        >
                          {t(key)}
                        </button>
                      ))}
                    </div>
                    {own.status === "sold" && (
                      <div className="form-grid">
                        {field(t("fields.winner"), own.winner, (v) =>
                          setResult(p.id, "winner", v),
                        )}
                        {field(
                          t("fields.value"),
                          own.value,
                          (v) => setResult(p.id, "value", v),
                          { dir: "ltr", inputMode: "decimal" },
                        )}
                      </div>
                    )}
                    {own.status === "unsold" &&
                      field(t("fields.reason"), own.reason, (v) =>
                        setResult(p.id, "reason", v),
                      )}
                  </fieldset>
                );
              })}
              <h3>{t("signing")}</h3>
              <div className="form-grid">
                {gallery("signature")}
                {gallery("stamp")}
              </div>
            </>
          )}
          {report === "outputs_report" && (
            <>
              <h3>{t("cover")}</h3>
              <div className="form-grid">
                {field(
                  t("fields.period_from"),
                  r.period_from,
                  (v) => setReportValue("period_from", v || null),
                  { type: "date", dir: "ltr" },
                )}
                {field(
                  t("fields.period_to"),
                  r.period_to,
                  (v) => setReportValue("period_to", v || null),
                  { type: "date", dir: "ltr" },
                )}
                {field(
                  t("fields.court"),
                  r.court,
                  (v) => setReportValue("court", v),
                  {
                    placeholder: "محكمة التنفيذ",
                  },
                )}
              </div>
              <label>
                <span className="label-text">{t("fields.intro")}</span>
                <textarea
                  rows={5}
                  value={text(r.intro)}
                  placeholder={t("introPlaceholder")}
                  onChange={(e) => setReportValue("intro", e.target.value)}
                />
              </label>
              <h3>{t("boards")}</h3>
              <div className="form-grid">
                {field(
                  t("fields.boards_installed"),
                  r.boards_installed,
                  (v) => setReportValue("boards_installed", v || null),
                  { type: "date", dir: "ltr" },
                )}
                {field(
                  t("fields.boards_removed"),
                  r.boards_removed,
                  (v) => setReportValue("boards_removed", v || null),
                  { type: "date", dir: "ltr" },
                )}
              </div>
              <label>
                <span className="label-text">{t("fields.boards")}</span>
                <textarea
                  rows={5}
                  value={(r.boards || []).join("\n")}
                  placeholder={t("boardsPlaceholder")}
                  onChange={(e) =>
                    setReportValue(
                      "boards",
                      e.target.value.split("\n").slice(0, 60),
                    )
                  }
                />
              </label>
              {gallery("board")}
              <h3>{t("channels")}</h3>
              <table className="report-channels">
                <thead>
                  <tr>
                    <th>{t("fields.channel")}</th>
                    <th>{t("fields.content")}</th>
                    <th>{t("fields.views")}</th>
                  </tr>
                </thead>
                <tbody>
                  {CHANNELS.map((key) => {
                    const own = r.channels?.[key] || { content: "", views: "" };
                    const set = (k: keyof Channel, v: string) =>
                      setReportValue("channels", {
                        ...r.channels,
                        [key]: { ...own, [k]: v },
                      });
                    return (
                      <tr key={key}>
                        <th scope="row">{t(`channel.${key}`)}</th>
                        <td>
                          <input
                            aria-label={`${t(`channel.${key}`)}: ${t("fields.content")}`}
                            value={own.content}
                            placeholder={t(`contentDefault.${key}`)}
                            onChange={(e) => set("content", e.target.value)}
                          />
                        </td>
                        <td>
                          <input
                            aria-label={`${t(`channel.${key}`)}: ${t("fields.views")}`}
                            value={own.views}
                            dir="ltr"
                            onChange={(e) => set("views", e.target.value)}
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <h3>{t("channel.x")}</h3>
              <div className="form-grid">
                {count("x_posts")}
                {count("x_paid")}
                {count("x_unpaid")}
              </div>
              {gallery("x")}
              <h3>{t("channel.tiktok")}</h3>
              <div className="form-grid">{count("tiktok_videos")}</div>
              {gallery("tiktok")}
              <h3>{t("channel.whatsapp")}</h3>
              {gallery("whatsapp")}
              <h3>{t("youtube")}</h3>
              {gallery("youtube")}
              <h3>{t("participantsTitle")}</h3>
              <div className="form-grid">
                {count("participants")}
                {count("interested")}
                {count("visitors")}
              </div>
              <h3>{t("assets")}</h3>
              <p className="muted">{t("assetsHelp")}</p>
              <div className="form-grid">
                {shared.properties.map((p) => (
                  <React.Fragment key={p.id}>
                    {field(
                      `${t("fields.opening_price")} · ${p.title || p.deed}`,
                      result(p.id).opening_price,
                      (v) => setResult(p.id, "opening_price", v),
                      { dir: "ltr", inputMode: "decimal" },
                    )}
                  </React.Fragment>
                ))}
              </div>
              <label>
                <span className="label-text">{t("fields.unsold_reason")}</span>
                <textarea
                  rows={3}
                  value={text(r.unsold_reason)}
                  onChange={(e) =>
                    setReportValue("unsold_reason", e.target.value)
                  }
                />
              </label>
              <h3>{t("contact")}</h3>
              <div className="form-grid">
                {field(t("fields.address"), r.address, (v) =>
                  setReportValue("address", v),
                )}
                {field(
                  t("fields.phone"),
                  r.phone,
                  (v) => setReportValue("phone", v),
                  {
                    dir: "ltr",
                    type: "tel",
                    placeholder: shared.agent_phone || undefined,
                  },
                )}
                {field(
                  t("fields.email"),
                  r.email,
                  (v) => setReportValue("email", v),
                  {
                    dir: "ltr",
                    type: "email",
                  },
                )}
              </div>
            </>
          )}
          <div className="flex-row report-actions">
            <button type="submit" className="secondary" disabled={busy}>
              {t("save")}
            </button>
            <button
              type="button"
              className="primary"
              disabled={busy || !shared.properties.length}
              onClick={issue}
            >
              <FileCheck2 size={17} />
              {t("issue", { report: t(report) })}
            </button>
          </div>
          <OutputList
            outputs={detail.outputs.filter((o) => o.output_type === report)}
            onOpen={setReview}
          />
        </form>
        <ReportPreview
          projectId={id}
          report={report}
          data={entries}
          version={images}
        />
      </div>
    </div>
  );
}
