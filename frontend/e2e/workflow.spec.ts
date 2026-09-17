import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const root = path.resolve(process.cwd(), "..");
const envFile = path.join(root, ".env");
const local = fs.existsSync(envFile)
  ? Object.fromEntries(
      fs
        .readFileSync(envFile, "utf8")
        .split("\n")
        .filter((line) => line.includes("=") && !line.startsWith("#"))
        .map((line) => {
          const i = line.indexOf("=");
          return [line.slice(0, i), line.slice(i + 1)];
        }),
    )
  : {};
const email = process.env.ADMIN_EMAIL || local.ADMIN_EMAIL;
const password = process.env.ADMIN_PASSWORD || local.ADMIN_PASSWORD;

test("administrator completes manual and Excel input, uploads image, reviews and exports", async ({
  page,
}) => {
  test.skip(
    !email || !password,
    "Set ADMIN_EMAIL and ADMIN_PASSWORD or create the root .env",
  );
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in to workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Your workspace, at a glance." }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Create project", exact: true })
    .first()
    .click();
  await page
    .getByLabel("Project name", { exact: true })
    .fill("Browser workflow demo");
  await page.getByLabel("Reference code").fill("BROWSER-" + Date.now());
  await page.getByLabel("Customer / entity").fill("Development demo");
  await page
    .locator("form")
    .getByRole("button", { name: "Create project" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Browser workflow demo" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Items", exact: true }).click();
  await page.getByRole("button", { name: "Add item", exact: true }).click();
  await page.getByLabel("Item title").fill("وحدة طاقة تجريبية");
  await page.getByLabel("Quantity", { exact: true }).fill("2");
  await page.getByLabel("Unit financial value").fill("1200.50");
  await page
    .getByLabel("Description", { exact: true })
    .fill("بيانات تجريبية للمراجعة");
  await page.getByRole("button", { name: "Save item", exact: true }).click();
  await expect(
    page.getByText("وحدة طاقة تجريبية", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Excel Import", exact: true }).click();
  await page
    .getByLabel("Excel workbook")
    .setInputFiles(path.join(root, "samples/demo-assets.xlsx"));
  await page.getByRole("button", { name: "Preview workbook" }).click();
  await expect(
    page.getByText("3 valid rows · 0 invalid rows (will be skipped)"),
  ).toBeVisible();
  await page.getByRole("button", { name: "Import 3 valid rows" }).click();
  await expect(page.locator(".project-tabs .selected")).toHaveText("Items");
  await expect(
    page.getByText("Industrial compressor", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Images", exact: true }).click();
  await page
    .getByLabel("Attach to")
    .selectOption({ label: "وحدة طاقة تجريبية" });
  await page
    .getByLabel("Image", { exact: true })
    .setInputFiles(path.join(root, "samples/demo-generator.jpg"));
  await page.getByRole("button", { name: "Upload image", exact: true }).click();
  await expect(page.getByAltText("Uploaded project asset")).toBeVisible();
  await page.getByRole("button", { name: "Generate", exact: true }).click();
  await page.getByRole("button", { name: "Select all eight" }).click();
  await page.getByRole("button", { name: "Generate 8 draft outputs" }).click();
  await expect(page.locator(".output-card")).toHaveCount(8, {
    timeout: 120000,
  });
  await page
    .locator(".output-card")
    .filter({ has: page.getByRole("heading", { name: "Social Content" }) })
    .click();
  await page
    .getByLabel("Editable content")
    .fill("Reviewed browser demo copy / محتوى تمت مراجعته");
  await page.getByRole("button", { name: "Save reviewed text" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Review saved" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Approve output" }).click();
  await expect(
    page.getByRole("link", { name: "Download document · PDF ↓" }),
  ).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download document · PDF ↓" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("social_content.pdf");
  await page.screenshot({
    path: path.join(root, "output/browser-review.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Back to workspace" }).click();
  await page
    .getByRole("button", { name: "Overview", exact: true })
    .first()
    .click();
  await page.screenshot({
    path: path.join(root, "output/dashboard.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.getByRole("button", { name: "Toggle navigation" }).click();
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(
    page.getByRole("heading", { name: "Welcome back." }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
