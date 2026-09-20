"use client";
import { ReactNode, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { api, Detail, send } from "./api";
import { readProperty } from "./AuctionWorkspace";

type Preview = {
  image: string;
  page: number;
  pages: { kind: string; item: string }[];
  fits: boolean;
  text: string;
};
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
  const version = useRef(0);
  const imageVersion = useRef(0);
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    setDraft({});
    setPage(null);
    setFocus(stage);
    imageVersion.current++;
  }, [detail, stage]);
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
        // Decode first: replacing the old image cannot flash an empty page.
        const img = new Image();
        img.src = result.image;
        await img.decode();
        if (request === version.current) setPreview(result);
      } catch (e) {
        if (request === version.current && !controller.signal.aborted)
          setError(true);
      } finally {
        if (request === version.current) setUpdating(false);
      }
    }, 550);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [detail, draft, page, focus, retry]);
  async function changed(target: HTMLInputElement) {
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
                <option key={i} value={i}>
                  {i + 1}. {t.has(p.kind) ? t(p.kind) : p.kind}
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
        <div
          className="live-preview-paper"
          aria-busy={updating}
          data-page-kind={preview?.pages[preview.page]?.kind}
        >
          {preview ? (
            <img
              src={preview.image}
              alt={t("imageAlt", { number: preview.page + 1 })}
            />
          ) : (
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
        {preview && !preview.fits && (
          <p className="notice error" role="alert">
            {t("overflow")}
          </p>
        )}
        <p className="muted">{t("draft")}</p>
      </aside>
    </div>
  );
}
