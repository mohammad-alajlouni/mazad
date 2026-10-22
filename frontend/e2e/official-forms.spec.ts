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
test("the official forms take the booklet's data and the author fills the rest, with a live preview", async ({
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
    "Forms " + Date.now(),
    "booklet",
    {},
    {
      auction_name: "Forms auction",
      auction_date: "2026-10-10",
      start_time: "16:00",
      physical_location: "الرياض",
    },
  );
  const added = await page.request.post(`/api/projects/${project.id}/items`, {
    data: {
      title: "Villa",
      property_data: {
        property_type: "فيلا",
        city: "الرياض",
        area: "625.5",
        deed_number: "410112034455",
      },
    },
  });
  expect(added.ok()).toBeTruthy();
  // Open the project again, with its property.
  await page.locator(".sidebar nav button").nth(1).click();
  await page.getByText(project.name, { exact: true }).first().click();
  await page.locator(".workflow-steps").waitFor();
  await page.locator(".workflow-steps button", { hasText: "Forms" }).click();
  const form = page.locator(".forms-step");
  await expect(form).toBeVisible();
  // The booklet's values are shown, not asked for again.
  await expect(
    form.locator(".form-given", { hasText: "410112034455" }),
  ).toHaveCount(1);
  await expect(
    form.locator(".form-given", { hasText: "Forms auction" }),
  ).toHaveCount(1);
  // What is typed shows at once in the authority's form, in the preview.
  await form
    .locator("label", { hasText: "Commercial registration" })
    .locator("input")
    .fill("1010123456");
  const preview = page.frameLocator(
    '.live-preview-paper iframe[aria-hidden="false"]',
  );
  await expect(preview.getByText("1010123456")).toBeVisible();
  await expect(page.locator(".live-preview-paper")).toHaveAttribute(
    "data-page-kind",
    "request-1",
  );
  // Next saves the request form and opens the study.
  await page.locator(".nav-next").click();
  await expect(
    form.locator(".page-parts button.selected", { hasText: "Property study" }),
  ).toBeVisible();
  await expect(page.locator(".live-preview-paper")).toHaveAttribute(
    "data-page-kind",
    "study",
  );
  await page
    .getByRole("radio", { name: /fully sellable: Yes|بالكامل: Yes/ })
    .first()
    .click();
  await page.locator(".nav-next").click();
  await expect(
    page.locator(".workflow-steps button.selected", { hasText: "Review" }),
  ).toBeVisible();
  const saved = await page.request
    .get(`/api/projects/${project.id}/forms`)
    .then((r) => r.json());
  expect(saved.forms.request.cr_number).toBe("1010123456");
  const answers = Object.values(saved.forms.properties)[0] as {
    answers: Record<string, { answer: string }>;
  };
  expect(answers.answers.sellable.answer).toBe("yes");
  expect(errors).toEqual([]);
});
