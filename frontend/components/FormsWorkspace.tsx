"use client";
// One official form as a section of the project: the authority's auction
// request form or Infath's property study. It is filled from the project's
// data (the auction and its properties) and issued on its own, without the
// booklet or any other output.
import { useRef } from "react";
import { useTranslations } from "next-intl";
import { FileCheck2 } from "lucide-react";
import { api, send, Detail, Output, Run } from "./api";
import { FormsStep } from "./FormsStep";
import LiveBookletPreview from "./LiveBookletPreview";
import { OutputList } from "./shared";

export const FORM_OUTPUTS = {
  request: "auction_request",
  study: "property_study",
} as const;

export default function FormsWorkspace({
  detail,
  form,
  busy,
  run,
  reloadProject,
  setReview,
}: {
  detail: Detail;
  form: keyof typeof FORM_OUTPUTS;
  busy: boolean;
  run: Run;
  reloadProject: () => Promise<void>;
  setReview: (output: Output) => void;
}) {
  const t = useTranslations("forms");
  const root = useRef<HTMLDivElement>(null);
  // Issuing saves the form first, then generates it from the saved values.
  const issuing = useRef(false);
  const type = FORM_OUTPUTS[form];
  const issue = () =>
    void run(async () => {
      const [output] = await api<Output[]>(
        `/projects/${detail.project.id}/generate`,
        {
          method: "POST",
          body: send({
            types: [type],
            output_language: detail.project.auction?.document_language || "ar",
          }),
        },
      );
      await reloadProject();
      setReview(output);
    }, t("issued"));
  return (
    <LiveBookletPreview detail={detail} stage="forms">
      <div ref={root} className="forms-workspace">
        <FormsStep
          key={form}
          detail={detail}
          run={run}
          only={form}
          onSaved={() => {
            if (!issuing.current) return;
            issuing.current = false;
            issue();
          }}
        />
        <section className="panel form-panel">
          <h2>{t("issueTitle", { form: t(form) })}</h2>
          <p className="muted">{t("issueHelp")}</p>
          {!detail.items.length && (
            <p className="notice error">{t("needsProperty")}</p>
          )}
          <button
            type="button"
            className="primary"
            disabled={busy || !detail.items.length}
            onClick={() => {
              issuing.current = true;
              root.current
                ?.querySelector<HTMLFormElement>("form.forms-step")
                ?.requestSubmit();
            }}
          >
            <FileCheck2 size={17} />
            {t("issue", { form: t(form) })}
          </button>
          <OutputList
            outputs={detail.outputs.filter((o) => o.output_type === type)}
            onOpen={setReview}
          />
        </section>
      </div>
    </LiveBookletPreview>
  );
}
