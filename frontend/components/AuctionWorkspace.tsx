"use client";
import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import FileInput from "./FileInput";
import { api, send, Detail, Item, Run } from "./api";

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
const propertyGroups = [
  [
    "property_type",
    "city",
    "district",
    "usage",
    "area",
    "deed_number",
    "plan_number",
    "plot_number",
    "execution_request_number",
    "participation_amount",
  ],
  [
    "auction_close_date",
    "auction_close_time",
    "survey_link",
    "rental_information_link",
    "additional_images_link",
    "location_link",
    "other_document_link",
    "additional_information",
  ],
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
function Fields({
  fields,
  prefix = "",
  values = {},
  requiredFields = [],
}: {
  fields: string[];
  prefix?: string;
  values?: Values;
  requiredFields?: string[];
}) {
  const t = useTranslations("auction");
  const v = useTranslations("validationFlow");
  const [invalid, setInvalid] = useState<Record<string, boolean>>({});
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
        <label key={key}>
          {t(key)}
          {requiredFields.includes(key) && <span aria-hidden="true"> *</span>}
          {key.endsWith("_text") ||
          key.endsWith("_description") ||
          [
            "description",
            "additional_information",
            "contact_information",
            "social_accounts",
          ].includes(key) ? (
            <textarea
              rows={4}
              name={prefix + key}
              aria-label={t(key)}
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
              defaultValue={String(values[key] ?? "")}
            />
          ) : (
            <input
              name={prefix + key}
              aria-label={t(key)}
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
              defaultValue={String(values[key] ?? "")}
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
                          ].includes(key)
                        ? "number"
                        : "text"
              }
              min={
                key === "area" && requiredFields.includes(key) ? "0.0001" : "0"
              }
              step="any"
            />
          )}
          {invalid[prefix + key] && (
            <small className="field-error">{v("required")}</small>
          )}
        </label>
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
  values.features = String(form.get("property.features") || "")
    .split("\n")
    .filter((v) => v.trim());
  values.boundaries = boundaries;
  values.rental_contracts = Object.values(rentals);
  return values;
}
export function PropertyFields({
  existing,
  requiredFields = [],
  auctionType = "physical",
}: {
  existing?: Item;
  requiredFields?: string[];
  auctionType?: string;
}) {
  const t = useTranslations("auction");
  const prop = existing?.property_data || {};
  const [rentals, setRentals] = useState<{ key: number; data: Values }[]>(
    ((prop.rental_contracts || []) as Values[]).map((data, key) => ({
      key,
      data,
    })),
  );
  const [nextKey, setNextKey] = useState(rentals.length);
  return (
    <>
      {propertyGroups.map((fields, index) => (
        <details key={index} open={index === 0}>
          <summary>
            {t(index === 0 ? "property_details" : "property_links")}
          </summary>
          <Fields
            fields={fields.filter(
              (key) =>
                auctionType !== "physical" ||
                !["auction_close_date", "auction_close_time"].includes(key),
            )}
            prefix="property."
            values={prop}
            requiredFields={requiredFields}
          />
        </details>
      ))}
      <details>
        <summary>{t("features")}</summary>
        <label>
          {t("one_per_line")}
          <textarea
            name="property.features"
            rows={5}
            defaultValue={((prop.features || []) as string[]).join("\n")}
          />
        </label>
      </details>
      <details>
        <summary>{t("boundaries")}</summary>
        {["north", "south", "east", "west"].map((side) => (
          <Fields
            key={side}
            fields={[side + "_description", side + "_length"]}
            prefix="boundary."
            values={(prop.boundaries || {}) as Values}
          />
        ))}
      </details>
      <details>
        <summary>{t("rental_contracts")}</summary>
        {rentals.map((row, index) => (
          <fieldset key={row.key}>
            <legend>
              {t("rental_contracts")} {index + 1}
            </legend>
            <Fields
              fields={rentalFields}
              prefix={`rental.${row.key}.`}
              values={row.data}
            />
            <button
              type="button"
              className="text-button danger"
              onClick={() =>
                setRentals(rentals.filter((r) => r.key !== row.key))
              }
            >
              {t("remove")}
            </button>
          </fieldset>
        ))}
        <button
          type="button"
          className="secondary"
          onClick={() => {
            setRentals([...rentals, { key: nextKey, data: {} }]);
            setNextKey(nextKey + 1);
          }}
        >
          {t("add_rental")}
        </button>
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
  const [logoFile, setLogoFile] = useState<File | null>(null);
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
      {section === "agent" && (
        <form
          data-stage-form
          className="panel form-panel"
          onSubmit={(event) => {
            event.preventDefault();
            const values = Object.fromEntries(
              new FormData(event.currentTarget),
            );
            void run(async () => {
              if (logoFile) {
                const data = new FormData();
                data.append("file", logoFile);
                data.append("category", "agent_logo");
                const image = await api<{ id: string }>(
                  `/projects/${detail.project.id}/images`,
                  { method: "POST", body: data },
                );
                values.logo_image_id = image.id;
              }
              await api(`/projects/${detail.project.id}/selling-agent`, {
                method: "PUT",
                body: send(values),
              });
              await reload();
              onSaved?.();
            }, t("saved"));
          }}
        >
          <h2>{t("selling_agent")}</h2>
          <Fields
            fields={[
              "name",
              "description",
              "website",
              "phone",
              "whatsapp",
              "contact_information",
              "social_accounts",
            ]}
            values={detail.selling_agent || {}}
            requiredFields={rules?.agent_required}
          />
          <label>
            {t("agent_logo")}
            <select
              name="logo_image_id"
              required={rules?.agent_logo_required && !logoFile}
              defaultValue={String(detail.selling_agent?.logo_image_id || "")}
            >
              <option value="">-</option>
              {detail.images
                .filter((i) => !i.item_id)
                .map((image, index) => (
                  <option key={image.id} value={image.id}>
                    {image.caption || t("image_number", { number: index + 1 })}
                  </option>
                ))}
            </select>
          </label>
          <label>
            {f("uploadLogo")}
            <FileInput
              accept="image/png,image/jpeg,image/webp"
              onChange={(e) => {
                setLogoFile(e.target.files?.[0] || null);
                const select =
                  e.target.form?.elements.namedItem("logo_image_id");
                if (select instanceof HTMLSelectElement)
                  select.setCustomValidity("");
              }}
            />
          </label>
          <p className="muted">{f("logoHelp")}</p>
          <button className="primary">{t("save_agent")}</button>
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
      <p>
        {String(review.auction.auction_name || "-")} ·{" "}
        {t(String(review.auction.auction_type || "physical"))} ·{" "}
        {String(review.selling_agent.name || "-")}
      </p>
      <p>
        {String(
          review.auction.auction_date ||
            review.auction.auction_start_date ||
            "-",
        )}{" "}
        · {String(review.auction.start_time || "-")} ·{" "}
        {String(
          review.auction.physical_location ||
            review.auction.electronic_platform_name ||
            "-",
        )}
      </p>
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
      {review.valid && <p className="notice">{t("ready")}</p>}
    </section>
  );
}
