"use client";
import { formatNumber, localizeKnownMessage } from "../i18n/format";
import { errorMessage } from "../i18n/errors";

import LanguageSwitcher from "./LanguageSwitcher";

import { useTranslations } from "next-intl";
import Login from "./Login";
import UserManagement from "./UserManagement";
import DashboardView, { Dashboard } from "./Dashboard";
import ProjectWorkspace from "./ProjectWorkspace";
import { useEffect, useState, useCallback } from "react";
import {
  LayoutDashboard,
  FolderOpen,
  Plus,
  Files,
  Settings as SettingsIcon,
  LogOut,
  Search,
  Menu,
  X,
  Users,
} from "lucide-react";
import { api, Project, Output, Detail, Run, Account } from "./api";
import { ProjectList, OutputList, title } from "./shared";
import { ProjectForm } from "./ProjectForms";
import OutputReview from "./OutputReview";
import Settings, { Config } from "./Settings";
type Page =
  | "dashboard"
  | "projects"
  | "create"
  | "outputs"
  | "settings"
  | "project"
  | "users";
export default function Workspace() {
  const tr = useTranslations();

  const [user, setUser] = useState<Account | null>(null),
    [ready, setReady] = useState(false),
    [page, setPage] = useState<Page>("dashboard"),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState(""),
    [error, setError] = useState<unknown>(null),
    [mobile, setMobile] = useState(false);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null),
    [projects, setProjects] = useState<Project[]>([]),
    [outputs, setOutputs] = useState<Output[]>([]),
    [detail, setDetail] = useState<Detail | null>(null),
    [config, setConfig] = useState<Config | null>(null),
    [review, setReview] = useState<Output | null>(null);
  const [tab, setTab] = useState("overview"),
    [query, setQuery] = useState(""),
    [filter, setFilter] = useState("ALL"),
    [types, setTypes] = useState<{ key: string; title: string }[]>([]);
  const refresh = useCallback(async () => {
    const [d, p, o, c, t] = await Promise.all([
      api<Dashboard>("/dashboard"),
      api<Project[]>("/projects"),
      api<Output[]>("/outputs"),
      api<Config>("/settings"),
      api<{ key: string; title: string }[]>("/output-types"),
    ]);
    setDashboard(d);
    setProjects(p);
    setOutputs(o);
    setConfig(c);
    setTypes(t);
  }, []);
  const run: Run = async (fn, success) => {
    setBusy(true);
    setError(null);
    setNotice("");
    try {
      await fn();
      if (success) setNotice(success);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    const expired = () => {
      setUser(null);
      setReview(null);
    };
    window.addEventListener("session-expired", expired);
    api<Account>("/auth/me")
      .then((u) => {
        setUser(u);
        setPage(u.role === "admin" ? "users" : "dashboard");
        return refresh();
      })
      .catch(() => {})
      .finally(() => setReady(true));
    return () => window.removeEventListener("session-expired", expired);
  }, [refresh]);
  useEffect(() => {
    if (notice) {
      const id = setTimeout(() => setNotice(""), 5000);
      return () => clearTimeout(id);
    }
  }, [notice]);
  const openProject = async (id: string) => {
    const next = await api<Detail>("/projects/" + id);
    setDetail(next);
    setPage("project");
    const a = next.project.auction || {};
    setTab(
      !a.auction_name ||
        !(a.auction_date || a.auction_start_date) ||
        !a.start_time
        ? "auction"
        : !next.selling_agent?.name
          ? "agent"
          : !next.items.length ||
              next.items.some(
                (i) =>
                  !i.property_data?.property_type || !i.property_data?.city,
              )
            ? "items"
            : next.outputs.some((o) => o.output_type === "project_booklet")
              ? "outputs"
              : "generate",
    );
    setReview(null);
  };
  const reloadProject = async () => {
    if (detail) setDetail(await api<Detail>("/projects/" + detail.project.id));
    await refresh();
  };
  const navigate = (next: Page) => {
    setPage(next);
    setReview(null);
    setMobile(false);
    setQuery("");
    void run(refresh);
  };
  if (!ready)
    return (
      <div className="startup">
        <div className="brand-symbol">a</div>
        <p>{tr("ui.opening_your_workspace")}</p>
      </div>
    );
  if (!user)
    return (
      <Login
        run={run}
        setUser={(account) => {
          setUser(account);
          setPage(account.role === "admin" ? "users" : "dashboard");
        }}
        refresh={refresh}
        error={error ? errorMessage(error) : ""}
        busy={busy}
      />
    );
  const heading: Record<Page, [string, string]> = {
    users: [tr("flow.adminHome"), tr("flow.usersHelp")],
    dashboard: [
      tr("ui.your_workspace_at_a_glance"),
      tr("ui.turn_project_data_into_polished_approved_deliverables"),
    ],
    projects: [
      tr("ui.a_home_for_every_project"),
      tr("ui.organize_your_data_and_keep_every_deliverable_moving"),
    ],
    create: [
      tr("ui.create_a_project"),
      tr("ui.start_with_the_essentials_add_your_data_when_you_re_ready"),
    ],
    outputs: [
      tr("ui.from_draft_to_done"),
      tr("ui.review_refine_and_approve_your_generated_deliverables"),
    ],
    settings: [
      tr("ui.make_it_yours"),
      tr("ui.manage_your_organization_branding_and_generation_settings"),
    ],
    project: [
      detail?.project.name || tr("ui.project"),
      tr("ui.one_source_of_truth_for_every_output"),
    ],
  };
  return (
    <div className="app-shell">
      <aside className={"sidebar " + (mobile ? "open" : "")}>
        <div className="brand">
          <span className="brand-symbol">a</span>atlas
          <span className="brand-tag">{tr("ui.workspace_upper")}</span>
        </div>
        <p className="nav-label">{tr("flow.authorArea")}</p>
        <nav>
          {(
            [
              {
                id: "dashboard",
                label: tr("ui.overview"),
                icon: LayoutDashboard,
              },
              { id: "projects", label: tr("ui.projects"), icon: FolderOpen },
              { id: "create", label: tr("ui.create_project"), icon: Plus },
              { id: "outputs", label: tr("ui.outputs"), icon: Files },
            ] as const
          ).map((n) => (
            <button
              key={n.id}
              className={
                page === n.id || (n.id === "projects" && page === "project")
                  ? "active"
                  : ""
              }
              onClick={() => navigate(n.id)}
            >
              <n.icon size={19} />
              {n.label}
              {n.id === "projects" && (
                <span className="nav-count">
                  {formatNumber(projects.length)}
                </span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="workspace-note">
            <span className="tiny-dot" />
            {tr("ui.your_next_great_project")}
            <br />
            <strong>{tr("ui.starts_with_good_data")}</strong>
          </div>
          {user.role === "admin" && (
            <>
              <p className="nav-label">{tr("flow.adminArea")}</p>
              <button
                className={page === "users" ? "active" : ""}
                onClick={() => navigate("users")}
              >
                <Users size={18} />
                {tr("flow.users")}
              </button>
              <button
                className={page === "settings" ? "active" : ""}
                onClick={() => navigate("settings")}
              >
                <SettingsIcon size={18} />
                {tr("ui.settings")}
              </button>
            </>
          )}
          <div className="account">
            <div className="avatar">{user.email.slice(0, 2).toUpperCase()}</div>
            <div>
              <strong>
                {tr(user.role === "admin" ? "flow.adminRole" : "flow.userRole")}
              </strong>
              <small title={user.email} dir="ltr">
                {user.email}
              </small>
            </div>
            <button
              aria-label={tr("ui.log_out")}
              onClick={() =>
                void run(async () => {
                  await api("/auth/logout", { method: "POST" });
                  setUser(null);
                  setReview(null);
                })
              }
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <button
            className="mobile-menu"
            onClick={() => setMobile(!mobile)}
            aria-label={tr("ui.toggle_navigation")}
          >
            <Menu />
          </button>
          <div className="breadcrumbs">
            {tr("ui.workspace")}
            <span>/</span>{" "}
            <strong>
              {page === "users"
                ? tr("flow.users")
                : page === "dashboard"
                  ? tr("flow.home")
                  : title(page)}
            </strong>
          </div>
          <div className="topbar-right">
            <LanguageSwitcher />
            <span className="environment">
              <i />
              {tr(user.role === "admin" ? "flow.adminRole" : "flow.userRole")}
            </span>
            <div className="avatar small">
              {user.email.slice(0, 2).toUpperCase()}
            </div>
          </div>
        </header>
        <main className="main-content" aria-busy={busy}>
          {!!error && (
            <div role="alert" className="toast error">
              {errorMessage(error)}
              <button
                aria-label={tr("ui.dismiss_error")}
                onClick={() => setError(null)}
              >
                <X size={16} />
              </button>
            </div>
          )}
          {notice && (
            <div role="status" className="toast success">
              {localizeKnownMessage(notice)}
            </div>
          )}
          {busy && <div className="loading-line" />}
          {review ? (
            <OutputReview
              key={review.id}
              output={review}
              run={run}
              onChange={(o) => {
                setReview(o);
                void reloadProject();
              }}
              onClose={() => setReview(null)}
            />
          ) : (
            <>
              <div className="section-heading">
                <div>
                  <p className="eyebrow">
                    {page === "dashboard"
                      ? tr("ui.project_automation_upper")
                      : page === "project"
                        ? detail?.project.code
                        : tr("ui.your_workspace_upper")}
                  </p>
                  <h1>{heading[page][0]}</h1>
                  <p>{heading[page][1]}</p>
                </div>
                {["dashboard", "projects"].includes(page) && (
                  <button
                    className="primary"
                    onClick={() => navigate("create")}
                  >
                    <Plus size={17} />
                    {tr("ui.create_project")}
                  </button>
                )}
              </div>
              {page === "dashboard" && dashboard && (
                <DashboardView
                  dashboard={dashboard}
                  navigate={navigate}
                  run={run}
                  openProject={openProject}
                />
              )}
              {page === "projects" && (
                <section className="panel">
                  <div className="panel-heading flex-row">
                    <h2>
                      {tr("ui.all_projects")}{" "}
                      <span className="count">
                        {formatNumber(projects.length)}
                      </span>
                    </h2>
                    <label className="search">
                      <Search size={16} />
                      <input
                        aria-label={tr("ui.search_projects")}
                        placeholder={tr("ui.search_projects_2")}
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                      />
                    </label>
                  </div>
                  <ProjectList
                    projects={projects.filter((p) =>
                      (p.name + " " + p.code + " " + p.customer)
                        .toLowerCase()
                        .includes(query.toLowerCase()),
                    )}
                    onOpen={(id) => void run(() => openProject(id))}
                  />
                </section>
              )}
              {page === "create" && (
                <ProjectForm
                  run={run}
                  onDone={(id) => {
                    void openProject(id);
                    void refresh();
                  }}
                />
              )}
              {page === "outputs" && (
                <>
                  <div className="filter-row">
                    <div className="tabs">
                      {["ALL", "DRAFT", "APPROVED", "NEEDS_REGENERATION"].map(
                        (f) => (
                          <button
                            key={f}
                            className={filter === f ? "selected" : ""}
                            onClick={() => setFilter(f)}
                          >
                            {title(f)}
                          </button>
                        ),
                      )}
                    </div>
                  </div>
                  <OutputList
                    outputs={outputs.filter(
                      (o) => filter === "ALL" || o.status === filter,
                    )}
                    onOpen={setReview}
                  />
                </>
              )}
              {page === "users" && user.role === "admin" && (
                <UserManagement run={run} busy={busy} />
              )}
              {page === "settings" && user.role === "admin" && config && (
                <Settings config={config} run={run} reload={refresh} />
              )}
              {page === "project" && detail && (
                <ProjectWorkspace
                  key={detail.project.id}
                  detail={detail}
                  config={config}
                  types={types}
                  busy={busy}
                  run={run}
                  tab={tab}
                  setTab={setTab}
                  reloadProject={reloadProject}
                  setReview={setReview}
                />
              )}
            </>
          )}
          <footer className="workspace-footer">
            <span>{tr("ui.atlas_workspace_upper")}</span>
            <span>{tr("ui.thoughtfully_organized_ready_for_what_s_next")}</span>
          </footer>
        </main>
      </div>
      {busy && (
        <div className="busy-indicator" role="status">
          {tr("ui.working")}
        </div>
      )}
    </div>
  );
}
