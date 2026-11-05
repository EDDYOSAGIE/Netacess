"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ACTIONS, ReasonDialog, AdminShell, ago, fmtReceived, adminStatus } from "@/components/AdminShell";
import { api, ApiError, esp, money, naira } from "@/lib/api";

type Summary = { revenue_today: Record<string, string>; active_subscribers: number; success_rate_7d: number | null; needs_review: number;
  providers: { name: string; enabled: boolean; degraded: boolean }[] };
type Row = { id: string; provider_reference: string; user_phone: string; plan: string; provider: string; amount: string; currency: string; status: string; created_at: string; issue: string | null; received: string | null };

export default function Dashboard() {
  const [s, setS] = useState<Summary | null>(null);
  const [queue, setQueue] = useState<Row[]>([]);
  const [espRate, setEspRate] = useState("");
  const [savingRate, setSavingRate] = useState(false);
  const [rateNotice, setRateNotice] = useState("");
  const [err, setErr] = useState("");
  const [dlg, setDlg] = useState<null | { kind: "pay"; row: Row; action: "approve" | "refund" } | { kind: "prov"; name: string; enabled: boolean }>(null);

  const load = useCallback(() => {
    api<Summary>("/api/admin/summary").then(setS).catch((x) => setErr((x as ApiError).message));
    api<{ results: Row[] }>("/api/admin/payments?status=NEEDS_REVIEW").then((d) => setQueue(d.results)).catch(() => {});
    api<{ esp_to_ngn: string }>("/api/admin/currency-rate").then((d) => setEspRate(d.esp_to_ngn)).catch((x) => setErr((x as ApiError).message));
  }, []);

  async function saveEspRate(e: React.FormEvent) {
    e.preventDefault(); setSavingRate(true); setErr(""); setRateNotice("");
    try {
      const saved = await api<{ esp_to_ngn: string }>("/api/admin/currency-rate", {
        method: "PATCH", body: { esp_to_ngn: espRate },
      });
      setEspRate(saved.esp_to_ngn);
      setRateNotice("Espees conversion rate updated.");
    } catch (x) { setErr((x as ApiError).message); }
    finally { setSavingRate(false); }
  }
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, [load]); // stays current without a refresh

  const rev = s ? Object.entries(s.revenue_today).map(([c, v]) => (c === "NGN" ? naira(v) : esp(v))).join(" + ") || "₦0" : "…";
  return (
    <AdminShell>
      <div><h1 style={{ fontSize: 28, fontWeight: 800, letterSpacing: -.7 }}>Payment review</h1>
        <p className="lead" style={{ fontSize: 15 }}>Money received that the system could not match on its own. Nothing here is lost.</p></div>
      {err && <div className="alert bad" role="alert"><div>{err}</div></div>}

      <div className="stats">
        <div className="card stat"><span className="hint">Revenue, last 24 hours</span><b>{rev}</b></div>
        <div className="card stat"><span className="hint">Active subscribers</span><b>{s?.active_subscribers ?? "…"}</b></div>
        <div className="card stat"><span className="hint">Success rate, 7 days</span><b>{s ? (s.success_rate_7d === null ? "–" : `${s.success_rate_7d}%`) : "…"}</b></div>
        <div className="card stat" style={s && s.needs_review > 0 ? { borderColor: "#F1C26B", background: "var(--warn-bg)" } : undefined}><span className="hint">Needs review</span><b>{s?.needs_review ?? "…"}</b></div>
      </div>

      <div className="card">
        <div className="row" style={{ marginBottom: 10 }}><h2 style={{ fontSize: 18, fontWeight: 800 }}>Needs review</h2><Link href="/admin/payments" style={{ color: "var(--blue)", fontWeight: 700, fontSize: 14 }}>All payments</Link></div>
        {queue.length === 0 ? <p className="hint" style={{ padding: "10px 0" }}>Nothing waiting. All payments are matched.</p> : (
          <div style={{ overflowX: "auto" }}><table>
            <thead><tr><th>Reference</th><th>Issue</th><th>Expected</th><th>Received</th><th>Provider</th><th>Age</th><th>Actions</th></tr></thead>
            <tbody>{queue.map((p) => (
              <tr key={p.id}>
                <td><Link href={`/admin/payments/${p.id}`} style={{ color: "var(--blue)", fontWeight: 700 }}>{p.provider_reference.slice(0, 18)}</Link><div className="hint">{p.user_phone}</div></td>
                <td><span className="pill warn">{p.issue}</span></td>
                <td>{money(p.amount, p.currency)}</td><td>{fmtReceived(p.received)}</td>
                <td>{p.provider === "espees" ? "Espees" : "Flutterwave"}</td><td>{ago(p.created_at)}</td>
                <td><div style={{ display: "flex", gap: 6 }}>
                  <button className="btn sm" onClick={() => setDlg({ kind: "pay", row: p, action: "approve" })}>Approve</button>
                  <button className="btn sm ghost bad" onClick={() => setDlg({ kind: "pay", row: p, action: "refund" })}>Refund</button>
                </div></td>
              </tr>))}</tbody></table></div>
        )}
        <p className="hint" style={{ marginTop: 12 }}>Every action is saved to the audit log with your name and a reason.</p>
      </div>

      <div className="card" style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        <h2 style={{ fontSize: 18, fontWeight: 800, marginBottom: 6 }}>Payment providers</h2>
        {s?.providers.map((p) => (
          <div key={p.name} className="row" style={{ padding: "12px 0", borderTop: "1px solid var(--line2)" }}>
            <div><b>{p.name === "espees" ? "Espees" : "Flutterwave"}</b>{" "}
              <span className={`pill ${!p.enabled ? "bad" : p.degraded ? "warn" : "ok"}`}>{!p.enabled ? "Switched off" : p.degraded ? "Having trouble" : "Healthy"}</span></div>
            <button className={`toggle ${p.enabled ? "on" : ""}`} role="switch" aria-checked={p.enabled} aria-label={`${p.name} on or off`}
              onClick={() => setDlg({ kind: "prov", name: p.name, enabled: !p.enabled })} />
          </div>))}
        <p className="hint">Turn a provider off and it disappears from checkout at once. No deploy needed.</p>
      </div>

      <form className="card" onSubmit={saveEspRate} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <h2 style={{ fontSize: 18, fontWeight: 800 }}>Espees conversion</h2>
        <p className="hint">Set the current Naira value used for Espees price equivalents. Existing Espees checkout prices stay as configured per plan.</p>
        <div className="field" style={{ maxWidth: 360 }}>
          <label htmlFor="esp-to-ngn">1 ESP equals (₦)</label>
          <input id="esp-to-ngn" type="number" min="0.0001" step="0.0001" required value={espRate}
            onChange={(e) => setEspRate(e.target.value)} />
        </div>
        {rateNotice && <div className="alert info" role="status">{rateNotice}</div>}
        <div><button className="btn sm" disabled={savingRate || !espRate}>{savingRate ? "Saving…" : "Save conversion rate"}</button></div>
      </form>

      {dlg?.kind === "pay" && (() => { const a = ACTIONS[dlg.action]; return (
        <ReasonDialog title={a.title} body={a.body} confirm={a.label} danger={a.danger} onClose={() => setDlg(null)}
          onSubmit={async (reason) => { await api(`/api/admin/payments/${dlg.row.id}/action`, { body: { action: dlg.action, reason } }); load(); }} />); })()}
      {dlg?.kind === "prov" && (
        <ReasonDialog title={`${dlg.enabled ? "Switch on" : "Switch off"} ${dlg.name === "espees" ? "Espees" : "Flutterwave"}`}
          body={dlg.enabled ? "Customers will see this payment method at checkout again." : "Customers will no longer see this method at checkout. Payments already started are still checked and honoured."}
          confirm={dlg.enabled ? "Switch on" : "Switch off"} danger={!dlg.enabled} onClose={() => setDlg(null)}
          onSubmit={async (reason) => { await api(`/api/admin/providers/${dlg.name}`, { body: { enabled: dlg.enabled, reason } }); load(); }} />)}
    </AdminShell>
  );
}
