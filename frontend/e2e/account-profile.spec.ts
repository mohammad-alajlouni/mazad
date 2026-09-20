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
      const n = l.indexOf("=");
      return [l.slice(0, n), l.slice(n + 1)];
    }),
);
test("account onboarding supplies projects and can only be edited in account settings", async ({
  page,
}) => {
  const email = `profile-${Date.now()}@example.com`,
    password = "Profile-browser-test-123";
  expect(
    (
      await page.request.post("/api/auth/login", {
        data: { email: env.ADMIN_EMAIL, password: env.ADMIN_PASSWORD },
      })
    ).ok(),
  ).toBeTruthy();
  expect(
    (
      await page.request.post("/api/admin/users", { data: { email, password } })
    ).ok(),
  ).toBeTruthy();
  await page.request.post("/api/auth/logout");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.locator(".language-switcher").selectOption("en");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in to workspace" }).click();
  const profile = page.locator(".account-profile");
  await expect(
    page.getByRole("heading", { name: "Complete your selling agent profile" }),
  ).toBeVisible();
  await profile.getByRole("button", { name: "Save and start" }).click();
  await expect(page.locator(".sidebar")).toHaveCount(0);
  expect(
    (await page.request.get("/api/auth/me").then((r) => r.json()))
      .profile_complete,
  ).toBe(false);
  await profile.locator('[name="name"]').fill("وكيل حسابي");
  await profile
    .locator('[name="description"]')
    .fill("شركة تسويق وبيع العقارات");
  await profile.locator('[name="phone"]').fill("0555888888");
  await profile
    .locator('input[type="file"]')
    .setInputFiles(path.join(root, "samples/demo-generator.jpg"));
  await profile.getByRole("button", { name: "Save and start" }).click();
  await expect(page.locator(".sidebar")).toBeAttached();
  await page.reload();
  await expect(page.locator(".profile-onboarding")).toHaveCount(0);
  const response = await page.request.post("/api/projects", {
    data: { name: "Profile project", code: `ACCOUNT-${Date.now()}` },
  });
  expect(response.ok()).toBeTruthy();
  const project = await response.json();
  let detail = await page.request
    .get(`/api/projects/${project.id}`)
    .then((r) => r.json());
  expect(detail.selling_agent.name).toBe("وكيل حسابي");
  expect(detail.selling_agent.logo_image_id).toBeTruthy();
  await page.getByRole("button", { name: "Toggle navigation" }).click();
  await page
    .getByRole("button", { name: "My account settings", exact: true })
    .click();
  await profile.locator('[name="name"]').fill("وكيل مُحدّث");
  const saved = page.waitForResponse(
    (r) =>
      r.url().endsWith("/account/profile") && r.request().method() === "PUT",
  );
  await profile.getByRole("button", { name: "Save my details" }).click();
  expect((await saved).ok()).toBeTruthy();
  detail = await page.request
    .get(`/api/projects/${project.id}`)
    .then((r) => r.json());
  expect(detail.selling_agent.name).toBe("وكيل مُحدّث");
  await page.locator(".language-switcher").selectOption("ar");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await page.screenshot({
    path: path.join(root, "output/account-profile-mobile.png"),
    fullPage: true,
  });
  await page.locator(".language-switcher").selectOption("en");
  await page.getByRole("button", { name: "Toggle navigation" }).click();
  await page
    .locator(".sidebar")
    .getByRole("button", { name: /My projects/ })
    .click();
  await page.getByText("Profile project", { exact: true }).click();
  await expect(page.locator(".workflow-steps button")).toHaveCount(3);
  await expect(page.locator(".workflow-steps")).not.toContainText(
    "Selling agent",
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBeTruthy();
});
