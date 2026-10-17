"use client";
import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { ImagePlus, RotateCcw } from "lucide-react";
import { api, send, Run } from "./api";
import { useImageEditor } from "./ImageEditor";

type Identity = {
  values: Record<string, string>;
  defaults: Record<string, string>;
  has_logo: boolean;
};
const FIELDS = ["title", "text", "phone", "website", "social"] as const;
// Where the guide puts Infath's logo: the frame an uploaded one is placed in.
const LOGO_FRAME = { key: "logo", width: 63.3, height: 47.8 };

// Infath as every booklet shows it: an administrator changes its logo and
// introduction page here, without touching any design. An empty field keeps
// the guide's (shown beneath it).
export default function InfathSettings({ run }: { run: Run }) {
  const t = useTranslations("supervisor");
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [version, setVersion] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const editImages = useImageEditor();
  const load = async () => setIdentity(await api<Identity>("/settings/infath"));
  useEffect(() => {
    void run(load);
  }, []);
  if (!identity) return null;
  const upload = async (picked?: File) => {
    if (!picked) return;
    const edited = await editImages([picked], {
      frames: [LOGO_FRAME],
      title: t("logo"),
      logo: true,
    });
    const file = edited?.[0];
    if (!file) return;
    void run(async () => {
      const body = new FormData();
      body.set("file", file);
      setIdentity(
        await api<Identity>("/settings/infath/logo", { method: "POST", body }),
      );
      setVersion((v) => v + 1);
    }, t("logoSaved"));
  };
  return (
    <form
      className="panel form-panel infath-settings"
      onSubmit={(e) => {
        e.preventDefault();
        const data = Object.fromEntries(new FormData(e.currentTarget));
        void run(async () => {
          setIdentity(
            await api<Identity>("/settings/infath", {
              method: "PUT",
              body: send(data),
            }),
          );
        }, t("saved"));
      }}
    >
      <h2>{t("infathTitle")}</h2>
      <p className="muted">{t("infathHelp")}</p>
      <div className="logo-setting">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={
            identity.has_logo
              ? `/api/settings/infath/logo?v=${version}`
              : "/api/booklet-assets/booklet-art/infath-logo.svg"
          }
          alt={t("logo")}
        />
        <div>
          <strong>{t("logo")}</strong>
          <p className="muted">
            {t(identity.has_logo ? "logoOwn" : "logoGuide")} {t("logoHelp")}
          </p>
          <div className="cover-photo-actions">
            <button
              type="button"
              className="secondary"
              onClick={() => input.current?.click()}
            >
              <ImagePlus size={16} />
              {t(identity.has_logo ? "replaceLogo" : "chooseLogo")}
            </button>
            {identity.has_logo && (
              <button
                type="button"
                className="text-button"
                onClick={() =>
                  void run(async () => {
                    setIdentity(
                      await api<Identity>("/settings/infath/logo", {
                        method: "DELETE",
                      }),
                    );
                  }, t("logoReset"))
                }
              >
                <RotateCcw size={15} />
                {t("resetLogo")}
              </button>
            )}
          </div>
          <input
            ref={input}
            type="file"
            hidden
            aria-label={t("logo")}
            accept="image/png,image/jpeg,image/webp"
            onChange={(e) => {
              void upload(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
        </div>
      </div>
      {FIELDS.map((key) => (
        <label key={key}>
          {t(key)}
          {key === "text" || key === "social" ? (
            <textarea
              name={key}
              rows={key === "text" ? 6 : 2}
              defaultValue={identity.values[key]}
              placeholder={identity.defaults[key]}
            />
          ) : (
            <input
              name={key}
              defaultValue={identity.values[key]}
              placeholder={identity.defaults[key]}
            />
          )}
        </label>
      ))}
      <button className="primary">{t("save")}</button>
    </form>
  );
}
