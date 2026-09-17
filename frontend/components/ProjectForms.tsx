"use client";
import { PropertyFields, readProperty } from "./AuctionWorkspace";
import FileInput from "./FileInput";
import { formatNumber } from "../i18n/format";
import { validationMessage, type Violation } from "../i18n/errors";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { api, send, Project, Item, Run, Detail } from "./api";

export function ProjectForm({
  run,
  onDone,
  existing,
}: {
  run: Run;
  onDone: (id: string) => void;
  existing?: Project;
}) {
  const tr = useTranslations();

  return (
    <form
      className="panel form-panel"
      onSubmit={(e) => {
        e.preventDefault();
        const data = Object.fromEntries(new FormData(e.currentTarget));
        void run(async () => {
          const p = await api<Project>(
            existing ? `/projects/${existing.id}` : "/projects",
            {
              method: existing ? "PUT" : "POST",
              body: send({
                ...data,
                ...(existing ? { auction: existing.auction } : { auction: { auction_name: data.name, auction_type: "physical", selected_cover_template_id: "infath-2", document_language: "ar" } }),
              }),
            },
          );
          onDone(p.id);
        }, tr("ui.project_saved"));
      }}
    >
      <div className="panel-heading">
        <h2>
          {existing ? tr("ui.project_details") : tr("ui.a_new_beginning")}
        </h2>
        <p>{tr("ui.give_your_project_a_name_and_a_little_context")}</p>
      </div>
      <div className="form-grid">
        {[
          ["name", tr("ui.project_name"), true],
          ["code", tr("ui.reference_code"), true],
          ["customer", tr("ui.customer_entity")],
          ["location", tr("ui.location")],
          ["date", tr("ui.project_date")],
        ].map(([key, label, required]) => (
          <label key={String(key)}>
            {label}
            <input
              dir={key === "code" || key === "date" ? "ltr" : undefined}
              name={String(key)}
              required={!!required}
              defaultValue={String(existing?.[key as keyof Project] || "")}
              type={key === "date" ? "date" : "text"}
              maxLength={key === "code" ? 100 : 200}
            />
          </label>
        ))}
      </div>
      <label>
        {tr("ui.project_status")}
        <select name="status" defaultValue={existing?.status || "DRAFT"}>
          <option value="DRAFT">{tr("ui.draft")}</option>
          <option value="ACTIVE">{tr("ui.active")}</option>
          <option value="COMPLETED">{tr("ui.completed")}</option>
        </select>
      </label>
      <label>
        {tr("ui.description")}
        <textarea
          name="description"
          rows={4}
          defaultValue={existing?.description}
        />
      </label>
      <label>
        {tr("ui.notes")}
        <textarea name="notes" rows={3} defaultValue={existing?.notes} />
      </label>
      <button className="primary" type="submit">
        {existing ? tr("ui.save_project") : tr("ui.create_project")}{" "}
        <span className="direction-arrow">→</span>
      </button>
    </form>
  );
}
export function ItemForm({
  projectId,
  run,
  onDone,
  existing,
}: {
  projectId: string;
  run: Run;
  onDone: () => void;
  existing?: Item;
}) {
  const tr = useTranslations();

  const [jsonError, setJsonError] = useState("");
  return (
    <form
      className="panel form-panel"
      onSubmit={(e) => {
        e.preventDefault();
        const data = Object.fromEntries(new FormData(e.currentTarget));
        const form = new FormData(e.currentTarget);
        const property_data = readProperty(form);
        for (const key of Object.keys(data))
          if (/^(property|boundary|rental)\./.test(key)) delete data[key];
        let attributes;
        try {
          attributes = JSON.parse(String(data.attributes) || "{}");
          if (
            !attributes ||
            Array.isArray(attributes) ||
            typeof attributes !== "object"
          )
            throw Error();
          setJsonError("");
        } catch {
          setJsonError("ui.additional_attributes_must_be_a_json_object");
          return;
        }
        void run(async () => {
          await api(
            `/projects/${projectId}/items${existing ? "/" + existing.id : ""}`,
            {
              method: existing ? "PUT" : "POST",
              body: send({
                ...data,
                attributes,
                property_data,
                sequence_number: existing?.sequence_number || 0,
              }),
            },
          );
          onDone();
        }, tr("ui.item_saved"));
      }}
    >
      <h2>{existing ? tr("ui.edit_item") : tr("ui.add_an_item")}</h2>
      <div className="form-grid">
        {[
          ["title", tr("ui.item_title")],
          ["reference", tr("ui.reference")],
          ["category", tr("ui.category")],
          ["quantity", tr("ui.quantity")],
          ["financial_value", tr("ui.unit_financial_value")],
        ].map(([key, label]) => (
          <label key={key}>
            {label}
            <input
              dir={
                ["reference", "quantity", "financial_value"].includes(key)
                  ? "ltr"
                  : undefined
              }
              name={key}
              required={key === "title"}
              type={
                ["quantity", "financial_value"].includes(key)
                  ? "number"
                  : "text"
              }
              min={key === "quantity" ? "0.0001" : "0"}
              step={key === "quantity" ? "0.0001" : "0.01"}
              defaultValue={String(
                existing?.[key as keyof Item] ??
                  (key === "quantity" ? 1 : key === "financial_value" ? 0 : ""),
              )}
            />
          </label>
        ))}
      </div>
      <PropertyFields existing={existing} />
      {[
        ["description", tr("ui.description")],
        ["specifications", tr("ui.specifications")],
        ["technical_information", tr("ui.technical_information")],
        ["notes", tr("ui.notes")],
      ].map(([key, label]) => (
        <label key={key}>
          {label}
          <textarea
            rows={2}
            name={key}
            defaultValue={String(existing?.[key as keyof Item] ?? "")}
          />
        </label>
      ))}
      <details><summary>{tr("flow.otherTools")}</summary><label>
        {tr("ui.additional_attributes_json")}
        <textarea
          dir="ltr"
          name="attributes"
          rows={3}
          defaultValue={JSON.stringify(existing?.attributes || {}, null, 2)}
        />
      </label>
      </details>
      {jsonError && <p className="error">{tr(jsonError)}</p>}
      <div className="actions">
        <button type="submit" className="primary">
          {tr("ui.save_item")}
        </button>
        <button type="button" className="secondary" onClick={onDone}>
          {tr("ui.cancel")}
        </button>
      </div>
    </form>
  );
}
type Preview = {
  id: string;
  valid_count: number;
  invalid_count: number;
  columns: { header: string; target: string }[];
  target_fields: string[];
  rows: {
    sheet: string;
    row_number: number;
    data: Record<string, unknown>;
    source?: Record<string, string>;
    errors: string[];
    issues?: Violation[];
  }[];
};
export function ExcelUpload({
  projectId,
  run,
  onDone,
}: {
  projectId: string;
  run: Run;
  onDone: () => void;
}) {
  const tr = useTranslations();

  const [preview, setPreview] = useState<Preview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [workbook, setWorkbook] = useState<File | null>(null);
  const at = useTranslations("auction");
  return (
    <div className="panel form-panel">
      <h2>{tr("ui.import_from_excel")}</h2>
      <p className="muted">
        {tr(
          "ui.upload_a_workbook_inspect_the_normalized_rows_then_import_valid_r",
        )}
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const form = new FormData(e.currentTarget);
          setWorkbook(form.get("file") as File);
          setMapping({});
          void run(async () =>
            setPreview(
              await api<Preview>(`/projects/${projectId}/imports/preview`, {
                method: "POST",
                body: form,
              }),
            ),
          );
        }}
      >
        <label>
          {tr("ui.excel_workbook")}
          <FileInput
            aria-label={tr("ui.excel_workbook")}
            name="file"
            type="file"
            accept=".xlsx,.xls"
            required
          />
        </label>
        <details>
          <summary>{tr("ui.custom_column_mapping")}</summary>
          <p className="muted">
            {tr(
              "ui.map_source_column_headers_to_normalized_fields_unmapped_columns_b",
            )}
          </p>
          <textarea
            dir="ltr"
            name="mapping"
            rows={4}
            aria-label={tr("ui.custom_column_mapping")}
            placeholder={tr.raw("common.mappingExample")}
          />
        </details>
        <button className="primary" type="submit">
          {tr("ui.preview_workbook")}
        </button>
      </form>
      {preview && (
        <>
          <details open>
            <summary>{at("column_mapping")}</summary>
            <div className="form-grid">
              {preview.columns.map((c) => (
                <label key={c.header}>
                  {c.header}
                  <select
                    aria-label={c.header}
                    value={mapping[c.header] ?? c.target}
                    onChange={(event) => {
                      setMapping({
                        ...mapping,
                        [c.header]: event.target.value,
                      });
                    }}
                  >
                    <option value="">{at("keep_attribute")}</option>
                    {preview.target_fields.map((field) => (
                      <option key={field} value={field}>
                        {field}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
            <button
              type="button"
              className="secondary"
              onClick={() =>
                void run(async () => {
                  if (!workbook) return;
                  const form = new FormData();
                  form.set("file", workbook);
                  form.set(
                    "mapping",
                    JSON.stringify(
                      Object.fromEntries(
                        preview.columns
                          .map((c) => [c.header, mapping[c.header] ?? c.target])
                          .filter(([, value]) => value),
                      ),
                    ),
                  );
                  setPreview(
                    await api<Preview>(
                      `/projects/${projectId}/imports/preview`,
                      { method: "POST", body: form },
                    ),
                  );
                  setMapping({});
                })
              }
            >
              {at("validate_mapping")}
            </button>
          </details>
          <details>
            <summary>{at("source_preview")}</summary>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>{tr("ui.sheet_row")}</th>
                    {preview.columns.map((c) => (
                      <th key={c.header}>{c.header}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.rows.map((row, index) => (
                    <tr key={index}>
                      <td>
                        {row.sheet} / {row.row_number}
                      </td>
                      {preview.columns.map((c) => (
                        <td key={c.header}>{row.source?.[c.header] || "-"}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
          <div className="notice">
            {tr("common.importSummary", {
              valid: preview.valid_count,
              invalid: preview.invalid_count,
            })}
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{tr("ui.sheet_row")}</th>
                  <th>{tr("ui.normalized_title")}</th>
                  <th>{tr("ui.quantity")}</th>
                  <th>{tr("ui.value")}</th>
                  <th>{tr("ui.validation")}</th>
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((r, i) => (
                  <tr key={i}>
                    <td>
                      <bdi>{r.sheet}</bdi> / {formatNumber(r.row_number)}
                    </td>
                    <td>{String(r.data.title || "—")}</td>
                    <td>
                      {r.data.quantity != null &&
                      Number.isFinite(Number(r.data.quantity))
                        ? formatNumber(String(r.data.quantity))
                        : String(r.data.quantity || "—")}
                    </td>
                    <td>
                      {r.data.financial_value != null &&
                      Number.isFinite(Number(r.data.financial_value))
                        ? formatNumber(String(r.data.financial_value))
                        : String(r.data.financial_value || "—")}
                    </td>
                    <td>
                      {r.errors.length ? (
                        <span className="error">
                          {r.issues
                            ?.map(
                              (v) =>
                                validationMessage(v) +
                                (v.original_value
                                  ? ` (${v.original_value})`
                                  : ""),
                            )
                            .join("؛ ") || tr("common.invalidRow")}
                        </span>
                      ) : (
                        tr("ui.ready")
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button
            disabled={!preview.valid_count || Object.keys(mapping).length > 0}
            className="primary"
            onClick={() =>
              void run(async () => {
                await api(
                  `/projects/${projectId}/imports/${preview.id}/commit`,
                  { method: "POST" },
                );
                setPreview(null);
                onDone();
              }, tr("ui.excel_records_imported"))
            }
          >
            {tr("common.importButton", { count: preview.valid_count })}
          </button>
        </>
      )}
    </div>
  );
}
export function ImageUpload({
  detail,
  run,
  onDone,
}: {
  detail: Detail;
  run: Run;
  onDone: () => void;
}) {
  const tr = useTranslations();
  const at = useTranslations("auction");

  return (
    <div className="panel form-panel">
      <h2>{tr("ui.project_images")}</h2>
      <p className="muted">
        {tr(
          "ui.jpeg_png_or_webp_up_to_10_mb_images_are_validated_resized_and_sto",
        )}
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const data = new FormData(e.currentTarget);
          if (!data.get("item_id")) data.delete("item_id");
          void run(async () => {
            for (const file of data.getAll("file")) {
              const upload = new FormData();
              for (const [k, v] of data) if (k !== "file") upload.set(k, v);
              upload.set("file", file);
              await api(`/projects/${detail.project.id}/images`, {
                method: "POST",
                body: upload,
              });
            }
            onDone();
          }, tr("ui.image_uploaded"));
        }}
      >
        <label>
          {tr("ui.attach_to")}
          <select name="item_id">
            <option value="">{tr("ui.project_cover_shared_image")}</option>
            {detail.items.map((i) => (
              <option key={i.id} value={i.id}>
                {i.title}
              </option>
            ))}
          </select>
        </label>
        <label>
          {at("image_category")}
          <select name="category">
            {["additional", "main", "cover", "auction_logo", "agent_logo"].map(
              (k) => (
                <option key={k} value={k}>
                  {at(k === "cover" ? "cover_image" : k)}
                </option>
              ),
            )}
          </select>
        </label>
        <label>
          {at("caption")}
          <input name="caption" maxLength={300} />
        </label>
        <label>
          {tr("ui.image")}
          <FileInput
            aria-label={tr("ui.image")}
            name="file"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            required
          />
        </label>
        <button className="primary">{tr("ui.upload_image")}</button>
      </form>
      <div className="image-grid">
        {detail.images.map((i) => (
          <figure key={i.id}>
            <img
              src={"/api/images/" + i.id}
              alt={tr("ui.uploaded_project_asset")}
            />
            <figcaption>
              {detail.items.find((item) => item.id === i.item_id)?.title ||
                tr("ui.project_image")}
              <small>
                {tr("ui.import_reference")}
                <bdi dir="ltr">{i.id}</bdi>
              </small>
            </figcaption>
          </figure>
        ))}
      </div>
    </div>
  );
}
