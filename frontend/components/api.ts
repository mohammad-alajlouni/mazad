import { ApiError } from "../i18n/errors";
export async function api<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const response = await fetch("/api" + path, {
    ...options,
    headers,
    credentials: "include",
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response
      .json()
      .catch(() => ({ detail: "Request failed" }));
    if (response.status === 401 && path != "/auth/login")
      window.dispatchEvent(new Event("session-expired"));
    throw new ApiError(body.code || "UNKNOWN", body.violations || []);
  }
  return response.json();
}
export const send = (body: unknown) => JSON.stringify(body);
export type Account = { email: string; role: "admin" | "user" };
export type Project = {
  workspace_type?: "booklet" | "banners";
  banner_config?: { size: string; property_ids: string[] };
  auction?: Record<string, unknown>;
  id: string;
  name: string;
  code: string;
  customer: string;
  description: string;
  date: string;
  location: string;
  notes: string;
  status: string;
  created_at: string;
};
export type Item = {
  property_data?: Record<string, unknown>;
  sequence_number?: number;
  id: string;
  title: string;
  reference: string;
  category: string;
  description: string;
  specifications: string;
  quantity: string;
  financial_value: string;
  technical_information: string;
  notes: string;
  attributes: Record<string, unknown>;
};
export type Output = {
  banner?: { size: string; scale: string } | null;
  official_booklet?: boolean;
  id: string;
  project_id: string;
  project_name: string;
  output_type: string;
  status: string;
  content: { review_text: string; ai_status: string; ai_message?: string };
  created_at: string;
  updated_at: string;
  files: { id: string; media_type: string }[];
};
export type ImageAsset = {
  id: string;
  item_id: string | null;
  key: string;
  category?: string;
  caption?: string;
};
export type Detail = {
  selling_agent?: Record<string, unknown>;
  project: Project;
  items: Item[];
  outputs: Output[];
  images: ImageAsset[];
};
export type Run = (fn: () => Promise<void>, success?: string) => Promise<void>;
