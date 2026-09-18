import LanguageSwitcher from "./LanguageSwitcher";

import { useTranslations } from "next-intl";
import { ArrowRight } from "lucide-react";
import { api, send, Run, Account } from "./api";
export default function Login({
  run,
  setUser,
  refresh,
  error,
  busy,
}: {
  run: Run;
  setUser: (account: Account) => void;
  refresh: () => Promise<void>;
  error: string;
  busy: boolean;
}) {
  const tr = useTranslations();

  return (
    <main className="login">
      <div className="login-language">
        <LanguageSwitcher />
      </div>
      <div className="login-story">
        <div className="brand">
          <span className="brand-symbol">{tr("ui.brand_symbol")}</span>
          {tr("ui.brand_name")}
          <span className="brand-tag">{tr("ui.workspace_upper")}</span>
        </div>
        <div>
          <p className="eyebrow">
            {tr("ui.less_repetition_more_possibility_upper")}
          </p>
          <h1>
            {tr("ui.great_projects")}
            <br />
            {tr("ui.beautifully")}
            <br />
            <em>{tr("ui.delivered")}</em>
          </h1>
          <p>
            {tr("ui.one_workspace_for_your_data_documents")}
            <br />
            {tr("ui.and_everything_ready_for_approval")}
          </p>
        </div>
        <span className="muted">{tr("ui.project_automation_mvp_upper")}</span>
      </div>
      <form
        className="login-form"
        onSubmit={(e) => {
          e.preventDefault();
          const data = Object.fromEntries(new FormData(e.currentTarget));
          void run(async () => {
            const u = await api<Account>("/auth/login", {
              method: "POST",
              body: send(data),
            });
            await refresh();
            setUser(u);
          }, tr("ui.welcome_to_your_workspace"));
        }}
      >
        <span className="eyebrow">{tr("ui.your_work_connected_upper")}</span>
        <h2>{tr("ui.welcome_back")}</h2>
        <p className="muted">
          {tr("ui.sign_in_to_your_administrator_workspace")}
        </p>
        <label>
          {tr("ui.email_address")}
          <input
            name="email"
            type="email"
            dir="ltr"
            autoComplete="username"
            required
            placeholder="name@organization.com"
          />
        </label>
        <label>
          {tr("ui.password")}
          <input
            name="password"
            type="password"
            dir="ltr"
            autoComplete="current-password"
            required
            placeholder={tr("ui.enter_your_password")}
          />
        </label>
        {error && (
          <div className="notice error" role="alert">
            {error}
          </div>
        )}
        <button className="primary" disabled={busy}>
          {busy ? tr("ui.signing_in") : tr("ui.sign_in_to_workspace")}{" "}
          <ArrowRight size={17} />
        </button>
        <small className="muted">{tr("flow.accountHelp")}</small>
      </form>
    </main>
  );
}
