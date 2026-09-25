import { completeClosing, fillPages, finishPages } from "./required-setup";
import { completeAccount } from "./account-setup";
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

// Uploads go into the box for their role (auction logo, cover, main image...).
async function uploadTo(
  page: import("@playwright/test").Page,
  box: string,
  file: string | string[],
) {
  const slot = page.locator(".image-slot").filter({ hasText: box });
  await slot.locator('input[type="file"]').setInputFiles(file);
  await slot.getByRole("button", { name: /^(Upload|Replace)$/ }).click();
}

for (const flow of ["manual", "excel"])
  test(`official auction ${flow} browser flow`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto("/");
    await page.locator(".language-switcher").selectOption("en");
    await page.getByLabel("Email address").fill(env.ADMIN_EMAIL);
    await page.getByLabel("Password", { exact: true }).fill(env.ADMIN_PASSWORD);
    await page.getByRole("button", { name: "Sign in to workspace" }).click();
    await completeAccount(page);
    await page
      .getByRole("button", { name: "Create project", exact: true })
      .first()
      .click();
    const name = `Auction browser ${flow} ${Date.now()}`;
    await page.getByLabel("Project / auction name", { exact: true }).fill(name);
    await page.getByLabel("Reference code").fill(`AU-${flow}-${Date.now()}`);
    await page.getByLabel("Project type").selectOption("booklet");
    await page
      .locator("form")
      .getByRole("button", { name: "Create project" })
      .click();
    await page
      .getByRole("button", { name: /Auction and cover/, exact: true })
      .click();
    // Pages in booklet order: cover (1), Infath (2), agent (3), auction (4).
    const auction = page.locator(".auction-workspace form").first();
    await auction.locator('input[value="infath-5"]').check();
    await fillPages(page, {
      auction_type: "hybrid",
      auction_name: "مزاد الاختبار المتكامل",
      auction_start_date: "2026-10-10",
      auction_end_date: "2026-10-12",
      start_time: "16:00",
      end_time: "18:00",
      physical_location: "الرياض",
      electronic_platform_name: "منصة تجريبية",
    });
    await finishPages(page);
    if (flow === "manual") {
      for (let n = 1; n <= 2; n++) {
        await page.getByRole("button", { name: /Properties/ }).click();
        await page
          .getByRole("button", { name: "Add property", exact: true })
          .click();
        await page.getByLabel("Item title").fill(`عقار المتصفح ${n}`);
        await page
          .getByLabel("Property type", { exact: true })
          .fill("أرض سكنية");
        await page.getByLabel("City", { exact: true }).fill("الرياض");
        await page.getByLabel("District", { exact: true }).fill("النرجس");
        await page.getByLabel("Area m²", { exact: true }).fill("1200");
        await page
          .locator('[name="property.booklet_layout"]')
          .selectOption(n === 1 ? "landscape" : "portrait");
        await page
          .locator('[name="property.booklet_image_fit"]')
          .selectOption("contain");
        await page
          .locator('[name="booklet.include_information_page"]')
          .selectOption("false");
        await page
          .locator('[name="booklet.include_images_page"]')
          .selectOption("false");
        await page
          .locator('[name="booklet.include_rentals_page"]')
          .selectOption("false");
        await page
          .locator("summary")
          .filter({ hasText: "Property boundaries" })
          .click();
        await page.getByLabel("North boundary description").fill("شارع رئيسي");
        await page.getByLabel("North length").fill("30 م");
        await page
          .locator("summary")
          .filter({ hasText: "Property links and additional information" })
          .click();
        await page
          .getByLabel("Additional information", { exact: true })
          .fill("معلومات إضافية لاختبار ظهور الصفحة");
        await page
          .locator('[name="property.survey_link"]')
          .fill(`https://example.com/survey/${n}`);
        await page
          .locator("summary")
          .filter({ hasText: "Rental contracts" })
          .click();
        await page.getByRole("button", { name: "Add rental contract" }).click();
        await page.getByLabel("Unit number").fill("1");
        await page.getByLabel("Annual rent").fill("12000");
        const savedRequest = page.waitForResponse(
          (response) =>
            response.url().endsWith("/items") &&
            response.request().method() === "POST",
        );
        await page
          .getByRole("button", { name: "Save item", exact: true })
          .click();
        const savedItem = await (await savedRequest).json();
        expect(savedItem.property_data.booklet_layout).toBe(
          n === 1 ? "landscape" : "portrait",
        );
        expect(savedItem.property_data.booklet_image_fit).toBe("contain");
        expect(savedItem.property_data.include_information_page).toBe(false);
        expect(savedItem.property_data.include_images_page).toBe(false);
        expect(savedItem.property_data.include_rentals_page).toBe(false);
        expect(savedItem.property_data.rental_contracts).toHaveLength(1);
        await expect(
          page.getByText(`عقار المتصفح ${n}`, { exact: true }),
        ).toBeVisible();
      }
      await page
        .getByRole("button", { name: /Images and attachments/ })
        .click();
      await uploadTo(
        page,
        "Main image: عقار المتصفح 1",
        path.join(root, "samples/demo-generator.jpg"),
      );
      await expect(page.getByAltText("Uploaded project asset")).toBeVisible();
      await uploadTo(page, "Additional images: عقار المتصفح 1", [
        path.join(root, "samples/demo-generator.jpg"),
      ]);
      await expect(page.getByAltText("Uploaded project asset")).toHaveCount(3);
    } else {
      await page
        .getByRole("button", {
          name: "Import properties from Excel",
          exact: true,
        })
        .click();
      await page
        .getByLabel("Excel workbook")
        .setInputFiles(path.join(root, "samples/approved-properties.xlsx"));
      await page
        .getByLabel("City for all workbook properties (optional)")
        .fill("الرياض");
      await page.getByRole("button", { name: "Preview workbook" }).click();
      await expect(
        page.getByText("Valid properties: 3 · Sheets with errors: 0"),
      ).toBeVisible();
      await page.getByRole("button", { name: "Import 3 properties" }).click();
    }
    // The closing pages (participation steps, contact) follow the properties.
    await completeClosing(page, {
      electronic_platform_url: "https://example.com/auction/browser",
    });
    await page.getByRole("button", { name: /Review and generate/ }).click();
    await expect(
      page.getByText("Data is ready to generate a draft"),
    ).toBeVisible();
    await page
      .getByLabel("Output language", { exact: true })
      .selectOption("ar");
    await page
      .getByRole("button", { name: "Generate auction booklet", exact: true })
      .click();
    await expect(page.getByTitle("Output preview")).toBeVisible();
    await page.getByRole("button", { name: "Approve output" }).click();
    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("link", { name: "Download document · PDF ↓" }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/^auction-/);
    await download.saveAs(
      path.join(root, `output/pdf/browser-auction-${flow}.pdf`),
    );
    await page.screenshot({
      path: path.join(root, `output/browser-auction-${flow}.png`),
      fullPage: true,
    });
    expect(errors).toEqual([]);
  });
