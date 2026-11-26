"use client";

import { getSupabase } from "@/lib/supabase/client";
import type {
  AnalyticsSummary, CategoryCount, Feedback, HistoryDetail, HistoryPage, ModelInfo, PredictionResult,
} from "./types";

/** Error carrying the backend envelope {"error": {code, message, request_id}}. */
export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public requestId?: string) {
    super(message);
  }
}

async function token(): Promise<string | null> {
  const { data } = await getSupabase().auth.getSession();
  return data.session?.access_token ?? null;
}

async function request<T>(path: string, init: RequestInit = {}, auth = true): Promise<T> {
  const headers = new Headers(init.headers);
  if (auth) {
    const t = await token();
    if (!t) throw new ApiError(401, "not_authenticated", "Not logged in");
    headers.set("Authorization", `Bearer ${t}`);
  }
  let res: Response;
  try {
    res = await fetch(`/api/v1${path}`, { ...init, headers, cache: "no-store" });
  } catch {
    throw new ApiError(0, "network_error", "Network error");
  }
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const e = body?.error;
    throw new ApiError(res.status, e?.code ?? "http_error", e?.message ?? res.statusText, e?.request_id);
  }
  return body as T;
}

export const api = {
  health: () => request<{ status: string; model_loaded: boolean; model_version: string | null }>("/health", {}, false),
  modelInfo: () => request<ModelInfo>("/model-info", {}, false),
  predict: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<PredictionResult>("/predict", { method: "POST", body: fd });
  },
  history: (params: Record<string, string | number | boolean | undefined>) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== "") q.set(k, String(v)); });
    return request<HistoryPage>(`/history?${q.toString()}`);
  },
  historyDetail: (id: string) => request<HistoryDetail>(`/history/${encodeURIComponent(id)}`),
  deleteHistory: (id: string) => request<void>(`/history/${encodeURIComponent(id)}`, { method: "DELETE" }),
  feedback: (id: string, body: { user_correctness_feedback: boolean; corrected_category?: string | null; comments?: string | null }) =>
    request<Feedback>(`/history/${encodeURIComponent(id)}/feedback`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    }),
  analytics: () => request<AnalyticsSummary>("/analytics"),
  distribution: () => request<CategoryCount[]>("/analytics/category-distribution"),
  deleteAccount: () => request<void>("/account", { method: "DELETE" }),
};

/** Maps an ApiError to a user-facing message (bilingual handled by caller via dictionary keys). */
export function errorKey(e: unknown): "sessionExpired" | "offline" | "rateLimited" | null {
  if (!(e instanceof ApiError)) return null;
  if (e.status === 401) return "sessionExpired";
  if (e.status === 0) return "offline";
  if (e.status === 429) return "rateLimited";
  return null;
}
