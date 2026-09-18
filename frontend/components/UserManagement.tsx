"use client";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api, send, Run } from "./api";
import { useConfirm } from "./Confirmation";

type ManagedUser = {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
};
export default function UserManagement({
  run,
  busy,
}: {
  run: Run;
  busy: boolean;
}) {
  const t = useTranslations();
  const confirm = useConfirm();
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const load = async () => setUsers(await api<ManagedUser[]>("/admin/users"));
  useEffect(() => {
    void run(load);
  }, []);
  return (
    <div className="admin-grid">
      <form
        className="panel form-panel"
        onSubmit={(event) => {
          event.preventDefault();
          const form = event.currentTarget;
          const values = Object.fromEntries(new FormData(form));
          void run(async () => {
            await api("/admin/users", { method: "POST", body: send(values) });
            form.reset();
            await load();
          }, t("flow.created"));
        }}
      >
        <h2>{t("flow.newUser")}</h2>
        <p className="muted">{t("flow.accountScope")}</p>
        <label>
          {t("ui.email_address")}
          <input
            name="email"
            type="email"
            dir="ltr"
            required
            maxLength={255}
            autoComplete="off"
          />
        </label>
        <label>
          {t("ui.password")}
          <input
            name="password"
            type="password"
            dir="ltr"
            required
            minLength={12}
            maxLength={128}
            autoComplete="new-password"
          />
        </label>
        <p className="muted">{t("flow.passwordHelp")}</p>
        <button className="primary" disabled={busy}>
          {t("flow.createUser")}
        </button>
      </form>
      <section className="panel form-panel">
        <h2>{t("flow.users")}</h2>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{t("ui.email_address")}</th>
                <th>{t("flow.role")}</th>
                <th>{t("flow.accountStatus")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td>
                    <bdi>{user.email}</bdi>
                  </td>
                  <td>
                    {t(
                      user.role === "admin"
                        ? "flow.adminRole"
                        : "flow.userRole",
                    )}
                  </td>
                  <td>{t(user.is_active ? "flow.active" : "flow.inactive")}</td>
                  <td>
                    {user.role !== "admin" && (
                      <button
                        className="text-button"
                        disabled={busy}
                        onClick={async () => {
                          if (
                            user.is_active &&
                            !(await confirm(
                              t("flow.disable") + " — " + user.email + "؟",
                            ))
                          )
                            return;
                          void run(async () => {
                            await api(`/admin/users/${user.id}`, {
                              method: "PATCH",
                              body: send({ is_active: !user.is_active }),
                            });
                            await load();
                          });
                        }}
                      >
                        {t(user.is_active ? "flow.disable" : "flow.enable")}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
