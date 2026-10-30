"use client";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Minus, Plus, RotateCcw } from "lucide-react";
import { api, send } from "./api";

type Kind = "booklet" | "banner" | "social";
const STEP = 0.1,
  LEAST = 0.4,
  MOST = 1.5;

// The selling agent's logo larger or smaller, from the live preview: each kind
// of output has its own size, saved at once. Only the preview is refreshed, so
// the forms keep what is typed in them.
export default function AgentLogoSize({
  projectId,
  kind,
  onChange,
}: {
  projectId: string;
  kind: Kind;
  onChange: () => void;
}) {
  const t = useTranslations("agentLogoSize");
  const [scale, setScale] = useState(1);
  const [saving, setSaving] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let current = true;
    void api<Record<Kind, number>>(`/projects/${projectId}/agent-logo-scales`)
      .then((saved) => {
        if (current) setScale(saved[kind]);
      })
      .catch(() => undefined);
    return () => {
      current = false;
    };
  }, [projectId, kind]);
  const save = async (next: number) => {
    const value = Math.round(Math.min(MOST, Math.max(LEAST, next)) * 100) / 100;
    setSaving(true);
    setFailed(false);
    try {
      await api(`/projects/${projectId}/agent-logo-scales`, {
        method: "PUT",
        body: send({ kind, scale: value }),
      });
      setScale(value);
      onChange();
    } catch {
      setFailed(true);
    } finally {
      setSaving(false);
    }
  };
  return (
    <div className="agent-logo-size" role="group" aria-label={t("title")}>
      <span className="agent-logo-size-title" title={t("help")}>
        {t("title")}
      </span>
      <button
        type="button"
        className="icon-button"
        disabled={saving || scale <= LEAST}
        aria-label={t("smaller")}
        title={t("smaller")}
        onClick={() => void save(scale - STEP)}
      >
        <Minus size={16} />
      </button>
      <span className="agent-logo-size-value" aria-live="polite">
        {Math.round(scale * 100)}%
      </span>
      <button
        type="button"
        className="icon-button"
        disabled={saving || scale >= MOST}
        aria-label={t("larger")}
        title={t("larger")}
        onClick={() => void save(scale + STEP)}
      >
        <Plus size={16} />
      </button>
      <button
        type="button"
        className="icon-button"
        disabled={saving || scale === 1}
        aria-label={t("reset")}
        title={t("reset")}
        onClick={() => void save(1)}
      >
        <RotateCcw size={14} />
      </button>
      {failed && (
        <small className="field-error" role="alert">
          {t("failed")}
        </small>
      )}
      <small className="muted agent-logo-size-help">{t("help")}</small>
    </div>
  );
}
