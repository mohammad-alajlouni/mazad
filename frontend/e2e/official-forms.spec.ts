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
test("each official form is its own section of the project, issued without the booklet", async ({
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
  // A full project whose booklet is far from ready (no closing pages, no
  // photographs): its forms need only its data.
  const project = await newProject(
    page,
    "Forms " + Date.now(),
    "project",
    {},
    {
      auction_name: "مزاد النماذج",
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
  await page.reload();
  await page.locator(".sidebar nav button").nth(1).click();
  await page.getByText(project.name, { exact: true }).first().click();
  const sections = page.locator(".project-sections");
  await sections.getByRole("button", { name: "Auction request" }).click();
  const form = page.locator(".forms-step");
  await expect(form).toBeVisible();
  // The project's values are shown, not asked for again.
  await expect(
    form.locator(".form-given", { hasText: "مزاد النماذج" }),
  ).toHaveCount(1);
  await expect(form.getByText("From project data").first()).toBeVisible();
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
  // Issued alone: saved, generated, open for review.
  await page.getByRole("button", { name: /Save and issue/ }).click();
  await expect(
    page.getByText("Form issued and ready for review"),
  ).toBeVisible();
  await expect(page.locator(".review h1")).toHaveText("Auction request form");
  await page
    .getByRole("button", { name: "← Back to workspace", exact: true })
    .click();
  // Back in the project, where its sections are.
  await expect(sections).toBeVisible();
  await sections.getByRole("button", { name: "Property study" }).click();
  await expect(page.locator(".live-preview-paper")).toHaveAttribute(
    "data-page-kind",
    "study",
  );
  await page
    .getByRole("radio", { name: /fully sellable: Yes|بالكامل: Yes/ })
    .first()
    .click();
  await page.getByRole("button", { name: /Save and issue/ }).click();
  await expect(page.locator(".review h1")).toHaveText("Property study form");
  const saved = await page.request
    .get(`/api/projects/${project.id}/forms`)
    .then((r) => r.json());
  expect(saved.forms.request.cr_number).toBe("1010123456");
  const answers = Object.values(saved.forms.properties)[0] as {
    answers: Record<string, { answer: string }>;
  };
  expect(answers.answers.sellable.answer).toBe("yes");
  // Only the two forms: no booklet, banners or posts were needed.
  const detail = await page.request
    .get(`/api/projects/${project.id}`)
    .then((r) => r.json());
  expect(
    detail.outputs.map((o: { output_type: string }) => o.output_type).sort(),
  ).toEqual(["auction_request", "property_study"]);
  expect(errors).toEqual([]);
});
