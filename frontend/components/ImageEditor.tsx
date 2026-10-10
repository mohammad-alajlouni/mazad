"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useTranslations } from "next-intl";
import { Minus, Plus, RotateCcw } from "lucide-react";

// A frame a photograph is shown in: its size fixes the proportions.
export type Frame = { key: string; width: number; height: number };
// A logo is shown whole to begin with and keeps its transparency.
type Options = { frames: Frame[]; title: string; logo?: boolean };
type Job = Options & {
  files: File[];
  at: number;
  done: File[];
  resolve: (files: File[] | null) => void;
};

const Context = createContext<
  (files: File[], options: Options) => Promise<File[] | null>
>(async (files) => files);
// Photographs are placed in their frame before they are stored: the returned
// files are cut to the frame, or null when the author cancelled.
export const useImageEditor = () => useContext(Context);

// Hands an input the edited files in place of the picked ones, and tells
// whoever shows or previews them (see FileInput and LiveBookletPreview).
export function setInputFiles(input: HTMLInputElement, files: File[]) {
  const list = new DataTransfer();
  for (const file of files) list.items.add(file);
  input.files = list.files;
  input.dispatchEvent(new Event("files-set", { bubbles: true }));
  input.dispatchEvent(new Event("preview-form", { bubbles: true }));
}

const MAX_ZOOM = 4;
const OUTPUT = 2400; // widest stored cut, in pixels
const LOGO_OUTPUT = 1600;

// Whether a picture has see-through parts (looked at in a small copy).
function seeThrough(image: HTMLImageElement) {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 64;
  const context = canvas.getContext("2d", { willReadFrequently: true })!;
  context.drawImage(image, 0, 0, 64, 64);
  const pixels = context.getImageData(0, 0, 64, 64).data;
  for (let i = 3; i < pixels.length; i += 4) if (pixels[i] < 250) return true;
  return false;
}

export function ImageEditorProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const t = useTranslations("imageEditor");
  const [job, setJob] = useState<Job | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const picture = useRef<HTMLImageElement>(null);
  // The loaded picture's own size, kept with its source so a picture still
  // loading is never taken for the one before it.
  const [loaded, setLoaded] = useState<{
    source: string;
    size: [number, number];
    clear: boolean;
  } | null>(null);
  const [frame, setFrame] = useState<Frame | null>(null);
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState<[number, number]>([0, 0]);
  const [room, setRoom] = useState<[number, number]>([560, 440]);

  const file = job?.files[job.at];
  const source = useMemo(() => (file ? URL.createObjectURL(file) : ""), [file]);
  useEffect(() => () => URL.revokeObjectURL(source), [source]);
  useEffect(() => {
    if (!job) return;
    dialog.current?.showModal();
    const measure = () =>
      setRoom([
        Math.min(560, innerWidth - 72),
        Math.max(180, Math.min(440, innerHeight - 330)),
      ]);
    measure();
    addEventListener("resize", measure);
    return () => removeEventListener("resize", measure);
  }, [job]);
  const natural = loaded && loaded.source === source ? loaded.size : null;
  // A new picture starts whole in view, in the frame that suits it.
  useEffect(() => {
    setZoom(1);
    setOffset([0, 0]);
    setFrame(job?.frames[0] || null);
  }, [file]);

  // The frame on screen, and the picture's size in it at each zoom.
  const aspect = frame ? frame.width / frame.height : 1;
  const view: [number, number] =
    room[0] / aspect <= room[1]
      ? [room[0], room[0] / aspect]
      : [room[1] * aspect, room[1]];
  const cover = natural
    ? Math.max(view[0] / natural[0], view[1] / natural[1])
    : 1;
  const whole = natural
    ? Math.min(view[0] / natural[0], view[1] / natural[1]) / cover
    : 1;
  const shown: [number, number] = natural
    ? [natural[0] * cover * zoom, natural[1] * cover * zoom]
    : view;
  // The picture never leaves a gap on one side only: it is centred on an
  // axis it does not fill, and held to the frame's edges on one it does.
  const held = (value: number, axis: 0 | 1, size = shown) => {
    const spare = Math.max(0, (size[axis] - view[axis]) / 2);
    return Math.max(-spare, Math.min(spare, value));
  };
  const place: [number, number] = [held(offset[0], 0), held(offset[1], 1)];
  const zoomTo = (next: number) =>
    setZoom(Math.max(whole, Math.min(MAX_ZOOM, next)));

  // Dragging moves the picture; two fingers or the wheel change its size.
  const pointers = useRef(new Map<number, [number, number]>());
  const pinch = useRef(0);
  useEffect(() => {
    const element = stage.current;
    if (!element || !job) return;
    const wheel = (event: WheelEvent) => {
      event.preventDefault();
      setZoom((z) =>
        Math.max(whole, Math.min(MAX_ZOOM, z * Math.exp(-event.deltaY / 600))),
      );
    };
    element.addEventListener("wheel", wheel, { passive: false });
    return () => element.removeEventListener("wheel", wheel);
  }, [job, whole]);

  const finish = (files: File[] | null) => {
    dialog.current?.close();
    job?.resolve(files);
    setJob(null);
  };
  const apply = async () => {
    if (!job || !file || !natural || !frame || !picture.current) return;
    // The frame at the picture's own resolution, no wider than OUTPUT.
    const width = Math.round(
      Math.min(
        job.logo ? LOGO_OUTPUT : OUTPUT,
        Math.max(600, view[0] / (cover * zoom)),
      ),
    );
    const k = width / view[0];
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = Math.round(width / aspect);
    const context = canvas.getContext("2d")!;
    // A picture shown smaller than its frame stands on white; a see-through
    // logo keeps nothing behind it.
    const clear = !!job.logo && !!loaded?.clear;
    if (!clear) {
      context.fillStyle = "#fff";
      context.fillRect(0, 0, canvas.width, canvas.height);
    }
    context.imageSmoothingQuality = "high";
    context.drawImage(
      picture.current,
      (view[0] / 2 + place[0] - shown[0] / 2) * k,
      (view[1] / 2 + place[1] - shown[1] / 2) * k,
      shown[0] * k,
      shown[1] * k,
    );
    // Logos stay PNG (flat colour, transparency); photographs are JPEG.
    const type = job.logo ? "image/png" : "image/jpeg";
    const blob = await new Promise<Blob | null>((done) =>
      canvas.toBlob(done, type, 0.92),
    );
    if (!blob) return;
    const cut = new File(
      [blob],
      file.name.replace(/\.[^.]*$/, "") + (job.logo ? ".png" : ".jpg"),
      { type },
    );
    const done = [...job.done, cut];
    if (job.at + 1 < job.files.length) setJob({ ...job, at: job.at + 1, done });
    else finish(done);
  };

  return (
    <Context.Provider
      value={(files, options) =>
        new Promise((resolve) => {
          if (!files.length || !options.frames.length) resolve(files);
          else setJob({ ...options, files, at: 0, done: [], resolve });
        })
      }
    >
      {children}
      <dialog
        ref={dialog}
        className="image-editor"
        aria-labelledby="image-editor-title"
        onCancel={(event) => {
          event.preventDefault();
          finish(null);
        }}
      >
        {job && frame && (
          <>
            <h2 id="image-editor-title">{job.title}</h2>
            <p className="muted">
              {t(job.logo ? "helpLogo" : "help")}
              {job.files.length > 1 &&
                " " +
                  t("count", { number: job.at + 1, total: job.files.length })}
            </p>
            {job.frames.length > 1 && (
              <div
                className="frame-choice"
                role="group"
                aria-label={t("shape")}
              >
                {job.frames.map((option) => (
                  <button
                    key={option.key}
                    type="button"
                    aria-pressed={option.key === frame.key}
                    className={option.key === frame.key ? "selected" : ""}
                    onClick={() => {
                      setFrame(option);
                      setZoom(1);
                      setOffset([0, 0]);
                    }}
                  >
                    {t("frame." + option.key)}
                  </button>
                ))}
              </div>
            )}
            <div
              ref={stage}
              className={job.logo ? "editor-stage logo" : "editor-stage"}
              tabIndex={0}
              aria-label={t("stage")}
              style={{ width: view[0], height: view[1] }}
              onPointerDown={(event) => {
                event.currentTarget.setPointerCapture(event.pointerId);
                pointers.current.set(event.pointerId, [
                  event.clientX,
                  event.clientY,
                ]);
                pinch.current = 0;
              }}
              onPointerMove={(event) => {
                const last = pointers.current.get(event.pointerId);
                if (!last) return;
                pointers.current.set(event.pointerId, [
                  event.clientX,
                  event.clientY,
                ]);
                if (pointers.current.size === 2) {
                  const [a, b] = [...pointers.current.values()];
                  const apart = Math.hypot(a[0] - b[0], a[1] - b[1]);
                  if (pinch.current) zoomTo((zoom * apart) / pinch.current);
                  pinch.current = apart;
                  return;
                }
                setOffset([
                  place[0] + event.clientX - last[0],
                  place[1] + event.clientY - last[1],
                ]);
              }}
              onPointerUp={(event) => pointers.current.delete(event.pointerId)}
              onPointerCancel={(event) =>
                pointers.current.delete(event.pointerId)
              }
              onKeyDown={(event) => {
                const step = event.shiftKey ? 40 : 10;
                const move: Record<string, [number, number]> = {
                  ArrowLeft: [-step, 0],
                  ArrowRight: [step, 0],
                  ArrowUp: [0, -step],
                  ArrowDown: [0, step],
                };
                if (move[event.key]) {
                  event.preventDefault();
                  setOffset([
                    place[0] + move[event.key][0],
                    place[1] + move[event.key][1],
                  ]);
                } else if (event.key === "+" || event.key === "=") {
                  zoomTo(zoom * 1.1);
                } else if (event.key === "-") zoomTo(zoom / 1.1);
              }}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                ref={picture}
                src={source}
                alt=""
                draggable={false}
                onLoad={(event) => {
                  const image = event.currentTarget;
                  const size: [number, number] = [
                    image.naturalWidth,
                    image.naturalHeight,
                  ];
                  setLoaded({ source, size, clear: seeThrough(image) });
                  // A logo starts whole inside its frame.
                  if (job.logo) {
                    const fit = [view[0] / size[0], view[1] / size[1]];
                    setZoom(Math.min(...fit) / Math.max(...fit));
                  }
                  // With a choice of frames, start in the picture's own shape.
                  if (job.frames.length > 1)
                    setFrame(
                      job.frames.find(
                        (f) => f.width > f.height === size[0] >= size[1],
                      ) || job.frames[0],
                    );
                }}
                style={{
                  width: shown[0],
                  height: shown[1],
                  left: view[0] / 2 + place[0] - shown[0] / 2,
                  top: view[1] / 2 + place[1] - shown[1] / 2,
                  visibility: natural ? "visible" : "hidden",
                }}
              />
            </div>
            <div className="editor-zoom">
              <button
                type="button"
                className="icon-button"
                aria-label={t("smaller")}
                title={t("smaller")}
                onClick={() => zoomTo(zoom / 1.15)}
              >
                <Minus size={16} />
              </button>
              <input
                type="range"
                aria-label={t("size")}
                min={whole}
                max={MAX_ZOOM}
                step={0.01}
                value={zoom}
                onChange={(event) => zoomTo(Number(event.target.value))}
              />
              <button
                type="button"
                className="icon-button"
                aria-label={t("larger")}
                title={t("larger")}
                onClick={() => zoomTo(zoom * 1.15)}
              >
                <Plus size={16} />
              </button>
              <button
                type="button"
                className="text-button"
                onClick={() => {
                  setZoom(job.logo ? whole : 1);
                  setOffset([0, 0]);
                }}
              >
                <RotateCcw size={14} />
                {t("reset")}
              </button>
            </div>
            <div className="actions">
              <button
                type="button"
                className="secondary"
                onClick={() => finish(null)}
              >
                {t("cancel")}
              </button>
              <button
                type="button"
                className="primary"
                disabled={!natural}
                onClick={() => void apply()}
              >
                {t(job.logo ? "applyLogo" : "apply")}
              </button>
            </div>
          </>
        )}
      </dialog>
    </Context.Provider>
  );
}
