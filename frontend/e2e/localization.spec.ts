import { completeAccount } from "./account-setup";
import { completeBookletBasics } from "./required-setup";
import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { createTranslator } from "next-intl";
import en from "../messages/en.json";
import ar from "../messages/ar.json";
test.use({ actionTimeout: 20000 });
const root = path.resolve(process.cwd(), "..");
const env = Object.fromEntries(
  fs
    .readFileSync(path.join(root, ".env"), "utf8")
    .split("\n")
    .filter((l) => l.includes("=") && !l.startsWith("#"))
    .map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1)]),
);
for (const locale of ["en", "ar"] as const)
  for (const mobile of [false, true]) {
    test(`${locale} ${mobile ? "mobile" : "desktop"} complete localized workflow`, async ({
      page,
      context,
    }) => {
      const t = createTranslator({
        locale,
        messages: locale === "ar" ? ar : en,
      });
      const problems: string[] = [];
      page.on("pageerror", (e) => problems.push(e.message));
      page.on("console", (m) => {
        if (
          m.type() === "error" &&
          /MISSING_MESSAGE|FORMATTING_ERROR|INVALID_MESSAGE|hydration/i.test(
            m.text(),
          )
        )
          problems.push(m.text());
      });
      if (mobile) await page.setViewportSize({ width: 390, height: 844 });
      await page.goto("/");
      await page.locator(".language-switcher").selectOption(locale);
      await expect(page.locator("html")).toHaveAttribute(
        "dir",
        locale === "ar" ? "rtl" : "ltr",
      );
      await page.reload();
      await expect(page.locator("html")).toHaveAttribute("lang", locale);
      await expect(page.locator(".language-switcher")).toHaveValue(locale);
      await page.getByLabel(t("ui.email_address")).fill(env.ADMIN_EMAIL);
      await expect(page.getByLabel(t("ui.email_address"))).toHaveAttribute(
        "dir",
        "ltr",
      );
      await page
        .getByLabel(t("ui.password"), { exact: true })
        .fill(env.ADMIN_PASSWORD);
      await page
        .getByRole("button", { name: t("ui.sign_in_to_workspace") })
        .click();
      await completeAccount(page);
      await expect(
        page.getByRole("heading", { name: t("flow.adminHome") }),
      ).toBeVisible();
      await expect(page.locator(".admin-grid")).toBeVisible();
      const noOverflow = async () =>
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
        ).toBeTruthy();
      await noOverflow();
      await page.screenshot({
        path: path.join(
          root,
          `output/${locale}-${mobile ? "mobile" : "desktop"}-dashboard.png`,
        ),
        fullPage: true,
      });
      const nav = async (name: string) => {
        if (mobile)
          await page
            .getByRole("button", { name: t("ui.toggle_navigation") })
            .click();
        await page
          .locator(".sidebar")
          .getByRole("button", { name, exact: true })
          .click();
      };
      await nav(t("ui.create_project"));
      // Required validation uses the selected language; unsaved input survives switching.
      await page
        .locator("form")
        .getByRole("button", { name: t("ui.create_project") })
        .click();
      expect(
        await page
          .getByLabel(t("ui.project_name"), { exact: true })
          .evaluate((e: HTMLInputElement) => e.validationMessage),
      ).toBe(t("common.required"));
      const projectName = `مشروع Atlas ${locale} ${mobile ? "mobile" : "desktop"} — Long mixed project title for layout checking`;
      await page
        .getByLabel(t("ui.project_name"), { exact: true })
        .fill(projectName);
      await page
        .locator(".language-switcher")
        .selectOption(locale === "ar" ? "en" : "ar");
      await page.locator(".language-switcher").selectOption(locale);
      await expect(
        page.getByLabel(t("ui.project_name"), { exact: true }),
      ).toHaveValue(projectName);
      await page.getByLabel(t("projectFlow.scope")).selectOption("booklet");
      await page.getByLabel(t("ui.reference_code")).fill("L10N-" + Date.now());
      await expect(page.getByLabel(t("ui.reference_code"))).toHaveAttribute(
        "dir",
        "ltr",
      );
      await page
        .getByLabel(t("ui.customer_entity"))
        .fill("مؤسسة Atlas / Amman");
      await page
        .getByLabel(t("ui.description"), { exact: true })
        .fill(
          "تفاصيل المشروع مع رابط https://example.com/assets?id=A-01 وبريد test@example.com",
        );
      await page
        .locator("form")
        .getByRole("button", { name: t("ui.create_project") })
        .click();
      await expect(
        page.getByRole("heading", { name: projectName }),
      ).toBeVisible();
      const projectId = (
        await page.request.get("/api/projects").then((r) => r.json())
      ).find((p: { name: string }) => p.name === projectName).id;
      await completeBookletBasics(page);
      await page
        .getByRole("button", { name: new RegExp(t("flow.properties")) })
        .click();
      await page
        .getByRole("button", { name: t("ui.add_item"), exact: true })
        .click();
      await page.getByLabel(t("ui.item_title")).fill("مولد Generator A-01");
      await page.locator('[name="property.property_type"]').fill("معدات");
      await page.locator('[name="property.city"]').fill("الرياض");
      await page.getByLabel(t("ui.quantity"), { exact: true }).fill("2");
      await page.getByLabel(t("ui.unit_financial_value")).fill("1200.50");
      await page
        .locator("form summary")
        .filter({ hasText: t("flow.otherTools") })
        .click();
      await page.getByLabel(t("ui.additional_attributes_json")).fill("invalid");
      await page
        .getByRole("button", { name: t("ui.save_item"), exact: true })
        .click();
      await expect(
        page.getByText(t("ui.additional_attributes_must_be_a_json_object")),
      ).toBeVisible();
      await page
        .getByLabel(t("ui.additional_attributes_json"))
        .fill('{"URL":"https://example.com/A-01","البريد":"test@example.com"}');
      await page
        .getByRole("button", { name: t("ui.save_item"), exact: true })
        .click();
      await expect(
        page.getByText("مولد Generator A-01", { exact: true }),
      ).toBeVisible();
      await page
        .getByRole("button", { name: t("ui.delete"), exact: true })
        .click();
      await expect(page.getByRole("dialog")).toBeVisible();
      await expect(page.getByRole("dialog")).toHaveCSS(
        "direction",
        locale === "ar" ? "rtl" : "ltr",
      );
      await page
        .getByRole("dialog")
        .getByRole("button", { name: t("ui.cancel") })
        .click();
      await expect(
        page.getByText("مولد Generator A-01", { exact: true }),
      ).toBeVisible();
      await page
        .getByRole("button", { name: t("flow.importProperties"), exact: true })
        .click();
      await page
        .getByLabel(t("ui.excel_workbook"))
        .setInputFiles(path.join(root, "samples/approved-properties.xlsx"));
      await page.getByLabel(t("excel.city"), { exact: true }).fill("الرياض");
      await page
        .getByRole("button", { name: t("ui.preview_workbook") })
        .click();
      await expect(
        page.getByText(t("excel.summary", { valid: 3, invalid: 0 })),
      ).toBeVisible();
      await page
        .getByRole("button", { name: t("excel.import", { count: 3 }) })
        .click();
      await expect(page.locator(".workflow-steps .selected")).toContainText(
        t("flow.properties"),
      );
      await expect(
        page
          .locator("tbody strong")
          .getByText("أرض · حي تجريبي 1", { exact: true }),
      ).toBeVisible();
      await page
        .getByRole("button", { name: new RegExp(t("flow.images")) })
        .click();
      // Each property has a main-image box; upload into the first one.
      const mainBox = page.locator('[data-slot^="main:"]').first();
      await mainBox
        .locator('input[type="file"]')
        .setInputFiles(path.join(root, "samples/demo-generator.jpg"));
      await mainBox
        .getByRole("button", { name: t("imagesStep.upload"), exact: true })
        .click();
      await expect(
        page.getByAltText(t("ui.uploaded_project_asset")),
      ).toBeVisible();
      await page
        .getByRole("button", { name: new RegExp(t("flow.review")) })
        .click();
      await page
        .getByLabel(t("common.outputLanguage"), { exact: true })
        .selectOption(locale);
      await page
        .getByRole("button", { name: t("flow.otherTools"), exact: true })
        .click();
      await page
        .getByRole("button", { name: t("ui.select_all_eight") })
        .click();
      await page
        .locator(".generator-option")
        .filter({ hasText: t("labels.project_booklet") })
        .locator("input")
        .uncheck();
      await noOverflow();
      await page
        .getByRole("button", { name: t("common.generateButton", { count: 5 }) })
        .click();
      await expect(page.locator(".output-card")).toHaveCount(5, {
        timeout: 120000,
      });
      await page
        .locator(".output-card")
        .filter({
          has: page.getByRole("heading", { name: t("labels.asset_study") }),
        })
        .click();
      await page
        .getByLabel(t("ui.editable_content"))
        .fill("Reviewed copy / نص تمت مراجعته");
      await page
        .getByRole("button", { name: t("ui.save_reviewed_text") })
        .click();
      await expect(
        page.getByRole("status").filter({ hasText: t("ui.review_saved") }),
      ).toBeVisible();
      await page.getByRole("button", { name: t("ui.approve_output") }).click();
      const link = page.getByRole("link", { name: t("common.downloadPdf") });
      await expect(link).toBeVisible();
      const downloadPromise = page.waitForEvent("download");
      await link.click();
      const download = await downloadPromise;
      expect(download.suggestedFilename()).toBe("asset_study.pdf");
      await download.saveAs(
        path.join(
          root,
          `output/${locale}-${mobile ? "mobile" : "desktop"}-social.pdf`,
        ),
      );
      await page.screenshot({
        path: path.join(
          root,
          `output/${locale}-${mobile ? "mobile" : "desktop"}-review.png`,
        ),
        fullPage: true,
      });
      await noOverflow();
      await page
        .getByRole("button", { name: t("ui.regenerate"), exact: true })
        .click();
      await page
        .getByRole("dialog")
        .getByRole("button", { name: t("common.confirm"), exact: true })
        .click();
      await expect(
        page.getByRole("status").filter({ hasText: t("ui.draft_regenerated") }),
      ).toBeVisible();
      const detail = await page.request
        .get("/api/projects/" + projectId)
        .then((r) => r.json());
      expect(detail.project.name).toBe(projectName);
      expect(
        detail.outputs.every(
          (o: { content: { output_language: string } }) =>
            o.content.output_language === locale,
        ),
      ).toBeTruthy();
      await nav(t("ui.settings"));
      await expect(
        page.getByRole("heading", { name: t("ui.organization_branding") }),
      ).toBeVisible();
      await page.getByRole("button", { name: t("ui.save_settings") }).click();
      await expect(
        page.getByRole("status").filter({ hasText: t("ui.settings_saved") }),
      ).toBeVisible();
      await noOverflow();
      await page.reload();
      await expect(page.locator("html")).toHaveAttribute("lang", locale);
      if (mobile)
        await page
          .getByRole("button", { name: t("ui.toggle_navigation") })
          .click();
      await page.getByRole("button", { name: t("ui.log_out") }).click();
      await expect(
        page.getByRole("heading", { name: t("ui.welcome_back") }),
      ).toBeVisible();
      expect(
        (await context.cookies()).find((c) => c.name === "atlas_locale")?.value,
      ).toBe(locale);
      expect(problems).toEqual([]);
    });
  }
