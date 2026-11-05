"use client";
import { useEffect, useState } from "react";
import { AdminShell } from "@/components/AdminShell";
import { api, fmtDateTime } from "@/lib/api";
import Link from "next/link";

type Row = { id: number; actor: string; actor_phone: string; action: string; target_type: string; target_id: string; reason: string; created_at: string };
const LABEL: Record<string, string> = { approve: "Approved payment", fail: "Marked failed", refund: "Marked refunded", recheck: "Re-checked payment", provider_on: "Switched provider on", provider_off: "Switched provider off" };

export default function Audit() {
  const [rows, setRows] = useState<Row[]>([]);
  const [next, setNext] = useState<string | null>(null);
  useEffect(() => { api<{ results: Row[]; next: string | null }>("/api/admin/audit").then((d) => { setRows(d.results); setNext(d.next); }); }, []);
  return (
    <AdminShell>
      <h1 style={{ fontSize: 28, fontWeight: 800, letterSpacing: -.7 }}>Audit log</h1>
      <div className="card">
        {rows.length === 0 ? <p className="hint">No staff actions yet.</p> : (
          <div style={{ overflowX: "auto" }}><table>
            <thead><tr><th>When</th><th>Who</th><th>Action</th><th>Target</th><th>Reason</th></tr></thead>
            <tbody>{rows.map((r) => (
              <tr key={r.id}><td>{fmtDateTime(r.created_at)}</td><td>{r.actor || r.actor_phone}</td><td><b>{LABEL[r.action] || r.action}</b></td>
                <td>{r.target_type === "payment" ? <Link href={`/admin/payments/${r.target_id}`} style={{ color: "var(--blue)", fontWeight: 700 }}>{r.target_id.slice(0, 8)}</Link> : r.target_id}</td>
                <td>{r.reason}</td></tr>))}</tbody></table></div>)}
        {next && <button className="btn ghost sm" style={{ marginTop: 14 }} onClick={async () => { const d = await api<{ results: Row[]; next: string | null }>(next); setRows([...rows, ...d.results]); setNext(d.next); }}>Load more</button>}
      </div>
    </AdminShell>
  );
}
