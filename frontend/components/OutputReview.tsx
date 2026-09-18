"use client";

import { useTranslations } from "next-intl";
import { useConfirm } from "./Confirmation";
import { useState } from "react";
import { api, send, Output, Run } from "./api";
import { Badge, title } from "./shared";
export default function OutputReview({
  output,
  run,
  onChange,
  onClose,
}: {
  output: Output;
  run: Run;
  onChange: (o: Output) => void;
  onClose: () => void;
}) {
  const tr = useTranslations();
  const confirm = useConfirm();

  const [text, setText] = useState(output.content.review_text || "");
  const [fileId, setFileId] = useState("");
  const selected =
    output.files.find((f) => f.id === fileId) ||
    output.files.find((f) =>
      output.output_type === "banners"
        ? f.media_type === "image/png"
        : f.media_type === "application/pdf",
    ) ||
    output.files[0];
  const mutate = (action: string) =>
    void run(
      async () => {
        const o = await api<Output>(`/outputs/${output.id}/${action}`, {
          method: "POST",
        });
        setText(o.content.review_text || "");
        onChange(o);
      },
      action === "approve"
        ? tr("ui.output_approved")
        : tr("ui.draft_regenerated"),
    );
  return (
    <div className="review">
      <div className="flex-row">
        <button className="text-button" onClick={onClose}>
          {tr("ui.back_to_workspace")}
        </button>
        <Badge status={output.status} />
      </div>
      <div className="section-heading">
        <div>
          <p className="eyebrow">{tr("ui.review_approval_upper")}</p>
          <h1>{title(output.output_type)}</h1>
          <p>{output.project_name}</p>
        </div>
        <div className="actions">
          <button
            className="secondary"
            onClick={async () => {
              if (
                await confirm(
                  tr(
                    "ui.regenerate_using_current_data_this_replaces_the_reviewed_narrativ",
                  ),
                )
              )
                mutate("regenerate");
            }}
          >
            {tr("ui.regenerate")}
          </button>
          <button
            className="primary"
            disabled={
              output.status !== "DRAFT" || text !== output.content.review_text
            }
            onClick={() => mutate("approve")}
          >
            {tr("ui.approve_output")}
          </button>
        </div>
      </div>
      {output.banner && <p className="notice">{tr("banner.printScale")}</p>}
      {output.status === "NEEDS_REGENERATION" && (
        <div className="notice">
          {tr(
            "ui.project_data_changed_regenerate_this_output_before_review_and_app",
          )}
        </div>
      )}
      <div className="review-grid">
        <div className="panel preview-panel">
          <div className="panel-heading">
            <h2>{tr("ui.document_preview")}</h2>
            <select
              aria-label={tr("ui.preview_file")}
              value={selected?.id || ""}
              onChange={(e) => setFileId(e.target.value)}
            >
              {output.files.map((f, i) => (
                <option key={f.id} value={f.id}>
                  {f.media_type.startsWith("image")
                    ? tr("common.bannerNumber", { number: i })
                    : f.media_type.startsWith("text")
                      ? tr("ui.text")
                      : tr("ui.pdf_upper")}
                </option>
              ))}
            </select>
          </div>
          {selected &&
            (selected.media_type.startsWith("image") ? (
              <img
                className="banner-preview"
                src={"/api/files/" + selected.id}
                alt={tr("ui.generated_banner_preview")}
              />
            ) : (
              <iframe
                title={tr("ui.output_preview")}
                src={"/api/files/" + selected.id}
              />
            ))}
          <a
            className="text-button"
            href={"/api/files/" + selected?.id}
            target="_blank"
            rel="noreferrer"
          >
            {tr("ui.open_preview_in_a_new_tab")}
          </a>
        </div>
        <aside className="panel form-panel">
          {output.official_booklet || output.banner ? (
            <p>
              {tr(
                output.banner
                  ? "banner.exportHelp"
                  : "auction.fixed_content_help",
              )}
            </p>
          ) : (
            <>
              <h2>{tr("ui.review_narrative")}</h2>
              <p className="muted">
                {tr(
                  "ui.edit_the_summary_or_social_copy_below_saving_changes_returns_the_",
                )}
              </p>
              <label>
                {tr("ui.editable_content")}
                <textarea
                  rows={13}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                />
              </label>
              <button
                className="secondary"
                disabled={output.status === "NEEDS_REGENERATION"}
                onClick={() =>
                  void run(async () => {
                    onChange(
                      await api<Output>("/outputs/" + output.id, {
                        method: "PUT",
                        body: send({ review_text: text }),
                      }),
                    );
                  }, tr("ui.review_saved"))
                }
              >
                {tr("ui.save_reviewed_text")}
              </button>
              <div className="ai-status">
                <strong>
                  {tr("ui.ai_upper")}{" "}
                  {output.content.ai_status === "UNAVAILABLE"
                    ? tr("ui.unavailable_or_not_requested")
                    : title(output.content.ai_status)}
                </strong>
                <p>
                  {tr(
                    output.content.ai_status === "ERROR"
                      ? "common.aiError"
                      : output.content.ai_status === "DRAFT"
                        ? "common.aiDraft"
                        : "common.aiUnavailable",
                  )}
                </p>
              </div>
            </>
          )}
          <h3>{tr("ui.export_files")}</h3>
          {output.status === "APPROVED" ? (
            output.files.map((f, i) => (
              <a
                className="download"
                key={f.id}
                href={"/api/files/" + f.id + "?download=true"}
              >
                {f.media_type.startsWith("image")
                  ? tr("common.downloadBanner", { number: i })
                  : tr(
                      f.media_type.startsWith("text")
                        ? "common.downloadText"
                        : "common.downloadPdf",
                    )}
              </a>
            ))
          ) : (
            <p className="muted">
              {tr("ui.approve_this_output_to_enable_final_downloads")}
            </p>
          )}
        </aside>
      </div>
    </div>
  );
}
