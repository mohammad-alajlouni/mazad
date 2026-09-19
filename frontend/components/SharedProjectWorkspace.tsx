"use client";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Detail, Output, Run } from "./api";
import { Config } from "./Settings";
import { useConfirm } from "./Confirmation";
import { OutputList } from "./shared";
import ProjectWorkspace from "./ProjectWorkspace";
import BannerWorkspace from "./BannerWorkspace";

export type ProjectSection =
  "data" | "booklet" | "banner" | "social" | "outputs";

export default function SharedProjectWorkspace({
  detail,
  config,
  types,
  busy,
  run,
  reloadProject,
  setReview,
  initialSection = "data",
}: {
  detail: Detail;
  config: Config | null;
  types: { key: string; title: string }[];
  busy: boolean;
  run: Run;
  reloadProject: () => Promise<void>;
  setReview: (output: Output) => void;
  initialSection?: ProjectSection;
}) {
  const t = useTranslations("projectFlow");
  const tr = useTranslations();
  const confirm = useConfirm();
  const [section, setSection] = useState<ProjectSection>(initialSection);
  const [dataTab, setDataTab] = useState("auction");
  const [bookletTab, setBookletTab] = useState("generate");
  const [dirty, setDirty] = useState(false);
  useEffect(() => setDirty(false), [detail]);
  const select = async (next: ProjectSection) => {
    if (next === section) return;
    if (dirty && !(await confirm(tr("flow.notSaved")))) return;
    setDirty(false);
    setSection(next);
  };
  const fix = (step: string) => {
    setDataTab(step);
    setSection("data");
  };
  return (
    <div
      className="shared-project"
      onChangeCapture={(event) => {
        if ((event.target as HTMLElement).closest("form")) setDirty(true);
      }}
    >
      <section className="panel form-panel">
        <h2>{t("title")}</h2>
        <p>{t("reused")}</p>
        <p className="muted">
          {t("counts", {
            items: detail.items.length,
            images: detail.images.length,
          })}
        </p>
        <nav className="tabs project-sections" aria-label={t("sections")}>
          {(
            [
              "data",
              "booklet",
              "banner",
              "social",
              "outputs",
            ] as ProjectSection[]
          ).map((key) => (
            <button
              key={key}
              disabled={busy}
              className={section === key ? "selected" : ""}
              aria-current={section === key ? "page" : undefined}
              onClick={() => void select(key)}
            >
              {t(key)}
            </button>
          ))}
        </nav>
      </section>
      {section === "data" || section === "booklet" ? (
        <ProjectWorkspace
          key={section}
          detail={detail}
          config={config}
          types={types}
          busy={busy}
          run={run}
          reloadProject={reloadProject}
          setReview={setReview}
          sharedMode={section}
          onSharedFix={fix}
          tab={section === "data" ? dataTab : bookletTab}
          setTab={section === "data" ? setDataTab : setBookletTab}
        />
      ) : section === "outputs" ? (
        <section className="panel form-panel">
          <h2>{t("outputs")}</h2>
          <p>{t("outputsHelp")}</p>
          <OutputList outputs={detail.outputs} onOpen={setReview} />
        </section>
      ) : (
        <BannerWorkspace
          key={section}
          mode={section}
          shared
          onSharedFix={fix}
          detail={detail}
          busy={busy}
          run={run}
          reloadProject={reloadProject}
          setReview={setReview}
        />
      )}
      {section === "data" && (
        <div className="flow-actions">
          <p>{t("choose")}</p>
          {(["booklet", "banner", "social"] as ProjectSection[]).map((key) => (
            <button
              className="secondary"
              key={key}
              onClick={() => void select(key)}
            >
              {t(key)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
