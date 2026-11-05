"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ACTIONS, AdminShell, ReasonDialog, adminStatus, fmtReceived } from "@/components/AdminShell";
import { api, ApiError, fmtDateTime, money } from "@/lib/api";

type Detail = { id: string; provider_reference: string; user_phone: string; plan: string; provider: string; amount: string; currency: string; status: string;
  created_at: string; issue: string | null; received: string | null; has_code: boolean;
  events: { source: string; event_type: string; payload: Record<string, any>; received_at: string }[] };

export default function PaymentDetail() {
  const { id } = useParams<{ id: string }>();
  const [d, setD] = useState<Detail | null>(null);
  const [err, setErr] = useState("");
  const [note, setNote] = useState("");
  const [act, setAct] = useState<string | null>(null);

  useEffect(() => { api<Detail>(`/api/admin/payments/${id}`).then(setD).catch((x) => setErr((x as ApiError).message)); }, [id]);
  async function recheck() {
    setNote(""); setErr("");
    try { const r = await api<Detail>(`/api/admin/payments/${id}/action`, { body: { action: "recheck" } }); setD(r); setNote("Checked with the provider."); }
    catch (x) { setErr((x as ApiError).message); }
  }
  const [c, l] = d ? adminStatus(d.status) : ["info", ""];
  return (
    <AdminShell>
      <Link href="/admin/payments" style={{ color: "var(--blue)", fontWeight: 700, fontSize: 14 }}>← All payments</Link>
      {err && <div className="alert bad" role="alert"><div>{err}</div></div>}
      {!d ? <div className="spinner" /> : (
        <>
          <div className="row"><h1 style={{ fontSize: 26, fontWeight: 800, letterSpacing: -.6 }}>{money(d.amount, d.currency)} · {d.plan}</h1><span className={`pill ${c}`}>{l}</span></div>
          <div className="card grid2" style={{ gap: 14 }}>
            <div><span className="hint">Customer</span><div><b>{d.user_phone}</b></div></div>
            <div><span className="hint">Provider</span><div><b>{d.provider === "espees" ? "Espees" : "Flutterwave"}</b></div></div>
            <div><span className="hint">Reference</span><div style={{ wordBreak: "break-all" }}>{d.provider_reference}</div></div>
            <div><span className="hint">Started</span><div>{fmtDateTime(d.created_at)}</div></div>
            {d.issue && <div><span className="hint">Issue</span><div><span className="pill warn">{d.issue}</span> received {fmtReceived(d.received)}</div></div>}
            <div><span className="hint">Access code</span><div>{d.has_code ? "Issued" : "Not issued"}</div></div>
          </div>
          <div className="card" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <b>Actions</b>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {Object.entries(ACTIONS).filter(([, a]) => a.when.includes(d.status)).map(([k, a]) => (
                <button key={k} className={`btn sm ${k === "recheck" ? "ghost" : a.danger ? "ghost bad" : ""}`} onClick={() => (k === "recheck" ? recheck() : setAct(k))}>{a.label}</button>))}
              {Object.entries(ACTIONS).every(([, a]) => !a.when.includes(d.status)) && <span className="hint">No actions available for this status.</span>}
            </div>
            {note && <span className="hint">{note}</span>}
          </div>
          <div className="card">
            <b>Timeline</b>
            <div className="tl">
              {d.events.length === 0 && <p className="hint" style={{ paddingTop: 8 }}>No events yet.</p>}
              {d.events.map((e, i) => (
                <div className="tli" key={i}>
                  <span className="pill info" style={{ alignSelf: "flex-start", textTransform: "capitalize" }}>{e.source}</span>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <b style={{ fontSize: 14 }}>{e.event_type.replace(/_/g, " ")}</b> <span className="hint">{fmtDateTime(e.received_at)}</span>
                    {e.payload?.reason && <div style={{ fontSize: 14 }}>Reason: {e.payload.reason}</div>}
                    {Object.keys(e.payload || {}).filter((k) => k !== "reason" && k !== "by").length > 0 && (
                      <pre>{JSON.stringify(Object.fromEntries(Object.entries(e.payload).filter(([k]) => k !== "reason" && k !== "by")), null, 1)}</pre>)}
                  </div>
                </div>))}
            </div>
          </div>
          {act && <ReasonDialog title={ACTIONS[act].title} body={ACTIONS[act].body} confirm={ACTIONS[act].label} danger={ACTIONS[act].danger} onClose={() => setAct(null)}
            onSubmit={async (reason) => { setD(await api<Detail>(`/api/admin/payments/${id}/action`, { body: { action: act, reason } })); }} />}
        </>
      )}
    </AdminShell>
  );
}
