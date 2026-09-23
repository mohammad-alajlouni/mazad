"use client";
import { PropertyFields, readProperty } from "./AuctionWorkspace";
import FileInput from "./FileInput";

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
                ...(existing
                  ? {
                      auction: existing.auction,
                      workspace_type: existing.workspace_type,
                      banner_config: existing.banner_config,
                      social_config: existing.social_config,
                    }
                  : {
                      auction: {
                        auction_name: data.name,
                        auction_type: "physical",
                        selected_cover_template_id: "infath-2",
                        document_language: "ar",
                      },
                    }),
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
      {!existing && (
        <label>
          {tr("projectFlow.scope")}
          <select name="workspace_type" defaultValue="project">
            <option value="project">{tr("projectFlow.sharedOption")}</option>
            <option value="booklet">{tr("projectFlow.bookletOnly")}</option>
          </select>
        </label>
      )}
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
  requiredFields,
  auctionType,
}: {
  requiredFields?: string[];
  auctionType?: string;
  projectId: string;
  run: Run;
  onDone: () => void;
  existing?: Item;
}) {
  const tr = useTranslations();

  const [jsonError, setJsonError] = useState("");
  return (
    <form
      data-stage-form
      data-preview-form="item"
      data-item-id={existing?.id}
      className="panel form-panel"
      onSubmit={(e) => {
        e.preventDefault();
        const data = Object.fromEntries(new FormData(e.currentTarget));
        const form = new FormData(e.currentTarget);
        const property_data = readProperty(form);
        for (const key of Object.keys(data))
          // Structured fields travel inside property_data, never top level.
          if (/^(property|boundary|rental|booklet)\./.test(key))
            delete data[key];
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
      <PropertyFields
        existing={existing}
        requiredFields={requiredFields}
        auctionType={auctionType}
      />
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
      <details>
        <summary>{tr("flow.otherTools")}</summary>
        <label>
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
export { default as ExcelUpload } from "./ApprovedExcelUpload";
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
  const im = useTranslations("imagesStep");
  const project = detail.project;
  // The auction icon and the cover are fixed design assets (the cover is chosen
  // in the first step); only property photographs are uploaded here.
  const mainRequired = project.workspace_type === "project";
  const find = (category: string, itemId: string | null = null) =>
    detail.images.find(
      (i) => i.category === category && (i.item_id || null) === itemId,
    );
  const upload = (form: HTMLFormElement) => {
    const data = new FormData(form);
    if (!data.get("item_id")) data.delete("item_id");
    void run(async () => {
      for (const file of data.getAll("file")) {
        const body = new FormData();
        for (const [k, v] of data) if (k !== "file") body.set(k, v);
        body.set("file", file);
        await api(`/projects/${project.id}/images`, { method: "POST", body });
      }
      form.reset();
      onDone();
    }, tr("ui.image_uploaded"));
  };
  // Each required image has its own box: it states the role, shows the
  // current image and uploads straight into that role (with live preview).
  const slot = (
    key: string,
    title: string,
    category: string,
    itemId: string | null,
    required: boolean,
    multiple = false,
  ) => {
    const current = multiple ? undefined : find(category, itemId);
    return (
      <form
        key={key}
        data-slot={key}
        data-preview-form="images"
        className={`image-slot ${current || !required ? "done" : "missing"}`}
        tabIndex={-1}
        onSubmit={(e) => {
          e.preventDefault();
          upload(e.currentTarget);
        }}
      >
        <input type="hidden" name="category" value={category} />
        <input type="hidden" name="item_id" value={itemId || ""} />
        <div className="image-slot-heading">
          <strong>{title}</strong>
          <span>
            {current ? im("added") : required ? im("required") : im("optional")}
          </span>
        </div>
        {current && (
          <img src={`/api/images/${current.id}?size=preview`} alt={title} />
        )}
        <FileInput
          aria-label={title}
          name="file"
          type="file"
          accept="image/jpeg,image/png,image/webp"
          multiple={multiple}
          required
        />
        <button className={current ? "secondary" : "primary"}>
          {current ? im("replace") : im("upload")}
        </button>
      </form>
    );
  };
  const role = (i: { category?: string; item_id: string | null }) => {
    const item = detail.items.find((x) => x.id === i.item_id);
    if (i.category === "agent_logo") return im("agentLogo");
    if (i.category === "main" && item)
      return im("mainOf", { item: item.title });
    return item ? im("additionalOf", { item: item.title }) : im("projectImage");
  };
  return (
    <div className="panel form-panel">
      <h2>{tr("ui.project_images")}</h2>
      <p className="muted">{im("help")}</p>
      <div className="image-slots">
        {detail.items.map((item) =>
          slot(
            "main:" + item.id,
            im("mainOf", { item: item.title }),
            "main",
            item.id,
            mainRequired,
          ),
        )}
        {detail.items.map((item) =>
          slot(
            "additional:" + item.id,
            im("additionalOf", { item: item.title }),
            "additional",
            item.id,
            false,
            true,
          ),
        )}
      </div>
      <p className="muted">
        {tr(
          "ui.jpeg_png_or_webp_up_to_10_mb_images_are_validated_resized_and_sto",
        )}
      </p>
      {detail.images.length > 0 && <h3>{im("uploaded")}</h3>}
      <div className="image-grid">
        {detail.images.map((i) => (
          <figure key={i.id}>
            <img
              src={`/api/images/${i.id}?size=preview`}
              alt={tr("ui.uploaded_project_asset")}
            />
            <figcaption>
              <strong>{role(i)}</strong>
              {i.category !== "agent_logo" && (
                <>
                  <label>
                    {im("useAs")}
                    <select
                      value={
                        i.category === "main" || i.category === "additional"
                          ? `${i.category}|${i.item_id || ""}`
                          : "additional|"
                      }
                      onChange={(e) => {
                        const [category, item] = e.target.value.split("|");
                        void run(async () => {
                          await api(`/images/${i.id}`, {
                            method: "PUT",
                            body: send({ category, item_id: item || null }),
                          });
                          onDone();
                        }, im("updated"));
                      }}
                    >
                      <option value="additional|">{im("projectImage")}</option>
                      {detail.items.map((item) => [
                        <option key={"m" + item.id} value={`main|${item.id}`}>
                          {im("mainOf", { item: item.title })}
                        </option>,
                        <option
                          key={"a" + item.id}
                          value={`additional|${item.id}`}
                        >
                          {im("additionalOf", { item: item.title })}
                        </option>,
                      ])}
                    </select>
                  </label>
                  <button
                    type="button"
                    className="text-button danger"
                    onClick={() =>
                      void run(async () => {
                        await api(`/images/${i.id}`, { method: "DELETE" });
                        onDone();
                      }, im("deleted"))
                    }
                  >
                    {im("delete")}
                  </button>
                </>
              )}
            </figcaption>
          </figure>
        ))}
      </div>
    </div>
  );
}
