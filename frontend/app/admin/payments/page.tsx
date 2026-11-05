"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AdminShell, adminStatus, ago } from "@/components/AdminShell";
import { api, fmtDateTime, money } from "@/lib/api";

type Row = { id: string; provider_reference: string; user_phone: string; plan: string; provider: string; amount: string; currency: string; status: string; created_at: string };
const STATUSES = ["", "SUCCESSFUL", "PENDING", "NEEDS_REVIEW", "FAILED", "EXPIRED", "REFUNDED"];

export default function Payments() {
  const [rows, setRows] = useState<Row[]>([]);
  const [next, setNext] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [provider, setProvider] = useState("");
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    const t = setTimeout(() => {
      const p = new URLSearchParams();
      if (status) p.set("status", status); if (provider) p.set("provider", provider); if (q.trim()) p.set("q", q.trim());
      setBusy(true);
      api<{ results: Row[]; next: string | null }>(`/api/admin/payments?${p}`).then((d) => { setRows(d.results); setNext(d.next); }).finally(() => setBusy(false));
    }, q ? 300 : 0);
    return () => clearTimeout(t);
  }, [status, provider, q]);

  return (
    <AdminShell>
      <h1 style={{ fontSize: 28, fontWeight: 800, letterSpacing: -.7 }}>Payments</h1>
      <div className="card">
        <div className="row" style={{ marginBottom: 14 }}>
          <div className="chips" style={{ flexWrap: "wrap" }}>
            {STATUSES.map((s) => <button key={s} className={`chip ${status === s ? "on" : ""}`} onClick={() => setStatus(s)}>{s ? adminStatus(s)[1] : "All"}</button>)}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <select value={provider} onChange={(e) => setProvider(e.target.value)} aria-label="Provider" style={{ padding: "9px 12px", borderRadius: 12, border: "1px solid #BFD3F7", fontFamily: "inherit" }}>
              <option value="">All providers</option><option value="flutterwave">Flutterwave</option><option value="espees">Espees</option>
            </select>
            <input aria-label="Search" placeholder="Search phone or reference" value={q} onChange={(e) => setQ(e.target.value)} style={{ padding: "9px 12px", borderRadius: 12, border: "1px solid #BFD3F7", fontFamily: "inherit", minWidth: 220 }} />
          </div>
        </div>
        {!busy && rows.length === 0 ? <p className="hint">No payments match.</p> : (
          <div style={{ overflowX: "auto" }}><table>
            <thead><tr><th>When</th><th>Customer</th><th>Plan</th><th>Provider</th><th>Amount</th><th>Status</th></tr></thead>
            <tbody>{rows.map((p) => { const [c, l] = adminStatus(p.status); return (
              <tr key={p.id}>
                <td><Link href={`/admin/payments/${p.id}`} style={{ color: "var(--blue)", fontWeight: 700 }}>{fmtDateTime(p.created_at)}</Link><div className="hint">{ago(p.created_at)} ago</div></td>
                <td>{p.user_phone}</td><td>{p.plan}</td><td>{p.provider === "espees" ? "Espees" : "Flutterwave"}</td>
                <td><b>{money(p.amount, p.currency)}</b></td><td><span className={`pill ${c}`}>{l}</span></td>
              </tr>); })}</tbody></table></div>
        )}
        {next && <button className="btn ghost sm" style={{ marginTop: 14 }} onClick={async () => { const d = await api<{ results: Row[]; next: string | null }>(next); setRows([...rows, ...d.results]); setNext(d.next); }}>Load more</button>}
      </div>
    </AdminShell>
  );
}
