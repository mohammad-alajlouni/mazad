import { useTranslations } from "next-intl";
import { Detail } from "./api";
export const dataStages = ["auction", "agent", "items", "images"];
export function missingStage(detail: Detail, before = "generate") {
  const index = dataStages.indexOf(before);
  return dataStages
    .slice(0, index < 0 ? 4 : index)
    .find((key) => detail.workflow?.stages[key]?.valid === false);
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
