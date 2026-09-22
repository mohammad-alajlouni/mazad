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
export function WorkflowProblems({
  detail,
  stage,
  onFix,
}: {
  detail: Detail;
  stage?: string | null;
  onFix?: (stage: string) => void;
}) {
  const t = useTranslations("validationFlow");
  const at = useTranslations("auction");
  const ft = useTranslations("flow");
  if (!stage) return null;
  const issues = detail.workflow?.stages[stage]?.missing || [];
  return (
    <div className="notice error workflow-problems" role="alert">
      <strong>{t("completeFirst")}</strong>
      <p>{t("saveFirst")}</p>
      <ul>
        {issues.map((issue, index) => (
          <li key={index}>
            {issue.item ? issue.item + ": " : ""}
            {at.has(issue.field)
              ? at(issue.field)
              : issue.field === "properties"
                ? ft("properties")
                : t.has(issue.field)
                  ? t(issue.field)
                  : issue.field}
            {issue.limit ? t("maxLength", { limit: issue.limit }) : ""}
          </li>
        ))}
      </ul>
      {onFix && (
        <button
          type="button"
          className="text-button"
          onClick={() => onFix(stage)}
        >
          {t("fix")}
        </button>
      )}
    </div>
  );
}
