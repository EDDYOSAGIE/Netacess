"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Header } from "@/components/Header";
import { api, ApiError, auth, money } from "@/lib/api";

type Payment = { id: string; provider: string; amount: string; currency: string; status: string; checkout_url: string; access_code: string | null };

export default function PaymentStatus() {
  const { id } = useParams<{ id: string }>();
  const r = useRouter();
  const [p, setP] = useState<Payment | null>(null);
  const [offline, setOffline] = useState(false);
  const [copied, setCopied] = useState(false);
  const started = useRef(Date.now());

  useEffect(() => {
    if (!auth.get()) { sessionStorage.setItem("netacess_next", `/payment/${id}`); r.replace("/login"); return; }
    let stop = false;
    async function tick() {
      try {
        const d = await api<Payment>(`/api/payments/${id}`);
        if (stop) return;
        setP(d); setOffline(false);
        if (["SUCCESSFUL", "FAILED", "EXPIRED", "NEEDS_REVIEW", "REFUNDED"].includes(d.status)) {
          if (d.status !== "SUCCESSFUL") Object.keys(sessionStorage).filter((k) => k.startsWith("idem:")).forEach((k) => sessionStorage.removeItem(k));
          return;
        }
      } catch (x) {
        if ((x as ApiError).status === 401) { r.replace("/login"); return; }
        setOffline(true);
      }
      if (!stop && Date.now() - started.current < 15 * 60 * 1000) setTimeout(tick, 3000);
    }
    tick();
    return () => { stop = true; };
  }, [id, r]);

  const copy = async () => {
    if (!p?.access_code) return;
    try { await navigator.clipboard.writeText(p.access_code); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch {}
  };
  const amount = p ? money(p.amount, p.currency) : "";
  const prov = p?.provider === "espees" ? "Espees" : "Flutterwave";

  return (
    <>
      <Header />
      <main className="center">
        {!p && <div className="card" style={{ textAlign: "center" }}><div className="spinner" /><p className="lead" style={{ marginTop: 16 }}>Loading your payment…</p></div>}

        {p && (p.status === "PENDING" || p.status === "INITIATED") && (
          <div className="card" style={{ display: "flex", flexDirection: "column", gap: 16, textAlign: "center" }}>
            <div className="spinner" />
            <h1 style={{ fontSize: 26, fontWeight: 800 }}>Checking your payment</h1>
            <p className="lead" style={{ fontSize: 15 }}>
              {p.provider === "espees" ? "We are waiting for Espees to confirm your payment." : "We are waiting for Flutterwave to confirm your payment."} This usually takes under a minute. You can leave this page open.
            </p>
            {offline && <div className="alert warn"><div>We lost connection for a moment. Still trying…</div></div>}
            <div className="alert info"><div>Already paid? Your code appears here automatically. If you were charged and it does not show within a few minutes, it will still be added to your account.</div></div>
            {p.checkout_url && <a className="btn ghost" href={p.checkout_url}>Open the payment page again</a>}
          </div>
        )}

        {p?.status === "SUCCESSFUL" && (
          <div className="card" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <span className="pill ok" style={{ alignSelf: "flex-start" }}>Payment confirmed</span>
            <h1 style={{ fontSize: 28, fontWeight: 800, letterSpacing: -.6 }}>You're all set</h1>
            <p className="lead" style={{ fontSize: 15 }}>We received {amount} via {prov}. Here is your Netacess access code.</p>
            <div style={{ background: "var(--soft)", borderRadius: 16, padding: 20, display: "flex", flexDirection: "column", gap: 12 }}>
              <span className="hint" style={{ fontWeight: 600 }}>Your access code</span>
              <span className="code" data-testid="code">{p.access_code}</span>
              <button className="btn sm" style={{ alignSelf: "flex-start" }} onClick={copy}>{copied ? "Copied" : "Copy code"}</button>
            </div>
            <span className="hint">Keep this code safe. You can always find it again in your profile.</span>
            <Link href="/profile" className="btn">Go to my profile</Link>
          </div>
        )}

        {p?.status === "FAILED" && (
          <div className="card" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div className="alert bad"><div><b>Payment did not go through</b>You were not charged, or any charge will be reversed by your bank or {prov}.</div></div>
            <Link href="/checkout" className="btn">Try again</Link>
            <span className="hint" style={{ textAlign: "center" }}>You can also try the other payment method.</span>
          </div>
        )}

        {p?.status === "EXPIRED" && (
          <div className="card" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div className="alert warn"><div><b>This payment link expired</b>If you already paid, your code will still be added to your profile once the payment is confirmed.</div></div>
            <Link href="/checkout" className="btn">Start a new payment</Link>
            <Link href="/profile" className="btn ghost">Check my profile</Link>
          </div>
        )}

        {p?.status === "NEEDS_REVIEW" && (
          <div className="card" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div className="alert warn"><div><b>We are reviewing your payment</b>Something about this payment needs a quick check by our team. If you were charged, you will get your access code and a notification. You do not need to pay again.</div></div>
            <Link href="/profile" className="btn">Go to my profile</Link>
          </div>
        )}

        {p?.status === "REFUNDED" && (
          <div className="card"><div className="alert info"><div><b>This payment was refunded</b>Contact support if you think this is a mistake.</div></div></div>
        )}
      </main>
    </>
  );
}
