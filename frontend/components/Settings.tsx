"use client";
import FileInput from "./FileInput";

import { useTranslations } from "next-intl";
import { api, send, Run } from "./api";
export type Config = {
  branding: {
    organization_name: string;
    primary_color: string;
    default_language: string;
    logo_key: string;
  };
  ai: { available: boolean; model: string; provider: string };
  max_upload_mb: number;
};
export default function Settings({
  config,
  run,
  reload,
}: {
  config: Config;
  run: Run;
  reload: () => Promise<void>;
}) {
  const tr = useTranslations();

  return (
    <div className="settings-grid">
      <form
        className="panel form-panel"
        onSubmit={(e) => {
          e.preventDefault();
          const data = Object.fromEntries(new FormData(e.currentTarget));
          void run(async () => {
            await api("/settings", {
              method: "PUT",
              body: send({ ...data, logo_key: config.branding.logo_key }),
            });
            await reload();
          }, tr("ui.settings_saved"));
        }}
      >
        <h2>{tr("ui.organization_branding")}</h2>
        <label>
          {tr("ui.organization_name")}
          <input
            name="organization_name"
            defaultValue={config.branding.organization_name}
            required
          />
        </label>
        <label>
          {tr("ui.primary_color")}
          <input
            name="primary_color"
            type="color"
            defaultValue={config.branding.primary_color}
          />
        </label>
        <label>
          {tr("ui.document_language")}
          <select
            name="default_language"
            defaultValue={config.branding.default_language}
          >
            <option value="en">{tr("ui.english")}</option>
            <option value="ar">{tr("ui.rtl_upper")}</option>
          </select>
        </label>
        <p className="muted">
          {tr(
            "ui.branding_is_captured_when_an_output_is_generated_regenerate_exist",
          )}
        </p>
        <button className="primary">{tr("ui.save_settings")}</button>
      </form>
      <div>
        <div className="panel form-panel">
          <h2>{tr("ui.organization_logo")}</h2>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const data = new FormData(e.currentTarget);
              void run(async () => {
                await api("/settings/logo", { method: "POST", body: data });
                await reload();
              }, tr("ui.logo_saved"));
            }}
          >
            <label>
              {tr("ui.upload_logo")}
              <FileInput
                aria-label={tr("ui.upload_logo")}
                name="file"
                type="file"
                accept="image/png,image/jpeg,image/webp"
                required
              />
            </label>
            <button className="secondary">{tr("ui.upload_logo")}</button>
          </form>
        </div>
        <div className="panel form-panel">
          <h2>{tr("ui.ai_configuration")}</h2>
          <span
            className={"badge " + (config.ai.available ? "approved" : "draft")}
          >
            {config.ai.available ? tr("ui.configured") : tr("ui.unavailable")}
          </span>
          <p>
            {config.ai.provider} · {config.ai.model}
          </p>
          <p className="muted">
            {tr(
              "ui.set_ai_api_key_ai_model_and_ai_base_url_in_the_server_environment",
            )}
          </p>
        </div>
      </div>
    </div>
  );
}
