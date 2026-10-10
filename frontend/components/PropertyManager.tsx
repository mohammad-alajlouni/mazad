"use client";
import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import {
  ArrowUp,
  Copy,
  FileSpreadsheet,
  ImageOff,
  Plus,
  Trash2,
} from "lucide-react";
import { api, send, Detail, Item, Run } from "./api";
import { useConfirm } from "./Confirmation";
import { ItemForm, SaveAction } from "./ProjectForms";

// Values a similar property usually shares: same scheme, same area, same use.
const SHARED = [
  "property_type",
  "city",
  "district",
  "usage",
  "plan_number",
  "participation_amount",
  "auction_close_date",
  "auction_close_time",
  "booklet_layout",
  "booklet_image_fit",
];

export type Editing = Item | "new" | null;

// Properties are entered one after another: the list stays in view, the form
// sits under it, and saving can go straight on to a new (or similar) property.
export default function PropertyManager({
  detail,
  run,
  reload,
  editing,
  setEditing,
  onImport,
}: {
  detail: Detail;
  run: Run;
  reload: () => Promise<void>;
  editing: Editing;
  setEditing: (item: Editing) => void;
  onImport: () => void;
}) {
  const t = useTranslations("properties");
  const tr = useTranslations();
  const confirm = useConfirm();
  const [template, setTemplate] = useState<Record<string, unknown>>();
  const [formKey, setFormKey] = useState(0);
  const editor = useRef<HTMLDivElement>(null);
  const items = detail.items;
  // With no property yet, the form is simply open.
  const current: Editing = editing ?? (items.length ? null : "new");
  const index =
    current && current !== "new"
      ? items.findIndex((i) => i.id === current.id)
      : -1;
  const missing = (item: Item) =>
    (detail.workflow?.stages.items?.missing || []).filter(
      (issue) => (issue as { item_id?: string }).item_id === item.id,
    ).length;

  // Every new form starts at its top, first field focused, list still visible.
  useEffect(() => {
    if (!current || !editor.current) return;
    editor.current.scrollIntoView({ behavior: "smooth", block: "start" });
    const first = editor.current.querySelector<HTMLInputElement>(
      "input:not([type=hidden]), textarea",
    );
    first?.focus({ preventScroll: true });
  }, [formKey, index]);

  const saved = async (action: SaveAction, item: Item) => {
    await reload();
    if (action === "close") {
      setTemplate(undefined);
      setEditing(null);
    } else if (action === "next") {
      setEditing(items[index + 1] || null);
    } else {
      setTemplate(
        action === "similar"
          ? Object.fromEntries(
              SHARED.filter((k) => item.property_data?.[k]).map((k) => [
                k,
                item.property_data?.[k],
              ]),
            )
          : undefined,
      );
      setEditing("new");
    }
    setFormKey((k) => k + 1);
  };
  const open = (item: Editing, from?: Record<string, unknown>) => {
    setTemplate(from);
    setEditing(item);
    setFormKey((k) => k + 1);
  };

  return (
    <div className="property-manager">
      <section className="panel property-list-panel">
        {/* How properties come in: the approved Excel file, or one by one. */}
        <div className="choice-cards method-cards">
          <button type="button" className="choice-card" onClick={onImport}>
            <span className="choice-icon">
              <FileSpreadsheet size={20} />
            </span>
            <strong>{t("import")}</strong>
            <small aria-hidden="true">{t("methodExcelHelp")}</small>
          </button>
          <button
            type="button"
            className={
              current === "new" ? "choice-card selected" : "choice-card"
            }
            onClick={() => open("new")}
          >
            <span className="choice-icon">
              <Plus size={20} />
            </span>
            <strong>{t("add")}</strong>
            <small aria-hidden="true">{t("methodManualHelp")}</small>
          </button>
        </div>
        <div className="panel-heading flex-row">
          <h2>
            {t("title")} <small>{t("count", { count: items.length })}</small>
          </h2>
        </div>
        {items.length === 0 ? (
          <p className="muted">{t("empty")}</p>
        ) : (
          <ol className="property-cards">
            {items.map((item, at) => {
              const gaps = missing(item);
              const prop = item.property_data || {};
              const photo = detail.images.find(
                (i) => i.item_id === item.id && i.category === "main",
              );
              return (
                <li
                  key={item.id}
                  className={
                    current !== "new" && current?.id === item.id
                      ? "selected"
                      : ""
                  }
                >
                  <button
                    type="button"
                    className="property-card"
                    onClick={() => open(item)}
                  >
                    <span className="property-number">
                      {String(at + 1).padStart(2, "0")}
                    </span>
                    {/* Its main photograph, or a sign that it has none yet. */}
                    {photo ? (
                      <img
                        className="property-thumb"
                        src={`/api/images/${photo.id}?size=preview`}
                        alt=""
                      />
                    ) : (
                      <span
                        className="property-thumb empty"
                        title={t("noPhoto")}
                      >
                        <ImageOff size={16} />
                      </span>
                    )}
                    <span className="property-text">
                      <strong>{item.title}</strong>
                      <small>
                        {[prop.city, prop.district, prop.deed_number]
                          .filter(Boolean)
                          .map(String)
                          .join(" · ") || "—"}
                      </small>
                    </span>
                    <span className={gaps ? "chip warning" : "chip done"}>
                      {gaps ? t("missing", { count: gaps }) : t("complete")}
                    </span>
                  </button>
                  <span className="property-tools">
                    <button
                      type="button"
                      className="icon-button"
                      title={t("duplicate")}
                      aria-label={t("duplicate")}
                      onClick={() =>
                        open(
                          "new",
                          Object.fromEntries(
                            SHARED.filter((k) => prop[k]).map((k) => [
                              k,
                              prop[k],
                            ]),
                          ),
                        )
                      }
                    >
                      <Copy size={15} />
                    </button>
                    <button
                      type="button"
                      className="icon-button"
                      title={t("moveUp")}
                      aria-label={t("moveUp")}
                      disabled={at === 0}
                      onClick={() =>
                        void run(async () => {
                          const ids = items.map((v) => v.id);
                          [ids[at - 1], ids[at]] = [ids[at], ids[at - 1]];
                          await api(
                            `/projects/${detail.project.id}/item-order`,
                            {
                              method: "PUT",
                              body: send({ item_ids: ids }),
                            },
                          );
                          await reload();
                        })
                      }
                    >
                      <ArrowUp size={15} />
                    </button>
                    <button
                      type="button"
                      className="icon-button danger"
                      title={tr("ui.delete")}
                      aria-label={tr("ui.delete") + " " + item.title}
                      onClick={async () => {
                        if (
                          await confirm(
                            tr(
                              "ui.delete_this_item_and_its_image_associations_existing_outputs_will",
                            ),
                          )
                        )
                          void run(async () => {
                            await api(
                              `/projects/${detail.project.id}/items/${item.id}`,
                              { method: "DELETE" },
                            );
                            if (current !== "new" && current?.id === item.id)
                              setEditing(null);
                            await reload();
                          }, tr("ui.item_deleted"));
                      }}
                    >
                      <Trash2 size={15} />
                    </button>
                  </span>
                </li>
              );
            })}
          </ol>
        )}
      </section>
      <div ref={editor} className="property-editor">
        {current ? (
          <ItemForm
            key={formKey + ":" + (current === "new" ? "new" : current.id)}
            projectId={detail.project.id}
            requiredFields={detail.workflow?.rules.property_required}
            auctionType={String(
              detail.project.auction?.auction_type || "physical",
            )}
            existing={current === "new" ? undefined : current}
            images={
              current === "new"
                ? []
                : detail.images.filter((i) => i.item_id === current.id)
            }
            photoRequired={detail.project.workspace_type === "project"}
            template={current === "new" ? template : undefined}
            number={current === "new" ? items.length + 1 : index + 1}
            hasNext={index >= 0 && index < items.length - 1}
            run={run}
            onSaved={saved}
            onDone={() => {
              setTemplate(undefined);
              setEditing(null);
            }}
          />
        ) : (
          <p className="muted property-hint">{t("pick")}</p>
        )}
      </div>
    </div>
  );
}
