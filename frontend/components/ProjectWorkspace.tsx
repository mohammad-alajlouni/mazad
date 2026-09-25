import LiveBookletPreview from "./LiveBookletPreview";
import {
  type Issue,
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
import { useEffect, useState, useRef } from "react";
import { ArrowUpRight, Plus, Layers, Sparkles } from "lucide-react";
import { api, send, Detail, Item, Output, Run } from "./api";
import { Config } from "./Settings";
import { Badge, Empty, OutputList, title } from "./shared";
import {
  ProjectForm,
  ItemForm,
  ExcelUpload,
  ImageUpload,
} from "./ProjectForms";
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
}: {
  sharedMode?: "data" | "booklet";
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
  const [selected, setSelected] = useState<string[]>(["project_booklet"]);
  const [otherTools, setOtherTools] = useState(false);
  const [dirty, setDirty] = useState(false);
  useEffect(() => {
    setDirty(false);
    setBlocked(null);
  }, [detail]);
  // Steps follow the booklet: its first pages, the properties and their
  // photographs, then the closing pages (terms, participation, contact).
  const steps =
    sharedMode === "data"
      ? ["auction", "items", "images", "closing"]
      : sharedMode === "booklet"
        ? ["generate", "outputs"]
        : ["auction", "items", "images", "closing", "generate", "outputs"];
  const allStepKeys = [
    "auction",
    "properties",
    "images",
    "closing",
    "review",
    "export",
  ];
  const stepKeys = steps.map(
    (step) =>
      allStepKeys[
        [
          "auction",
          "items",
          "images",
          "closing",
          "generate",
          "outputs",
        ].indexOf(step)
      ],
  );
  const stepIndex = steps.indexOf(tab === "excel import" ? "items" : tab);
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
    const target = issue.stage === "images" ? "images" : issue.stage;
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
        `[name="property.${issue.field}"], [name="boundary.${issue.field}"], [name="${issue.field}"]`,
      );
    } else if (issue.stage === "images") {
      const slot =
        issue.field === "campaign_image"
          ? "cover"
          : issue.field === "main_image"
            ? `main:${issue.item_id}`
            : issue.field;
      setFocusTarget(`[data-slot="${slot}"]`);
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
      const limit = limits[field.name.replace(/^property\./, "")];
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
                <span>{formatNumber(index + 1)}</span>
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
            key={tab}
            section={tab}
            detail={detail}
            run={run}
            reload={reloadProject}
            onSaved={() => {
              setDirty(false);
              setTab("items");
            }}
          />
        )}
        {tab === "items" && !itemEditor && (
          <div className="flow-actions">
            <p>{tr("flow.propertiesHelp")}</p>
            <button
              className="secondary"
              onClick={() => void go("excel import")}
            >
              {tr("flow.importProperties")}
            </button>
          </div>
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
                  ["02", tr("ui.upload_real_images"), "images"],
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
        {tab === "items" &&
          (itemEditor ? (
            <ItemForm
              projectId={detail.project.id}
              requiredFields={detail.workflow?.rules.property_required}
              auctionType={String(
                detail.project.auction?.auction_type || "physical",
              )}
              existing={itemEditor === "new" ? undefined : itemEditor}
              run={run}
              onDone={() => {
                setItemEditor(null);
                void reloadProject();
              }}
            />
          ) : (
            <section className="panel">
              <div className="panel-heading flex-row">
                <h2>{tr("ui.normalized_items")}</h2>
                <button
                  className="primary"
                  onClick={() => setItemEditor("new")}
                >
                  <Plus size={16} />
                  {tr("ui.add_item")}
                </button>
              </div>
              {detail.items.length ? (
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>{tr("ui.item")}</th>
                        <th>{tr("ui.category")}</th>
                        <th>{tr("ui.quantity")}</th>
                        <th>{tr("ui.unit_value")}</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {detail.items.map((i) => (
                        <tr key={i.id}>
                          <td>
                            <strong>{i.title}</strong>
                            <small dir="ltr">{i.reference}</small>
                          </td>
                          <td>{i.category || "—"}</td>
                          <td>{formatNumber(i.quantity)}</td>
                          <td>{formatNumber(i.financial_value)}</td>
                          <td>
                            <div className="actions">
                              <button
                                className="text-button"
                                onClick={() => setItemEditor(i)}
                              >
                                {tr("ui.edit")}
                              </button>
                              <button
                                className="text-button"
                                disabled={detail.items.indexOf(i) === 0}
                                onClick={() =>
                                  void run(async () => {
                                    const ids = detail.items.map((v) => v.id);
                                    const index = ids.indexOf(i.id);
                                    [ids[index - 1], ids[index]] = [
                                      ids[index],
                                      ids[index - 1],
                                    ];
                                    await api(
                                      `/projects/${detail.project.id}/item-order`,
                                      {
                                        method: "PUT",
                                        body: send({ item_ids: ids }),
                                      },
                                    );
                                    await reloadProject();
                                  })
                                }
                              >
                                {tr("auction.move_up")}
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
                                        `/projects/${detail.project.id}/items/${i.id}`,
                                        { method: "DELETE" },
                                      );
                                      await reloadProject();
                                    }, tr("ui.item_deleted"));
                                }}
                              >
                                {tr("ui.delete")}
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <Empty
                  text={tr(
                    "ui.add_an_item_manually_or_import_an_excel_workbook",
                  )}
                />
              )}
            </section>
          ))}
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
            key={tab}
            section="closing"
            detail={detail}
            run={run}
            reload={reloadProject}
            onSaved={() => {
              setDirty(false);
              if (sharedMode !== "data") setTab("generate");
            }}
          />
        )}
        {tab === "images" && (
          <ImageUpload
            detail={detail}
            run={run}
            onDone={() => void reloadProject()}
          />
        )}
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
            <button
              className="secondary"
              disabled={busy || stepIndex === 0}
              onClick={() => void go(steps[stepIndex - 1])}
            >
              {tr("flow.previous")}
            </button>
            <button
              className="secondary"
              disabled={busy || stepIndex === steps.length - 1}
              onClick={() => void go(steps[stepIndex + 1])}
            >
              {tr("flow.next")}
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
