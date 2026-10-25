import { completeAccount } from "./account-setup";
import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
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
test("the banner's QR link shows the booklet on a phone, without signing in", async ({
  page,
  browser,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/#login");
  await page.locator(".language-switcher").selectOption("en");
  await page.getByLabel("Email address").fill(env.ADMIN_EMAIL);
  await page.getByLabel("Password", { exact: true }).fill(env.ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Sign in to workspace" }).click();
  await completeAccount(page);
  const before: { id: string }[] = await page.request
    .get("/api/projects")
    .then((r) => r.json());
  await page
    .getByRole("button", { name: "Create project", exact: true })
    .first()
    .click();
  await page.getByRole("button", { name: "Sample fill" }).click();
  await page.getByRole("dialog").getByRole("button").last().click();
  await expect(
    page.getByText("3 properties and 4 images in this shared project"),
  ).toBeVisible({ timeout: 30000 });
  // The booklet link field shows the platform's public link.
  const shown = page.locator("[data-booklet-link]");
  await page.locator(".workflow-steps button").nth(2).click();
  // (on the closing pages' contact page, with the booklet link field)
  await expect(shown).toHaveCount(1);
  const link = await shown.getAttribute("data-booklet-link");
  expect(link).toMatch(/\/api\/b\/[\w-]{12}$/);
  await page.locator(".workflow-steps button").nth(3).click();
  const generate = page
    .locator(".project-generation")
    .getByRole("button", { name: /Generate/ });
  await expect(generate).toBeEnabled({ timeout: 20000 });
  await generate.click();
  await expect(page.getByRole("status")).toContainText(/generated|ready/i, {
    timeout: 120000,
  });
  const project = (
    await page.request.get("/api/projects").then((r) => r.json())
  ).find((x: { id: string }) => !before.some((b) => b.id === x.id));
  const detail = await page.request
    .get(`/api/projects/${project.id}`)
    .then((r) => r.json());
  // The issued banner carries exactly that link in its QR code: read from
  // the banner's own picture.
  const banner = detail.outputs.find(
    (o: { output_type: string }) => o.output_type === "banners",
  );
  const output = await page.request
    .get(`/api/outputs/${banner.id}`)
    .then((r) => r.json());
  const picture = output.files.find(
    (f: { media_type: string }) => f.media_type === "image/png",
  );
  const png = path.join(root, "output/booklet-link-banner.png");
  fs.mkdirSync(path.dirname(png), { recursive: true });
  fs.writeFileSync(
    png,
    await (await page.request.get(`/api/files/${picture.id}`)).body(),
  );
  const scanned = execFileSync(path.join(root, "backend/.venv/bin/python"), [
    "-c",
    "import sys, zxingcpp; from PIL import Image; " +
      "print(*[c.text for c in zxingcpp.read_barcodes(Image.open(sys.argv[1]))])",
    png,
  ])
    .toString()
    .trim();
  expect(scanned).toBe(link);

  // A phone scanning it: no session, a phone's screen.
  const phone = await browser.newContext({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
  });
  const visitor = await phone.newPage();
  const response = await visitor.goto(link!);
  expect(response!.status()).toBe(200);
  await expect(visitor.locator("header h1")).toHaveText(
    detail.project.auction.auction_name,
  );
  const pages = visitor.locator("main img");
  const count = await pages.count();
  expect(count).toBeGreaterThan(5);
  // Every page is shown: each picture loaded, filling the phone's width.
  for (let n = 0; n < count; n++) {
    const picture = pages.nth(n);
    await picture.scrollIntoViewIfNeeded();
    await expect
      .poll(() =>
        picture.evaluate((img: HTMLImageElement) =>
          img.complete ? img.naturalWidth : 0,
        ),
      )
      .toBe(1240);
  }
  const box = (await pages.first().boundingBox())!;
  expect(box.width).toBeGreaterThan(340);
  await visitor.screenshot({
    path: path.join(root, "output/booklet-link-phone.png"),
  });
  // And the PDF, from the page's button.
  const pdf = await visitor.request.get(
    (await visitor.getByRole("link", { name: /PDF/ }).getAttribute("href"))!,
  );
  expect(pdf.status()).toBe(200);
  expect((await pdf.body()).subarray(0, 5).toString()).toBe("%PDF-");
  await phone.close();
  expect(errors).toEqual([]);
});
