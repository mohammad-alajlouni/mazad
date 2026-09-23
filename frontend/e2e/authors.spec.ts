import { completeAccount } from "./account-setup";
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

test("Arabic default, administrator provisioning, private author booklet and approved PDF", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("lang", "ar");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await page.getByLabel(t("ui.email_address")).fill(env.ADMIN_EMAIL);
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
  const email = `author-${Date.now()}@example.com`,
    password = "Author-browser-test-123";
  await page.getByLabel(t("ui.email_address")).fill(email);
  await page.getByLabel(t("ui.password"), { exact: true }).fill(password);
  await page.getByRole("button", { name: t("flow.createUser") }).click();
  await expect(
    page.getByRole("cell", { name: email, exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: t("ui.log_out") }).click();
  await expect(page.locator(".login-form")).toBeVisible();
  await page.getByLabel(t("ui.email_address")).fill(email);
  await page.getByLabel(t("ui.password"), { exact: true }).fill(password);
  await page
    .getByRole("button", { name: t("ui.sign_in_to_workspace") })
    .click();
  await completeAccount(page);
  await expect(
    page.getByRole("heading", { name: t("flow.home") }),
  ).toBeVisible();
  await expect(
    page
      .locator(".sidebar")
      .getByRole("button", { name: t("ui.settings"), exact: true }),
  ).toHaveCount(0);
  await expect(
    page
      .locator(".sidebar")
      .getByRole("button", { name: t("flow.users"), exact: true }),
  ).toHaveCount(0);
  expect((await page.request.get("/api/admin/users")).status()).toBe(403);
  expect(await page.request.get("/api/projects").then((r) => r.json())).toEqual(
    [],
  );
  await page
    .getByRole("button", { name: t("flow.create"), exact: true })
    .first()
    .click();
  await page
    .getByLabel(t("ui.project_name"), { exact: true })
    .fill("مزاد المستخدم الجديد");
  await page.getByLabel(t("projectFlow.scope")).selectOption("booklet");
  await page.getByLabel(t("ui.reference_code")).fill(`AUTHOR-${Date.now()}`);
  await page
    .locator("form")
    .getByRole("button", { name: t("flow.create") })
    .click();
  const step = (key: keyof typeof ar.flow) =>
    page
      .locator(".workflow-steps")
      .getByRole("button", { name: new RegExp(t(`flow.${key}`)) });
  await expect(page.locator(".workflow-steps button")).toHaveCount(5);
  await step("review").click();
  await expect(
    page.locator('.auction-workspace [name="auction_date"]'),
  ).toBeVisible();
  await page
    .getByLabel(t("auction.auction_date"), { exact: true })
    .fill("2026-11-10");
  await page.getByLabel(t("auction.start_time"), { exact: true }).fill("16:00");
  await page
    .getByLabel(t("auction.physical_location"), { exact: true })
    .fill("الرياض");
  await page.getByRole("button", { name: t("auction.save_auction") }).click();
  await expect(page.locator(".workflow-steps .selected")).toContainText(
    t("flow.properties"),
  );
  await page
    .getByRole("button", { name: t("ui.add_item"), exact: true })
    .click();
  await page.getByLabel(t("ui.item_title")).fill("أرض سكنية — اختبار");
  await page
    .getByLabel(t("auction.property_type"), { exact: true })
    .fill("أرض");
  await page.getByLabel(t("auction.city"), { exact: true }).fill("الرياض");
  await page
    .getByRole("button", { name: t("ui.save_item"), exact: true })
    .click();
  await expect(
    page.getByText("أرض سكنية — اختبار", { exact: true }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await step("images").click();
  // The main image goes into that property's own box.
  const mainBox = page
    .locator(".image-slot")
    .filter({ hasText: "الصورة الرئيسية: أرض سكنية — اختبار" });
  await mainBox
    .locator('input[type="file"]')
    .setInputFiles(path.join(root, "samples/demo-generator.jpg"));
  await mainBox.getByRole("button", { name: "رفع", exact: true }).click();
  await expect(page.getByAltText(t("ui.uploaded_project_asset"))).toHaveCount(
    2,
  );
  await step("review").click();
  await expect(page.getByText(t("auction.ready"))).toBeVisible();
  await page.screenshot({
    path: path.join(root, "output/author-ar-mobile-review.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: t("flow.generate"), exact: true })
    .click();
  await expect(page.getByTitle(t("ui.output_preview"))).toBeVisible();
  await page.getByRole("button", { name: t("ui.approve_output") }).click();
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: t("common.downloadPdf") }).click();
  expect((await download).suggestedFilename()).toMatch(/^auction-/);
  const projects = await page.request
    .get("/api/projects")
    .then((r) => r.json());
  expect(projects).toHaveLength(1);
  const detail = await page.request
    .get("/api/projects/" + projects[0].id)
    .then((r) => r.json());
  expect(detail.outputs).toHaveLength(1);
  expect(detail.outputs[0].official_booklet).toBe(true);
  expect(detail.selling_agent.logo_image_id).toBeTruthy();
  expect(errors).toEqual([]);
});
