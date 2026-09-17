import { useTranslations } from "next-intl";
import { ArrowUpRight, FolderOpen, FileText } from "lucide-react";
import { Project, Output } from "./api";
export { systemLabel as title, formatDate as date } from "../i18n/format";
import { systemLabel as title, formatDate as date } from "../i18n/format";
export function Badge({ status }: { status: string }) {
  const tr = useTranslations();

  return (
    <span className={"badge " + status.toLowerCase()}>
      <i />
      {title(status)}
    </span>
  );
}
export function Empty({ text }: { text: string }) {
  const tr = useTranslations();

  return (
    <div className="empty">
      <FolderOpen size={30} />
      <p>{text}</p>
    </div>
  );
}
export function ProjectList({
  projects,
  onOpen,
}: {
  projects: Project[];
  onOpen: (id: string) => void;
}) {
  const tr = useTranslations();

  return projects.length ? (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>{tr("ui.project")}</th>
            <th>{tr("ui.client_entity")}</th>
            <th>{tr("ui.created")}</th>
            <th>{tr("ui.status")}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {projects.map((p) => (
            <tr
              key={p.id}
              onClick={() => onOpen(p.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onOpen(p.id);
                }
              }}
              tabIndex={0}
              aria-label={tr("common.openProject", { name: p.name })}
              className="clickable"
            >
              <td>
                <div className="project-cell">
                  <span className="project-icon">
                    <FolderOpen size={19} />
                  </span>
                  <span>
                    <strong>
                      <bdi>{p.name}</bdi>
                    </strong>
                    <small dir="ltr">{p.code}</small>
                  </span>
                </div>
              </td>
              <td>
                <bdi>{p.customer || "—"}</bdi>
              </td>
              <td>{date(p.created_at)}</td>
              <td>
                <Badge status={p.status} />
              </td>
              <td>
                <ArrowUpRight size={17} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : (
    <Empty text={tr("ui.create_your_first_project_to_get_started")} />
  );
}
export function OutputList({
  outputs,
  onOpen,
}: {
  outputs: Output[];
  onOpen: (o: Output) => void;
}) {
  const tr = useTranslations();

  return outputs.length ? (
    <div className="output-grid">
      {outputs.map((o) => (
        <button className="output-card" key={o.id} onClick={() => onOpen(o)}>
          <div className="flex-row">
            <span className="project-icon">
              <FileText size={20} />
            </span>
            <Badge status={o.status} />
          </div>
          <h3>{title(o.output_type)}</h3>
          <p>{o.project_name}</p>
          <div className="output-footer">
            <span>{date(o.created_at)}</span>
            <ArrowUpRight size={17} />
          </div>
        </button>
      ))}
    </div>
  ) : (
    <Empty
      text={tr("ui.generated_drafts_will_appear_here_ready_for_your_review")}
    />
  );
}
