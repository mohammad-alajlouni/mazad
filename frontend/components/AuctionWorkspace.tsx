"use client";
import React, { useEffect, useRef, useState } from "react";
import { Plus, X } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { api, send, Detail, Item, Run } from "./api";
import { BookletPages } from "./BookletPages";
import { PageSettings, RentalContracts } from "./PropertySections";

type Values = Record<string, unknown>;
const auctionGroups = [
  [
    "auction_name",
    "license_number",
    "auction_contact_number",
    "supervising_authority",
  ],
  [
    "auction_date",
    "auction_start_date",
    "auction_end_date",
    "start_time",
    "end_time",
  ],
  [
    "physical_location",
    "electronic_platform_name",
    "electronic_platform_url",
    "auction_location_url",
    "booklet_url",
    "contact_url",
  ],
  ["legal_announcement_text", "court_decision_text"],
];
// Electronic auction platforms offered in the platform field (any other name
// may be typed in the same field).
const PLATFORMS = [
  "منصة إنفاذ للمزادات",
  "منصة سومتك للمزادات",
  "منصة مباشر للمزادات",
  "منصة السعودية للمزادات",
  "منصة وصلت للمزادات",
  "منصة الدال للمزادات",
];
// The property's statement (notes p.17): eight fields, two to a row: type and
// city, district and area, plan and plot, deed and participation amount.
const STATEMENT = [
  "property_type",
  "city",
  "district",
  "area",
  "plan_number",
  "plot_number",
  "deed_number",
  "participation_amount",
];
// Its links (the "other documents" link is no longer asked for) and the
// additional information.
const LINKS = [
  "survey_link",
  "rental_information_link",
  "additional_images_link",
  "location_link",
  "additional_information",
];
const rentalFields = [
  "unit_number",
  "property_type",
  "contract_status",
  "contract_start_date",
  "contract_end_date",
  "contract_duration",
  "paid_period",
  "next_due_date",
  "annual_rent_value",
];
// A field of the grid. One with further inputs of its own (the deeds) keeps
// them in its cell, outside the label so their buttons are not its control.
function FieldCell({
  more,
  children,
}: {
  more: React.ReactNode;
  children: React.ReactNode;
}) {
  if (!more) return <label>{children}</label>;
  return (
    <div className="field-with-more">
      <label>{children}</label>
      {more}
    </div>
  );
}
// Icons a nearby landmark may carry (booklet-art/landmarks), as the booklet
// prints them beside the landmark's name in the additional information.
const LANDMARK_ICONS = [
  "road",
  "hospital",
  "school",
  "mosque",
  "market",
  "park",
  "airport",
  "station",
  "bank",
  "government",
  "location",
  "city",
];
// Nearby landmarks (up to twelve): each an icon and a short name, added and
// removed one at a time.
function Landmarks({ initial }: { initial: { icon: string; text: string }[] }) {
  const t = useTranslations("auction");
  const [rows, setRows] = useState(
    initial.map((value, key) => ({ key, ...value })),
  );
  const [next, setNext] = useState(initial.length);
  const marker = useRef<HTMLSpanElement>(null);
  const change = (list: typeof rows) => {
    setRows(list);
    // A change by a button is no typed change: the preview reads the form again.
    setTimeout(() =>
      marker.current
        ?.closest("form")
        ?.dispatchEvent(new Event("preview-form", { bubbles: true })),
    );
  };
  return (
    <fieldset className="landmarks">
      <legend>{t("landmarks")}</legend>
      <span ref={marker} hidden />
      <p className="muted">{t("landmarksHelp")}</p>
      {rows.map((row, at) => (
        <div className="landmark-row" key={row.key}>
          <img
            src={`/api/booklet-assets/booklet-art/landmarks/${row.icon}.svg`}
            alt=""
          />
          <select
            name={`property.landmarks.${at}.icon`}
            aria-label={t("landmarkIcon", { number: at + 1 })}
            value={row.icon}
            onChange={(e) =>
              change(
                rows.map((r) =>
                  r.key === row.key ? { ...r, icon: e.target.value } : r,
                ),
              )
            }
          >
            {LANDMARK_ICONS.map((icon) => (
              <option key={icon} value={icon}>
                {t("landmark_" + icon)}
              </option>
            ))}
          </select>
          <input
            name={`property.landmarks.${at}.text`}
            aria-label={t("landmarkText", { number: at + 1 })}
            maxLength={60}
            defaultValue={row.text}
            autoFocus={!row.text && at === rows.length - 1}
            placeholder={t("landmarkPlaceholder")}
          />
          <button
            type="button"
            className="icon-button danger"
            title={t("removeLandmark")}
            aria-label={t("removeLandmark") + " " + (at + 1)}
            onClick={() => change(rows.filter((r) => r.key !== row.key))}
          >
            <X size={15} />
          </button>
        </div>
      ))}
      {rows.length < 12 && (
        <button
          type="button"
          className="text-button add-deed"
          onClick={() => {
            change([...rows, { key: next, icon: "road", text: "" }]);
            setNext(next + 1);
          }}
        >
          <Plus size={14} />
          {t("addLandmark")}
        </button>
      )}
    </fieldset>
  );
}
// Up to seven more deeds after the first: added one at a time, each named.
function MoreDeeds({
  initial,
  onCount,
}: {
  initial: string[];
  onCount: (count: number) => void;
}) {
  const t = useTranslations("auction");
  const [rows, setRows] = useState(
    initial.map((value, key) => ({ key, value })),
  );
  const [next, setNext] = useState(initial.length);
  const change = (list: typeof rows) => {
    setRows(list);
    onCount(list.length);
  };
  // Taking a deed away is no typed change: tell the live preview to read the
  // form again.
  const marker = useRef<HTMLSpanElement>(null);
  const shown = useRef(rows.length);
  useEffect(() => {
    if (shown.current === rows.length) return;
    shown.current = rows.length;
    marker.current
      ?.closest("form")
      ?.dispatchEvent(new Event("preview-form", { bubbles: true }));
  }, [rows.length]);
  // The deeds' own boundaries (DeedBoundaries) follow the deeds listed here.
  useEffect(() => {
    marker.current
      ?.closest("form")
      ?.dispatchEvent(new CustomEvent("deeds-changed", { detail: rows }));
  }, [rows]);
  return (
    <>
      <span ref={marker} hidden />
      {rows.map((row, at) => (
        <label key={row.key} className="more-deed">
          <span className="label-text">
            {t("deed_number_n", { number: at + 2 })}
          </span>
          <span className="more-deed-row">
            <input
              name="property.extra_deed_numbers"
              aria-label={t("deed_number_n", { number: at + 2 })}
              defaultValue={row.value}
              autoFocus={!row.value}
              onBlur={(e) =>
                setRows(
                  rows.map((r) =>
                    r.key === row.key ? { ...r, value: e.target.value } : r,
                  ),
                )
              }
            />
            <button
              type="button"
              className="icon-button danger"
              title={t("remove_deed")}
              aria-label={t("remove_deed") + " " + (at + 2)}
              onClick={() => change(rows.filter((r) => r.key !== row.key))}
            >
              <X size={15} />
            </button>
          </span>
        </label>
      ))}
      {rows.length < 7 && (
        <button
          type="button"
          className="text-button add-deed"
          onClick={() => {
            change([...rows, { key: next, value: "" }]);
            setNext(next + 1);
          }}
        >
          <Plus size={14} />
          {t("add_deed")}
        </button>
      )}
    </>
  );
}
type Deed = { key: number; value: string };
const SIDES = ["north", "south", "east", "west"];
// Boundaries for each further deed, when they differ from the first deed's:
// each deed then has its own box on the boundaries page. The deeds come from
// MoreDeeds (its "deeds-changed" event); a deed taken away takes its
// boundaries with it.
function DeedBoundaries({
  first,
  initialDeeds,
  initial,
  initialDiffer,
  children,
}: {
  first: string;
  initialDeeds: string[];
  initial: Values[];
  initialDiffer: boolean;
  children: React.ReactNode;
}) {
  const t = useTranslations("auction");
  const marker = useRef<HTMLSpanElement>(null);
  const [deeds, setDeeds] = useState<Deed[]>(
    initialDeeds.map((value, key) => ({ key, value })),
  );
  const [differ, setDiffer] = useState(initialDiffer);
  useEffect(() => {
    const form = marker.current?.closest("form");
    const listen = (e: Event) => setDeeds((e as CustomEvent<Deed[]>).detail);
    form?.addEventListener("deeds-changed", listen);
    return () => form?.removeEventListener("deeds-changed", listen);
  }, []);
  const several = deeds.length > 0;
  const on = several && differ;
  const title = (value: string, n: number) =>
    t("deedBoundariesOf", {
      deed: value.trim() || t("deed_number_n", { number: n }),
    });
  return (
    <>
      <span ref={marker} hidden />
      {several && (
        <label className="checkbox-label">
          <input
            type="checkbox"
            name="property.deeds_differ"
            value="true"
            checked={differ}
            onChange={(e) => {
              setDiffer(e.target.checked);
              setTimeout(() =>
                marker.current
                  ?.closest("form")
                  ?.dispatchEvent(new Event("preview-form", { bubbles: true })),
              );
            }}
          />
          {t("deedsDiffer")}
        </label>
      )}
      {on ? (
        <fieldset>
          <legend>{title(first, 1)}</legend>
          {children}
        </fieldset>
      ) : (
        children
      )}
      {deeds.map((deed, at) => (
        <fieldset key={deed.key} hidden={!on}>
          <legend>{title(deed.value, at + 2)}</legend>
          {SIDES.map((side) => (
            <Fields
              key={side}
              fields={[side + "_description", side + "_length"]}
              prefix={`deedb.${at}.`}
              values={initial[deed.key] || {}}
            />
          ))}
        </fieldset>
      ))}
    </>
  );
}
export function Fields({
  fields,
  prefix = "",
  values = {},
  defaults = {},
  requiredFields = [],
}: {
  fields: string[];
  prefix?: string;
  values?: Values;
  // Shown when a field has no value of its own (e.g. a calculated one).
  defaults?: Values;
  requiredFields?: string[];
}) {
  const t = useTranslations("auction");
  const v = useTranslations("validationFlow");
  const [invalid, setInvalid] = useState<Record<string, boolean>>({});
  const [deeds, setDeeds] = useState(
    ((values.extra_deed_numbers || []) as string[]).length,
  );
  // Several deeds: each is named, the first included.
  const labelOf = (key: string) =>
    prefix + key === "property.deed_number" && deeds > 0
      ? t("deed_number_n", { number: 1 })
      : t(key);
  return (
    <div
      className="form-grid"
      onInvalidCapture={(e) => {
        const target = e.target as HTMLInputElement;
        setInvalid((current) => ({ ...current, [target.name]: true }));
        let node = target.parentElement;
        while (node) {
          if (node instanceof HTMLDetailsElement) node.open = true;
          node = node.parentElement;
        }
      }}
      onInputCapture={(e) => {
        const target = e.target as HTMLInputElement;
        if (target.required && !target.value.trim())
          target.setCustomValidity(v("required"));
        setInvalid((current) => ({ ...current, [target.name]: false }));
      }}
    >
      {fields.map((key) => (
        <FieldCell
          key={key}
          more={
            prefix + key === "property.deed_number" ? (
              <MoreDeeds
                initial={(values.extra_deed_numbers || []) as string[]}
                onCount={setDeeds}
              />
            ) : null
          }
        >
          <span className="label-text">
            {labelOf(key)}
            {requiredFields.includes(key) && <b aria-hidden="true"> *</b>}
          </span>
          {key.endsWith("_text") ||
          key.endsWith("_description") ||
          [
            "description",
            "additional_information",
            "contact_information",
            "social_accounts",
            "supervisor_social",
          ].includes(key) ? (
            <textarea
              rows={4}
              name={prefix + key}
              aria-label={labelOf(key)}
              required={requiredFields.includes(key)}
              onBlur={(e) => {
                if (
                  requiredFields.includes(key) &&
                  !e.currentTarget.value.trim()
                )
                  setInvalid((current) => ({
                    ...current,
                    [prefix + key]: true,
                  }));
              }}
              defaultValue={String(values[key] || defaults[key] || "")}
            />
          ) : (
            <input
              name={prefix + key}
              aria-label={labelOf(key)}
              list={
                key === "electronic_platform_name" ? "platforms" : undefined
              }
              required={requiredFields.includes(key)}
              onBlur={(e) => {
                if (
                  requiredFields.includes(key) &&
                  !e.currentTarget.value.trim()
                )
                  setInvalid((current) => ({
                    ...current,
                    [prefix + key]: true,
                  }));
              }}
              defaultValue={String(values[key] || defaults[key] || "")}
              type={
                key.endsWith("_date")
                  ? "date"
                  : key.endsWith("_time")
                    ? "time"
                    : key.endsWith("_url") ||
                        key.endsWith("_link") ||
                        key === "website"
                      ? "url"
                      : [
                            "area",
                            "participation_amount",
                            "annual_rent_value",
                            "close_interval_minutes",
                          ].includes(key)
                        ? "number"
                        : "text"
              }
              min={
                key === "area" && requiredFields.includes(key) ? "0.0001" : "0"
              }
              step={key === "close_interval_minutes" ? "1" : "any"}
            />
          )}
          {invalid[prefix + key] && (
            <small className="field-error">{v("required")}</small>
          )}
          {key === "electronic_platform_name" && (
            // The known platforms to choose from; any other may be typed.
            <datalist id="platforms">
              {PLATFORMS.map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
          )}
        </FieldCell>
      ))}
    </div>
  );
}
export function readProperty(form: FormData) {
  const values: Values = {};
  const boundaries: Values = {};
  const rentals: Record<string, Values> = {};
  for (const [key, v] of form.entries()) {
    if (key.startsWith("property.")) values[key.slice(9)] = String(v);
    if (key.startsWith("boundary.")) boundaries[key.slice(9)] = String(v);
    if (key.startsWith("rental.")) {
      const [, index, field] = key.split(".");
      (rentals[index] ||= {})[field] = String(v);
    }
  }
  // Further deeds of the property (up to three after the first).
  values.extra_deed_numbers = form
    .getAll("property.extra_deed_numbers")
    .map((v) => String(v).trim())
    .filter(Boolean);
  // Nearby landmarks, in the order they are listed.
  const landmarks: Record<string, Values> = {};
  for (const [key, v] of form.entries()) {
    const found = key.match(/^property\.landmarks\.(\d+)\.(icon|text)$/);
    if (found) (landmarks[found[1]] ||= {})[found[2]] = String(v);
  }
  for (const key of Object.keys(values))
    if (key.startsWith("landmarks.")) delete values[key];
  values.landmarks = Object.keys(landmarks)
    .sort((a, b) => Number(a) - Number(b))
    .map((at) => landmarks[at])
    .filter((m) => String(m.text || "").trim());
  values.features = String(form.get("property.features") || "")
    .split("\n")
    .filter((v) => v.trim());
  values.boundaries = boundaries;
  // Each further deed's boundaries, in the deeds' order.
  const deedBoundaries: Record<string, Values> = {};
  for (const [key, v] of form.entries()) {
    const found = key.match(/^deedb\.(\d+)\.(\w+)$/);
    if (found) (deedBoundaries[found[1]] ||= {})[found[2]] = String(v);
  }
  // An empty deed is dropped (as the server drops it): its boundaries too.
  values.deed_boundaries = form
    .getAll("property.extra_deed_numbers")
    .map((deed, at) => [String(deed).trim(), deedBoundaries[at] || {}] as const)
    .filter(([deed]) => deed)
    .map(([, own]) => own);
  values.deeds_differ = form.get("property.deeds_differ") === "true";
  values.rental_contracts = Object.values(rentals).filter((row) =>
    Object.values(row).some((value) => String(value).trim()),
  );
  // The optional pages in the author's order.
  delete values.page_order;
  const order = form.getAll("property.page_order").map(String);
  if (order.length) values.page_order = order;
  for (const field of [
    "include_information_page",
    "include_images_page",
    "include_rentals_page",
    "include_features_page",
    "include_boundaries_page",
  ]) {
    if (form.has(`booklet.${field}`))
      values[field] = form.get(`booklet.${field}`) === "true";
  }
  return values;
}
export function PropertyFields({
  existing,
  template,
  requiredFields = [],
  auctionType = "physical",
  closing,
  children,
  featurePhotos,
}: {
  // The property's share of the closing schedule (date, time).
  closing?: [string, string];
  existing?: Item;
  // Starting values for a new property (e.g. copied from a similar one).
  template?: Values;
  requiredFields?: string[];
  auctionType?: string;
  // The description, in the property's details (as on its page).
  children?: React.ReactNode;
  // The features' own photographs, entered with the features.
  featurePhotos?: React.ReactNode;
}) {
  const t = useTranslations("auction");
  const prop = existing?.property_data || template || {};
  const fields = (keys: string[], open = false) => (
    <Fields
      fields={keys}
      prefix="property."
      values={prop}
      defaults={
        open && closing
          ? { auction_close_date: closing[0], auction_close_time: closing[1] }
          : undefined
      }
      requiredFields={requiredFields}
    />
  );
  // The order of the notes on the data entry (p.17-18): each section as the
  // booklet uses it, the photographs last (in the property's form).
  return (
    <>
      <details open>
        <summary>{t("section_statement")}</summary>
        {fields(STATEMENT)}
      </details>
      <details open>
        <summary>{t("property_details")}</summary>
        {auctionType !== "physical" && (
          <>
            {fields(["auction_close_date", "auction_close_time"], true)}
            <p className="muted">{t("closingAutoHelp")}</p>
          </>
        )}
        {children}
        {fields(["usage", "execution_request_number"])}
      </details>
      <details>
        <summary>{t("boundaries")}</summary>
        <DeedBoundaries
          first={String(prop.deed_number || "")}
          initialDeeds={(prop.extra_deed_numbers || []) as string[]}
          initial={(prop.deed_boundaries || []) as Values[]}
          initialDiffer={Boolean(prop.deeds_differ)}
        >
          {SIDES.map((side) => (
            <Fields
              key={side}
              fields={[side + "_description", side + "_length"]}
              prefix="boundary."
              values={(prop.boundaries || {}) as Values}
            />
          ))}
        </DeedBoundaries>
      </details>
      <details>
        <summary>{t("property_links")}</summary>
        {fields(LINKS)}
        <Landmarks
          initial={(prop.landmarks || []) as { icon: string; text: string }[]}
        />
      </details>
      <details>
        <summary>{t("section_features")}</summary>
        <label>
          {t("one_per_line")}
          <textarea
            name="property.features"
            rows={5}
            defaultValue={((prop.features || []) as string[]).join("\n")}
          />
        </label>
        {featurePhotos}
      </details>
      <details>
        <summary>{t("section_rentals")}</summary>
        <RentalContracts
          initial={(prop.rental_contracts || []) as Values[]}
          summaryFields={["unit_number", "property_type", "annual_rent_value"]}
          renderFields={(prefix, values) => (
            <Fields fields={rentalFields} prefix={prefix} values={values} />
          )}
        />
      </details>
      <details>
        <summary>{t("booklet_pages")}</summary>
        <label>
          {t("booklet_layout")}
          <select
            name="property.booklet_layout"
            defaultValue={String(prop.booklet_layout || "auto")}
          >
            {["auto", "landscape", "portrait"].map((value) => (
              <option key={value} value={value}>
                {t(`layout_${value}`)}
              </option>
            ))}
          </select>
        </label>
        <PageSettings prop={prop} />
      </details>
    </>
  );
}
export function AuctionWorkspace({
  detail,
  run,
  reload,
  section = "auction",
  bannerMode = false,
  socialMode = false,
  onSaved,
  onPage,
}: {
  detail: Detail;
  run: Run;
  reload: () => Promise<void>;
  section?: "auction" | "agent" | "closing";
  bannerMode?: boolean;
  socialMode?: boolean;
  onSaved?: () => void;
  onPage?: (index: number, count: number) => void;
}) {
  // Booklet flows are entered page by page in the booklet's order.
  if (
    !bannerMode &&
    !socialMode &&
    (section === "auction" || section === "closing") &&
    detail.workflow?.rules.closing_fields?.length
  )
    return (
      <div className="auction-workspace">
        <BookletPages
          detail={detail}
          run={run}
          reload={reload}
          section={section}
          onSaved={onSaved}
          onPage={onPage}
        />
      </div>
    );
  return (
    <LegacyAuctionForm
      detail={detail}
      run={run}
      reload={reload}
      section={section === "closing" ? "auction" : section}
      bannerMode={bannerMode}
      socialMode={socialMode}
      onSaved={onSaved}
    />
  );
}
function LegacyAuctionForm({
  detail,
  run,
  reload,
  section = "auction",
  bannerMode = false,
  socialMode = false,
  onSaved,
}: {
  detail: Detail;
  run: Run;
  reload: () => Promise<void>;
  section?: "auction" | "agent";
  bannerMode?: boolean;
  socialMode?: boolean;
  onSaved?: () => void;
}) {
  const t = useTranslations("auction");
  const bt = useTranslations(socialMode ? "social" : "banner");
  const auction = detail.project.auction || {};
  const [kind, setKind] = useState(String(auction.auction_type || "physical"));
  const [draft, setDraft] = useState<Values>({});
  const rules = detail.workflow?.rules;
  const fieldRules = rules?.auction[kind];
  const locale = useLocale();
  const f = useTranslations("flow");
  const [covers, setCovers] = useState<
    { id: string; name_ar: string; name_en: string; thumbnail: string }[]
  >([]);
  const [cover, setCover] = useState(
    String(auction.selected_cover_template_id || "infath-2"),
  );
  useEffect(() => {
    if (section === "auction" && !bannerMode)
      void run(async () => setCovers(await api("/booklet-templates")));
  }, []);
  return (
    <div className="auction-workspace">
      {section === "auction" && (
        <form
          data-stage-form
          data-preview-form={section}
          className="panel form-panel"
          onChange={(event) => {
            const form = event.currentTarget;
            setDraft(Object.fromEntries(new FormData(form)));
          }}
          onSubmit={(event) => {
            event.preventDefault();
            const values = Object.fromEntries(
              new FormData(event.currentTarget),
            );
            delete values["cover-choice"];
            void run(async () => {
              await api(`/projects/${detail.project.id}`, {
                method: "PUT",
                body: send({
                  ...detail.project,
                  auction: { ...values, selected_cover_template_id: cover },
                }),
              });
              await reload();
              onSaved?.();
            }, t("saved"));
          }}
        >
          <h2>{t("auction_setup")}</h2>
          <p className="muted">
            {bannerMode ? bt("auctionHelp") : t("setup_help")}
          </p>
          <label>
            {t("auction_type")}
            <select
              name="auction_type"
              value={kind}
              onChange={(e) => setKind(e.target.value)}
            >
              {["physical", "electronic", "hybrid"].map((k) => (
                <option key={k} value={k}>
                  {t(k)}
                </option>
              ))}
            </select>
          </label>
          <p className="notice">{f("typeHelp_" + kind)}</p>
          {auctionGroups.map((fields, index) => (
            <details
              key={index}
              open={
                bannerMode ||
                index < 3 ||
                fields.some((key) => fieldRules?.required.includes(key))
              }
            >
              <summary>
                {t(
                  [
                    "auction_information",
                    "schedule",
                    "location_links",
                    "legal_information",
                  ][index],
                )}
              </summary>
              <Fields
                fields={fields.filter(
                  (key) => !fieldRules || fieldRules.visible.includes(key),
                )}
                values={{ ...auction, ...draft }}
                requiredFields={fieldRules?.required}
              />
            </details>
          ))}
          <label>
            {t("document_language")}
            <select
              name="document_language"
              defaultValue={String(auction.document_language || "ar")}
            >
              <option value="ar">العربية</option>
              <option value="en">English</option>
            </select>
          </label>
          {!bannerMode && (
            <label>
              {t("booklet_edition")}
              <select
                name="booklet_edition"
                defaultValue={String(auction.booklet_edition || "print")}
              >
                <option value="print">{t("booklet_edition_print")}</option>
                <option value="digital">{t("booklet_edition_digital")}</option>
              </select>
            </label>
          )}
          {!bannerMode && (
            <>
              <h3>{t("select_cover")}</h3>
              <div className="cover-options">
                {covers.map((c) => (
                  <label
                    key={c.id}
                    className={
                      cover === c.id ? "cover-option selected" : "cover-option"
                    }
                  >
                    <input
                      type="radio"
                      name="cover-choice"
                      value={c.id}
                      checked={cover === c.id}
                      onChange={() => setCover(c.id)}
                    />
                    <img
                      src={c.thumbnail}
                      alt={t("cover", { number: c.id.slice(-1) })}
                    />
                    <span>{locale === "ar" ? c.name_ar : c.name_en}</span>
                  </label>
                ))}
              </div>
            </>
          )}
          <button className="primary">
            {bannerMode ? f("saveAuctionOnly") : t("save_auction")}
          </button>
        </form>
      )}
    </div>
  );
}
type Review = {
  valid: boolean;
  property_count: number;
  errors: { field: string; code: string }[];
  warnings: { field: string; code: string }[];
  properties: Values[];
  auction: Values;
  selling_agent: Values;
};
export function AuctionReview({
  detail,
  run,
  onValid,
  onFix,
}: {
  detail: Detail;
  run: Run;
  onValid: (value: boolean) => void;
  onFix?: (step: string) => void;
}) {
  const t = useTranslations("auction");
  const f = useTranslations("flow");
  const [review, setReview] = useState<Review | null>(null);
  useEffect(() => {
    onValid(false);
    void run(async () => {
      const value = await api<Review>(`/projects/${detail.project.id}/review`);
      setReview(value);
      onValid(value.valid);
    });
  }, [detail]);
  if (!review) return <p>{t("checking")}</p>;
  const fieldLabel = (field: string) => {
    const parts = field.split(".");
    const key = parts.at(-1)!;
    const label = t.has(key)
      ? t(key)
      : key === "properties"
        ? f("properties")
        : key;
    return parts[0] === "properties" && parts.length > 1
      ? f("propertyNumber", { number: parts[1] }) + " · " + label
      : label;
  };

  return (
    <section className="auction-review">
      <h2>{t("review")}</h2>
      {/* The same facts as before, laid out as summary tiles. */}
      <div className="review-tiles">
        <div>
          <small>{t("auction_name")}</small>
          <strong>{String(review.auction.auction_name || "-")}</strong>
        </div>
        <div>
          <small>{t("auction_type")}</small>
          <strong>
            {t(String(review.auction.auction_type || "physical"))} ·{" "}
            {String(review.selling_agent.name || "-")}
          </strong>
        </div>
        <div>
          <small>{t("schedule")}</small>
          <strong>
            <bdi dir="ltr">
              {String(
                review.auction.auction_date ||
                  review.auction.auction_start_date ||
                  "-",
              )}
            </bdi>{" "}
            · <bdi dir="ltr">{String(review.auction.start_time || "-")}</bdi>
          </strong>
        </div>
        <div>
          <small>{t("location_links")}</small>
          <strong>
            {String(
              review.auction.physical_location ||
                review.auction.electronic_platform_name ||
                "-",
            )}
          </strong>
        </div>
      </div>
      <p>{t("property_count", { count: review.property_count })}</p>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {[
                "sequence_number",
                "property_type",
                "city",
                "district",
                "area",
                "deed_number",
                "plan_number",
                "plot_number",
                "additional_image_count",
              ].map((key) => (
                <th key={key}>{t(key)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {review.properties.map((p) => (
              <tr key={String(p.id)}>
                {[
                  "sequence_number",
                  "property_type",
                  "city",
                  "district",
                  "area",
                  "deed_number",
                  "plan_number",
                  "plot_number",
                  "additional_image_count",
                ].map((key) => (
                  <td key={key}>{String(p[key] ?? "-") || "-"}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted">{f("requiredLegend")}</p>
      {review.errors.map((e, i) => (
        <p className="error" key={i}>
          {t(e.code)}: {fieldLabel(e.field)}
          {onFix && (
            <button
              className="text-button"
              onClick={() =>
                onFix(
                  e.field.startsWith("selling_agent")
                    ? "agent"
                    : e.field.startsWith("properties")
                      ? "items"
                      : "auction",
                )
              }
            >
              {f(
                e.field.startsWith("selling_agent")
                  ? "fixAgent"
                  : e.field.startsWith("properties")
                    ? "fixProperties"
                    : "fixAuction",
              )}
            </button>
          )}
        </p>
      ))}
      <details>
        <summary>{t("warnings", { count: review.warnings.length })}</summary>
        {review.warnings.map((w, i) => (
          <p key={i}>
            {t(w.code)}: {fieldLabel(w.field)}
          </p>
        ))}
      </details>
      {review.valid && <p className="notice success ready">{t("ready")}</p>}
    </section>
  );
}
