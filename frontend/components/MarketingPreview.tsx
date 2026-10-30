"use client";
import React, { ReactNode, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import AgentLogoSize from "./AgentLogoSize";
import { Eye, X, ZoomIn, ZoomOut } from "lucide-react";
import { api, Detail, send } from "./api";
import { readProperty } from "./AuctionWorkspace";
import { smallImage } from "./LiveBookletPreview";

// The guide's board or post being prepared (backend generation/marketing):
// its own design with the values as the forms stand, saved or not.
type Preview = {
  html: string;
  page: number;
  pages: { kind: string; item: string }[];
  width_pt: number;
  height_pt: number;
  overflow: { page: number; item: string; field: string }[];
};
type Draft = {
  auction?: Record<string, unknown>;
  agent?: Record<string, unknown>;
  item?: Record<string, unknown>;
  image?: { src: string; category: string; item_id?: string };
};
const ZOOMS = [1, 1.5, 2, 3];

export default function MarketingPreview({
  detail,
  kind,
  config,
  children,
}: {
  detail: Detail;
  kind: "banner" | "social";
  // The template step's choices as they stand (BannerConfig, SocialConfig).
  config: Record<string, unknown>;
  children: ReactNode;
}) {
  const t = useTranslations("liveMarketing"),
    at = useTranslations("auction"),
    bt = useTranslations("banner");
  const [draft, setDraft] = useState<Draft>({});
  const [preview, setPreview] = useState<Preview | null>(null);
  const [page, setPage] = useState<number | null>(null);
  const [updating, setUpdating] = useState(true);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  const [sheet, setSheet] = useState(false);
  const [small, setSmall] = useState(false);
  const [zoom, setZoom] = useState(1);
  // Two frames: the new page loads in the hidden one, then they swap.
  const [frames, setFrames] = useState<[string, string]>(["", ""]);
  const [front, setFront] = useState(0);
  const [scale, setScale] = useState(0.3);
  const shown = useRef<{ frames: [string, string]; front: number }>({
    frames: ["", ""],
    front: 0,
  });
  const pending = useRef<{
    slot: number;
    request: number;
    result: Preview;
  } | null>(null);
  const version = useRef(0);
  const imageVersion = useRef(0);
  const paper = useRef<HTMLDivElement>(null);
  const frameRefs = [
    useRef<HTMLIFrameElement>(null),
    useRef<HTMLIFrameElement>(null),
  ];
  const settings = JSON.stringify(config);
  const pageWidth = ((preview?.width_pt || 800) * 4) / 3;
  const pageHeight = ((preview?.height_pt || 400) * 4) / 3;
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
  // Saved: the stored values are the draft's starting point again.
  useEffect(() => {
    setDraft({});
    imageVersion.current++;
  }, [detail]);
  const widthRef = useRef(pageWidth);
  widthRef.current = pageWidth;
  useEffect(() => {
    const element = paper.current;
    if (!element) return;
    const observer = new ResizeObserver(() =>
      setScale(element.clientWidth / widthRef.current),
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    if (paper.current) setScale(paper.current.clientWidth / pageWidth);
  }, [pageWidth]);
  useEffect(() => {
    const request = ++version.current;
    const controller = new AbortController();
    setUpdating(true);
    setError(false);
    const timer = setTimeout(async () => {
      try {
        const result = await api<Preview>(
          `/projects/${detail.project.id}/marketing-preview`,
          {
            method: "POST",
            signal: controller.signal,
            body: send({ kind, config, page, ...draft }),
          },
        );
        if (request !== version.current) return;
        // A frame already holding this exact page fires no load event.
        const same = shown.current.frames.indexOf(result.html);
        if (same >= 0) {
          pending.current = null;
          setPreview(result);
          setFront(same);
          shown.current.front = same;
          setUpdating(false);
          return;
        }
        const slot = 1 - shown.current.front;
        pending.current = { slot, request, result };
        shown.current.frames[slot] = result.html;
        setFrames([...shown.current.frames] as [string, string]);
      } catch {
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
  }, [detail, draft, page, settings, retry, kind]);
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
    setPreview(job.result);
    setFront(slot);
    shown.current.front = slot;
    setUpdating(false);
  }
  // The forms of the other steps, read as they are typed.
  async function changed(target: HTMLInputElement) {
    const form = target.closest<HTMLFormElement>("form[data-preview-form]");
    if (!form) return;
    const data = new FormData(form);
    const which = form.dataset.previewForm;
    const values = Object.fromEntries(
      [...data].filter(([, v]) => typeof v === "string"),
    );
    if (which === "auction") {
      delete values["cover-choice"];
      setDraft((d) => ({ ...d, auction: values }));
    } else if (which === "agent") {
      setDraft((d) => ({ ...d, agent: values }));
    } else if (which === "item") {
      setPage(null);
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
    }
    const picker =
      target.type === "file"
        ? target
        : form.querySelector<HTMLInputElement>('input[type="file"]');
    const file = picker?.files?.[0];
    if (!file || !["images", "agent", "item"].includes(which || "")) return;
    const category =
      which === "agent"
        ? "agent_logo"
        : which === "item"
          ? picker?.dataset.category || "main"
          : String(data.get("category"));
    // Only the photographs the designs show: the cover, a property's main
    // one, the agent's logo.
    if (!["cover", "main", "agent_logo"].includes(category)) return;
    const item =
      which === "item"
        ? form.dataset.itemId || ""
        : String(data.get("item_id") || "");
    const serial = ++imageVersion.current;
    try {
      const src = await smallImage(file);
      if (serial !== imageVersion.current) return;
      if (category === "main" && !item && which !== "item") return;
      setDraft((d) => ({
        ...d,
        image: { src, category, item_id: item || undefined },
      }));
    } catch {
      setError(true);
    }
  }
  const label = (field: string) =>
    ["headline", "tagline", "court_name"].includes(field)
      ? bt(`fields.${field}`)
      : at(field);
  const overflow = preview?.overflow || [];
  return (
    <div
      className="live-booklet-layout marketing-preview-layout"
      onChange={(e) => void changed(e.target as HTMLInputElement)}
    >
      <div className="live-booklet-fields">{children}</div>
      <button
        type="button"
        className={"preview-open" + (overflow.length ? " warns" : "")}
        aria-expanded={sheet}
        onClick={() => setSheet(true)}
      >
        <Eye size={18} />
        {t("open")}
      </button>
      <aside
        className={"live-booklet-preview" + (sheet ? " open" : "")}
        aria-label={t(kind === "banner" ? "boardTitle" : "postTitle")}
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
          <strong>{t(kind === "banner" ? "boardTitle" : "postTitle")}</strong>
          <span aria-live="polite">
            {error ? t("failed") : updating ? t("updating") : t("current")}
          </span>
        </div>
        <p className="muted">{t("help")}</p>
        {preview && preview.pages.length > 1 && (
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
                <option key={i} value={i}>
                  {i + 1}. {p.item || t("announcement")}
                </option>
              ))}
            </select>
            <button
              type="button"
              disabled={preview.page === preview.pages.length - 1}
              aria-label={t("next")}
              onClick={() => setPage(preview.page + 1)}
            >
              ›
            </button>
          </div>
        )}
        {!!detail.selling_agent?.logo_image_id && (
          <AgentLogoSize
            projectId={detail.project.id}
            kind={kind}
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
              <div className="live-preview-placeholder">
                {error ? t("empty") : t("loading")}
              </div>
            )}
          </div>
        </div>
        {error && preview && (
          <div className="notice error" role="alert">
            {t("retryHelp")}{" "}
            <button type="button" onClick={() => setRetry((v) => v + 1)}>
              {t("retry")}
            </button>
          </div>
        )}
        {!!overflow.length && (
          <div className="notice error" role="alert">
            <p>{t("overflow")}</p>
            <ul>
              {overflow.map((row, i) => (
                <li key={i}>
                  {row.item ? `${row.item}: ` : ""}
                  {label(row.field)}
                </li>
              ))}
            </ul>
          </div>
        )}
        <p className="muted">
          {t(kind === "banner" ? "boardNote" : "postNote")}
        </p>
      </aside>
    </div>
  );
}
