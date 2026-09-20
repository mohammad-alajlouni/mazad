import { completeAccount } from "./account-setup";
import { completeBookletBasics } from "./required-setup";
import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { createTranslator } from "next-intl";
import ar from "../messages/ar.json";
const root = path.resolve(process.cwd(), "..");
const env = Object.fromEntries(
  fs
    .readFileSync(path.join(root, ".env"), "utf8")
    .split("\n")
    .filter((l) => l.includes("=") && !l.startsWith("#"))
    .map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1)]),
);
const t = createTranslator({ locale: "ar", messages: ar });
test("approved template download, invalid files, atomic import and stale preview", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel(t("ui.email_address")).fill(env.ADMIN_EMAIL);
  await page
    .getByLabel(t("ui.password"), { exact: true })
    .fill(env.ADMIN_PASSWORD);
  await page
    .getByRole("button", { name: t("ui.sign_in_to_workspace") })
    .click();
  await completeAccount(page);
  await page
    .getByRole("button", { name: t("flow.create"), exact: true })
    .first()
    .click();
  await page
    .getByLabel(t("ui.project_name"), { exact: true })
    .fill("فحص القالب المعتمد");
  await page.getByLabel(t("projectFlow.scope")).selectOption("booklet");
  await page.getByLabel(t("ui.reference_code")).fill(`APPROVED-${Date.now()}`);
  await page
    .locator("form")
    .getByRole("button", { name: t("flow.create") })
    .click();
  await completeBookletBasics(page);
  await page
    .getByRole("button", { name: new RegExp(t("flow.properties")) })
    .click();
  await page
    .getByRole("button", { name: t("flow.importProperties"), exact: true })
    .click();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: t("excel.download") }).click();
  expect((await downloadPromise).suggestedFilename()).toBe(
    "kutayyib-booklet-template.xlsx",
  );
  const input = page.getByLabel(t("ui.excel_workbook"));
  const preview = page.getByRole("button", { name: t("ui.preview_workbook") });
  await input.setInputFiles({
    name: "wrong.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("invalid"),
  });
  await preview.click();
  await expect(page.locator('.notice[role="alert"]')).toHaveText(
    t("excel.wrongType"),
  );
  await input.setInputFiles({
    name: "corrupt.xlsx",
    mimeType: "application/octet-stream",
    buffer: Buffer.from("invalid"),
  });
  await preview.click();
  await expect(page.locator('.notice[role="alert"]')).toContainText(
    t(
      "errors.COULD_NOT_READ_WORKBOOK_CHECK_ITS_FORMAT_AND_REMOVE_PASSWORD_PROTECTION",
    ),
  );
  await input.setInputFiles(
    path.join(root, "samples/approved-properties-invalid.xlsx"),
  );
  await preview.click();
  await expect(
    page.getByText(t("excel.summary", { valid: 2, invalid: 1 })),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: t("excel.import", { count: 2 }) }),
  ).toBeDisabled();
  await expect(page.locator(".excel-property").nth(1)).toContainText("F7:");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: path.join(root, "output/approved-import-errors-mobile.png"),
    fullPage: true,
  });
  await input.setInputFiles(
    path.join(root, "samples/approved-properties.xlsx"),
  );
  await expect(page.locator(".excel-property")).toHaveCount(0);
  await preview.click();
  const commit = page.getByRole("button", {
    name: t("excel.import", { count: 3 }),
  });
  await expect(commit).toBeDisabled();
  await page.getByRole("checkbox", { name: t("excel.acknowledge") }).check();
  await expect(commit).toBeEnabled();
  // A changed city/file must invalidate the previous preview.
  await page.getByLabel(t("excel.city"), { exact: true }).fill("حائل");
  await expect(page.locator(".excel-property")).toHaveCount(0);
  await preview.click();
  await expect(commit).toBeEnabled();
  await commit.click();
  await expect(page.locator(".workflow-steps .selected")).toContainText(
    t("flow.properties"),
  );
  await expect(
    page
      .locator("tbody strong")
      .getByText("أرض · حي تجريبي 1", { exact: true }),
  ).toBeVisible();
});
