"use client";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api, Run } from "./api";
import { Fields } from "./AuctionWorkspace";
import FileInput from "./FileInput";

type Profile = {
  values: Record<string, unknown>;
  has_logo: boolean;
  complete: boolean;
};
export default function AccountProfile({
  run,
  busy,
  onboarding = false,
  onSaved,
}: {
  run: Run;
  busy: boolean;
  onboarding?: boolean;
  onSaved: () => Promise<void>;
}) {
  const t = useTranslations("accountProfile");
  const a = useTranslations("auction");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    setFailed(false);
    api<Profile>("/account/profile")
      .then((p) => {
        if (active) setProfile(p);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, [retry]);
  return (
    <section className="panel form-panel account-profile">
      <h2>{t(onboarding ? "welcome" : "title")}</h2>
      <p>{t(onboarding ? "intro" : "help")}</p>
      {failed ? (
        <div role="alert">
          <p>{t("failed")}</p>
          <button onClick={() => setRetry((v) => v + 1)}>{t("retry")}</button>
        </div>
      ) : !profile ? (
        <p>{t("loading")}</p>
      ) : (
        <form
          onInput={(event) =>
            (event.target as HTMLInputElement).value?.trim() &&
            (event.target as HTMLInputElement).setCustomValidity?.("")
          }
          onSubmit={(event) => {
            event.preventDefault();
            const form = new FormData(event.currentTarget);
            const payload = new FormData();
            payload.append(
              "data",
              JSON.stringify(
                Object.fromEntries([...form].filter(([key]) => key !== "file")),
              ),
            );
            const file = form.get("file");
            if (file instanceof File && file.size) payload.append("file", file);
            void run(async () => {
              const saved = await api<Profile>("/account/profile", {
                method: "PUT",
                body: payload,
              });
              setProfile(saved);
              setRetry((v) => v + 1);
              await onSaved();
            }, t("saved"));
          }}
        >
          <Fields
            fields={["name", "description", "phone"]}
            requiredFields={["name", "description", "phone"]}
            values={profile.values}
          />
          <label>
            {a("agent_logo")} *
            {profile.has_logo && (
              <img
                className="account-profile-logo"
                src={`/api/account/profile/logo?v=${retry}`}
                alt={a("agent_logo")}
              />
            )}
            <FileInput
              key={retry}
              name="file"
              required={!profile.has_logo}
              accept="image/png,image/jpeg,image/webp"
            />
          </label>
          <details>
            <summary>{t("optional")}</summary>
            <Fields
              fields={[
                "website",
                "whatsapp",
                "contact_information",
                "social_accounts",
              ]}
              values={profile.values}
            />
          </details>
          {!onboarding && <p className="muted">{t("updateHelp")}</p>}
          <button className="primary" disabled={busy}>
            {t(onboarding ? "continue" : "save")}
          </button>
        </form>
      )}
    </section>
  );
}
