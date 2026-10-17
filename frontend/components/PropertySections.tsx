"use client";
// Parts of a property's form that keep their own state: its rental contracts
// (a short list, each opened to be edited) and its booklet page settings.
import React, { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import {
  ArrowDown,
  ArrowUp,
  Check,
  FileSpreadsheet,
  FileText,
  GripVertical,
  Images,
  Pencil,
  Plus,
  Ruler,
  Star,
  Trash2,
} from "lucide-react";

type Values = Record<string, unknown>;

// A change made by a button is no typed change: the live preview reads the
// form again.
function usePreviewAgain() {
  const marker = useRef<HTMLSpanElement>(null);
  const again = () =>
    setTimeout(() =>
      marker.current
        ?.closest("form")
        ?.dispatchEvent(new Event("preview-form", { bubbles: true })),
    );
  return { marker, again };
}

type Contract = {
  key: number;
  data: Values;
  editing: boolean;
  version: number;
};

// The rental contracts: each saved one stands as one line (its unit, type
// and rent) with edit and delete; the one being entered is open. Every
// contract's fields stay in the form (closed ones hidden): saving the
// property saves them all.
export function RentalContracts({
  initial,
  summaryFields,
  renderFields,
}: {
  initial: Values[];
  summaryFields: string[];
  renderFields: (prefix: string, values: Values) => React.ReactNode;
}) {
  const t = useTranslations("auction");
  const { marker, again } = usePreviewAgain();
  const [rows, setRows] = useState<Contract[]>(
    initial.map((data, key) => ({ key, data, editing: false, version: 0 })),
  );
  const [next, setNext] = useState(initial.length);
  const boxes = useRef<Record<number, HTMLDivElement | null>>({});
  const read = (key: number) => {
    const data: Values = {};
    boxes.current[key]
      ?.querySelectorAll<HTMLInputElement>("input, select, textarea")
      .forEach((field) => {
        data[field.name.split(".").pop() || ""] = field.value;
      });
    return data;
  };
  const filled = (data: Values) =>
    Object.values(data).some((value) => String(value ?? "").trim());
  const update = (list: Contract[]) => {
    setRows(list);
    again();
  };
  return (
    <div className="rental-list">
      <span ref={marker} hidden />
      {rows.length === 0 && <p className="muted">{t("rentalsEmpty")}</p>}
      <ol>
        {rows.map((row, at) => (
          <li key={row.key} className={row.editing ? "editing" : ""}>
            <div className="rental-row">
              <strong>{t("rentalN", { number: at + 1 })}</strong>
              <span className="rental-summary">
                {summaryFields
                  .map((key) => String(row.data[key] ?? "").trim())
                  .filter(Boolean)
                  .join(" · ") || t("rentalBlank")}
              </span>
              {!row.editing && (
                <span className="rental-tools">
                  <button
                    type="button"
                    className="icon-button"
                    title={t("rentalEdit")}
                    aria-label={t("rentalEdit") + " " + (at + 1)}
                    onClick={() => {
                      setRows(
                        rows.map((r) =>
                          r.key === row.key ? { ...r, editing: true } : r,
                        ),
                      );
                      // Its first field taken up: the preview shows the page.
                      setTimeout(() =>
                        boxes.current[row.key]
                          ?.querySelector<HTMLElement>("input, select")
                          ?.focus(),
                      );
                    }}
                  >
                    <Pencil size={15} />
                  </button>
                  <button
                    type="button"
                    className="icon-button danger"
                    title={t("remove")}
                    aria-label={t("rentalDelete") + " " + (at + 1)}
                    onClick={() =>
                      update(rows.filter((r) => r.key !== row.key))
                    }
                  >
                    <Trash2 size={15} />
                  </button>
                </span>
              )}
            </div>
            <div
              key={row.version}
              hidden={!row.editing}
              ref={(el) => {
                boxes.current[row.key] = el;
              }}
            >
              {renderFields(`rental.${row.key}.`, row.data)}
              <div className="rental-actions">
                <button
                  type="button"
                  className="secondary"
                  onClick={() => {
                    const data = read(row.key);
                    update(
                      filled(data)
                        ? rows.map((r) =>
                            r.key === row.key
                              ? { ...r, data, editing: false }
                              : r,
                          )
                        : rows.filter((r) => r.key !== row.key),
                    );
                  }}
                >
                  <Check size={15} />
                  {t("rentalSave")}
                </button>
                <button
                  type="button"
                  className="text-button"
                  onClick={() =>
                    // Back to what was saved (an empty new one goes away).
                    update(
                      filled(row.data)
                        ? rows.map((r) =>
                            r.key === row.key
                              ? { ...r, editing: false, version: r.version + 1 }
                              : r,
                          )
                        : rows.filter((r) => r.key !== row.key),
                    )
                  }
                >
                  {t("rentalCancel")}
                </button>
              </div>
            </div>
          </li>
        ))}
      </ol>
      {!rows.some((r) => r.editing && !filled(r.data)) && (
        <button
          type="button"
          className="secondary"
          onClick={() => {
            setRows([
              ...rows,
              { key: next, data: {}, editing: true, version: 0 },
            ]);
            setNext(next + 1);
            setTimeout(() =>
              boxes.current[next]
                ?.querySelector<HTMLElement>("input, select")
                ?.focus(),
            );
          }}
        >
          <Plus size={15} />
          {t("add_rental")}
        </button>
      )}
    </div>
  );
}

// The property's optional pages, in the booklet's order (the server's
// composer.OPTIONAL_PAGES): each with its switch, or switched on by itself
// when the property's data calls for it (text continuing, boundaries that
// do not fit). Dragged (or moved with the arrows) into the order the
// author wants in the booklet.
const PAGES = {
  information: { field: "include_information_page", icon: FileText, on: true },
  features: { field: "include_features_page", icon: Star, on: true },
  images: { field: "include_images_page", icon: Images, on: true },
  boundaries: { field: "include_boundaries_page", icon: Ruler, on: false },
  rentals: { field: "include_rentals_page", icon: FileSpreadsheet, on: true },
} as const;
type Page = keyof typeof PAGES;
const GUIDE_ORDER: Page[] = [
  "features",
  "boundaries",
  "information",
  "images",
  "rentals",
];

export function PageSettings({ prop }: { prop: Values }) {
  const t = useTranslations("auction");
  const { marker, again } = usePreviewAgain();
  const chosen = ((prop.page_order || []) as string[]).filter(
    (key): key is Page => key in PAGES,
  );
  const [order, setOrder] = useState<Page[]>([
    ...new Set(chosen),
    ...GUIDE_ORDER.filter((key) => !chosen.includes(key)),
  ]);
  const [on, setOn] = useState<Record<Page, boolean>>(
    () =>
      Object.fromEntries(
        Object.entries(PAGES).map(([key, page]) => [
          key,
          prop[page.field] === undefined ? page.on : Boolean(prop[page.field]),
        ]),
      ) as Record<Page, boolean>,
  );
  // What the live preview found the property's data calls for.
  const [auto, setAuto] = useState<Partial<Record<Page, boolean>>>({});
  useEffect(() => {
    const seen = (e: Event) =>
      setAuto(
        (e as CustomEvent<Partial<Record<Page, boolean>> | null>).detail || {},
      );
    window.addEventListener("preview-auto-pages", seen);
    return () => window.removeEventListener("preview-auto-pages", seen);
  }, []);
  const [dragged, setDragged] = useState<Page | null>(null);
  const move = (key: Page, to: number) => {
    const list = order.filter((k) => k !== key);
    list.splice(Math.max(0, Math.min(to, list.length)), 0, key);
    setOrder(list);
    again();
  };
  return (
    <div className="page-settings">
      <span ref={marker} hidden />
      <p className="muted">{t("pagesHelp")}</p>
      <ol>
        {order.map((key, at) => {
          const Icon = PAGES[key].icon;
          const automatic = !!auto[key];
          return (
            <li
              key={key}
              draggable
              className={dragged === key ? "dragging" : ""}
              onDragStart={(e) => {
                setDragged(key);
                e.dataTransfer.effectAllowed = "move";
              }}
              onDragEnd={() => setDragged(null)}
              onDragOver={(e) => {
                if (!dragged || dragged === key) return;
                e.preventDefault();
                move(dragged, at);
              }}
              onDrop={(e) => e.preventDefault()}
            >
              <GripVertical size={16} className="grip" aria-hidden="true" />
              <span className={`page-icon page-icon-${key}`} aria-hidden="true">
                <Icon size={17} />
              </span>
              <span className="page-text">
                <strong>{t(`page_${key}`)}</strong>
                <small>{t(`page_${key}_help`)}</small>
              </span>
              {automatic ? (
                <span className="chip done page-auto">
                  <Check size={13} />
                  {t("page_auto")}
                </span>
              ) : (
                <label className="switch">
                  <input
                    type="checkbox"
                    role="switch"
                    checked={on[key]}
                    aria-label={t(`page_${key}`)}
                    onChange={(e) => {
                      setOn({ ...on, [key]: e.target.checked });
                      again();
                    }}
                  />
                  <span aria-hidden="true" />
                </label>
              )}
              <span className="page-move">
                <button
                  type="button"
                  className="icon-button"
                  disabled={at === 0}
                  aria-label={t("pageUp", { page: t(`page_${key}`) })}
                  title={t("pageUp", { page: t(`page_${key}`) })}
                  onClick={() => move(key, at - 1)}
                >
                  <ArrowUp size={14} />
                </button>
                <button
                  type="button"
                  className="icon-button"
                  disabled={at === order.length - 1}
                  aria-label={t("pageDown", { page: t(`page_${key}`) })}
                  title={t("pageDown", { page: t(`page_${key}`) })}
                  onClick={() => move(key, at + 1)}
                >
                  <ArrowDown size={14} />
                </button>
              </span>
              <input
                type="hidden"
                name={`booklet.${PAGES[key].field}`}
                value={String(on[key])}
              />
              <input type="hidden" name="property.page_order" value={key} />
            </li>
          );
        })}
      </ol>
    </div>
  );
}
