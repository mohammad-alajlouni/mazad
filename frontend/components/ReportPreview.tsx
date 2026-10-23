"use client";
// The authority's report being prepared, as the form stands (unsaved): the
// template's own page with this auction's values (backend generation/reports).
import React, { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { ZoomIn, ZoomOut } from "lucide-react";
import { api, send } from "./api";

type Preview = {
  html: string;
  page: number;
  pages: { kind: string; item: string }[];
  width_pt: number;
  height_pt: number;
  overflow: { page: number; field: string }[];
};
const ZOOMS = [1, 1.5, 2, 3];

export default function ReportPreview({
  projectId,
  report,
  data,
  version,
}: {
  projectId: string;
  report: "auction_closing" | "outputs_report";
  // The unsaved entries (ReportsInput).
  data: unknown;
  // Changes when the images change (they are stored at once).
  version: number;
}) {
  const t = useTranslations("authorityReports");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [page, setPage] = useState<number | null>(null);
  const [updating, setUpdating] = useState(true);
  const [error, setError] = useState(false);
  const [zoom, setZoom] = useState(1);
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
  const request = useRef(0);
  const paper = useRef<HTMLDivElement>(null);
  const frameRefs = [
    useRef<HTMLIFrameElement>(null),
    useRef<HTMLIFrameElement>(null),
  ];
  const pageWidth = ((preview?.width_pt || 1440) * 4) / 3;
  const pageHeight = ((preview?.height_pt || 810) * 4) / 3;
  const entries = JSON.stringify(data);
  useEffect(() => setPage(null), [report]);
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
    const serial = ++request.current;
    const controller = new AbortController();
    setUpdating(true);
    setError(false);
    const timer = setTimeout(async () => {
      try {
        const result = await api<Preview>(
          `/projects/${projectId}/reports-preview`,
          {
            method: "POST",
            signal: controller.signal,
            body: send({ report, data, page }),
          },
        );
        if (serial !== request.current) return;
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
        pending.current = { slot, request: serial, result };
        shown.current.frames[slot] = result.html;
        setFrames([...shown.current.frames] as [string, string]);
      } catch {
        if (serial === request.current && !controller.signal.aborted) {
          setError(true);
          setUpdating(false);
        }
      }
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [projectId, report, entries, page, version]);
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
    if (job.request !== request.current) return;
    pending.current = null;
    setPreview(job.result);
    setFront(slot);
    shown.current.front = slot;
    setUpdating(false);
  }
  return (
    <aside className="live-booklet-preview" aria-label={t("preview")}>
      <div className="live-preview-heading">
        <strong>{t("preview")}</strong>
        <span aria-live="polite">
          {error ? t("failed") : updating ? t("updating") : t("current")}
        </span>
      </div>
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
                {i + 1}. {t(`pages.${p.kind}`)}
                {p.item ? ` · ${p.item}` : ""}
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
            setZoom(ZOOMS[Math.min(ZOOMS.length - 1, ZOOMS.indexOf(zoom) + 1)])
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
            <div className="live-preview-placeholder">{t("loading")}</div>
          )}
        </div>
      </div>
      {!!preview?.overflow.length && (
        <p className="notice error" role="alert">
          {t("overflow")}
        </p>
      )}
      <p className="muted">{t("draft")}</p>
    </aside>
  );
}
