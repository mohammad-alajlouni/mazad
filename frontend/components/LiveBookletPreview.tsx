"use client";
import React, { ReactNode, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import AgentLogoSize from "./AgentLogoSize";
import { Eye, X, ZoomIn, ZoomOut } from "lucide-react";
import { api, Detail, send } from "./api";
import { readProperty } from "./AuctionWorkspace";

type Preview = {
  html: string;
  page: number;
  pages: { kind: string; item: string; step: string }[];
  // The property being entered: the optional pages its data calls for.
  auto?: Record<string, boolean> | null;
  // The page's own size (the official forms have a landscape page).
  width_pt?: number;
  height_pt?: number;
};
// The official forms' unsaved values (FormsStep's "forms-draft" event).
export type FormsDraft = {
  forms: unknown;
  form: "request" | "study";
  item?: string;
};
// Booklet pages follow the data-entry steps; later steps stay locked until the
// earlier ones are complete, so the preview never runs ahead of the form.
const STEPS = ["auction", "items", "closing", "forms", "generate"];
const PAGE_WIDTH = 794; // 595.276 pt in CSS pixels
const PAGE_HEIGHT = 1123;
// The page of a property a field of its form prints on (the server falls
// back to the property's own page when it has no such page).
function sectionOf(field: HTMLElement) {
  const name = field.getAttribute("name") || "";
  const photo = field.dataset.category;
  if (/^(boundary|deedb)\./.test(name) || name === "property.deeds_differ")
    return "boundaries";
  if (name.startsWith("rental.")) return "rentals";
  if (name === "property.features" || photo === "features") return "features";
  if (photo === "additional") return "photos";
  if (["specifications", "technical_information"].includes(name))
    return "information";
  return "items";
}
// The words of an edited value to look for on the page (kashidas aside).
const plain = (text: string) =>
  text
    .replace(/\u0640/g, "")
    .replace(/\s+/g, " ")
    .trim();
function snippetsOf(field: HTMLElement | null) {
  const value = (field as HTMLInputElement | null)?.value || "";
  const lines = value.split("\n").map(plain).filter(Boolean);
  const caret = (field as HTMLTextAreaElement | null)?.selectionStart ?? -1;
  // The line being typed (else the last), its last few words.
  const before = caret >= 0 ? value.slice(0, caret).split("\n").length - 1 : -1;
  const line = plain(value.split("\n")[before] || "") || lines.at(-1) || "";
  // The last three words, else fewer (a page line may break between them).
  const words = line.split(" ");
  return [3, 2, 1]
    .map((n) => words.slice(-n).join(" "))
    .filter((text) => text.length >= 3);
}
const ZOOMS = [1, 1.5, 2, 3];
function stepOf(stage: string) {
  if (stage === "excel import") return "items";
  if (stage === "outputs" || stage === "finish") return "generate";
  return STEPS.includes(stage) ? stage : "auction";
}
function requiredComplete(root: HTMLElement | null) {
  if (!root) return true;
  return [
    ...root.querySelectorAll<
      HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
    >("form[data-stage-form] [required]"),
  ].every((el) => el.value.trim() !== "");
}
// Text regions carry data-fit and a maximum height; the browser measures them
// the way export preflight does, without a PDF round trip.
function overflows(doc: Document) {
  for (const el of doc.querySelectorAll<HTMLElement>("[data-fit]")) {
    const limit = el.dataset.maxHeight || "";
    const max = parseFloat(limit) * (limit.endsWith("pt") ? 96 / 72 : 1);
    // Same tolerance as export preflight: glyphs may overhang a tight line box.
    const slack = 1 + 0.9 * parseFloat(getComputedStyle(el).fontSize);
    if (
      (max && el.scrollHeight > max + slack) ||
      el.scrollWidth > el.clientWidth + slack
    )
      return true;
  }
  return false;
}
type Draft = {
  auction?: Record<string, unknown>;
  agent?: Record<string, unknown>;
  item?: Record<string, unknown>;
  image?: {
    src: string;
    category: string;
    item_id?: string;
    more?: string[];
    main?: string;
  };
};

export async function smallImage(file: File) {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(
    1,
    (file.type === "image/jpeg" ? 1200 : 800) /
      Math.max(bitmap.width, bitmap.height),
  );
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  const context = canvas.getContext("2d")!;
  context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  return file.type === "image/jpeg"
    ? canvas.toDataURL("image/jpeg", 0.85)
    : canvas.toDataURL("image/png");
}

export default function LiveBookletPreview({
  detail,
  stage,
  children,
}: {
  detail: Detail;
  stage: string;
  children: ReactNode;
}) {
  const t = useTranslations("liveBooklet");
  const [draft, setDraft] = useState<Draft>({});
  const [preview, setPreview] = useState<Preview | null>(null);
  const [page, setPage] = useState<number | null>(null);
  const [focus, setFocus] = useState(stage);
  const [updating, setUpdating] = useState(true);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  const [formComplete, setFormComplete] = useState(true);
  const [fits, setFits] = useState(true);
  // On a phone the preview is a sheet over the form, opened from a button.
  const [sheet, setSheet] = useState(false);
  const [small, setSmall] = useState(false);
  useEffect(() => {
    const query = matchMedia("(max-width: 1050px)");
    const read = () => setSmall(query.matches);
    read();
    query.addEventListener("change", read);
    return () => query.removeEventListener("change", read);
  }, []);
  useEffect(() => {
    if (!sheet) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSheet(false);
    };
    addEventListener("keydown", close);
    return () => removeEventListener("keydown", close);
  }, [sheet]);
  // Two frames: the new page loads in the hidden one, then they swap.
  const [frames, setFrames] = useState<[string, string]>(["", ""]);
  const [front, setFront] = useState(0);
  const [scale, setScale] = useState(0.4);
  // In the forms step the preview shows the official forms, not the booklet.
  const formsMode = stage === "forms";
  const [formsDraft, setFormsDraft] = useState<FormsDraft | null>(null);
  useEffect(() => {
    const take = (event: Event) => {
      const detail = (event as CustomEvent<FormsDraft>).detail;
      setFormsDraft((current) => {
        if (current?.form !== detail.form || current?.item !== detail.item)
          setPage(null);
        return detail;
      });
    };
    window.addEventListener("forms-draft", take);
    return () => window.removeEventListener("forms-draft", take);
  }, []);
  const pageWidth = ((preview?.width_pt || 595.276) * 4) / 3;
  const pageHeight = ((preview?.height_pt || 841.89) * 4) / 3;
  // Larger than the column to read details: the page scrolls in its frame,
  // following the field being edited.
  const [zoom, setZoom] = useState(1);
  const viewport = useRef<HTMLDivElement>(null);
  const edited = useRef<HTMLElement | null>(null);
  const version = useRef(0);
  const imageVersion = useRef(0);
  const root = useRef<HTMLDivElement>(null);
  const paper = useRef<HTMLDivElement>(null);
  const frameRefs = [
    useRef<HTMLIFrameElement>(null),
    useRef<HTMLIFrameElement>(null),
  ];
  // Frame contents and the visible frame, read inside async request callbacks.
  const shown = useRef<{ frames: [string, string]; front: number }>({
    frames: ["", ""],
    front: 0,
  });
  const pending = useRef<{
    slot: number;
    request: number;
    result: Preview;
  } | null>(null);
  // The booklet page the form is filling (a paged form marks it on itself).
  const formPage = () =>
    root.current?.querySelector<HTMLElement>("form[data-preview-page]")?.dataset
      .previewPage;
  useEffect(() => {
    const closed = () => {
      imageVersion.current++;
      // A stored property stays in view, as stored; a new one leaves it.
      setDraft((d) => ({
        ...d,
        item: d.item?.id ? { id: d.item.id } : undefined,
        image: undefined,
      }));
    };
    window.addEventListener("preview-item-closed", closed);
    return () => window.removeEventListener("preview-item-closed", closed);
  }, []);
  useEffect(() => {
    const follow = (event: Event) => {
      setPage(null);
      setFocus(String((event as CustomEvent).detail));
    };
    window.addEventListener("booklet-preview-page", follow);
    return () => window.removeEventListener("booklet-preview-page", follow);
  }, []);
  // A property's field taken up shows the page it prints on.
  useEffect(() => {
    const element = root.current;
    if (!element) return;
    const entered = (event: FocusEvent) => {
      const field = event.target as HTMLElement;
      if (!field.closest('form[data-preview-form="item"]')) return;
      if (!field.matches("input, textarea, select")) return;
      edited.current = field;
      setPage(null);
      setFocus(sectionOf(field));
    };
    element.addEventListener("focusin", entered);
    return () => element.removeEventListener("focusin", entered);
  }, []);
  // Zoomed in, the page scrolls to the text being edited.
  useEffect(() => {
    const box = viewport.current;
    const doc = frameRefs[front].current?.contentDocument;
    if (!box || !doc?.body || zoom === 1) return;
    let found: Element | null = null;
    for (const wanted of snippetsOf(edited.current)) {
      const walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_TEXT);
      for (
        let node = walker.nextNode();
        node && !found;
        node = walker.nextNode()
      )
        if (plain(node.textContent || "").includes(wanted))
          found = node.parentElement;
      if (found) break;
    }
    if (!found) return;
    // Where it stands on screen (the frame is scaled), brought to the
    // middle of the viewport: relative moves work in either direction.
    const at = found.getBoundingClientRect();
    const frame = frameRefs[front].current!.getBoundingClientRect();
    const view = box.getBoundingClientRect();
    box.scrollBy({
      top:
        frame.top +
        (at.top + at.height / 2) * scale -
        (view.top + view.height / 2),
      left:
        frame.left +
        (at.left + at.width / 2) * scale -
        (view.left + view.width / 2),
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth",
    });
  }, [preview, front, zoom, scale]);
  useEffect(() => {
    setDraft({});
    setPage(null);
    setFocus(formPage() || stage);
    imageVersion.current++;
    // Forms mount with the step; read their required fields once they exist.
    const timer = setTimeout(() =>
      setFormComplete(requiredComplete(root.current)),
    );
    return () => clearTimeout(timer);
  }, [detail, stage]);
  const pageWidthRef = useRef(pageWidth);
  pageWidthRef.current = pageWidth;
  useEffect(() => {
    const element = paper.current;
    if (!element) return;
    const observer = new ResizeObserver(() =>
      setScale(element.clientWidth / pageWidthRef.current),
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    if (paper.current) setScale(paper.current.clientWidth / pageWidth);
  }, [pageWidth]);
  const current = stepOf(stage);
  const stages = detail.workflow?.stages || {};
  const unlocked = new Set<string>();
  for (const [index, step] of STEPS.entries()) {
    unlocked.add(step);
    const saved =
      step === "generate" ||
      (stages[step]?.valid !== false &&
        (step !== "auction" || stages.agent?.valid !== false));
    const done = step === current ? saved && formComplete : saved;
    if (!done && index >= STEPS.indexOf(current)) break;
    if (!saved) break;
  }
  unlocked.add(current);
  const locked = (index: number) =>
    !!preview && !unlocked.has(preview.pages[index]?.step);
  useEffect(() => {
    const request = ++version.current;
    const controller = new AbortController();
    setUpdating(true);
    setError(false);
    const timer = setTimeout(async () => {
      try {
        const result = await api<Preview>(
          `/projects/${detail.project.id}/${formsMode ? "forms-preview" : "booklet-preview"}`,
          {
            method: "POST",
            signal: controller.signal,
            body: send(
              formsMode
                ? {
                    form: formsDraft?.form || "request",
                    ...(formsDraft ? { forms: formsDraft.forms } : {}),
                    item: formsDraft?.item,
                    page,
                  }
                : {
                    ...draft,
                    stage: [
                      "auction",
                      "agent",
                      "items",
                      "images",
                      "closing",
                      "generate",
                      "cover",
                      "introduction",
                      "terms",
                      "participation",
                      "contact",
                      "features",
                      "boundaries",
                      "information",
                      "photos",
                      "rentals",
                    ].includes(focus)
                      ? focus
                      : "items",
                    page,
                  },
            ),
          },
        );
        if (request !== version.current) return;
        // A frame already holding this exact page fires no load event: show it.
        // Its page settings show which pages switched on by themselves.
        window.dispatchEvent(
          new CustomEvent("preview-auto-pages", {
            detail: result.auto ?? null,
          }),
        );
        const same = shown.current.frames.indexOf(result.html);
        if (same >= 0) {
          pending.current = null;
          const doc = frameRefs[same].current?.contentDocument;
          if (doc) setFits(!overflows(doc));
          setPreview(result);
          setFront(same);
          shown.current.front = same;
          setUpdating(false);
          return;
        }
        // Load into the hidden frame; it becomes visible once rendered.
        const slot = 1 - shown.current.front;
        pending.current = { slot, request, result };
        shown.current.frames[slot] = result.html;
        setFrames([...shown.current.frames] as [string, string]);
      } catch (e) {
        if (request === version.current && !controller.signal.aborted) {
          setError(true);
          setUpdating(false);
        }
      }
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [detail, draft, page, focus, retry, formsMode, formsDraft]);
  async function loaded(slot: number) {
    const job = pending.current;
    const doc = frameRefs[slot].current?.contentDocument;
    if (!job || job.slot !== slot || !doc) return;
    await doc.fonts?.ready;
    await Promise.all(
      [...doc.images].map((img) =>
        img.complete ? null : img.decode().catch(() => null),
      ),
    );
    if (job.request !== version.current) return;
    pending.current = null;
    setFits(!overflows(doc));
    setPreview(job.result);
    setFront(slot);
    shown.current.front = slot;
    setUpdating(false);
  }
  async function changed(target: HTMLInputElement) {
    setFormComplete(requiredComplete(root.current));
    if (target.matches?.("input, textarea, select")) edited.current = target;
    const form = target.closest<HTMLFormElement>("form[data-preview-form]");
    if (!form) return;
    const data = new FormData(form);
    const kind = form.dataset.previewForm;
    const values = Object.fromEntries(
      [...data].filter(([, v]) => typeof v === "string"),
    );
    setPage(null);
    if (kind === "auction") {
      const cover = data.get("cover-choice");
      delete values["cover-choice"];
      setDraft((d) => ({
        ...d,
        auction: {
          ...values,
          ...(cover ? { selected_cover_template_id: cover } : {}),
        },
      }));
      setFocus(
        form.dataset.previewPage ||
          (target.name === "cover-choice" ? "cover" : "auction"),
      );
    } else if (kind === "agent") {
      setDraft((d) => ({ ...d, agent: values }));
      setFocus("agent");
    } else if (kind === "item") {
      setDraft((d) => ({
        ...d,
        item: {
          id: form.dataset.itemId || undefined,
          ...Object.fromEntries(
            Object.entries(values).filter(([k]) => !k.includes(".")),
          ),
          property_data: readProperty(data),
        },
      }));
      setFocus(sectionOf(target));
    }
    const picker =
      target.type === "file"
        ? target
        : form.querySelector<HTMLInputElement>('input[type="file"]');
    // The photograph slots of one kind (additional, the features' own): all
    // picked in the form are previewed together.
    const group = picker?.dataset.category;
    const together =
      group === "additional" || group === "features"
        ? Array.from(
            form.querySelectorAll<HTMLInputElement>(
              `input[type="file"][data-category="${group}"]`,
            ),
          ).flatMap((input) => Array.from(input.files || []))
        : [];
    const file = together[0] || picker?.files?.[0];
    if (target.type === "file" && !file) {
      imageVersion.current++;
      setDraft((d) => ({ ...d, image: undefined }));
    }
    if (file && (kind === "images" || kind === "agent" || kind === "item")) {
      const serial = ++imageVersion.current;
      try {
        const src = await smallImage(file);
        // Additional photographs picked together are all previewed: two of
        // them with features make the property's features page (guide p.17).
        const more = await Promise.all(together.slice(1, 12).map(smallImage));
        // With them, the main photograph picked in the same form and not
        // stored yet: the pages depend on it too.
        const pending =
          group === "additional" || group === "features"
            ? form.querySelector<HTMLInputElement>(
                'input[type="file"][data-category="main"]',
              )?.files?.[0]
            : undefined;
        const main = pending ? await smallImage(pending) : "";
        if (serial !== imageVersion.current) return;
        // A property's form names the role on each of its photograph inputs;
        // the photograph belongs to that property, saved or being entered.
        const category =
          kind === "agent"
            ? "agent_logo"
            : kind === "item"
              ? picker?.dataset.category || "main"
              : String(data.get("category"));
        const item =
          kind === "item"
            ? form.dataset.itemId || ""
            : String(data.get("item_id") || "");
        if (
          kind !== "item" &&
          ["main", "additional"].includes(category) &&
          !item
        )
          return;
        setDraft((d) => ({
          ...d,
          image: {
            src,
            category,
            item_id: item || undefined,
            ...(more.length ? { more } : {}),
            ...(main ? { main } : {}),
          },
        }));
        setFocus(
          category === "agent_logo"
            ? "agent"
            : category === "auction_logo"
              ? "auction"
              : kind === "item"
                ? "items"
                : "images",
        );
      } catch {
        setError(true);
      }
    }
  }
  // A form asks to be read again after the project reloaded under its unsaved
  // values (for example once a cover photograph is stored).
  useEffect(() => {
    const element = root.current;
    if (!element) return;
    const again = (event: Event) =>
      void changed(event.target as HTMLInputElement);
    element.addEventListener("preview-form", again);
    return () => element.removeEventListener("preview-form", again);
  }, []);
  return (
    <div
      className="live-booklet-layout"
      ref={root}
      onChange={(e) => void changed(e.target as HTMLInputElement)}
    >
      <div className="live-booklet-fields">{children}</div>
      <button
        type="button"
        className={"preview-open" + (fits ? "" : " warns")}
        aria-expanded={sheet}
        onClick={() => setSheet(true)}
      >
        <Eye size={18} />
        {t("open")}
      </button>
      <aside
        className={"live-booklet-preview" + (sheet ? " open" : "")}
        aria-label={t("title")}
        // Closed on a phone, it is out of reach of the keyboard and readers.
        inert={small && !sheet}
        aria-hidden={small && !sheet ? true : undefined}
      >
        <button
          type="button"
          className="preview-close"
          aria-label={t("close")}
          onClick={() => setSheet(false)}
        >
          <X size={20} />
        </button>
        <div className="live-preview-heading">
          <strong>{t(formsMode ? "formsTitle" : "title")}</strong>
          <span aria-live="polite">
            {error ? t("failed") : updating ? t("updating") : t("current")}
          </span>
        </div>
        <p className="muted">{t("help")}</p>
        {preview && (
          <div className="live-preview-navigation">
            <button
              type="button"
              disabled={preview.page === 0}
              aria-label={t("previous")}
              onClick={() => setPage(preview.page - 1)}
            >
              ‹
            </button>
            <select
              aria-label={t("page")}
              value={preview.page}
              onChange={(e) => setPage(Number(e.target.value))}
            >
              {preview.pages.map((p, i) => (
                <option key={i} value={i} disabled={locked(i)}>
                  {i + 1}. {t.has(p.kind) ? t(p.kind) : p.kind}
                  {p.item ? ` · ${p.item}` : ""}
                  {locked(i) ? ` · ${t("locked")}` : ""}
                </option>
              ))}
            </select>
            <button
              type="button"
              disabled={
                preview.page === preview.pages.length - 1 ||
                locked(preview.page + 1)
              }
              aria-label={t("next")}
              onClick={() => setPage(preview.page + 1)}
            >
              ›
            </button>
          </div>
        )}
        {preview && preview.pages.some((_, i) => locked(i)) && (
          <p className="muted live-preview-locked">{t("lockedHelp")}</p>
        )}
        {!formsMode && !!detail.selling_agent?.logo_image_id && (
          <AgentLogoSize
            projectId={detail.project.id}
            kind="booklet"
            onChange={() => setRetry((v) => v + 1)}
          />
        )}
        <div className="live-preview-zoom">
          <button
            type="button"
            className="icon-button"
            disabled={zoom === ZOOMS[0]}
            aria-label={t("zoomOut")}
            title={t("zoomOut")}
            onClick={() => setZoom(ZOOMS[Math.max(0, ZOOMS.indexOf(zoom) - 1)])}
          >
            <ZoomOut size={16} />
          </button>
          <span aria-live="polite">{Math.round(zoom * 100)}%</span>
          <button
            type="button"
            className="icon-button"
            disabled={zoom === ZOOMS.at(-1)}
            aria-label={t("zoomIn")}
            title={t("zoomIn")}
            onClick={() =>
              setZoom(
                ZOOMS[Math.min(ZOOMS.length - 1, ZOOMS.indexOf(zoom) + 1)],
              )
            }
          >
            <ZoomIn size={16} />
          </button>
        </div>
        <div
          className="live-preview-viewport"
          ref={viewport}
          style={{ "--zoom": zoom } as React.CSSProperties}
        >
          <div
            className="live-preview-paper"
            ref={paper}
            style={{ aspectRatio: `${pageWidth} / ${pageHeight}` }}
            aria-busy={updating}
            data-page-kind={preview?.pages[preview.page]?.kind}
          >
            {frames.map((html, slot) => (
              <iframe
                key={slot}
                ref={frameRefs[slot]}
                title={t("imageAlt", { number: (preview?.page ?? 0) + 1 })}
                // Same origin for fonts and photographs; no scripts run inside.
                sandbox="allow-same-origin"
                srcDoc={html}
                aria-hidden={slot !== front}
                tabIndex={-1}
                onLoad={() => void loaded(slot)}
                style={{
                  width: pageWidth,
                  height: pageHeight,
                  transform: `scale(${scale})`,
                  visibility: slot === front && preview ? "visible" : "hidden",
                }}
              />
            ))}
            {!preview && (
              <div className="live-preview-placeholder">{t("loading")}</div>
            )}
          </div>
        </div>
        {error && (
          <div className="notice error" role="alert">
            {t("retryHelp")}{" "}
            <button type="button" onClick={() => setRetry((v) => v + 1)}>
              {t("retry")}
            </button>
          </div>
        )}
        {preview && !fits && (
          <p className="notice error" role="alert">
            {t("overflow")}
          </p>
        )}
        <p className="muted">{t("draft")}</p>
      </aside>
    </div>
  );
}
