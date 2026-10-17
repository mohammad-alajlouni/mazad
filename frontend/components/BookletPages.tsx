"use client";
import { useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import {
  Building2,
  CalendarDays,
  Check,
  Clock3,
  Globe,
  ImagePlus,
  Landmark,
  Layers,
  RotateCcw,
  Sparkles,
  UserRound,
} from "lucide-react";
import { api, send, Detail, Item, Run } from "./api";
import { useImageEditor } from "./ImageEditor";
import { Fields } from "./AuctionWorkspace";

type Values = Record<string, unknown>;
type Part = {
  page: string; // booklet page kind shown in the live preview
  key: string;
  number?: number; // page number in the booklet (guide order)
  fields?: string[];
  fixed?: boolean;
  terms?: boolean;
  agent?: boolean;
  cover?: boolean;
  supervisor?: boolean;
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
          "assignment_number",
          "auction_name",
          "auction_date",
          "auction_start_date",
          "auction_end_date",
        ],
      },
      {
        page: "introduction",
        key: "introduction",
        number: 2,
        supervisor: true,
      },
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
          "first_close_time",
          "close_interval_minutes",
          "physical_location",
          "electronic_platform_name",
        ],
      },
    ];
  return [
    { page: "terms", key: "terms", fixed: true, terms: true },
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

// The terms of entry: the guide's written in, each term on its own line; the
// author may change them for this auction or go back to the guide's.
function TermsText({ initial, guide }: { initial: string; guide: string }) {
  const p = useTranslations("bookletPages");
  const area = useRef<HTMLTextAreaElement>(null);
  return (
    <div className="terms-text">
      <label>
        <span className="label-text">{p("termsText")}</span>
        <textarea
          ref={area}
          name="terms_text"
          rows={14}
          defaultValue={initial}
        />
      </label>
      <button
        type="button"
        className="text-button"
        onClick={() => {
          if (!area.current) return;
          area.current.value = guide;
          area.current.dispatchEvent(new Event("input", { bubbles: true }));
          area.current.form?.dispatchEvent(
            new Event("change", { bubbles: true }),
          );
        }}
      >
        <RotateCcw size={14} />
        {p("termsRestore")}
      </button>
    </div>
  );
}

// Auction names to suggest, from the cities and districts of its properties
// when there are any (guide p.3: "مزاد درة البحر" — the cover adds "مزاد").
function nameIdeas(items: Item[], language: string) {
  const unique = (key: string) => [
    ...new Set(
      items
        .map((i) => String(i.property_data?.[key] || "").trim())
        .filter(Boolean),
    ),
  ];
  const [city] = unique("city");
  const [district] = unique("district");
  const oneCity = unique("city").length === 1;
  const oneDistrict = unique("district").length === 1;
  if (language === "en")
    return [
      ...(oneDistrict ? [`${district} Pearl`, `${district} Oasis`] : []),
      ...(oneCity ? [`${city} Prime Properties`, `${city} Horizon`] : []),
      "Prime Assets",
      "Investment Horizon",
      "Elite Properties",
    ];
  const quarter = district?.startsWith("حي") ? district : `حي ${district}`;
  return [
    ...(oneDistrict ? [`درة ${district}`, `واحة ${district}`, quarter] : []),
    ...(oneCity ? [`عقارات ${city}`, `لؤلؤة ${city}`, `نخبة ${city}`] : []),
    "درة الاستثمار",
    "الأفق العقاري",
    "نخبة الأصول",
    "واحة الاستثمار",
    "صفوة العقار",
  ];
}

// The covers that carry a photograph: the author may give their own.
const PHOTO_COVERS = ["infath-1", "infath-6"];

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
  onPage,
}: {
  detail: Detail;
  run: Run;
  reload: () => Promise<void>;
  section: "auction" | "closing";
  onSaved?: () => void;
  // The page being filled and how many there are, for the step navigation.
  onPage?: (index: number, count: number) => void;
}) {
  const t = useTranslations("auction");
  const p = useTranslations("bookletPages");
  const sv = useTranslations("supervisor");
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
  // Infath, or another body with its own logo and introduction page.
  const [supervisor, setSupervisor] = useState(
    String(auction.supervisor || "infath"),
  );
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
  const at = useRef(index);
  at.current = index;
  useEffect(() => onPage?.(index, parts.length), [index, parts.length]);
  // "Previous" in the step navigation: back one page while there is one.
  useEffect(() => {
    const element = form.current;
    if (!element) return;
    const back = (event: Event) => {
      if (at.current > 0) {
        event.preventDefault();
        setIndex(at.current - 1);
      }
    };
    element.addEventListener("wizard-previous", back);
    return () => element.removeEventListener("wizard-previous", back);
  }, []);
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
    // Another supervising body needs its logo (stored on its own).
    const logoButton = container.querySelector<HTMLButtonElement>(
      'button[name="supervisor_logo"][data-missing]',
    );
    if (logoButton) {
      logoButton.setCustomValidity(sv("otherLogoMissing"));
      logoButton.reportValidity();
      return false;
    }
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
          // The project is called after its auction until it is given its own name.
          name:
            values.auction_name &&
            (!auction.auction_name ||
              detail.project.name === auction.auction_name)
              ? String(values.auction_name)
              : detail.project.name,
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
  // The author's own photograph for a photographic cover, stored at once.
  const photo = detail.images.find((i) => i.category === "cover" && !i.item_id);
  const photoInput = useRef<HTMLInputElement>(null);
  // The preview starts again from the saved project when it reloads: hand it
  // this page's unsaved choices again (the cover may not be saved yet).
  // (The same for another supervising body's logo, stored at once too.)
  const logoSeen = detail.images.find(
    (i) => i.category === "supervisor_logo" && !i.item_id,
  )?.id;
  const photoSeen = useRef(`${photo?.id}|${logoSeen}`);
  useEffect(() => {
    const seen = `${photo?.id}|${logoSeen}`;
    if (photoSeen.current === seen) return;
    photoSeen.current = seen;
    const timer = setTimeout(() =>
      form.current?.dispatchEvent(new Event("preview-form", { bubbles: true })),
    );
    return () => clearTimeout(timer);
  }, [photo?.id, logoSeen]);
  const editImages = useImageEditor();
  const uploadPhoto = async (picked?: File) => {
    if (!picked) return;
    // The photograph is placed in the chosen cover's own window first.
    const window = detail.workflow?.rules.image_frames?.cover[cover];
    const edited = window
      ? await editImages([picked], {
          frames: [{ key: "cover", width: window[0], height: window[1] }],
          title: p("coverPhoto"),
        })
      : [picked];
    const file = edited?.[0];
    if (!file) return;
    void run(async () => {
      const body = new FormData();
      body.set("category", "cover");
      body.set("file", file);
      await api(`/projects/${detail.project.id}/images`, {
        method: "POST",
        body,
      });
      await reload();
    }, p("coverPhotoSaved"));
  };
  const removePhoto = () =>
    void run(async () => {
      await api(`/images/${photo!.id}`, { method: "DELETE" });
      await reload();
    }, p("coverPhotoRemoved"));
  // Another supervising body's logo, stored at once like the cover photograph.
  const bodyLogo = detail.images.find(
    (i) => i.category === "supervisor_logo" && !i.item_id,
  );
  const bodyLogoInput = useRef<HTMLInputElement>(null);
  const uploadBodyLogo = async (picked?: File) => {
    if (!picked) return;
    const frame = detail.workflow?.rules.image_frames?.logo;
    const edited = await editImages([picked], {
      frames: [
        {
          key: "logo",
          width: frame?.[0] || 145.2,
          height: frame?.[1] || 67,
        },
      ],
      title: sv("otherLogo"),
      logo: true,
    });
    const file = edited?.[0];
    if (!file) return;
    void run(async () => {
      const body = new FormData();
      body.set("category", "supervisor_logo");
      body.set("file", file);
      await api(`/projects/${detail.project.id}/images`, {
        method: "POST",
        body,
      });
      await reload();
    }, sv("logoSaved"));
  };
  const agent = detail.selling_agent || {};
  const logo = detail.images.find(
    (i) => i.id === agent.logo_image_id || i.category === "agent_logo",
  );
  const agentIssues = detail.workflow?.stages.agent?.missing || [];
  // Each press suggests the name after the current one; the author may edit it.
  const suggestName = () => {
    const input = form.current?.querySelector<HTMLInputElement>(
      'input[name="auction_name"]',
    );
    if (!input) return;
    const language = String(
      new FormData(form.current!).get("document_language") ||
        auction.document_language ||
        "ar",
    );
    const ideas = nameIdeas(detail.items, language);
    const next = ideas[(ideas.indexOf(input.value.trim()) + 1) % ideas.length];
    // Set as if typed, so the form and the live preview take it.
    Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      "value",
    )!.set!.call(input, next);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.setCustomValidity("");
    input.focus();
  };

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
              {item.number && <span>{p("page", { number: item.number })}</span>}
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
              {PHOTO_COVERS.includes(cover) && (
                <div className="cover-photo-box">
                  {photo && (
                    <img
                      src={`/api/images/${photo.id}?size=preview`}
                      alt={p("coverPhoto")}
                    />
                  )}
                  <div>
                    <strong>{p("coverPhoto")}</strong>
                    <p className="muted">
                      {p(photo ? "coverPhotoOwn" : "coverPhotoHelp")}
                    </p>
                    <div className="cover-photo-actions">
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => photoInput.current?.click()}
                      >
                        <ImagePlus size={16} />
                        {p(photo ? "coverPhotoReplace" : "coverPhotoChoose")}
                      </button>
                      {photo && (
                        <button
                          type="button"
                          className="text-button danger"
                          onClick={removePhoto}
                        >
                          {p("coverPhotoRemove")}
                        </button>
                      )}
                    </div>
                    {/* Not a form field: the photograph is stored on its own. */}
                    <input
                      ref={photoInput}
                      type="file"
                      hidden
                      aria-label={p("coverPhoto")}
                      accept="image/jpeg,image/png,image/webp"
                      onChange={(event) => {
                        void uploadPhoto(event.target.files?.[0]);
                        event.target.value = "";
                      }}
                    />
                  </div>
                </div>
              )}
            </>
          )}
          {item.fields &&
            (() => {
              // Dates and times sit together in a schedule panel; the fields
              // before and after it keep their order.
              const shown = visible(item.fields);
              const timed = (key: string) =>
                /_(date|time)$/.test(key) || key === "close_interval_minutes";
              const first = shown.findIndex(timed);
              const before = first < 0 ? shown : shown.slice(0, first);
              const schedule = shown.filter(timed);
              const after =
                first < 0 ? [] : shown.slice(first).filter((k) => !timed(k));
              const values = { ...auction, ...draft };
              const days = (() => {
                const start = Date.parse(String(values.auction_start_date));
                const end = Date.parse(String(values.auction_end_date));
                return item.cover && start && end && end >= start
                  ? Math.round((end - start) / 86400000) + 1
                  : 0;
              })();
              return (
                <>
                  {item.cover && before.includes("auction_name") ? (
                    // The assignment number beside the name, and between
                    // them the button that suggests one.
                    <div className="name-row">
                      <Fields
                        fields={before.filter((k) => k !== "auction_name")}
                        values={values}
                        requiredFields={rules?.required}
                      />
                      <button
                        type="button"
                        className="secondary suggest-name"
                        title={p("suggestNameHelp")}
                        onClick={suggestName}
                      >
                        <Sparkles size={16} />
                        {p("suggestName")}
                      </button>
                      <Fields
                        fields={["auction_name"]}
                        values={values}
                        requiredFields={rules?.required}
                      />
                    </div>
                  ) : (
                    before.length > 0 && (
                      <Fields
                        fields={before}
                        values={values}
                        requiredFields={rules?.required}
                      />
                    )
                  )}
                  {item.cover && (
                    <fieldset className="choice-group">
                      <legend>{t("auction_type")}</legend>
                      <div className="choice-cards">
                        {(
                          [
                            ["electronic", Globe],
                            ["physical", Building2],
                            ["hybrid", Layers],
                          ] as const
                        ).map(([key, Icon]) => (
                          <label
                            key={key}
                            className={
                              kind === key
                                ? "choice-card selected"
                                : "choice-card"
                            }
                          >
                            <input
                              type="radio"
                              name="auction_type"
                              value={key}
                              checked={kind === key}
                              onChange={() => setKind(key)}
                            />
                            <span className="choice-icon">
                              <Icon size={20} />
                            </span>
                            {kind === key && (
                              <Check className="choice-check" size={18} />
                            )}
                            <strong>{t(key)}</strong>
                            <small>{f("typeHelp_" + key)}</small>
                          </label>
                        ))}
                      </div>
                    </fieldset>
                  )}
                  {schedule.length > 0 && (
                    <section className="schedule-panel">
                      <header>
                        <h4>
                          {item.cover ? (
                            <CalendarDays size={18} />
                          ) : (
                            <Clock3 size={18} />
                          )}
                          {t("schedule")}
                        </h4>
                        {days > 0 && (
                          <span className="chip done">
                            {p("duration", { days })}
                          </span>
                        )}
                      </header>
                      <Fields
                        fields={schedule}
                        values={values}
                        requiredFields={rules?.required}
                      />
                    </section>
                  )}
                  {after.length > 0 && (
                    <Fields
                      fields={after}
                      values={values}
                      requiredFields={rules?.required}
                    />
                  )}
                </>
              );
            })()}
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
          {item.supervisor && (
            <>
              <fieldset className="choice-group">
                <legend>{sv("choice")}</legend>
                <div className="choice-cards two">
                  {(
                    [
                      ["infath", Landmark],
                      ["other", Building2],
                    ] as const
                  ).map(([key, Icon]) => (
                    <label
                      key={key}
                      className={
                        supervisor === key
                          ? "choice-card selected"
                          : "choice-card"
                      }
                    >
                      <input
                        type="radio"
                        name="supervisor"
                        value={key}
                        checked={supervisor === key}
                        onChange={() => setSupervisor(key)}
                      />
                      <span className="choice-icon">
                        <Icon size={20} />
                      </span>
                      {supervisor === key && (
                        <Check className="choice-check" size={18} />
                      )}
                      <strong>{sv(key)}</strong>
                      <small>{sv(key + "ChoiceHelp")}</small>
                    </label>
                  ))}
                </div>
              </fieldset>
              {supervisor === "other" && (
                <>
                  <div className="cover-photo-box">
                    {bodyLogo && (
                      <img
                        src={`/api/images/${bodyLogo.id}?size=preview`}
                        alt={sv("otherLogo")}
                      />
                    )}
                    <div>
                      <strong>
                        {sv("otherLogo")}
                        <b aria-hidden="true"> *</b>
                      </strong>
                      <p className="muted">
                        {bodyLogo
                          ? sv("otherLogoHelp")
                          : sv("otherLogoMissing")}
                      </p>
                      <div className="cover-photo-actions">
                        <button
                          type="button"
                          name="supervisor_logo"
                          className="secondary"
                          data-missing={bodyLogo ? undefined : ""}
                          onClick={(e) => {
                            e.currentTarget.setCustomValidity("");
                            bodyLogoInput.current?.click();
                          }}
                        >
                          <ImagePlus size={16} />
                          {sv(bodyLogo ? "replaceLogo" : "chooseLogo")}
                        </button>
                      </div>
                      <input
                        ref={bodyLogoInput}
                        type="file"
                        hidden
                        aria-label={sv("otherLogo")}
                        accept="image/jpeg,image/png,image/webp"
                        onChange={(event) => {
                          void uploadBodyLogo(event.target.files?.[0]);
                          event.target.value = "";
                        }}
                      />
                    </div>
                  </div>
                  <Fields
                    fields={[
                      "supervisor_title",
                      "supervisor_text",
                      "supervisor_phone",
                      "supervisor_website",
                      "supervisor_social",
                    ]}
                    values={{ ...auction, ...draft }}
                    requiredFields={["supervisor_title", "supervisor_text"]}
                  />
                </>
              )}
            </>
          )}
          {item.terms && (
            <TermsText
              initial={String(
                auction.terms_text ||
                  detail.workflow?.rules.terms_default ||
                  "",
              )}
              guide={String(detail.workflow?.rules.terms_default || "")}
            />
          )}
          {/* The agent's details live in the account: nothing is repeated
              here, only what is still missing and the way to its place. */}
          {item.agent && (
            <div className="agent-note">
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
                <UserRound size={16} />
                {p("agentEdit")}
              </button>
            </div>
          )}
        </div>
      ))}
      {/* No buttons of its own: the step navigation saves this page and moves
          on (submit), or steps back a page ("wizard-previous"). */}
    </form>
  );
}
