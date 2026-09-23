import { useTranslations } from "next-intl";
import { Detail } from "./api";
export const dataStages = ["auction", "items", "images"];
// The seller's name and logo come from the account profile but every output
// needs them, so they are part of completing the first (auction) step.
export function missingStage(detail: Detail, before = "generate") {
  const index = dataStages.indexOf(before);
  const stages = detail.workflow?.stages;
  return dataStages
    .slice(0, index < 0 ? dataStages.length : index)
    .find(
      (key) =>
        stages?.[key]?.valid === false ||
        (key === "auction" && stages?.agent?.valid === false),
    );
}
export function AgentReadiness({ detail }: { detail: Detail }) {
  const t = useTranslations("validationFlow");
  const at = useTranslations("auction");
  const agent = detail.workflow?.stages.agent;
  if (!agent || agent.valid !== false) return null;
  return (
    <div className="notice error workflow-problems" role="alert">
      <strong>{t("agentFirst")}</strong>
      <ul>
        {agent.missing.map((issue, index) => (
          <li key={index}>
            {t.has(issue.field)
              ? t(issue.field)
              : at.has(issue.field)
                ? at(issue.field)
                : issue.field}
            {issue.limit ? t("maxLength", { limit: issue.limit }) : ""}
          </li>
        ))}
      </ul>
      <button
        type="button"
        className="text-button"
        onClick={() => window.dispatchEvent(new Event("open-account-profile"))}
      >
        {t("agentFix")}
      </button>
    </div>
  );
}
export function validateForms(root: HTMLElement | null) {
  if (!root) return true;
  for (const form of root.querySelectorAll<HTMLFormElement>(
    "form[data-stage-form]",
  )) {
    for (const el of form.querySelectorAll<
      HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
    >("[required]")) {
      if (!el.value.trim()) {
        el.setCustomValidity("required");
        let node: HTMLElement | null = el.parentElement;
        while (node && node !== form) {
          if (node instanceof HTMLDetailsElement) node.open = true;
          node = node.parentElement;
        }
      }
    }
    if (!form.reportValidity()) return false;
  }
  return true;
}
export type Issue = {
  field: string;
  item?: string | null;
  item_id?: string | null;
  limit?: number | null;
  stage: string;
};
// What a step still needs, from the saved data. The first step also carries the
// selling-agent details, which every output uses.
export function stepIssues(detail: Detail, stage: string): Issue[] {
  const stages = detail.workflow?.stages || {};
  const own = (stages[stage]?.missing || []).map((i) => ({ ...i, stage }));
  if (stage !== "auction") return own;
  return [
    ...(stages.agent?.missing || []).map((i) => ({ ...i, stage: "agent" })),
    ...own,
  ];
}
function IssueLabel({ issue }: { issue: Issue }) {
  const t = useTranslations("validationFlow");
  const at = useTranslations("auction");
  const ft = useTranslations("flow");
  return (
    <>
      {issue.item ? issue.item + ": " : ""}
      {t.has(issue.field)
        ? t(issue.field)
        : at.has(issue.field)
          ? at(issue.field)
          : issue.field === "properties"
            ? ft("properties")
            : issue.field}
      {issue.limit ? t("maxLength", { limit: issue.limit }) : ""}
    </>
  );
}
// Each problem is a link to its field: clicking it opens the step (and the
// property) and focuses the field or image box to fill in.
export function IssueList({
  issues,
  onIssue,
}: {
  issues: Issue[];
  onIssue: (issue: Issue) => void;
}) {
  const t = useTranslations("validationFlow");
  return (
    <ul className="issue-list">
      {issues.map((issue, index) => (
        <li key={index}>
          <button
            type="button"
            className="issue-link"
            onClick={() => onIssue(issue)}
          >
            <IssueLabel issue={issue} />
            <span aria-hidden="true">{t("goTo")}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
export function StepChecklist({
  detail,
  stage,
  onIssue,
}: {
  detail: Detail;
  stage: string;
  onIssue: (issue: Issue) => void;
}) {
  const t = useTranslations("validationFlow");
  if (!["auction", "items", "images"].includes(stage)) return null;
  const issues = stepIssues(detail, stage);
  return issues.length ? (
    <section className="notice step-checklist" aria-label={t("stepNeedsTitle")}>
      <strong>{t("stepNeeds", { count: issues.length })}</strong>
      <IssueList issues={issues} onIssue={onIssue} />
    </section>
  ) : (
    <p className="notice success step-checklist">{t("stepComplete")}</p>
  );
}
export function WorkflowProblems({
  detail,
  stage,
  onIssue,
}: {
  detail: Detail;
  stage?: string | null;
  onIssue?: (issue: Issue) => void;
}) {
  const t = useTranslations("validationFlow");
  if (!stage) return null;
  const issues = stepIssues(detail, stage);
  return (
    <div className="notice error workflow-problems" role="alert">
      <strong>{t("completeFirst")}</strong>
      <p>{t("clickToFix")}</p>
      {onIssue ? (
        <IssueList issues={issues} onIssue={onIssue} />
      ) : (
        <ul>
          {issues.map((issue, index) => (
            <li key={index}>
              <IssueLabel issue={issue} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
