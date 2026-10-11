"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { ArrowLeft, Check } from "lucide-react";
import LanguageSwitcher from "./LanguageSwitcher";
import ThemeSwitcher from "./ThemeSwitcher";

// The four booklet pages of the hero, from the back of the pile to the cover.
const SHEETS = ["participation", "summary", "auction", "cover"] as const;
const STEPS = ["auction", "properties", "closing", "generate"] as const;
const DETAILS = [
  "preview",
  "excel",
  "editor",
  "summary",
  "deeds",
  "links",
  "approval",
  "languages",
] as const;
const FACTS = [
  ["6", "covers"],
  ["6", "banners"],
  ["3", "posts"],
  ["2", "languages"],
] as const;

// The public face of the platform, for selling agents: what it makes, how,
// and the way in. Its pictures are real outputs of the platform itself.
export default function Landing({ onEnter }: { onEnter: () => void }) {
  const t = useTranslations("landing");
  // "At the press of a button": the pile of pages fans out. It plays once on
  // arrival and again whenever the headline's own button is pressed.
  const [spread, setSpread] = useState(false);
  const [runs, setRuns] = useState(0);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  useEffect(() => {
    const calm = matchMedia("(prefers-reduced-motion: reduce)").matches;
    timer.current = setTimeout(() => setSpread(true), calm ? 0 : 650);
    return () => clearTimeout(timer.current);
  }, []);
  const press = () => {
    clearTimeout(timer.current);
    setRuns((n) => n + 1);
    setSpread(false);
    timer.current = setTimeout(() => setSpread(true), 380);
  };
  const enter = (
    <button type="button" className="lp-cta" onClick={onEnter}>
      {t("enter")}
      <ArrowLeft size={18} aria-hidden="true" />
    </button>
  );

  return (
    <div className="lp">
      <a className="lp-skip" href="#lp-main">
        {t("skip")}
      </a>
      <header className="lp-bar">
        <div className="lp-brand">
          <span className="lp-brand-mark" aria-hidden="true">
            {t("mark")}
          </span>
          {t("brand")}
        </div>
        <nav aria-label={t("nav")}>
          <a href="#lp-outputs">{t("navOutputs")}</a>
          <a href="#lp-steps">{t("navSteps")}</a>
          <a href="#lp-details">{t("navDetails")}</a>
        </nav>
        <div className="lp-bar-end">
          <ThemeSwitcher />
          <LanguageSwitcher />
          <button type="button" className="lp-signin" onClick={onEnter}>
            {t("signIn")}
          </button>
        </div>
      </header>

      <main id="lp-main">
        <section className="lp-hero">
          <div className="lp-hero-copy">
            <p className="lp-slug">{t("audience")}</p>
            <h1>
              <span>{t("heroLine1")}</span>
              <span className="lp-press-line">
                {t("heroLine2")}{" "}
                <button
                  type="button"
                  className="lp-key"
                  onClick={press}
                  aria-label={t("keyLabel")}
                >
                  {t("heroKey")}
                </button>
              </span>
            </h1>
            <p className="lp-lead">{t("lead")}</p>
            <div className="lp-actions">
              {enter}
              <a className="lp-more" href="#lp-outputs">
                {t("seeOutputs")}
              </a>
            </div>
            <p className="lp-hint">{t("keyHint")}</p>
          </div>

          <div
            className="lp-proof"
            data-state={spread ? "spread" : "stacked"}
            aria-label={t("proofLabel")}
            role="img"
          >
            <i className="lp-crop tl" />
            <i className="lp-crop tr" />
            <i className="lp-crop bl" />
            <i className="lp-crop br" />
            <p className="lp-ticket" aria-hidden="true">
              <span>{t("ticketJob")}</span>
              <span>{t("ticketSize")}</span>
              <span>
                {t("ticketRun")} {String(runs + 1).padStart(2, "0")}
              </span>
            </p>
            <div className="lp-fan" aria-hidden="true">
              {SHEETS.map((sheet, index) => (
                /* eslint-disable-next-line @next/next/no-img-element */
                <img
                  key={sheet}
                  className={"lp-sheet s" + index}
                  src={`/landing/${sheet}.webp`}
                  alt=""
                  width={760}
                  height={1075}
                  fetchPriority={sheet === "cover" ? "high" : undefined}
                />
              ))}
              <span className="lp-stamp">{t("stamp")}</span>
            </div>
          </div>
        </section>

        <ul className="lp-facts" aria-label={t("factsLabel")}>
          {FACTS.map(([figure, key]) => (
            <li key={key}>
              <strong>{figure}</strong>
              <span>{t("facts." + key)}</span>
            </li>
          ))}
        </ul>

        <section className="lp-section" id="lp-outputs">
          <header className="lp-heading">
            <p className="lp-folio">01</p>
            <h2>{t("outputsTitle")}</h2>
            <p>{t("outputsLead")}</p>
          </header>
          <div className="lp-outputs">
            <article className="lp-output booklet">
              <div className="lp-pages">
                {(["auction", "summary", "participation"] as const).map(
                  (page, index) => (
                    /* eslint-disable-next-line @next/next/no-img-element */
                    <img
                      key={page}
                      className={"p" + index}
                      src={`/landing/${page}.webp`}
                      alt={index ? "" : t("bookletAlt")}
                      width={760}
                      height={1075}
                      loading="lazy"
                    />
                  ),
                )}
              </div>
              <div className="lp-output-copy">
                <h3>{t("booklet.title")}</h3>
                <p>{t("booklet.text")}</p>
                <ul className="lp-specs">
                  <li>{t("booklet.spec1")}</li>
                  <li>{t("booklet.spec2")}</li>
                  <li>{t("booklet.spec3")}</li>
                </ul>
              </div>
            </article>
            <article className="lp-output banner">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/landing/banner.webp"
                alt={t("bannerAlt")}
                width={1400}
                height={700}
                loading="lazy"
              />
              <div className="lp-output-copy">
                <h3>{t("banner.title")}</h3>
                <p>{t("banner.text")}</p>
                <ul className="lp-sizes" aria-label={t("banner.sizes")}>
                  {["2×2", "4×2", "6×3", "10×3", "10×5", "15×5"].map((size) => (
                    <li key={size}>
                      <bdi dir="ltr">{size}</bdi>
                    </li>
                  ))}
                </ul>
              </div>
            </article>
            <article className="lp-output posts">
              <div className="lp-posts">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  className="story"
                  src="/landing/post-story.webp"
                  alt=""
                  width={600}
                  height={1067}
                  loading="lazy"
                />
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  className="square"
                  src="/landing/post-square.webp"
                  alt={t("postsAlt")}
                  width={720}
                  height={720}
                  loading="lazy"
                />
              </div>
              <div className="lp-output-copy">
                <h3>{t("posts.title")}</h3>
                <p>{t("posts.text")}</p>
                <ul className="lp-specs">
                  <li>{t("posts.spec1")}</li>
                  <li>{t("posts.spec2")}</li>
                </ul>
              </div>
            </article>
          </div>
        </section>

        <section className="lp-section" id="lp-steps">
          <header className="lp-heading">
            <p className="lp-folio">02</p>
            <h2>{t("stepsTitle")}</h2>
            <p>{t("stepsLead")}</p>
          </header>
          <ol className="lp-steps">
            {STEPS.map((step, index) => (
              <li key={step}>
                <span className="lp-tab" aria-hidden="true">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <h3>{t(`steps.${step}.title`)}</h3>
                <p>{t(`steps.${step}.text`)}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="lp-section" id="lp-details">
          <header className="lp-heading">
            <p className="lp-folio">03</p>
            <h2>{t("detailsTitle")}</h2>
            <p>{t("detailsLead")}</p>
          </header>
          <ul className="lp-details">
            {DETAILS.map((detail) => (
              <li key={detail}>
                <span className="lp-check" aria-hidden="true">
                  <Check size={15} strokeWidth={3} />
                </span>
                <div>
                  <h3>{t(`details.${detail}.title`)}</h3>
                  <p>{t(`details.${detail}.text`)}</p>
                </div>
              </li>
            ))}
          </ul>
        </section>

        <section className="lp-final">
          <i className="lp-crop tl" />
          <i className="lp-crop br" />
          <h2>{t("finalTitle")}</h2>
          <p>{t("finalText")}</p>
          {enter}
          <small>{t("finalNote")}</small>
        </section>
      </main>

      <footer className="lp-foot">
        <div className="lp-brand">
          <span className="lp-brand-mark" aria-hidden="true">
            {t("mark")}
          </span>
          {t("brand")}
        </div>
        <p>{t("footLine")}</p>
      </footer>
    </div>
  );
}
