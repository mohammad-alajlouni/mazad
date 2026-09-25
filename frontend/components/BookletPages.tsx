"use client";
import { useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { api, send, Detail, Run } from "./api";
import { Fields } from "./AuctionWorkspace";

type Values = Record<string, unknown>;
type Part = {
  page: string; // booklet page kind shown in the live preview
  key: string;
  number?: number; // page number in the booklet (guide order)
  fields?: string[];
  fixed?: boolean;
  agent?: boolean;
  cover?: boolean;
};

// The booklet's own order (guide V2, pages 9-26): each part fills one page and
// the live preview shows that page while it is being filled.
function partsFor(section: "auction" | "closing", kind: string): Part[] {
  if (section === "auction")
    return [
      {
        page: "cover",
        key: "cover",
        number: 1,
        cover: true,
        fields: [
          "auction_name",
          "auction_date",
          "auction_start_date",
          "auction_end_date",
        ],
      },
      { page: "introduction", key: "introduction", number: 2, fixed: true },
      { page: "agent", key: "agent", number: 3, agent: true },
      {
        page: "auction",
        key: "auction",
        number: 4,
        fields: [
          "legal_announcement_text",
          "court_decision_text",
          "start_time",
          "end_time",
          "physical_location",
          "electronic_platform_name",
        ],
      },
    ];
  return [
    { page: "terms", key: "terms", fixed: true },
    ...(kind === "physical"
      ? []
      : [
          {
            page: "participation",
            key: "participation",
            fields: ["electronic_platform_url"],
          },
        ]),
    {
      page: "contact",
      key: "contact",
      fields: ["auction_contact_number", "auction_location_url"],
    },
    {
      page: "contact",
      key: "marketing",
      fields: [
        "license_number",
        "supervising_authority",
        "booklet_url",
        "contact_url",
      ],
    },
  ];
}

function showPage(page: string) {
  window.dispatchEvent(
    new CustomEvent("booklet-preview-page", { detail: page }),
  );
}

export function BookletPages({
  detail,
  run,
  reload,
  section,
  onSaved,
}: {
  detail: Detail;
  run: Run;
  reload: () => Promise<void>;
  section: "auction" | "closing";
  onSaved?: () => void;
}) {
  const t = useTranslations("auction");
  const p = useTranslations("bookletPages");
  const f = useTranslations("flow");
  const v = useTranslations("validationFlow");
  const locale = useLocale();
  const auction = detail.project.auction || {};
  const [kind, setKind] = useState(String(auction.auction_type || "physical"));
  const [cover, setCover] = useState(
    String(auction.selected_cover_template_id || "infath-2"),
  );
  const [covers, setCovers] = useState<
    { id: string; name_ar: string; name_en: string; thumbnail: string }[]
  >([]);
  const [draft, setDraft] = useState<Values>({});
  const rules = detail.workflow?.rules.auction[kind];
  const visible = (fields: string[] = []) =>
    fields.filter((key) => !rules || rules.visible.includes(key));
  const parts = partsFor(section, kind).filter(
    (part) => !part.fields || part.fixed || visible(part.fields).length,
  );
  const [index, setIndex] = useState(0);
  const part = parts[Math.min(index, parts.length - 1)];
  const form = useRef<HTMLFormElement>(null);
  const containers = useRef<(HTMLDivElement | null)[]>([]);
  const revealing = useRef(false);

  useEffect(() => {
    if (section === "auction")
      void run(async () => setCovers(await api("/booklet-templates")));
  }, []);
  useEffect(() => showPage(part.page), [part.page]);
  // A requirement link or a failed check reveals the page holding the field.
  useEffect(() => {
    const element = form.current;
    if (!element) return;
    const reveal = (event: Event) => {
      const found = containers.current.findIndex((c) =>
        c?.contains(event.target as Node),
      );
      if (found >= 0) setIndex(found);
    };
    element.addEventListener("reveal", reveal);
    return () => element.removeEventListener("reveal", reveal);
  }, []);

  const partValid = (at: number) => {
    const container = containers.current[at];
    if (!container) return true;
    for (const el of container.querySelectorAll<
      HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
    >("input, textarea, select")) {
      if (!el.checkValidity()) {
        el.reportValidity();
        return false;
      }
    }
    return true;
  };
  const save = (then: () => void) => {
    const values = Object.fromEntries(new FormData(form.current!));
    delete values["cover-choice"];
    void run(async () => {
      await api(`/projects/${detail.project.id}`, {
        method: "PUT",
        body: send({
          ...detail.project,
          // Each part saves into the one auction record without clearing the others.
          auction: {
            ...auction,
            ...values,
            selected_cover_template_id: cover,
          },
        }),
      });
      await reload();
      then();
    }, t("saved"));
  };
  const last = index >= parts.length - 1;
  const agent = detail.selling_agent || {};
  const logo = detail.images.find(
    (i) => i.id === agent.logo_image_id || i.category === "agent_logo",
  );
  const agentIssues = detail.workflow?.stages.agent?.missing || [];

  return (
    <form
      ref={form}
      data-stage-form
      data-preview-form="auction"
      data-preview-page={part.page}
      className="panel form-panel booklet-pages"
      noValidate
      onChange={() =>
        setDraft(Object.fromEntries(new FormData(form.current!)) as Values)
      }
      onInvalidCapture={(event) => {
        // A failed check reports every invalid field: open the page of the first.
        if (revealing.current) return;
        revealing.current = true;
        setTimeout(() => (revealing.current = false));
        const target = event.target as HTMLElement;
        const found = containers.current.findIndex((c) => c?.contains(target));
        if (found >= 0 && found !== index) {
          setIndex(found);
          setTimeout(() => target.focus());
        }
      }}
      onSubmit={(event) => {
        event.preventDefault();
        if (!partValid(index)) return;
        if (!last) {
          save(() => setIndex(index + 1));
          return;
        }
        for (const [at] of parts.entries())
          if (!partValid(at)) {
            setIndex(at);
            return;
          }
        save(() => onSaved?.());
      }}
    >
      <h2>{f(section === "auction" ? "auction" : "closing")}</h2>
      <p className="muted">
        {f(section === "auction" ? "auctionHelp" : "closingHelp")}
      </p>
      <ol className="page-parts" aria-label={p("order")}>
        {parts.map((item, at) => (
          <li key={item.key}>
            <button
              type="button"
              aria-current={at === index ? "step" : undefined}
              className={at === index ? "selected" : at < index ? "done" : ""}
              onClick={() => {
                // Going forward checks the page being left, as the Next button does.
                if (at > index && !partValid(index)) return;
                setIndex(at);
              }}
            >
              <span>
                {item.number
                  ? p("page", { number: item.number })
                  : p("closingPage")}
              </span>
              {p(item.key)}
            </button>
          </li>
        ))}
      </ol>
      {parts.map((item, at) => (
        <div
          key={item.key}
          ref={(el) => {
            containers.current[at] = el;
          }}
          hidden={at !== index}
          className="page-part"
        >
          <h3>
            {item.number ? p("page", { number: item.number }) + " · " : ""}
            {p(item.key)}
          </h3>
          <p className="notice">{p(item.key + "Help", { type: t(kind) })}</p>
          {item.cover && (
            <>
              <h4>{t("select_cover")}</h4>
              <div className="cover-options">
                {covers.map((c) => (
                  <label
                    key={c.id}
                    className={
                      cover === c.id ? "cover-option selected" : "cover-option"
                    }
                  >
                    <input
                      type="radio"
                      name="cover-choice"
                      value={c.id}
                      checked={cover === c.id}
                      onChange={() => setCover(c.id)}
                    />
                    <img
                      src={c.thumbnail}
                      alt={t("cover", { number: c.id.slice(-1) })}
                    />
                    <span>{locale === "ar" ? c.name_ar : c.name_en}</span>
                  </label>
                ))}
              </div>
              <label>
                {t("auction_type")}
                <select
                  name="auction_type"
                  value={kind}
                  onChange={(e) => setKind(e.target.value)}
                >
                  {["physical", "electronic", "hybrid"].map((k) => (
                    <option key={k} value={k}>
                      {t(k)}
                    </option>
                  ))}
                </select>
              </label>
              <p className="muted">{f("typeHelp_" + kind)}</p>
            </>
          )}
          {item.fields && (
            <Fields
              fields={visible(item.fields)}
              values={{ ...auction, ...draft }}
              requiredFields={rules?.required}
            />
          )}
          {item.cover && (
            <>
              <div className="form-grid">
                <label>
                  {t("document_language")}
                  <select
                    name="document_language"
                    defaultValue={String(auction.document_language || "ar")}
                  >
                    <option value="ar">العربية</option>
                    <option value="en">English</option>
                  </select>
                </label>
                <label>
                  {t("booklet_edition")}
                  <select
                    name="booklet_edition"
                    defaultValue={String(auction.booklet_edition || "print")}
                  >
                    <option value="print">{t("booklet_edition_print")}</option>
                    <option value="digital">
                      {t("booklet_edition_digital")}
                    </option>
                  </select>
                </label>
              </div>
              <div className="agent-card compact">
                {logo ? (
                  <img
                    src={`/api/images/${logo.id}?size=preview`}
                    alt={p("agentLogo")}
                  />
                ) : (
                  <span className="muted">{p("noLogo")}</span>
                )}
                <div>
                  <strong>{p("agentLogo")}</strong>
                  <p className="muted">{p("agentLogoHelp")}</p>
                </div>
              </div>
            </>
          )}
          {item.agent && (
            <div className="agent-card">
              {logo && (
                <img
                  src={`/api/images/${logo.id}?size=preview`}
                  alt={p("agentLogo")}
                />
              )}
              <dl>
                {["name", "description", "social_accounts", "phone", "website"]
                  .filter((key) => agent[key])
                  .map((key) => (
                    <div key={key}>
                      <dt>{t.has(key) ? t(key) : key}</dt>
                      <dd dir={key === "description" ? undefined : "auto"}>
                        {String(agent[key])}
                      </dd>
                    </div>
                  ))}
              </dl>
              {agentIssues.length > 0 && (
                <div className="notice error" role="alert">
                  <strong>{p("agentMissing")}</strong>
                  <ul>
                    {agentIssues.map((issue, at) => (
                      <li key={at}>
                        {v.has(issue.field)
                          ? v(issue.field)
                          : t.has(issue.field)
                            ? t(issue.field)
                            : issue.field}
                        {issue.limit
                          ? v("maxLength", { limit: issue.limit })
                          : ""}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <button
                type="button"
                className="secondary"
                onClick={() =>
                  window.dispatchEvent(new Event("open-account-profile"))
                }
              >
                {p("agentEdit")}
              </button>
            </div>
          )}
        </div>
      ))}
      <div className="flow-actions page-part-actions">
        {index > 0 && (
          <button
            type="button"
            className="secondary"
            onClick={() => setIndex(index - 1)}
          >
            {p("previous")}
          </button>
        )}
        <button className="primary">
          {last
            ? section === "auction"
              ? t("save_auction")
              : p("finishClosing")
            : p("next", { title: p(parts[index + 1].key) })}
        </button>
      </div>
    </form>
  );
}
