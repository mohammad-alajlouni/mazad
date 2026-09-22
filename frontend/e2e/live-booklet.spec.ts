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
for (const mobile of [false, true])
  test(`live unsaved booklet preview ${mobile ? "mobile" : "desktop"}`, async ({
    page,
  }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    await page.locator(".language-switcher").selectOption("en");
    await page.getByLabel("Email address").fill(env.ADMIN_EMAIL);
    await page.getByLabel("Password", { exact: true }).fill(env.ADMIN_PASSWORD);
    await page.getByRole("button", { name: "Sign in to workspace" }).click();
    await completeAccount(page);
    if (mobile)
      await page.getByRole("button", { name: "Toggle navigation" }).click();
    await expect(
      page.getByRole("button", { name: "Create project", exact: true }).first(),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Create project", exact: true })
      .first()
      .click();
    const name = "Live " + Date.now();
    await page.getByLabel("Project / auction name", { exact: true }).fill(name);
    await page.getByLabel("Reference code").fill("LIVE-" + Date.now());
    await page
      .locator("form")
      .getByRole("button", { name: "Create project" })
      .click();
    await expect(
      page.getByRole("complementary", { name: "Live booklet preview" }),
    ).toBeVisible();
    const response = page.waitForResponse(
      (r) =>
        r.url().endsWith("/booklet-preview") &&
        r.request().postDataJSON()?.auction?.auction_name === "LIVE_CHANGED",
    );
    await page.getByLabel("Auction name", { exact: true }).fill("LIVE_CHANGED");
    const typed = Date.now();
    const preview = await (await response).json();
    expect(preview.html).toContain("LIVE_CHANGED");
    expect(preview.saved).toBe(false);
    // The page renders in the browser: the new text appears within a second.
    const frame = page.locator(
      '.live-preview-paper iframe[aria-hidden="false"]',
    );
    await expect(frame).toBeVisible();
    await expect(
      page
        .frameLocator('.live-preview-paper iframe[aria-hidden="false"]')
        .getByText("LIVE_CHANGED"),
    ).toBeVisible();
    expect(Date.now() - typed).toBeLessThan(1500);
    // Required fields of this step are still empty: later steps stay locked.
    const options = page
      .getByLabel("Preview page", { exact: true })
      .locator("option");
    const steps = await options.evaluateAll((list) =>
      list.map((o) => ({
        text: o.textContent || "",
        disabled: (o as HTMLOptionElement).disabled,
      })),
    );
    for (const option of steps.filter((o) => /Terms|Contact/.test(o.text)))
      expect(option.disabled).toBe(true);
    await expect(page.locator(".live-preview-paper")).toHaveAttribute(
      "data-page-kind",
      "auction",
    );
    const project = (
      await page.request.get("/api/projects").then((r) => r.json())
    ).find((p: { name: string }) => p.name === name);
    expect(project.auction.auction_name).toBe(name);
    await page.getByLabel("Preview page", { exact: true }).selectOption("0");
    await expect(page.locator(".live-preview-paper")).toHaveAttribute(
      "data-page-kind",
      "cover",
    );
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 1,
      ),
    ).toBe(true);
    await page.screenshot({
      path: path.join(
        root,
        `output/live-preview-${mobile ? "mobile" : "desktop"}.png`,
      ),
      fullPage: false,
    });
  });
