import { completeAccount } from "./account-setup";
import { newProject } from "./required-setup";
import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
const root = path.resolve(process.cwd(), "..");
const env = Object.fromEntries(
  fs
    .readFileSync(path.join(root, ".env"), "utf8")
    .split("\n")
    .filter((l) => l.includes("=") && !l.startsWith("#"))
    .map((l) => {
      const i = l.indexOf("=");
      return [l.slice(0, i), l.slice(i + 1)];
    }),
);
test("the authority's reports are prepared after the auction, from its project", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/#login");
  await page.locator(".language-switcher").selectOption("en");
  await page.getByLabel("Email address").fill(env.ADMIN_EMAIL);
  await page.getByLabel("Password", { exact: true }).fill(env.ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Sign in to workspace" }).click();
  await completeAccount(page);
  const project = await newProject(
    page,
    "Reports " + Date.now(),
    "project",
    {},
    {
      auction_name: "مزاد الريان",
      auction_date: "2026-07-27",
      start_time: "16:00",
      physical_location: "الرياض",
    },
  );
  for (const [deed, type] of [
    ["542104012563", "فيلا سكنية"],
    ["842122003917", "أرض مسورة"],
  ]) {
    const added = await page.request.post(`/api/projects/${project.id}/items`, {
      data: {
        title: type,
        property_data: {
          property_type: type,
          city: "الرياض",
          district: "الخطة",
          area: "875",
          deed_number: deed,
          usage: "سكني",
        },
      },
    });
    expect(added.ok()).toBeTruthy();
  }
  // Its own section: the auction's project is chosen first.
  await page.reload();
  await page
    .locator(".sidebar")
    .getByRole("button", { name: "REGA reports", exact: true })
    .click();
  await page.getByText(project.name, { exact: true }).first().click();
  const form = page.locator(".reports-form");
  await expect(form).toBeVisible();
  await expect(
    form.locator(".form-given", { hasText: "مزاد الريان" }),
  ).toHaveCount(1);
  const preview = page.frameLocator(
    '.live-preview-paper iframe[aria-hidden="false"]',
  );
  // The closing form: the project's properties, the results entered here,
  // shown at once on the authority's page.
  await expect(page.locator(".live-preview-paper")).toHaveAttribute(
    "data-page-kind",
    "closing_form",
  );
  await expect(preview.getByText("542104012563")).toBeVisible();
  await form
    .getByLabel("Auction approval number", { exact: true })
    .fill("7833");
  await expect(preview.getByText("7833")).toBeVisible();
  await form.getByRole("radio", { name: "فيلا سكنية: Sold" }).click();
  await form.getByLabel("Awarded to").fill("فهد الشمري");
  await form.getByLabel("Award value").fill("237000");
  await form.getByRole("radio", { name: "أرض مسورة: Not sold" }).click();
  await expect(preview.getByText("237,000")).toBeVisible();
  await page
    .getByRole("button", { name: "Save and issue the Auction closing form" })
    .click();
  await expect(page.locator(".review h1")).toHaveText("Auction closing form");
  await page
    .getByRole("button", { name: "← Back to workspace", exact: true })
    .click();
  // The outputs report: its pages on the authority's template, the results
  // carried over from the closing form.
  await page
    .getByRole("button", { name: "Outputs report", exact: true })
    .click();
  await expect(page.locator(".live-preview-paper")).toHaveAttribute(
    "data-page-kind",
    "cover",
  );
  await expect(preview.getByText("مزاد الريان")).toBeVisible();
  await form.getByLabel("Court").fill("محكمة التنفيذ بالرياض");
  await expect(
    preview.getByText("وبقرار من محكمة التنفيذ بالرياض"),
  ).toBeVisible();
  await form.getByLabel("Participants").fill("8");
  await page
    .getByLabel("Preview page")
    .selectOption({ label: "7. Asset list" });
  await expect(preview.getByText("تم البيع")).toBeVisible();
  await page
    .getByRole("button", { name: "Save and issue the Outputs report" })
    .click();
  await expect(page.locator(".review h1")).toHaveText("Auction outputs report");
  const detail = await page.request
    .get(`/api/projects/${project.id}`)
    .then((r) => r.json());
  expect(
    detail.outputs.map((o: { output_type: string }) => o.output_type).sort(),
  ).toEqual(["auction_closing", "outputs_report"]);
  expect(errors).toEqual([]);
});
