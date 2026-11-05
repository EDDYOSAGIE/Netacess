"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError, auth, naira } from "@/lib/api";
import { Bell } from "./Bell";
import { Logo } from "./Logo";

export function AdminShell({ children }: { children: React.ReactNode }) {
  const r = useRouter();
  const path = usePathname();
  const [ok, setOk] = useState(false);
  useEffect(() => {
    if (!auth.get()) { sessionStorage.setItem("netacess_next", "/admin"); r.replace("/login"); return; }
    api<{ is_staff: boolean }>("/api/me").then((m) => {
      if (m.is_staff) setOk(true);
      else {
        auth.clear();
        sessionStorage.setItem("netacess_next", "/admin");
        r.replace("/login");
      }
    }).catch(() => {
      auth.clear();
      sessionStorage.setItem("netacess_next", "/admin");
      r.replace("/login");
    });
  }, [r]);
  if (!ok) return <div className="center"><div className="spinner" /></div>;
  const links = [["/admin", "Dashboard"], ["/admin/plans", "Plans"], ["/admin/payments", "Payments"], ["/admin/audit", "Audit log"]];
  return (
    <div className="adm">
      <aside className="side">
        <div className="side-brand"><Logo /></div>
        <nav className="side-nav" aria-label="Admin navigation">
          {links.map(([h, l]) => <Link key={h} href={h} className={`link ${path === h || (h !== "/admin" && path.startsWith(h)) ? "on" : ""}`}>{l}</Link>)}
        </nav>
        <div className="side-account">
          <Link href="/profile" className="link">My profile</Link>
          <button className="link" onClick={() => { auth.endSession(); window.location.assign("/"); }}>Log out</button>
        </div>
      </aside>
      <main className="amain"><div style={{ display: "flex", justifyContent: "flex-end" }}><Bell /></div>{children}</main>
    </div>
  );
}

// Every action needs a written reason, which goes to the audit log
export function ReasonDialog({ title, body, confirm, danger, onClose, onSubmit }: {
  title: string; body: string; confirm: string; danger?: boolean; onClose: () => void; onSubmit: (reason: string) => Promise<void>;
}) {
  const [reason, setReason] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  async function go() {
    setBusy(true); setErr("");
    try { await onSubmit(reason.trim()); onClose(); } catch (x) { setErr((x as ApiError).message); setBusy(false); }
  }
  return (
    <div className="dlg" role="dialog" aria-label={title} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()}>
        <h2 style={{ fontSize: 20, fontWeight: 800 }}>{title}</h2>
        <p className="lead" style={{ fontSize: 14 }}>{body}</p>
        <div className="field"><label htmlFor="reason">Reason</label>
          <textarea id="reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="For example: seen in the Flutterwave dashboard" autoFocus /></div>
        <span className="hint">Saved to the audit log with your name.</span>
        {err && <div className="alert bad" role="alert"><div>{err}</div></div>}
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button className="btn ghost sm" onClick={onClose}>Cancel</button>
          <button className={`btn sm ${danger ? "bad" : ""}`} disabled={busy || reason.trim().length < 3} onClick={go}>{busy ? "Working…" : confirm}</button>
        </div>
      </div>
    </div>
  );
}

export const adminStatus = (s: string): [string, string] =>
  s === "SUCCESSFUL" ? ["ok", "Successful"] : s === "FAILED" ? ["bad", "Failed"] : s === "NEEDS_REVIEW" ? ["warn", "Needs review"] :
  s === "EXPIRED" ? ["warn", "Expired"] : s === "REFUNDED" ? ["info", "Refunded"] : ["info", s.charAt(0) + s.slice(1).toLowerCase()];

// "100 NGN" from the event log is in kobo for naira; show it as money
export function fmtReceived(r: string | null) {
  if (!r) return "–";
  const [n, c] = r.split(" ");
  return c === "NGN" ? naira(n) : `${Number(n)} ${c}`;
}

export const ago = (iso: string) => {
  const m = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  return m < 60 ? `${m} min` : m < 1440 ? `${Math.round(m / 60)} h` : `${Math.round(m / 1440)} d`;
};

export const ACTIONS: Record<string, { label: string; title: string; body: string; danger?: boolean; when: string[] }> = {
  recheck: { label: "Re-check", title: "Re-check with provider", body: "", when: ["INITIATED", "PENDING", "FAILED", "EXPIRED", "NEEDS_REVIEW", "SUCCESSFUL"] },
  approve: { label: "Approve and issue code", title: "Approve this payment", body: "Use this only after you have seen the money in the provider dashboard. The customer gets their access code straight away.", when: ["PENDING", "FAILED", "EXPIRED", "NEEDS_REVIEW"] },
  fail: { label: "Mark failed", title: "Mark as failed", body: "No code will be issued.", danger: true, when: ["NEEDS_REVIEW"] },
  refund: { label: "Mark refunded", title: "Mark as refunded", body: "Only mark this after you have returned the money through the provider. No code will be issued.", danger: true, when: ["NEEDS_REVIEW", "SUCCESSFUL"] },
};
