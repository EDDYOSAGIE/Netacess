"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, fmtDateTime } from "@/lib/api";

type Note = { id: string; kind: string; title: string; body: string; link: string; is_read: boolean; created_at: string };

// Notification bell. Checks for new items every 30 seconds so staff alerts show up without a refresh.
export function Bell() {
  const [notes, setNotes] = useState<Note[]>([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);

  const load = useCallback(() => {
    api<{ results: Note[]; unread_count?: number }>("/api/me/notifications")
      .then((d) => { setNotes(d.results); setUnread(d.unread_count ?? 0); }).catch(() => {});
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, [load]);

  async function markAll() {
    await api("/api/me/notifications/read", { body: {} }).catch(() => {});
    setNotes(notes.map((n) => ({ ...n, is_read: true }))); setUnread(0);
  }
  return (
    <div style={{ position: "relative" }}>
      <button className="bell" aria-label="Notifications" onClick={() => setOpen(!open)}>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#0B1F4B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9a6 6 0 0 1 12 0c0 6 2.5 7.5 2.5 7.5h-17S6 15 6 9z" /><path d="M10 20a2 2 0 0 0 4 0" /></svg>
        {unread > 0 && <span className="badge">{unread}</span>}
      </button>
      {open && (
        <div className="drop" style={{ right: 0, top: 54 }} role="dialog" aria-label="Notifications">
          <div className="row"><b style={{ fontSize: 16 }}>Alerts</b>
            {unread > 0 && <button onClick={markAll} style={{ background: "none", border: 0, color: "var(--blue)", fontWeight: 700, fontSize: 13 }}>Mark all as read</button>}</div>
          {notes.length === 0 && <p className="hint" style={{ padding: 12 }}>Nothing here yet.</p>}
          {notes.map((n) => {
            const inner = (
              <>
                <span className="ndot" />
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <b style={{ fontSize: 14 }}>{n.title}</b>
                  <span style={{ fontSize: 13, color: "var(--muted)", lineHeight: 1.45 }}>{n.body}</span>
                  <span className="hint">{fmtDateTime(n.created_at)}</span>
                </div>
              </>);
            return n.link
              ? <Link key={n.id} href={n.link} onClick={() => setOpen(false)} className={`nitem ${n.is_read ? "" : "unread"}`}>{inner}</Link>
              : <div key={n.id} className={`nitem ${n.is_read ? "" : "unread"}`}>{inner}</div>;
          })}
        </div>
      )}
    </div>
  );
}
