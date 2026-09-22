"use client";
import { ReactNode, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { api, Detail, send } from "./api";
import { readProperty } from "./AuctionWorkspace";

type Preview = {
  html: string;
  page: number;
  pages: { kind: string; item: string; step: string }[];
};
// Booklet pages follow the data-entry steps; later steps stay locked until the
// earlier ones are complete, so the preview never runs ahead of the form.
const STEPS = ["auction", "items", "images", "generate"];
const PAGE_WIDTH = 794; // 595.276 pt in CSS pixels
const PAGE_HEIGHT = 1123;
function stepOf(stage: string) {
  if (stage === "excel import") return "items";
  if (stage === "outputs") return "generate";
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
  image?: { src: string; category: string; item_id?: string };
};

async function smallImage(file: File) {
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
  // Two frames: the new page loads in the hidden one, then they swap.
  const [frames, setFrames] = useState<[string, string]>(["", ""]);
  const [front, setFront] = useState(0);
  const [scale, setScale] = useState(0.4);
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
  useEffect(() => {
    setDraft({});
    setPage(null);
    setFocus(stage);
    imageVersion.current++;
    // Forms mount with the step; read their required fields once they exist.
    const timer = setTimeout(() =>
      setFormComplete(requiredComplete(root.current)),
    );
    return () => clearTimeout(timer);
  }, [detail, stage]);
  useEffect(() => {
    const element = paper.current;
    if (!element) return;
    const observer = new ResizeObserver(() =>
      setScale(element.clientWidth / PAGE_WIDTH),
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
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
          `/projects/${detail.project.id}/booklet-preview`,
          {
            method: "POST",
            signal: controller.signal,
            body: send({
              ...draft,
              stage: [
                "auction",
                "agent",
                "items",
                "images",
                "generate",
                "cover",
              ].includes(focus)
                ? focus
                : "items",
              page,
            }),
          },
        );
        if (request !== version.current) return;
        // A frame already holding this exact page fires no load event: show it.
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
  }, [detail, draft, page, focus, retry]);
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
      setFocus(target.name === "cover-choice" ? "cover" : "auction");
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
      setFocus("items");
    }
    const file =
      target.type === "file"
        ? target.files?.[0]
        : form.querySelector<HTMLInputElement>('input[type="file"]')
            ?.files?.[0];
    if (target.type === "file" && !file) {
      imageVersion.current++;
      setDraft((d) => ({ ...d, image: undefined }));
    }
    if (file && (kind === "images" || kind === "agent")) {
      const serial = ++imageVersion.current;
      try {
        const src = await smallImage(file);
        if (serial !== imageVersion.current) return;
        const category =
          kind === "agent" ? "agent_logo" : String(data.get("category"));
        const item = String(data.get("item_id") || "");
        if (["main", "additional"].includes(category) && !item) return;
        setDraft((d) => ({
          ...d,
          image: { src, category, item_id: item || undefined },
        }));
        setFocus(
          category === "agent_logo"
            ? "agent"
            : category === "auction_logo"
              ? "auction"
              : "images",
        );
      } catch {
        setError(true);
      }
    }
  }
  return (
    <div
      className="live-booklet-layout"
      ref={root}
      onChange={(e) => void changed(e.target as HTMLInputElement)}
    >
      <div className="live-booklet-fields">{children}</div>
      <aside className="live-booklet-preview" aria-label={t("title")}>
        <div className="live-preview-heading">
          <strong>{t("title")}</strong>
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
        <div
          className="live-preview-paper"
          ref={paper}
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
                width: PAGE_WIDTH,
                height: PAGE_HEIGHT,
                transform: `scale(${scale})`,
                visibility: slot === front && preview ? "visible" : "hidden",
              }}
            />
          ))}
          {!preview && (
            <div className="live-preview-placeholder">{t("loading")}</div>
          )}
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
