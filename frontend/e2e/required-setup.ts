import { Page, expect } from "@playwright/test";

// Booklet flows are entered page by page. A field on another page is opened
// the way a requirement link opens it, then filled.
export async function fillPages(page: Page, values: Record<string, string>) {
  const form = page.locator(".auction-workspace form");
  for (const [name, value] of Object.entries(values)) {
    const named = form.locator(`[name="${name}"]`);
    await named
      .first()
      .evaluate((el) =>
        el.dispatchEvent(new Event("reveal", { bubbles: true })),
      );
    // A choice among cards (radio buttons): pick the card with that value.
    if ((await named.first().getAttribute("type")) === "radio") {
      await named
        .and(form.locator(`[value="${value}"]`))
        .check({ force: true });
      continue;
    }
    const field = named;
    await expect(field).toBeVisible();
    if ((await field.evaluate((el) => el.tagName)) === "SELECT")
      await field.selectOption(value);
    else await field.fill(value);
  }
}

// "Next" through the remaining pages until the step is saved.
export async function finishPages(page: Page) {
  const form = page.locator(".auction-workspace form");
  const current = form.locator('.page-parts [aria-current="step"]');
  for (let i = 0; i < 8 && (await form.count()); i++) {
    const before = await current.textContent();
    // The one Next of the flow saves this page and opens the following one.
    await page.locator(".workflow-navigation .nav-next").click();
    // Each page is saved before the next opens; allow for a busy server.
    await expect
      .poll(
        async () =>
          (await form.count()) === 0 ||
          // (the form may close between the two checks: do not wait for it)
          (await current.textContent({ timeout: 500 }).catch(() => null)) !==
            before,
        { timeout: 20000 },
      )
      .toBeTruthy();
  }
  await expect(form).toHaveCount(0);
}

// The closing pages (participation steps, contact) come after the photographs.
export async function completeClosing(
  page: Page,
  values: Record<string, string> = {},
) {
  await page
    .locator(".workflow-steps")
    .getByRole("button", { name: /Closing pages|الصفحات الختامية/ })
    .click();
  await fillPages(page, values);
  await finishPages(page);
}

// Standalone booklet fixtures must complete earlier stages before testing imports/tools.
export async function completeBookletBasics(page: Page) {
  await fillPages(page, {
    auction_date: "2026-10-10",
    start_time: "16:00",
    physical_location: "الرياض",
  });
  await finishPages(page);
}

// A property's photographs are entered in its own form: open the property,
// pick the photograph and save. The list then shows it on the property's card.
export async function addPhoto(page: Page, title: string, file: string) {
  const card = page.locator(".property-cards li").filter({ hasText: title });
  await card.locator(".property-card").click();
  await page
    .locator('.property-form [data-slot="main"] input[type="file"]')
    .setInputFiles(file);
  await page.locator(".property-form .item-actions button.primary").click();
  await expect(card.locator("img.property-thumb")).toBeVisible();
}

// A project created through the API and opened from "My projects". (In the
// app "Create project" opens the wizard directly; tests that need a given
// name or a booklet-only project start here.)
export async function newProject(
  page: Page,
  name: string,
  type: "project" | "booklet" = "project",
  extra: Record<string, string> = {},
  auction: Record<string, string> = {},
) {
  const response = await page.request.post("/api/projects", {
    data: {
      name,
      code: `E2E-${Date.now()}-${Math.round(Math.random() * 1e6)}`,
      workspace_type: type,
      ...extra,
      auction: {
        auction_name: name,
        auction_type: "physical",
        selected_cover_template_id: "infath-2",
        document_language: "ar",
        ...auction,
      },
    },
  });
  expect(response.ok()).toBeTruthy();
  const project = await response.json();
  await page.reload();
  const projects = page.locator(".sidebar nav button").nth(1);
  // The sidebar is there once the workspace has loaded (hidden on phones).
  await projects.waitFor({ state: "attached" });
  if (!(await projects.isVisible())) await page.locator(".mobile-menu").click();
  await projects.click();
  await page.getByText(name, { exact: true }).first().click();
  await expect(page.locator(".workflow-steps")).toBeVisible();
  return project as { id: string; name: string };
}
