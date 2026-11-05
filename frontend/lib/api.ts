const TOKEN_KEY = "netacess_token";

export const auth = {
  get(): string | null {
    try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
  },
  set(t: string) { try { localStorage.setItem(TOKEN_KEY, t); } catch {} },
  clear() { try { localStorage.removeItem(TOKEN_KEY); } catch {} },
  endSession() {
    this.clear();
    try {
      sessionStorage.removeItem("netacess_next");
      sessionStorage.removeItem("netacess_signup");
      sessionStorage.removeItem("netacess_payment");
    } catch {}
  },
};

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}

export async function api<T = any>(path: string, opts: { method?: string; body?: unknown } = {}): Promise<T> {
  // Cursor links come back as absolute backend URLs; keep only the path and query
  if (path.startsWith("http")) { const u = new URL(path); path = u.pathname + u.search; }
  const token = auth.get();
  let res: Response;
  try {
    res = await fetch(path, {
      method: opts.method || (opts.body ? "POST" : "GET"),
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    });
  } catch {
    throw new ApiError(0, "network", "Can't reach Netacess. Check your connection and try again.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 401 && token) auth.clear();
    const msg = data.message || data.detail || (typeof data === "object" && Object.values(data)[0]) || "Something went wrong";
    throw new ApiError(res.status, data.error || "error", Array.isArray(msg) ? String(msg[0]) : String(msg));
  }
  return data as T;
}

export const naira = (kobo: number | string) => "₦" + Math.round(Number(kobo) / 100).toLocaleString("en-NG");
export const esp = (v: number | string) => `${Number(v)} ESP`;
export const money = (amount: string | number, currency: string) =>
  currency === "ESP" ? esp(amount) : naira(amount);
export const fmtDate = (iso: string) =>
  new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
export const fmtDateTime = (iso: string) =>
  new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

export type Plan = { id: string; code: string; name: string; price_ngn_kobo: number;
  price_esp: string; price_esp_ngn_kobo?: string; is_recurring: boolean; duration_days: number };
