import {
  formatNumber,
  formatTime,
  activityLabel,
  activityDetail,
} from "../i18n/format";
import { useTranslations } from "next-intl";
import {
  FolderOpen,
  Clock3,
  CheckCheck,
  ArrowRight,
  ArrowUpRight,
} from "lucide-react";
import { ProjectList, Empty } from "./shared";
import { Project, Run } from "./api";
export type Dashboard = {
  total_projects: number;
  draft_projects: number;
  approved_outputs: number;
  projects: Project[];
  activity: {
    id: string;
    action: string;
    detail: string;
    created_at: string;
  }[];
};

export default function DashboardView({
  dashboard,
  navigate,
  run,
  openProject,
}: {
  dashboard: Dashboard;
  navigate: (page: "projects") => void;
  run: Run;
  openProject: (id: string) => Promise<void>;
}) {
  const tr = useTranslations();

  return (
    <>
      <div className="metrics">
        {[
          {
            label: tr("ui.total_projects"),
            value: dashboard.total_projects,
            icon: FolderOpen,
            note: tr("ui.all_your_work_organized"),
          },
          {
            label: tr("ui.draft_projects"),
            value: dashboard.draft_projects,
            icon: Clock3,
            note: tr("ui.ready_for_the_next_step"),
          },
          {
            label: tr("ui.approved_outputs"),
            value: dashboard.approved_outputs,
            icon: CheckCheck,
            note: tr("ui.reviewed_and_ready_to_share"),
          },
        ].map((m) => (
          <div className="metric panel" key={m.label}>
            <div className="flex-row">
              <span>{m.label}</span>
              <m.icon size={20} />
            </div>
            <strong>
              {formatNumber(m.value, { minimumIntegerDigits: 2 })}
            </strong>
            <small>{m.note}</small>
          </div>
        ))}
      </div>
      <div className="welcome-banner">
        <div>
          <span className="eyebrow">
            {tr("ui.one_input_eight_possibilities_upper")}
          </span>
          <h2>{tr("ui.your_data_does_the_heavy_lifting")}</h2>
          <p>
            {tr("ui.studies_booklets_banners_and_more")}
            <br />
            {tr("ui.generate_a_complete_set_then_make_it_your_own")}
          </p>
          <button onClick={() => navigate("projects")}>
            {tr("ui.explore_your_projects")}
            <ArrowRight size={16} />
          </button>
        </div>
        <div className="paper-stack" aria-hidden="true">
          <div className="paper back" />
          <div className="paper">
            <div className="paper-mark">a</div>
            <span>{tr("ui.project_booklet_upper")}</span>
            <b>
              {tr("ui.ideas_into")}
              <br />
              {tr("ui.impact")}
            </b>
            <div className="paper-lines" />
            <small>{tr("ui.generated_with_atlas_upper")}</small>
          </div>
          <span className="stack-tag">
            <CheckCheck size={15} />
            {tr("ui.ready_for_review")}
          </span>
        </div>
      </div>
      <div className="dashboard-lower">
        <section className="panel">
          <div className="panel-heading flex-row">
            <h2>
              {tr("ui.recent_projects")}{" "}
              <span className="count">
                {formatNumber(dashboard.projects.length)}
              </span>
            </h2>
            <button
              className="text-button"
              onClick={() => navigate("projects")}
            >
              {tr("ui.view_all")}
              <ArrowUpRight size={14} />
            </button>
          </div>
          <ProjectList
            projects={dashboard.projects}
            onOpen={(id) => void run(() => openProject(id))}
          />
        </section>
        <section className="panel activity">
          <div className="panel-heading">
            <h2>{tr("ui.recent_activity")}</h2>
          </div>
          {dashboard.activity.length ? (
            dashboard.activity.slice(0, 5).map((a) => (
              <div className="activity-entry" key={a.id}>
                <span className="activity-dot" />
                <div>
                  <strong>{activityLabel(a.action)}</strong>
                  <p>{activityDetail(a.action, a.detail)}</p>
                  <small>{formatTime(a.created_at)}</small>
                </div>
              </div>
            ))
          ) : (
            <Empty text={tr("ui.your_project_activity_will_appear_here")} />
          )}
        </section>
      </div>
    </>
  );
}
