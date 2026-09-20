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
test("one project reuses data for booklet, banners and social posts", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await page.locator(".language-switcher").selectOption("en");
  await page.getByLabel("Email address").fill(env.ADMIN_EMAIL);
  await page.getByLabel("Password", { exact: true }).fill(env.ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Sign in to workspace" }).click();
  await expect(page.locator(".sidebar")).toBeVisible();
  const before = await page.request.get("/api/projects").then((r) => r.json());
  await page
    .getByRole("button", { name: "Create project", exact: true })
    .first()
    .click();
  await expect(page.getByLabel("Project type")).toHaveValue("project");
  const name = "Shared " + Date.now();
  await page.getByLabel("Project / auction name", { exact: true }).fill(name);
  await page.getByLabel("Reference code").fill("SHARED-" + Date.now());
  await page
    .locator("form")
    .getByRole("button", { name: "Create project" })
    .click();
  const sections = page.getByRole("navigation", { name: "Project sections" });
  await expect(sections.getByRole("button")).toHaveCount(5);
  const projects = await page.request
    .get("/api/projects")
    .then((r) => r.json());
  const p = projects.find((p: { name: string }) => p.name === name);
  expect(p.workspace_type).toBe("project");
  // Store the shared inputs once, then exercise all three production flows.
  expect(
    (
      await page.request.put("/api/projects/" + p.id, {
        data: {
          ...p,
          auction: {
            ...p.auction,
            auction_name: "مزاد آفاق",
            auction_date: "2026-10-10",
            start_time: "16:00",
            physical_location: "الرياض",
            license_number: "420000053",
            auction_contact_number: "0555000000",
            legal_announcement_text: "إعلان تجريبي للمعاينة فقط",
            booklet_url: "https://example.com/booklet/demo",
          },
        },
      })
    ).ok(),
  ).toBeTruthy();
  const itemResponse = await page.request.post(
    "/api/projects/" + p.id + "/items",
    {
      data: {
        title: "العقار المشترك",
        property_data: {
          property_type: "أرض",
          city: "الرياض",
          district: "النرجس",
          area: "1200",
          deed_number: "0011",
          plan_number: "05",
          plot_number: "1",
          usage: "سكني",
          execution_request_number: "12345",
        },
      },
    },
  );
  expect(itemResponse.ok()).toBeTruthy();
  const item = await itemResponse.json();
  let logo = "";
  for (const category of ["agent_logo", "auction_logo", "cover", "main"]) {
    const r = await page.request.post("/api/projects/" + p.id + "/images", {
      multipart: {
        category,
        ...(category === "main" ? { item_id: item.id } : {}),
        file: {
          name: "photo.jpg",
          mimeType: "image/jpeg",
          buffer: fs.readFileSync(
            path.join(root, "samples/demo-generator.jpg"),
          ),
        },
      },
    });
    expect(r.ok()).toBeTruthy();
    if (category === "agent_logo") logo = (await r.json()).id;
  }
  expect(
    (
      await page.request.put("/api/projects/" + p.id + "/selling-agent", {
        data: { name: "وكيل تجريبي", logo_image_id: logo },
      })
    ).ok(),
  ).toBeTruthy();
  await page
    .locator(".sidebar")
    .getByRole("button", { name: /My projects/ })
    .click();
  await page.getByText(name, { exact: true }).click();
  await expect(
    page.getByText("1 properties and 4 images in this shared project"),
  ).toBeVisible();
  await sections.getByRole("button", { name: "Booklet", exact: true }).click();
  await page
    .getByRole("button", { name: "Generate auction booklet", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Approve output", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText("approved");
  await page
    .getByRole("button", { name: "← Back to workspace", exact: true })
    .click();
  await sections.getByRole("button", { name: "Banners", exact: true }).click();
  await expect(page.locator(".workflow-steps button")).toHaveCount(3);
  await page
    .getByRole("button", { name: "Save template and continue", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Generate banners", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Approve output", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText("approved");
  await page
    .getByRole("button", { name: "← Back to workspace", exact: true })
    .click();
  await sections
    .getByRole("button", { name: "Social posts", exact: true })
    .click();
  await expect(page.locator(".workflow-steps button")).toHaveCount(3);
  await page
    .getByLabel("Marketing headline", { exact: true })
    .fill("فرص عقارية مميزة");
  await page
    .getByRole("button", { name: "Save design and continue", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Generate social posts", exact: true })
    .click();
  await expect(
    page.getByText("Actual dimensions per image: 1080 × 1080 pixels."),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Approve output", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText("approved");
  await page
    .getByRole("button", { name: "← Back to workspace", exact: true })
    .click();
  await sections
    .getByRole("button", { name: "All project outputs", exact: true })
    .click();
  const detail = await page.request
    .get("/api/projects/" + p.id)
    .then((r) => r.json());
  expect(detail.items).toHaveLength(1);
  expect(detail.images).toHaveLength(4);
  expect(detail.outputs).toHaveLength(3);
  expect(
    detail.outputs.every((o: { status: string }) => o.status === "APPROVED"),
  ).toBeTruthy();
  expect(
    await page.request.get("/api/projects").then((r) => r.json()),
  ).toHaveLength(before.length + 1);
  // Shared data can be corrected once, without entering a campaign creation form.
  await sections
    .getByRole("button", { name: "Project data", exact: true })
    .click();
  await page.locator('[name="auction_contact_number"]').fill("0555111111");
  const savedAuction = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/projects/${p.id}`) &&
      response.request().method() === "PUT",
  );
  await page
    .getByRole("button", { name: "Save auction and cover", exact: true })
    .click();
  expect((await savedAuction).ok()).toBeTruthy();
  const changed = await page.request
    .get("/api/projects/" + p.id)
    .then((r) => r.json());
  expect(
    changed.outputs.every(
      (o: { status: string }) => o.status === "NEEDS_REGENERATION",
    ),
  ).toBeTruthy();
  const batch = page.waitForResponse(
    (r) =>
      r.url().endsWith(`/projects/${p.id}/generate`) &&
      r.request().postDataJSON()?.types?.length === 3,
  );
  await page
    .getByRole("button", {
      name: "Generate booklet, banners and social posts",
      exact: true,
    })
    .click();
  expect((await batch).ok()).toBeTruthy();
  await expect(
    sections.getByRole("button", { name: "All project outputs", exact: true }),
  ).toHaveAttribute("aria-current", "page");
  const complete = await page.request
    .get(`/api/projects/${p.id}`)
    .then((r) => r.json());
  expect(complete.outputs).toHaveLength(6);
  expect(
    complete.outputs.filter((o: { status: string }) => o.status === "DRAFT"),
  ).toHaveLength(3);
  await page.locator(".language-switcher").selectOption("ar");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: path.join(root, "output/shared-project-mobile.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
