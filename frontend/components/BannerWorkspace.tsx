"use client";
import { useEffect, useState, useRef } from "react";
import { useTranslations } from "next-intl";
import {
  api,
  send,
  type Detail,
  type Item,
  type Output,
  type Project,
  type Run,
} from "./api";
import { AuctionWorkspace } from "./AuctionWorkspace";
import { ItemForm, ExcelUpload, ImageUpload } from "./ProjectForms";
import { OutputList } from "./shared";
import SocialTemplateFields, {
  socialDefaults,
  type SocialConfig,
} from "./SocialTemplateFields";
import {
  missingStage,
  validateForms,
  WorkflowProblems,
} from "./workflowValidation";
import { useConfirm } from "./Confirmation";

type Template = {
  id: string;
  layout: string;
  width_mm: number;
  height_mm: number;
  preview: string;
};
type Review = {
  valid: boolean;
  count: number;
  missing: {
    field: string;
    section: string;
    item: string | null;
    limit?: number;
  }[];
};
export function BannerCreate({
  run,
  onDone,
  mode = "banner",
}: {
  run: Run;
  onDone: (id: string) => void;
  mode?: "banner" | "social";
}) {
  const t = useTranslations(mode);
  return (
    <form
      className="panel form-panel"
      onSubmit={(event) => {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        void run(async () => {
          const p = await api<Project>("/projects", {
            method: "POST",
            body: send({
              name: form.get("name"),
              code: form.get("code"),
              workspace_type: mode === "social" ? "social" : "banners",
              auction: {
                auction_name: form.get("name"),
                auction_type: "physical",
                document_language: "ar",
              },
            }),
          });
          onDone(p.id);
        });
      }}
    >
      <h2>{t("create")}</h2>
      <p>{t("independent")}</p>
      <label>
        {t("campaignName")}
        <input name="name" required maxLength={200} />
      </label>
      <label>
        {t("reference")}
        <input name="code" dir="ltr" required maxLength={100} />
      </label>
      <button className="primary">{t("create")}</button>
    </form>
  );
}
export default function BannerWorkspace({
  detail,
  run,
  reloadProject,
  setReview,
  busy,
  mode = "banner",
  shared = false,
  onSharedFix,
}: {
  shared?: boolean;
  onSharedFix?: (step: string) => void;
  detail: Detail;
  run: Run;
  reloadProject: () => Promise<void>;
  setReview: (o: Output) => void;
  busy: boolean;
  mode?: "banner" | "social";
}) {
  const t = useTranslations(mode),
    tr = useTranslations(),
    at = useTranslations("auction");
  const root = useRef<HTMLDivElement>(null);
  const [blocked, setBlocked] = useState<string | null>(null);
  const isSocial = mode === "social";
  const outputType = isSocial ? "social_content" : "banners";
  const [social, setSocial] = useState<SocialConfig>({
    ...socialDefaults,
    ...detail.project.social_config,
    ...(shared && !detail.project.social_config?.headline
      ? {
          headline:
            String(detail.project.auction?.auction_name || "").length <= 48
              ? String(detail.project.auction?.auction_name || "")
              : detail.project.auction?.document_language === "en"
                ? "Property auction"
                : "مزاد عقاري",
        }
      : {}),
  });
  const confirm = useConfirm();
  const [step, setStep] = useState("template"),
    [editor, setEditor] = useState<Item | "new" | null>(null),
    [dirty, setDirty] = useState(false);
  const [templates, setTemplates] = useState<Template[]>([]),
    [check, setCheck] = useState<Review | null>(null);
  const [size, setSize] = useState(detail.project.banner_config?.size || "4x2");
  const [ids, setIds] = useState<string[]>(
    (isSocial ? detail.project.social_config : detail.project.banner_config)
      ?.property_ids || [],
  );
  const [language, setLanguage] = useState(
    String(detail.project.auction?.document_language || "ar"),
  );
  const steps = shared
    ? ["template", "generate", "outputs"]
    : ["template", "auction", "items", "images", "generate", "outputs"];
  useEffect(() => {
    void run(async () => setTemplates(await api(`/${mode}-templates`)));
  }, []);
  useEffect(() => {
    setDirty(false);
    setBlocked(null);
    setCheck(null);
  }, [detail]);
  useEffect(() => {
    if (step === "generate")
      void run(async () =>
        setCheck(await api(`/projects/${detail.project.id}/${mode}-review`)),
      );
  }, [step, detail]);
  const go = async (next: string) => {
    if (steps.indexOf(next) > steps.indexOf(step)) {
      if (!validateForms(root.current)) return;
      // Account identity is managed separately from campaign images.
      const relevant =
        next === "items"
          ? ["auction"]
          : next === "images"
            ? ["auction", "items"]
            : next === "generate" || next === "outputs"
              ? ["auction", "items", "images", "closing"]
              : [];
      const missing = relevant.find(
        (key) => detail.workflow?.stages[key]?.valid === false,
      );
      if (missing) {
        setBlocked(missing);
        if (shared) onSharedFix?.(missing);
        else setStep(missing === "agent" ? "images" : missing);
        return;
      }
      if (dirty) {
        setBlocked(step);
        return;
      }
    }
    setBlocked(null);
    if (dirty && !(await confirm(tr("flow.notSaved")))) return;
    setDirty(false);
    setEditor(null);
    if (shared && !steps.includes(next)) onSharedFix?.(next);
    else setStep(next);
  };
  return (
    <div
      ref={root}
      className="banner-workflow"
      onChangeCapture={(event) => {
        if ((event.target as HTMLElement).closest("form")) setDirty(true);
      }}
    >
      <WorkflowProblems detail={detail} stage={blocked} />
      <section className="workflow-guide">
        <h2>{t("steps")}</h2>
        <p>{shared ? tr("projectFlow.reused") : t("independent")}</p>
        <nav className="workflow-steps">
          {steps.map((key, index) => (
            <button
              key={key}
              disabled={busy}
              className={
                step === key || (step === "excel" && key === "items")
                  ? "selected"
                  : ""
              }
              onClick={() => void go(key)}
            >
              <span>{index + 1}</span>
              {t(`step.${key}`)}
            </button>
          ))}
        </nav>
      </section>
      {step === "template" && (
        <form
          data-stage-form
          className="panel form-panel"
          onSubmit={(event) => {
            event.preventDefault();
            void run(async () => {
              await api(`/projects/${detail.project.id}/${mode}-config`, {
                method: "PUT",
                body: send(
                  isSocial
                    ? { ...social, property_ids: ids }
                    : { size, property_ids: ids },
                ),
              });
              await reloadProject();
              setStep(shared ? "generate" : "auction");
            }, at("saved"));
          }}
        >
          <h2>{t("chooseTemplate")}</h2>
          <p>{t("referenceHelp")}</p>
          {isSocial ? (
            <SocialTemplateFields value={social} onChange={setSocial} />
          ) : (
            <div className="banner-template-grid">
              {["panoramic", "landscape", "square"].map((layout) => (
                <article key={layout} className="banner-template-card">
                  <h3>{t(`layouts.${layout}`)}</h3>
                  <a
                    href={`/banner-references/${layout}.png`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <img
                      src={`/banner-references/${layout}.png`}
                      alt={t("referenceImage", {
                        layout: t(`layouts.${layout}`),
                      })}
                    />
                  </a>
                  <p>
                    {t("guidePage", {
                      page:
                        layout === "panoramic"
                          ? 28
                          : layout === "landscape"
                            ? 30
                            : 32,
                    })}
                  </p>
                  {templates
                    .filter((v) => v.layout === layout)
                    .map((v) => (
                      <label className="checkbox-label" key={v.id}>
                        <input
                          type="radio"
                          name="size"
                          value={v.id}
                          checked={size === v.id}
                          onChange={() => setSize(v.id)}
                        />
                        <bdi>{v.id.replace("x", " × ")} m</bdi>
                      </label>
                    ))}
                </article>
              ))}
            </div>
          )}
          <p className="notice">{t("printScale")}</p>
          {!!detail.items.length && (
            <details>
              <summary>{t("selectProperties")}</summary>
              <p>{t("allProperties")}</p>
              <button
                type="button"
                className="text-button"
                onClick={() => {
                  setIds([]);
                  setDirty(true);
                }}
              >
                {t("resetSelection")}
              </button>
              {detail.items.map((item) => (
                <label className="checkbox-label" key={item.id}>
                  <input
                    type="checkbox"
                    checked={ids.includes(item.id)}
                    onChange={(event) =>
                      setIds(
                        event.target.checked
                          ? [...ids, item.id]
                          : ids.filter((id) => id !== item.id),
                      )
                    }
                  />
                  {item.title}
                </label>
              ))}
            </details>
          )}
          <button className="primary">{t("saveTemplate")}</button>
        </form>
      )}
      {step === "auction" && (
        <AuctionWorkspace
          detail={detail}
          run={run}
          reload={reloadProject}
          bannerMode
          socialMode={isSocial}
          onSaved={() => setStep("items")}
        />
      )}
      {step === "items" &&
        (editor ? (
          <ItemForm
            projectId={detail.project.id}
            requiredFields={detail.workflow?.rules.property_required}
            auctionType={String(
              detail.project.auction?.auction_type || "physical",
            )}
            existing={editor === "new" ? undefined : editor}
            run={run}
            onDone={() => {
              setEditor(null);
              void reloadProject();
            }}
          />
        ) : (
          <section className="panel form-panel">
            <h2>{t("step.items")}</h2>
            <p>{t("propertiesHelp")}</p>
            <div className="flex-row">
              <button className="primary" onClick={() => setEditor("new")}>
                {tr("ui.add_item")}
              </button>
              <button className="secondary" onClick={() => void go("excel")}>
                {tr("flow.importProperties")}
              </button>
            </div>
            {detail.items.map((item) => (
              <div className="banner-property-row" key={item.id}>
                <strong>{item.title}</strong>
                <span>
                  <bdi>{String(item.property_data?.deed_number || "—")}</bdi>
                </span>
                <button className="text-button" onClick={() => setEditor(item)}>
                  {tr("ui.edit")}
                </button>
                <button
                  className="text-button danger"
                  onClick={async () => {
                    if (
                      await confirm(
                        tr(
                          "ui.delete_this_item_and_its_image_associations_existing_outputs_will",
                        ),
                      )
                    )
                      void run(async () => {
                        await api(
                          `/projects/${detail.project.id}/items/${item.id}`,
                          { method: "DELETE" },
                        );
                        await reloadProject();
                      });
                  }}
                >
                  {tr("ui.delete")}
                </button>
              </div>
            ))}
          </section>
        ))}
      {step === "excel" && (
        <ExcelUpload
          projectId={detail.project.id}
          run={run}
          onDone={() => {
            void reloadProject();
            setStep("items");
          }}
        />
      )}
      {step === "images" && (
        <>
          <section className="panel">
            <h2>{t("logos")}</h2>
            <p>{t("logosHelp")}</p>
          </section>
          <ImageUpload
            detail={detail}
            run={run}
            onDone={() => void reloadProject()}
          />
        </>
      )}
      {step === "generate" && (
        <section className="panel form-panel">
          <h2>{t("review")}</h2>
          <p>{t("printScale")}</p>
          {check && (
            <>
              <p className={check.valid ? "notice" : "notice error"}>
                {check.valid
                  ? t("ready", { count: check.count })
                  : t("missing")}
              </p>
              {check.missing.map((issue, index) => (
                <button
                  className="banner-missing"
                  key={index}
                  onClick={() =>
                    ["agent_name", "agent_logo"].includes(issue.field)
                      ? window.dispatchEvent(new Event("open-account-profile"))
                      : void go(issue.section)
                  }
                >
                  {issue.item ? `${issue.item}: ` : ""}
                  {issue.limit
                    ? t("tooLong", {
                        field: ["agent_name", "headline"].includes(issue.field)
                          ? t(`fields.${issue.field}`)
                          : at(issue.field),
                        limit: issue.limit,
                      })
                    : [
                          "properties",
                          "agent_name",
                          "property_selection",
                          "property_limit",
                          "headline",
                          "campaign_image",
                          "main_image",
                        ].includes(issue.field)
                      ? t(`fields.${issue.field}`)
                      : at(issue.field)}{" "}
                  →
                </button>
              ))}
            </>
          )}
          <label>
            {tr("common.outputLanguage")}
            <select
              value={language}
              onChange={(event) => setLanguage(event.target.value)}
            >
              <option value="ar">العربية</option>
              <option value="en">English</option>
            </select>
          </label>
          <button
            className="primary"
            disabled={busy || !check?.valid}
            onClick={() =>
              void run(async () => {
                const results = await api<Output[]>(
                  `/projects/${detail.project.id}/generate`,
                  {
                    method: "POST",
                    body: send({
                      types: [outputType],
                      output_language: language,
                    }),
                  },
                );
                await reloadProject();
                setStep("outputs");
                setReview(results[0]);
              }, tr("ui.drafts_generated_and_ready_for_review"))
            }
          >
            {t("generate")}
          </button>
        </section>
      )}
      {step === "outputs" && (
        <section className="panel form-panel">
          <h2>{t("step.outputs")}</h2>
          <p>{t("exportHelp")}</p>
          <p>{t("printScale")}</p>
          <OutputList
            outputs={detail.outputs.filter((o) => o.output_type === outputType)}
            onOpen={setReview}
          />
        </section>
      )}
      <div className="workflow-controls">
        <button
          className="secondary"
          disabled={busy || steps.indexOf(step) <= 0}
          onClick={() => void go(steps[steps.indexOf(step) - 1])}
        >
          {tr("flow.previous")}
        </button>
        <button
          className="primary"
          disabled={busy || steps.indexOf(step) === steps.length - 1}
          onClick={() => void go(steps[Math.max(0, steps.indexOf(step)) + 1])}
        >
          {tr("flow.next")}
        </button>
      </div>
    </div>
  );
}
