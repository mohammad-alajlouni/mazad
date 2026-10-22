"use client";
// The auction's official forms: the authority's auction request form and
// Infath's property study. What the booklet holds is shown as it is (from
// the booklet); only the rest is entered here. The live preview shows the
// form being filled; both forms are generated with the booklet.
import React, { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { BookOpen, Check } from "lucide-react";
import { api, send, Detail, Run } from "./api";

type Yes = "" | "yes" | "no";
type Answer = { answer: Yes; note: string };
type Disclosure = { answer: Yes; text: string };
type PropertyForms = Record<string, unknown> & {
  answers?: Record<string, Answer>;
};
type Forms = {
  request: Record<string, unknown> & { rulings?: string[] };
  study: Record<string, string>;
  properties: Record<string, PropertyForms>;
};
type View = {
  forms: Forms;
  shared: {
    request: Record<string, string>;
    properties: Record<string, Record<string, string>>;
  };
  missing: {
    form: string;
    field: string;
    item: string | null;
    count?: number;
  }[];
  overflow: string[];
  sections: {
    number: number;
    title: string;
    questions: { key: string; text: string }[];
  }[];
};

const PARTS = ["request", "study"] as const;
type Part = (typeof PARTS)[number];

export function FormsStep({
  detail,
  run,
  onSaved,
}: {
  detail: Detail;
  run: Run;
  // After a part is saved; done after the last one.
  onSaved: (done: boolean) => void;
}) {
  const t = useTranslations("forms");
  const [view, setView] = useState<View | null>(null);
  const [forms, setForms] = useState<Forms | null>(null);
  const [part, setPart] = useState<Part>("request");
  const [item, setItem] = useState(detail.items[0]?.id || "");
  const form = useRef<HTMLFormElement>(null);
  const at = useRef(part);
  at.current = part;
  useEffect(() => {
    void run(async () => {
      const loaded = await api<View>(`/projects/${detail.project.id}/forms`);
      setView(loaded);
      setForms(loaded.forms);
    });
  }, [detail.project.id]);
  // The live preview follows the form being filled, unsaved values included.
  useEffect(() => {
    if (!forms) return;
    window.dispatchEvent(
      new CustomEvent("forms-draft", {
        detail: {
          forms,
          form: part,
          item: part === "study" ? item : undefined,
        },
      }),
    );
  }, [forms, part, item]);
  // "Previous" in the step navigation: back to the request form first.
  useEffect(() => {
    const element = form.current;
    if (!element) return;
    const back = (event: Event) => {
      if (at.current === "study") {
        event.preventDefault();
        setPart("request");
      }
    };
    element.addEventListener("wizard-previous", back);
    return () => element.removeEventListener("wizard-previous", back);
  }, [view]);
  if (!view || !forms) return <section className="panel form-panel" />;
  const shared = view.shared;
  const request = forms.request;
  const setRequest = (key: string, value: unknown) =>
    setForms({ ...forms, request: { ...request, [key]: value } });
  const setStudy = (key: string, value: string) =>
    setForms({ ...forms, study: { ...forms.study, [key]: value } });
  const own = (id: string) => forms.properties[id] || {};
  const setOwn = (id: string, key: string, value: unknown) =>
    setForms({
      ...forms,
      properties: {
        ...forms.properties,
        [id]: { ...own(id), [key]: value },
      },
    });
  const text = (value: unknown) => String(value ?? "");
  // A value entered here.
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
  // A value the booklet already holds.
  const given = (label: string, value: unknown) => (
    <div className="form-given">
      <span className="label-text">{label}</span>
      <span className="given-value">
        {text(value) || <em>{t("notInBooklet")}</em>}
      </span>
      <small>
        <BookOpen size={12} />
        {t("fromBooklet")}
      </small>
    </div>
  );
  const choice = (
    name: string,
    options: [string, string][],
    value: unknown,
    change: (value: string) => void,
  ) => (
    <div className="segmented form-choice" role="radiogroup">
      {options.map(([key, label]) => (
        <button
          type="button"
          key={key}
          role="radio"
          aria-checked={value === key}
          className={value === key ? "selected" : ""}
          onClick={() => change(value === key ? "" : key)}
          data-name={name}
        >
          {value === key && <Check size={14} />}
          {label}
        </button>
      ))}
    </div>
  );
  const yesNo = (
    label: string,
    value: Disclosure | undefined,
    change: (value: Disclosure) => void,
  ) => (
    <div className="form-question">
      <span className="label-text">{label}</span>
      {choice(
        label,
        [
          ["no", t("no")],
          ["yes", t("yes")],
        ],
        value?.answer || "",
        (answer) => change({ answer: answer as Yes, text: value?.text || "" }),
      )}
      {value?.answer === "yes" && (
        <input
          aria-label={t("mention")}
          placeholder={t("mention")}
          value={value.text || ""}
          onChange={(e) => change({ answer: "yes", text: e.target.value })}
        />
      )}
    </div>
  );
  const missingOf = (which: Part) =>
    view.missing.filter((m) => m.form === which).length;
  const auctionType = text(shared.request.method);
  const methods: Record<string, string> = {
    electronic: t("electronic"),
    physical: t("physical"),
    hybrid: t("hybrid"),
  };
  const save = (then: () => void) =>
    void run(async () => {
      const saved = await api<View>(`/projects/${detail.project.id}/forms`, {
        method: "PUT",
        body: send(forms),
      });
      setView(saved);
      setForms(saved.forms);
      then();
    }, t("saved"));
  const property = (id: string) => shared.properties[id] || {};
  const name = (id: string) =>
    detail.items.find((i) => i.id === id)?.title || "";
  return (
    <form
      ref={form}
      className="panel form-panel booklet-pages forms-step"
      data-stage-form
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        if (part === "request")
          save(() => {
            onSaved(false);
            setPart("study");
          });
        else save(() => onSaved(true));
      }}
    >
      <h2>{t("title")}</h2>
      <p className="muted">{t("help")}</p>
      <ol className="page-parts" aria-label={t("title")}>
        {PARTS.map((key) => (
          <li key={key}>
            <button
              type="button"
              aria-current={part === key ? "step" : undefined}
              className={part === key ? "selected" : ""}
              onClick={() => setPart(key)}
            >
              <span>{t(key + "Body")}</span>
              {t(key)}
            </button>
          </li>
        ))}
      </ol>
      <p className={missingOf(part) ? "notice" : "notice success"}>
        {missingOf(part)
          ? t("missing", { count: missingOf(part) })
          : t("complete")}
      </p>
      {view.overflow.length > 0 && (
        <p className="notice error">{t("overflow")}</p>
      )}

      {part === "request" && (
        <div className="page-part">
          <details open>
            <summary>{t("establishment")}</summary>
            <div className="form-grid">
              {given(t("org_name"), shared.request.org_name)}
              {field(
                t("request_date"),
                request.date,
                (v) => setRequest("date", v || null),
                { type: "date", dir: "ltr" },
              )}
              {field(
                t("cr_number"),
                request.cr_number,
                (v) => setRequest("cr_number", v),
                { dir: "ltr", inputMode: "numeric" },
              )}
              {field(
                t("unified_number"),
                request.unified_number,
                (v) => setRequest("unified_number", v),
                { dir: "ltr", inputMode: "numeric" },
              )}
              {field(
                t("fal_license"),
                request.fal_license,
                (v) => setRequest("fal_license", v),
                {
                  dir: "ltr",
                  placeholder: shared.request.fal_license || undefined,
                },
              )}
            </div>
          </details>
          {(["manager", "crier"] as const).map((who) => (
            <details open key={who}>
              <summary>{t(who)}</summary>
              <div className="form-grid">
                {field(t("person_name"), request[`${who}_name`], (v) =>
                  setRequest(`${who}_name`, v),
                )}
                {field(
                  t("person_id"),
                  request[`${who}_id`],
                  (v) => setRequest(`${who}_id`, v),
                  { dir: "ltr", inputMode: "numeric" },
                )}
                {field(
                  t("person_mobile"),
                  request[`${who}_mobile`],
                  (v) => setRequest(`${who}_mobile`, v),
                  { dir: "ltr", type: "tel" },
                )}
                {field(
                  t("person_email"),
                  request[`${who}_email`],
                  (v) => setRequest(`${who}_email`, v),
                  { dir: "ltr", type: "email" },
                )}
              </div>
            </details>
          ))}
          <details open>
            <summary>{t("auction")}</summary>
            <div className="form-grid">
              {given(t("auction_name"), shared.request.auction_name)}
              {given(t("properties_count"), shared.request.properties_count)}
              {given(t("method"), methods[auctionType])}
              {auctionType !== "physical" &&
                given(t("platform_name"), shared.request.platform_name)}
              {given(t("city"), shared.request.city)}
              {auctionType !== "electronic" &&
                given(t("venue"), shared.request.venue)}
              {given(t("start"), shared.request.start)}
              {given(t("end"), shared.request.end)}
              {given(t("start_time"), shared.request.start_time)}
              {field(
                t("units_count"),
                request.units_count,
                (v) => setRequest("units_count", v),
                { inputMode: "numeric" },
              )}
              {field(
                t("stream_link"),
                request.stream_link,
                (v) => setRequest("stream_link", v),
                { dir: "ltr", type: "url" },
              )}
              {field(
                t("contract_number"),
                request.contract_number,
                (v) => setRequest("contract_number", v),
                { dir: "ltr" },
              )}
            </div>
          </details>
          <details open>
            <summary>{t("money")}</summary>
            {(["receive", "refund"] as const).map((key) => (
              <div className="form-question" key={key}>
                <span className="label-text">{t(key)}</span>
                {choice(
                  key,
                  [
                    ["transfer", t("transfer")],
                    ["cheque", t("cheque")],
                    ["other", t("other")],
                  ],
                  request[key],
                  (v) => setRequest(key, v),
                )}
                {request[key] === "other" && (
                  <input
                    aria-label={t("other_how")}
                    placeholder={t("other_how")}
                    value={text(request[`${key}_other`])}
                    onChange={(e) => setRequest(`${key}_other`, e.target.value)}
                  />
                )}
              </div>
            ))}
            <div className="form-grid">
              {field(t("keeping"), request.keeping, (v) =>
                setRequest("keeping", v),
              )}
              {field(
                t("receive_days"),
                request.receive_days,
                (v) => setRequest("receive_days", v),
                { inputMode: "numeric" },
              )}
              {field(
                t("refund_days"),
                request.refund_days,
                (v) => setRequest("refund_days", v),
                { inputMode: "numeric", placeholder: t("refund_days_hint") },
              )}
              {field(
                t("award_minutes"),
                request.award_minutes,
                (v) => setRequest("award_minutes", v),
                { placeholder: t("award_hint") },
              )}
            </div>
            <div className="form-question">
              <span className="label-text">{t("entry_type")}</span>
              {choice(
                "entry_type",
                [
                  ["deposit", t("deposit")],
                  ["advance", t("advance")],
                  ["refundable", t("refundable")],
                  ["none", t("none")],
                ],
                request.entry_type,
                (v) => setRequest("entry_type", v),
              )}
            </div>
            <div className="form-question">
              <span className="label-text">{t("disposal")}</span>
              {choice(
                "disposal",
                [
                  ["sale", t("sale")],
                  ["lease", t("lease")],
                ],
                request.disposal,
                (v) => setRequest("disposal", v),
              )}
            </div>
          </details>
          <details open>
            <summary>{t("rights_title")}</summary>
            <div className="form-question">
              <span className="label-text">{t("rulings")}</span>
              <div className="segmented form-choice">
                {(
                  [
                    "none",
                    "preemption",
                    "session",
                    "condition",
                    "deposit_sale",
                    "other",
                  ] as const
                ).map((key) => {
                  const on = (request.rulings || []).includes(key);
                  return (
                    <button
                      type="button"
                      key={key}
                      role="checkbox"
                      aria-checked={on}
                      className={on ? "selected" : ""}
                      onClick={() => {
                        const now = request.rulings || [];
                        // "None" stands alone.
                        setRequest(
                          "rulings",
                          on
                            ? now.filter((k) => k !== key)
                            : key === "none"
                              ? ["none"]
                              : [...now.filter((k) => k !== "none"), key],
                        );
                      }}
                    >
                      {on && <Check size={14} />}
                      {t("ruling_" + key)}
                    </button>
                  );
                })}
              </div>
              {(request.rulings || []).includes("other") && (
                <input
                  aria-label={t("mention")}
                  placeholder={t("mention")}
                  value={text(request.rulings_other)}
                  onChange={(e) => setRequest("rulings_other", e.target.value)}
                />
              )}
            </div>
            <div className="form-question">
              <span className="label-text">{t("ownership")}</span>
              {choice(
                "ownership",
                [
                  ["full", "100%"],
                  ["other", t("other")],
                ],
                request.ownership,
                (v) => setRequest("ownership", v),
              )}
              {request.ownership === "other" && (
                <input
                  aria-label={t("mention")}
                  placeholder={t("mention")}
                  value={text(request.ownership_other)}
                  onChange={(e) =>
                    setRequest("ownership_other", e.target.value)
                  }
                />
              )}
            </div>
            {(
              [
                "rights",
                "dispute",
                "value_info",
                "offplan",
                "contribution",
              ] as const
            ).map((key) => (
              <React.Fragment key={key}>
                {yesNo(t(key), request[key] as Disclosure, (v) =>
                  setRequest(key, v),
                )}
              </React.Fragment>
            ))}
          </details>
          <details open>
            <summary>{t("properties")}</summary>
            <p className="muted">{t("propertiesHelp")}</p>
            {detail.items.map((i, n) => {
              const p = property(i.id);
              const mine = own(i.id);
              return (
                <fieldset key={i.id} className="form-property">
                  <legend>
                    {n + 1}. {i.title}
                  </legend>
                  <div className="form-grid">
                    {given(t("deed"), p.deed)}
                    {given(t("area"), p.area)}
                    {given(t("property_type"), p.property_type)}
                    {given(t("usage"), p.usage)}
                    {given(t("entry_amount"), p.entry_amount)}
                    {field(t("owner"), mine.owner, (v) =>
                      setOwn(i.id, "owner", v),
                    )}
                    {field(t("age"), mine.age, (v) => setOwn(i.id, "age", v), {
                      placeholder: t("age_hint"),
                    })}
                    <label>
                      <span className="label-text">{t("status")}</span>
                      <select
                        value={text(mine.status)}
                        onChange={(e) => setOwn(i.id, "status", e.target.value)}
                      >
                        <option value="">—</option>
                        {[
                          "free",
                          "seized",
                          "mortgaged",
                          "stopped",
                          "other",
                        ].map((key) => (
                          <option key={key} value={key}>
                            {t("status_" + key)}
                          </option>
                        ))}
                      </select>
                    </label>
                    {mine.status === "other" &&
                      field(t("status_other"), mine.status_other, (v) =>
                        setOwn(i.id, "status_other", v),
                      )}
                    {field(
                      t("min_price"),
                      mine.min_price,
                      (v) => setOwn(i.id, "min_price", v),
                      { inputMode: "decimal", dir: "ltr" },
                    )}
                    {field(
                      t("estimated_value"),
                      mine.estimated_value,
                      (v) => setOwn(i.id, "estimated_value", v),
                      { inputMode: "decimal", dir: "ltr" },
                    )}
                    {field(
                      t("disclosure"),
                      mine.disclosure,
                      (v) => setOwn(i.id, "disclosure", v),
                      { placeholder: t("disclosure_hint") },
                    )}
                    {field(t("agent_name"), mine.agent_name, (v) =>
                      setOwn(i.id, "agent_name", v),
                    )}
                    {field(
                      t("agency_number"),
                      mine.agency_number,
                      (v) => setOwn(i.id, "agency_number", v),
                      { dir: "ltr" },
                    )}
                  </div>
                </fieldset>
              );
            })}
          </details>
          <details open>
            <summary>{t("declaration")}</summary>
            <div className="form-grid">
              {field(t("declarant"), request.declarant, (v) =>
                setRequest("declarant", v),
              )}
            </div>
          </details>
        </div>
      )}

      {part === "study" && (
        <div className="page-part">
          <details open>
            <summary>{t("study_basics")}</summary>
            <div className="form-grid">
              {field(
                t("project_name"),
                forms.study.project_name,
                (v) => setStudy("project_name", v),
                { placeholder: shared.request.auction_name || undefined },
              )}
              <label>
                <span className="label-text">{t("category")}</span>
                <select
                  value={forms.study.category || ""}
                  onChange={(e) => setStudy("category", e.target.value)}
                >
                  <option value="">—</option>
                  {["أ", "ب", "ج", "د"].map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </label>
              {field(t("project_manager"), forms.study.manager, (v) =>
                setStudy("manager", v),
              )}
            </div>
          </details>
          <label>
            <span className="label-text">{t("study_property")}</span>
            <select value={item} onChange={(e) => setItem(e.target.value)}>
              {detail.items.map((i, n) => (
                <option key={i.id} value={i.id}>
                  {n + 1}. {i.title}
                  {view.missing.some(
                    (m) => m.form === "study" && m.item === i.id,
                  )
                    ? ` · ${t("incomplete")}`
                    : ` · ${t("done")}`}
                </option>
              ))}
            </select>
          </label>
          {item && (
            <StudyProperty
              key={item}
              name={name(item)}
              shared={property(item)}
              mine={own(item)}
              sections={view.sections}
              set={(key, value) => setOwn(item, key, value)}
            />
          )}
        </div>
      )}
    </form>
  );
}

function StudyProperty({
  name,
  shared,
  mine,
  sections,
  set,
}: {
  name: string;
  shared: Record<string, string>;
  mine: PropertyForms;
  sections: View["sections"];
  set: (key: string, value: unknown) => void;
}) {
  const t = useTranslations("forms");
  const answers = mine.answers || {};
  const setAnswer = (key: string, value: Partial<Answer>) =>
    set("answers", {
      ...answers,
      [key]: {
        answer: value.answer ?? answers[key]?.answer ?? "",
        note: value.note ?? answers[key]?.note ?? "",
      },
    });
  const text = (value: unknown) => String(value ?? "");
  return (
    <>
      <details open>
        <summary>
          1. {t("location_section")} · {name}
        </summary>
        <div className="form-grid">
          {[
            ["deed", shared.deed],
            ["location_link", shared.location_link],
            ["area", shared.area],
            ["property_type", shared.property_type],
            ["city", shared.city],
          ].map(([key, value]) => (
            <div className="form-given" key={key}>
              <span className="label-text">{t(key)}</span>
              <span className="given-value" dir="auto">
                {value || <em>{t("notInBooklet")}</em>}
              </span>
              <small>
                <BookOpen size={12} />
                {t("fromBooklet")}
              </small>
            </div>
          ))}
        </div>
        <label>
          <span className="label-text">{t("location_note")}</span>
          <textarea
            rows={3}
            value={text(mine.location_note)}
            onChange={(e) => set("location_note", e.target.value)}
          />
        </label>
      </details>
      {sections.map((section) => (
        <details open key={section.number}>
          <summary>
            {section.number}. {section.title}
          </summary>
          <ol className="study-questions">
            {section.questions.map((q) => {
              const own = answers[q.key] || { answer: "", note: "" };
              // A property with rental contracts in the booklet is rented.
              const answer =
                own.answer || (q.key === "rented" ? shared.rented || "" : "");
              return (
                <li key={q.key}>
                  <span className="study-question">{q.text}</span>
                  <div className="segmented form-choice" role="radiogroup">
                    {(["yes", "no"] as const).map((key) => (
                      <button
                        type="button"
                        key={key}
                        role="radio"
                        aria-checked={answer === key}
                        aria-label={`${q.text}: ${t(key)}`}
                        className={answer === key ? "selected" : ""}
                        onClick={() =>
                          setAnswer(q.key, {
                            answer: own.answer === key ? "" : key,
                          })
                        }
                      >
                        {answer === key && <Check size={14} />}
                        {t(key)}
                      </button>
                    ))}
                  </div>
                  <input
                    aria-label={`${q.text}: ${t("note")}`}
                    placeholder={t("note")}
                    value={own.note}
                    onChange={(e) => setAnswer(q.key, { note: e.target.value })}
                  />
                </li>
              );
            })}
          </ol>
          {section.number === 4 && (
            <label>
              <span className="label-text">{t("age")}</span>
              <input
                value={text(mine.age)}
                placeholder={t("age_hint")}
                onChange={(e) => set("age", e.target.value)}
              />
              <small className="muted">{t("age_shared")}</small>
            </label>
          )}
        </details>
      ))}
      <details open>
        <summary>{t("study_values")}</summary>
        <div className="form-grid">
          <label>
            <span className="label-text">{t("estimated_price")}</span>
            <input
              dir="ltr"
              inputMode="decimal"
              value={text(mine.estimated_price)}
              onChange={(e) => set("estimated_price", e.target.value)}
            />
          </label>
          <label>
            <span className="label-text">{t("indicative_value")}</span>
            <input
              dir="ltr"
              inputMode="decimal"
              value={text(mine.indicative_value)}
              onChange={(e) => set("indicative_value", e.target.value)}
            />
          </label>
        </div>
        <label>
          <span className="label-text">{t("defects")}</span>
          <textarea
            rows={3}
            value={text(mine.defects)}
            onChange={(e) => set("defects", e.target.value)}
          />
        </label>
        <label>
          <span className="label-text">{t("features")}</span>
          <textarea
            rows={3}
            value={text(mine.features)}
            placeholder={shared.features || undefined}
            onChange={(e) => set("features", e.target.value)}
          />
          <small className="muted">{t("features_hint")}</small>
        </label>
      </details>
    </>
  );
}
