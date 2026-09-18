"use client";
import { useTranslations } from "next-intl";
export type SocialConfig = {
  format: "instagram" | "x" | "story";
  post_kind: "announcement" | "property";
  theme: "white" | "teal" | "navy";
  headline: string;
  tagline: string;
  caption: string;
  property_ids?: string[];
};
export const socialDefaults: SocialConfig = {
  format: "instagram",
  post_kind: "announcement",
  theme: "white",
  headline: "",
  tagline: "",
  caption: "",
};
export default function SocialTemplateFields({
  value,
  onChange,
}: {
  value: SocialConfig;
  onChange: (v: SocialConfig) => void;
}) {
  const t = useTranslations("social");
  return (
    <>
      <div className="banner-template-grid">
        {(["x", "instagram", "story"] as const).map((format) => (
          <article className="banner-template-card" key={format}>
            <h3>{t(`formats.${format}`)}</h3>
            <a
              href={`/social-references/${format}.png`}
              target="_blank"
              rel="noreferrer"
            >
              <img
                src={`/social-references/${format}.png`}
                alt={t(`formats.${format}`)}
              />
            </a>
            <label className="checkbox-label">
              <input
                type="radio"
                name="format"
                value={format}
                checked={value.format === format}
                onChange={() =>
                  onChange({
                    ...value,
                    format,
                    post_kind:
                      format === "story" ? "announcement" : value.post_kind,
                    theme:
                      format !== "story" && value.theme === "navy"
                        ? "white"
                        : value.theme,
                  })
                }
              />
              <bdi>
                1080 × {format === "x" ? 660 : format === "story" ? 1920 : 1080}{" "}
                px
              </bdi>
            </label>
            <p>
              {t("guidePage", {
                page: format === "x" ? 35 : format === "instagram" ? 36 : 37,
              })}
            </p>
          </article>
        ))}
      </div>
      <div className="form-grid">
        <label>
          {t("postKind")}
          <select
            value={value.post_kind}
            onChange={(e) =>
              onChange({
                ...value,
                post_kind: e.target.value as SocialConfig["post_kind"],
              })
            }
          >
            <option value="announcement">{t("announcement")}</option>
            {value.format !== "story" && (
              <option value="property">{t("property")}</option>
            )}
          </select>
        </label>
        <label>
          {t("theme")}
          <select
            value={value.theme}
            onChange={(e) =>
              onChange({
                ...value,
                theme: e.target.value as SocialConfig["theme"],
              })
            }
          >
            {(["white", "teal", "navy"] as const)
              .filter((v) => v !== "navy" || value.format === "story")
              .map((v) => (
                <option key={v} value={v}>
                  {t(`themes.${v}`)}
                </option>
              ))}
          </select>
        </label>
      </div>
      <label>
        {t("headline")}
        <input
          name="headline"
          required
          maxLength={48}
          value={value.headline}
          onChange={(e) => onChange({ ...value, headline: e.target.value })}
        />
      </label>
      <label>
        {t("tagline")}
        <input
          name="tagline"
          maxLength={70}
          value={value.tagline}
          onChange={(e) => onChange({ ...value, tagline: e.target.value })}
        />
      </label>
      <label>
        {t("caption")}
        <textarea
          name="caption"
          maxLength={1500}
          rows={4}
          value={value.caption}
          onChange={(e) => onChange({ ...value, caption: e.target.value })}
        />
      </label>
      <p>{t("captionHelp")}</p>
    </>
  );
}
