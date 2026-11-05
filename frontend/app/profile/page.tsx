"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Logo } from "@/components/Logo";
import { api, ApiError, auth, esp, fmtDate, fmtDateTime, money, naira, Plan } from "@/lib/api";

type Me = { full_name: string; phone: string; is_staff: boolean; preferred_provider: string; subscription: null | { plan: string; plan_code: string; starts_at: string; expires_at: string; days_left: number; is_recurring: boolean } };
type Tx = { id: string; plan: string; provider: string; amount: string; currency: string; status: string; created_at: string; card_brand: string; card_last4: string };
type Note = { id: string; kind: string; title: string; body: string; link?: string; is_read: boolean; created_at: string };
type Page<T> = { results: T[]; next: string | null; unread_count?: number };

const statusPill = (s: string) =>
  s === "SUCCESSFUL" ? ["ok", "Successful"] : s === "FAILED" ? ["bad", "Failed"] :
  s === "PENDING" || s === "INITIATED" ? ["info", "Pending"] : s === "NEEDS_REVIEW" ? ["warn", "In review"] :
  s === "EXPIRED" ? ["warn", "Expired"] : ["info", s.charAt(0) + s.slice(1).toLowerCase()];

export default function Profile() {
  const r = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [code, setCode] = useState<string | null>(null);
  const [tx, setTx] = useState<Tx[]>([]);
  const [txNext, setTxNext] = useState<string | null>(null);
  const [filter, setFilter] = useState<"" | "SUCCESSFUL" | "FAILED">("");
  const [notes, setNotes] = useState<Note[]>([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [err, setErr] = useState("");
  const [copied, setCopied] = useState(false);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [saved, setSaved] = useState("");

  const fail = useCallback((x: unknown) => {
    const e = x as ApiError;
    if (e.status === 401) { r.replace("/login"); return; }
    setErr(e.message || "Could not load your profile");
  }, [r]);

  useEffect(() => {
    if (!auth.get()) { r.replace("/login"); return; }
    api<Me>("/api/me").then(setMe).catch(fail);
    api<Plan[]>("/api/plans").then(setPlans).catch(() => {});
    api<any[]>("/api/me/codes").then((c) => setCode(c.find((x) => x.status === "ACTIVE")?.code ?? null)).catch(() => {});
    loadNotes();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    if (!auth.get()) return;
    api<Page<Tx>>(`/api/me/transactions${filter ? `?status=${filter}` : ""}`).then((d) => { setTx(d.results); setTxNext(d.next); }).catch(() => {});
  }, [filter]);

  function loadNotes() {
    api<Page<Note>>("/api/me/notifications").then((d) => { setNotes(d.results); setUnread(d.unread_count ?? 0); }).catch(() => {});
  }
  async function markAll() {
    await api("/api/me/notifications/read", { body: {} }).catch(() => {});
    setNotes(notes.map((n) => ({ ...n, is_read: true }))); setUnread(0);
  }
  async function more() {
    if (!txNext) return;
    const d = await api<Page<Tx>>(txNext);
    setTx([...tx, ...d.results]); setTxNext(d.next);
  }
  const copy = async () => { if (!code) return; try { await navigator.clipboard.writeText(code); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch {} };
  async function savePref(provider: string) {
    setSaved("");
    try { const d = await api<Me>("/api/me", { method: "PATCH", body: { preferred_provider: provider } }); setMe(d); setSaved("Saved. Renewals will start with this method."); }
    catch (x) { setSaved((x as ApiError).message); }
  }
  const logout = () => { auth.endSession(); window.location.assign("/"); };

  const sub = me?.subscription;
  const pct = sub ? Math.max(0, Math.min(100, ((new Date(sub.expires_at).getTime() - Date.now()) / (new Date(sub.expires_at).getTime() - new Date(sub.starts_at).getTime())) * 100)) : 0;
  const initials = (me?.full_name || me?.phone || "?").split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase();

  return (
    <>
      <header className="header">
        <Logo />
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <button className="bell" aria-label="Notifications" onClick={() => setOpen(!open)}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#0B1F4B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9a6 6 0 0 1 12 0c0 6 2.5 7.5 2.5 7.5h-17S6 15 6 9z" /><path d="M10 20a2 2 0 0 0 4 0" /></svg>
            {unread > 0 && <span className="badge">{unread}</span>}
          </button>
          {me?.is_staff && <Link href="/admin" className="btn ghost sm">Admin</Link>}
          <span className="pill info" style={{ width: 36, height: 36, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13 }}>{initials}</span>
        </div>
        {open && (
          <div className="drop" role="dialog" aria-label="Notifications">
            <div className="row"><b style={{ fontSize: 16 }}>Notifications</b>
              {unread > 0 && <button onClick={markAll} style={{ background: "none", border: 0, color: "var(--blue)", fontWeight: 700, fontSize: 13 }}>Mark all as read</button>}</div>
            {notes.length === 0 && <p className="hint" style={{ padding: 12 }}>Nothing here yet.</p>}
            {notes.map((n) => (
              <div key={n.id} className={`nitem ${n.is_read ? "" : "unread"}`} style={n.link ? { cursor: "pointer" } : undefined} onClick={() => n.link && r.push(n.link)}>
                <span className="ndot" />
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <b style={{ fontSize: 14 }}>{n.title}</b>
                  <span style={{ fontSize: 13, color: "var(--muted)", lineHeight: 1.45 }}>{n.body}</span>
                  <span className="hint">{fmtDateTime(n.created_at)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </header>

      <main className="pwrap">
        <div className="row">
          <div><h1 style={{ fontSize: 30, fontWeight: 800, letterSpacing: -.8 }}>Hello, {me?.full_name || "there"}</h1>
            <p className="hint" style={{ fontSize: 14 }}>{sub ? sub.plan : "No active plan"}</p></div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Link href="/#plans" className="btn ghost sm">Browse plans</Link>
            <button className="btn ghost sm" onClick={logout}>Log out</button>
          </div>
        </div>
        {err && <div className="alert bad" role="alert"><div>{err}</div></div>}

        <div className="grid2">
          <div className="card" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div className="row"><b>Plan validity</b>{sub ? <span className="pill ok">Active</span> : <span className="pill warn">No plan</span>}</div>
            {sub ? (
              <>
                <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}><span className="big">{sub.days_left}</span><span className="lead" style={{ fontSize: 17 }}>{sub.days_left === 1 ? "day" : "days"} left</span></div>
                <div className="bar"><div style={{ width: `${pct}%` }} /></div>
                <div className="row hint" style={{ fontSize: 12 }}><span>Started {fmtDate(sub.starts_at)}</span><span>Expires {fmtDate(sub.expires_at)}</span></div>
                <div className="alert info"><div>We remind you 3 days and 1 day before it ends.</div></div>
                <Link href={`/checkout?plan=${sub.plan_code}${me?.preferred_provider ? `&provider=${me.preferred_provider}` : ""}`} className="btn">Renew now</Link>
              </>
            ) : (
              <>
                <p className="lead" style={{ fontSize: 15 }}>You don't have an active plan yet.</p>
                <Link href="/#plans" className="btn">Choose a plan</Link>
              </>
            )}
          </div>

          <div className="card" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <b>Your access code</b>
            {code ? (
              <>
                <span className="code">{code}</span>
                <button className="btn sm" style={{ alignSelf: "flex-start" }} onClick={copy}>{copied ? "Copied" : "Copy code"}</button>
              </>
            ) : <p className="lead" style={{ fontSize: 15 }}>Your code appears here after your first confirmed payment.</p>}
          </div>
        </div>

        {sub && (() => {
          const plan = plans.find((x) => x.code === sub.plan_code);
          const pref = me?.preferred_provider || "";
          const amt = !plan ? "" : pref === "espees" ? esp(plan.price_esp) : naira(plan.price_ngn_kobo);
          return (
            <div className="card" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div className="row"><b>Next renewal</b><span className="hint" style={{ fontSize: 13 }}>Due by {fmtDate(sub.expires_at)}</span></div>
              {amt && <span style={{ fontSize: 26, fontWeight: 800, letterSpacing: -.5 }}>{amt}</span>}
              <div>
                <span className="hint" style={{ fontWeight: 600 }}>Payment method for renewals</span>
                <div className="chips" style={{ marginTop: 8 }}>
                  {([["flutterwave", "Flutterwave"], ["espees", "Espees"]] as const).map(([v, l]) => (
                    <button key={v} className={`chip ${pref === v ? "on" : ""}`} onClick={() => savePref(v)}>{l}</button>
                  ))}
                </div>
                <span className="hint" style={{ display: "block", marginTop: 8 }}>{saved || "Your renewal is a new payment each time, so nothing is charged automatically."}</span>
              </div>
            </div>
          );
        })()}

        <div className="card" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <b>Last card used</b>
          {tx.find((t) => t.provider === "flutterwave" && t.card_last4) ? (() => {
            const card = tx.find((t) => t.provider === "flutterwave" && t.card_last4)!;
            return <><span>{card.card_brand || "Card"} ending in •••• {card.card_last4}</span><span className="hint">Used {fmtDate(card.created_at)}. Card details are not stored for future charges.</span></>;
          })() : <p className="hint">No Flutterwave card payment recorded yet. Bank transfer and other payment methods do not show card details here.</p>}
        </div>

        <div className="card">
          <div className="row" style={{ marginBottom: 12 }}>
            <h2 style={{ fontSize: 20, fontWeight: 800 }}>Transaction history</h2>
            <div className="chips">
              {([["", "All"], ["SUCCESSFUL", "Successful"], ["FAILED", "Failed"]] as const).map(([v, l]) => (
                <button key={l} className={`chip ${filter === v ? "on" : ""}`} onClick={() => setFilter(v)}>{l}</button>
              ))}
            </div>
          </div>
          {tx.length === 0 ? <p className="hint" style={{ padding: "12px 0" }}>No transactions yet.</p> : (
            <div style={{ overflowX: "auto" }}>
              <table>
                <thead><tr><th>Date</th><th>Plan</th><th>Provider</th><th>Amount</th><th>Status</th></tr></thead>
                <tbody>
                  {tx.map((t) => { const [c, l] = statusPill(t.status); return (
                    <tr key={t.id}>
                      <td>{fmtDate(t.created_at)}</td><td>{t.plan}</td>
                      <td>{t.provider === "espees" ? "Espees" : "Flutterwave"}</td>
                      <td><b>{money(t.amount, t.currency)}</b></td>
                      <td><span className={`pill ${c}`}>{l}</span></td>
                    </tr>); })}
                </tbody>
              </table>
            </div>
          )}
          {txNext && <button className="btn ghost sm" style={{ marginTop: 14 }} onClick={more}>Load more</button>}
        </div>
      </main>
    </>
  );
}
