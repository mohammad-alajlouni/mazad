import LiveBookletPreview from "./LiveBookletPreview";
import PropertyManager from "./PropertyManager";
import SampleFill from "./SampleFill";
import {
  type Issue,
  dataStages,
  missingStage,
  StepChecklist,
  stepIssues,
  validateForms,
  WorkflowProblems,
} from "./workflowValidation";
import { AuctionWorkspace, AuctionReview } from "./AuctionWorkspace";
import { useConfirm } from "./Confirmation";
import { formatNumber, formatDate } from "../i18n/format";
import { useTranslations } from "next-intl";
import React, { useEffect, useState, useRef } from "react";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Check,
  Layers,
  Sparkles,
} from "lucide-react";
import { api, send, Detail, Item, Output, Run } from "./api";
import { Config } from "./Settings";
import { Badge, OutputList, title } from "./shared";
import { ProjectForm, ExcelUpload } from "./ProjectForms";
export default function ProjectWorkspace({
  detail,
  config,
  types,
  busy,
  run,
  tab,
  setTab,
  reloadProject,
  setReview,
  sharedMode,
  onSharedFix,
  finish,
}: {
  sharedMode?: "data" | "booklet";
  // What the shared project's last step shows (generate all outputs).
  finish?: React.ReactNode;
  onSharedFix?: (step: string) => void;
  detail: Detail;
  config: Config | null;
  types: { key: string; title: string }[];
  busy: boolean;
  run: Run;
  tab: string;
  setTab: (tab: string) => void;
  reloadProject: () => Promise<void>;
  setReview: (output: Output) => void;
}) {
  const tr = useTranslations();
  const confirm = useConfirm();
  const root = useRef<HTMLDivElement>(null);
  const [blocked, setBlocked] = useState<string | null>(null);
  const [outputLanguage, setOutputLanguage] = useState(
    String(detail.project.auction?.document_language || "ar"),
  );

  useEffect(() => {
    if (detail.project.auction?.document_language)
      setOutputLanguage(String(detail.project.auction.document_language));
  }, [detail.project.auction?.document_language]);
  const [itemEditor, setItemEditor] = useState<Item | "new" | null>(null);
  const [formVersion, setFormVersion] = useState(0); // reopen forms after a sample fill
  // Steps entered page by page report [current page, page count].
  const [pages, setPages] = useState<[number, number]>([0, 1]);
  const [selected, setSelected] = useState<string[]>(["project_booklet"]);
  const [otherTools, setOtherTools] = useState(false);
  const [dirty, setDirty] = useState(false);
  useEffect(() => {
    setDirty(false);
    setBlocked(null);
  }, [detail]);
  // Steps follow the booklet: its first pages, the properties (each entered
  // with its photographs), then the closing pages (terms, participation,
  // contact). A shared project ends its data steps with generating everything.
  const steps =
    sharedMode === "data"
      ? ["auction", "items", "closing", "finish"]
      : sharedMode === "booklet"
        ? ["generate", "outputs"]
        : ["auction", "items", "closing", "generate", "outputs"];
  const stepNames: Record<string, string> = {
    auction: "auction",
    items: "properties",
    images: "images",
    closing: "closing",
    generate: "review",
    outputs: "export",
    finish: "finish",
  };
  const stepKeys = steps.map((step) => stepNames[step]);
  const stepIndex = steps.indexOf(tab === "excel import" ? "items" : tab);
  const paged = tab === "auction" || tab === "closing";
  const pagedForm = () =>
    root.current?.querySelector<HTMLFormElement>("form.booklet-pages") || null;
  const go = async (next: string) => {
    if (next === "agent") {
      window.dispatchEvent(new Event("open-account-profile"));
      return;
    }
    if (steps.indexOf(next) > stepIndex || next === "generate") {
      if (!validateForms(root.current)) return;
      const missing = missingStage(detail, next);
      if (missing) {
        setBlocked(missing);
        if (sharedMode === "booklet") onSharedFix?.(missing);
        else setTab(missing);
        return;
      }
      if (dirty) {
        setBlocked(tab);
        return;
      }
    }
    setBlocked(null);
    if (dirty && !(await confirm(tr("flow.notSaved")))) return;
    setDirty(false);
    setItemEditor(null);
    if (sharedMode === "booklet" && !steps.includes(next)) onSharedFix?.(next);
    else setTab(next);
  };
  const [auctionValid, setAuctionValid] = useState(false);
  // Clicking a requirement opens its step (and property) and focuses the field.
  const [focusTarget, setFocusTarget] = useState<string | null>(null);
  useEffect(() => {
    if (!focusTarget) return;
    let tries = 0;
    const timer = setInterval(() => {
      const el = root.current?.querySelector<HTMLElement>(focusTarget);
      if (!el && ++tries < 25) return;
      clearInterval(timer);
      setFocusTarget(null);
      if (!el) return;
      for (let node = el.parentElement; node; node = node.parentElement)
        if (node instanceof HTMLDetailsElement) node.open = true;
      // A field on another booklet page: open that page, then focus it.
      el.dispatchEvent(new Event("reveal", { bubbles: true }));
      setTimeout(() => {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.focus({ preventScroll: true });
        el.classList.add("attention");
        setTimeout(() => el.classList.remove("attention"), 2400);
      }, 60);
    }, 80);
    return () => clearInterval(timer);
  }, [focusTarget, tab, itemEditor]);
  const fixIssue = async (issue: Issue) => {
    if (issue.stage === "agent") {
      window.dispatchEvent(new Event("open-account-profile"));
      return;
    }
    // A property's photograph is entered in that property's own form.
    if (issue.stage === "images") issue = { ...issue, stage: "items" };
    const target = issue.stage;
    if (tab !== target) {
      if (dirty && !(await confirm(tr("flow.notSaved")))) return;
      setDirty(false);
      setBlocked(null);
      if (sharedMode === "booklet" && !steps.includes(target))
        onSharedFix?.(target);
      else setTab(target);
    }
    if (issue.stage === "auction" || issue.stage === "closing") {
      setFocusTarget(`[name="${issue.field}"]`);
    } else if (issue.stage === "items") {
      if (issue.field === "properties") {
        setItemEditor("new");
        return;
      }
      const item = detail.items.find((i) => i.id === issue.item_id);
      if (item) setItemEditor(item);
      setFocusTarget(
        issue.field === "main_image"
          ? '.property-form [data-slot="main"]'
          : `[name="property.${issue.field}"], [name="boundary.${issue.field}"], [name="${issue.field}"]`,
      );
    }
  };
  // Refuse input longer than the booklet, banner and posts can set, so no
  // length problem is left for the generation step.
  const limits = detail.workflow?.rules.limits;
  useEffect(() => {
    if (!limits || !root.current) return;
    for (const field of root.current.querySelectorAll<
      HTMLInputElement | HTMLTextAreaElement
    >("input[name], textarea[name]")) {
      // Every deed of a property has the first one's limit.
      const limit =
        limits[
          field.name
            .replace(/^property\./, "")
            .replace(/^extra_deed_numbers$/, "deed_number")
        ];
      if (limit) field.maxLength = limit;
    }
  });
  const [useAI, setUseAI] = useState(false);
  return (
    <LiveBookletPreview detail={detail} stage={tab}>
      <div
        ref={root}
        className="booklet-workflow"
        onChangeCapture={(event) => {
          if ((event.target as HTMLElement).closest("form")) setDirty(true);
        }}
      >
        <WorkflowProblems
          detail={detail}
          stage={blocked}
          onIssue={(issue) => void fixIssue(issue)}
        />
        {!sharedMode && (
          <SampleFill
            detail={detail}
            run={run}
            reload={reloadProject}
            onFilled={() => {
              setItemEditor(null);
              setFormVersion((v) => v + 1);
            }}
          />
        )}
        <div className="project-meta">
          <Badge status={detail.project.status} />
          <span>{detail.project.customer || tr("ui.no_client_assigned")}</span>
          <span>{tr("common.itemsCount", { count: detail.items.length })}</span>
          <span>
            {tr("common.imagesCount", { count: detail.images.length })}
          </span>
        </div>
        <section
          className="workflow-guide"
          aria-label={tr(
            sharedMode === "data" ? "projectFlow.data" : "flow.steps",
          )}
        >
          <div className="workflow-title">
            <h2>
              {tr(sharedMode === "data" ? "projectFlow.data" : "flow.steps")}
            </h2>
            <span>
              {sharedMode
                ? tr("projectFlow.step", {
                    number: Math.max(stepIndex, 0) + 1,
                    total: steps.length,
                  })
                : tr("flow.stepCount", { number: Math.max(stepIndex, 0) + 1 })}
            </span>
          </div>
          <nav className="workflow-steps">
            {steps.map((step, index) => (
              <button
                key={step}
                disabled={busy}
                aria-current={stepIndex === index ? "step" : undefined}
                className={stepIndex === index ? "selected" : ""}
                onClick={() => void go(step)}
              >
                {/* A saved, complete data step shows a tick instead of its number. */}
                <span>
                  {index !== stepIndex &&
                  dataStages.includes(step) &&
                  detail.workflow?.stages[step] &&
                  (step === "auction" || detail.items.length > 0) &&
                  stepIssues(detail, step).length === 0 ? (
                    <Check size={15} />
                  ) : (
                    formatNumber(index + 1)
                  )}
                </span>
                {tr("flow." + stepKeys[index])}
                {stepIssues(detail, step).length > 0 && (
                  <em
                    className="step-missing"
                    title={tr("validationFlow.stepNeeds", {
                      count: stepIssues(detail, step).length,
                    })}
                  >
                    {formatNumber(stepIssues(detail, step).length)}
                  </em>
                )}
              </button>
            ))}
          </nav>
          {stepIndex >= 0 && (
            <p>{tr("flow." + stepKeys[stepIndex] + "Help")}</p>
          )}
          <p className="muted">{tr("flow.saveFirst")}</p>
        </section>
        {blocked !== tab && (
          <StepChecklist
            detail={detail}
            stage={tab === "excel import" ? "items" : tab}
            onIssue={(issue) => void fixIssue(issue)}
          />
        )}
        {tab === "auction" && (
          <AuctionWorkspace
            key={tab + formVersion}
            section={tab}
            detail={detail}
            run={run}
            reload={reloadProject}
            onPage={(index, count) => setPages([index, count])}
            onSaved={() => {
              setDirty(false);
              setTab("items");
            }}
          />
        )}
        {tab === "overview" && (
          <div className="project-overview">
            <section className="panel form-panel">
              <h2>{tr("ui.project_overview")}</h2>
              <p>
                {detail.project.description ||
                  tr("ui.add_a_description_in_project_details")}
              </p>
              <div className="overview-facts">
                <div>
                  <small>{tr("ui.reference_upper")}</small>
                  <strong>
                    <bdi dir="ltr">{detail.project.code}</bdi>
                  </strong>
                </div>
                <div>
                  <small>{tr("ui.location_upper")}</small>
                  <strong>{detail.project.location || "—"}</strong>
                </div>
                <div>
                  <small>{tr("ui.project_date_upper")}</small>
                  <strong>
                    {detail.project.date
                      ? formatDate(detail.project.date)
                      : "—"}
                  </strong>
                </div>
              </div>
              <h3>{tr("ui.notes")}</h3>
              <p className="muted">
                {detail.project.notes || tr("ui.no_notes_yet")}
              </p>
            </section>
            <section className="panel form-panel">
              <h2>{tr("ui.bring_your_project_to_life")}</h2>
              <div className="steps">
                {[
                  ["01", tr("ui.add_your_data"), "items"],
                  ["02", tr("ui.upload_real_images"), "items"],
                  ["03", tr("ui.generate_your_outputs"), "generate"],
                  ["04", tr("ui.review_and_approve"), "outputs"],
                ].map(([n, label, t]) => (
                  <button key={n} onClick={() => setTab(t)}>
                    <span>{formatNumber(n, { minimumIntegerDigits: 2 })}</span>
                    {label}
                    <ArrowUpRight size={16} />
                  </button>
                ))}
              </div>
            </section>
          </div>
        )}
        {tab === "items" && (
          <PropertyManager
            detail={detail}
            run={run}
            reload={reloadProject}
            editing={itemEditor}
            setEditing={setItemEditor}
            onImport={() => void go("excel import")}
          />
        )}
        {tab === "excel import" && (
          <ExcelUpload
            projectId={detail.project.id}
            run={run}
            onDone={async () => {
              await reloadProject();
              setDirty(false);
              setTab("items");
            }}
          />
        )}
        {tab === "closing" && (
          <AuctionWorkspace
            key={tab + formVersion}
            section="closing"
            detail={detail}
            run={run}
            reload={reloadProject}
            onPage={(index, count) => setPages([index, count])}
            onSaved={() => {
              setDirty(false);
              setTab(sharedMode === "data" ? "finish" : "generate");
            }}
          />
        )}
        {tab === "finish" && finish}
        {tab === "details" && (
          <ProjectForm
            key={detail.project.id}
            existing={detail.project}
            run={run}
            onDone={() => void reloadProject()}
          />
        )}
        {tab === "outputs" && (
          <section className="panel form-panel">
            <h2>{tr("flow.preview")}</h2>
            <p>{tr("flow.exportHelp")}</p>
            {!detail.outputs.some(
              (o) => o.output_type === "project_booklet",
            ) && (
              <>
                <p>{tr("flow.emptyBooklet")}</p>
                <button className="primary" onClick={() => void go("generate")}>
                  {tr("flow.review")}
                </button>
              </>
            )}
            <OutputList
              outputs={detail.outputs.filter(
                (o) => otherTools || o.output_type === "project_booklet",
              )}
              onOpen={setReview}
            />
          </section>
        )}
        {tab === "generate" && (
          <section className="panel form-panel">
            {!otherTools ||
            Object.keys(detail.project.auction || {}).length > 0 ? (
              <AuctionReview
                detail={detail}
                run={run}
                onValid={setAuctionValid}
                onFix={(step) => void go(step)}
              />
            ) : null}
            <div className="flex-row">
              <div>
                <h2>
                  {tr(
                    otherTools
                      ? "ui.one_project_a_complete_output_set"
                      : "flow.generate",
                  )}
                </h2>
                <p className="muted">{tr("flow.generateHelp")}</p>
              </div>
              {otherTools && (
                <button
                  className="text-button"
                  onClick={() =>
                    setSelected(
                      selected.length === types.length
                        ? []
                        : types.map((t) => t.key),
                    )
                  }
                >
                  {selected.length === types.length
                    ? tr("ui.clear_selection")
                    : tr("ui.select_all_eight")}
                </button>
              )}
            </div>
            {otherTools && (
              <div className="generation-grid">
                {types.map((t) => (
                  <label
                    className={
                      "generator-option " +
                      (selected.includes(t.key) ? "checked" : "")
                    }
                    key={t.key}
                  >
                    <input
                      type="checkbox"
                      checked={selected.includes(t.key)}
                      onChange={(e) =>
                        setSelected(
                          e.target.checked
                            ? [...selected, t.key]
                            : selected.filter((k) => k !== t.key),
                        )
                      }
                    />
                    <Layers size={21} />
                    <span>{title(t.key)}</span>
                  </label>
                ))}
              </div>
            )}
            <label>
              {tr("common.outputLanguage")}
              <select
                aria-label={tr("common.outputLanguage")}
                value={outputLanguage}
                onChange={(e) => setOutputLanguage(e.target.value)}
              >
                <option value="en">{tr("common.english")}</option>
                <option value="ar">{tr("common.arabic")}</option>
              </select>
            </label>
            <p className="muted">{tr("common.outputLanguageHelp")}</p>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={useAI}
                onChange={(e) => setUseAI(e.target.checked)}
              />
              <Sparkles size={16} />
              {tr("ui.assist_with_ai")}{" "}
              {config?.ai.available
                ? tr("ui.requires_review")
                : tr("ui.unavailable_no_api_key_configured")}
            </label>
            <p className="muted">
              {tr(
                "ui.your_current_data_and_branding_are_saved_with_each_output_changes",
              )}
            </p>
            <button
              disabled={
                !selected.length ||
                busy ||
                ((!otherTools ||
                  Object.keys(detail.project.auction || {}).length > 0) &&
                  selected.includes("project_booklet") &&
                  !auctionValid)
              }
              className="primary"
              onClick={() =>
                void run(async () => {
                  const generated = await api<Output[]>(
                    `/projects/${detail.project.id}/generate`,
                    {
                      method: "POST",
                      body: send({
                        types: selected,
                        use_ai: useAI,
                        output_language: outputLanguage,
                      }),
                    },
                  );
                  await reloadProject();
                  setTab("outputs");
                  if (!otherTools && generated[0]) setReview(generated[0]);
                }, tr("ui.drafts_generated_and_ready_for_review"))
              }
            >
              <Sparkles size={17} />
              {busy
                ? tr("ui.generating_documents")
                : otherTools
                  ? tr("common.generateButton", { count: selected.length })
                  : tr("flow.generate")}
            </button>
          </section>
        )}
        {stepIndex >= 0 && (
          <div className="workflow-navigation">
            {/* The only Previous / Next of the flow. In a step entered page by
                page, Next saves the page and opens the next one, then the next
                step; Previous goes back a page, then a step. */}
            <button
              className="text-button nav-previous"
              disabled={busy || (stepIndex === 0 && (!paged || pages[0] === 0))}
              onClick={() => {
                const form = pagedForm();
                if (form) {
                  const event = new Event("wizard-previous", {
                    cancelable: true,
                  });
                  form.dispatchEvent(event);
                  if (event.defaultPrevented) return;
                }
                void go(steps[stepIndex - 1]);
              }}
            >
              <ArrowLeft size={17} />
              {tr("flow.previous")}
            </button>
            <button
              className="primary nav-next"
              // The last step has its own action (generate, or the outputs list).
              hidden={!paged && stepIndex === steps.length - 1}
              disabled={busy || (!paged && stepIndex === steps.length - 1)}
              onClick={() => {
                const form = pagedForm();
                if (form) form.requestSubmit();
                else void go(steps[stepIndex + 1]);
              }}
            >
              {tr("flow.next")}
              <ArrowRight size={17} />
            </button>
          </div>
        )}
        {sharedMode !== "data" && (
          <div className="additional-tools">
            <button
              className="text-button"
              onClick={() => {
                setOtherTools(!otherTools);
                setSelected(["project_booklet"]);
              }}
            >
              {tr(otherTools ? "flow.hideTools" : "flow.otherTools")}
            </button>
            {otherTools && (
              <div className="tabs">
                {["overview", "details", "generate", "outputs"].map((key) => (
                  <button key={key} onClick={() => void go(key)}>
                    {title(key)}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </LiveBookletPreview>
  );
}
