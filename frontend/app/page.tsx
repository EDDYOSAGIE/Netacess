"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Header } from "@/components/Header";
import { api, naira, esp, Plan } from "@/lib/api";

// Shown if the API can't be reached, so the page never looks broken
const FALLBACK: Plan[] = [
  { id: "1", code: "ONETIME", name: "One-time plan", price_ngn_kobo: 10000000, price_esp: "", is_recurring: false, duration_days: 30 },
  { id: "2", code: "MONTHLY", name: "Monthly plan", price_ngn_kobo: 5000000, price_esp: "", is_recurring: true, duration_days: 30 },
];

export default function Landing() {
  const [plans, setPlans] = useState<Plan[]>(FALLBACK);
  useEffect(() => { api<Plan[]>("/api/plans").then(setPlans).catch(() => {}); }, []);
  const order = [...plans].sort((a, b) => (a.code === "ONETIME" ? -1 : 1) - (b.code === "ONETIME" ? -1 : 1));

  return (
    <>
      <Header landing />
      <main className="wrap">
        <section className="hero">
          <div style={{ flex: "1 1 420px", display: "flex", flexDirection: "column", gap: 24 }}>
             <h1>Fiber bandwidth you can buy in minutes</h1>
            <p className="lead">Choose a plan, pay securely, and get your NetAccess access code right after payment. Check how many days you have left from your profile.</p>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              <a href="#plans" className="btn">See plans</a>
              <Link href="/profile" className="btn ghost">Open my profile</Link>
            </div>
          </div>
          <div className="card" style={{ flex: "1 1 320px", maxWidth: 420, display: "flex", flexDirection: "column", gap: 16 }}>
            <div className="row"><b>Your plan</b><span className="pill ok">Active</span></div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}><span className="big">23</span><span className="lead" style={{ fontSize: 17 }}>days left</span></div>
            <div className="bar"><div style={{ width: "77%" }} /></div>
            <span className="hint">pay once or renew on demand</span>
          </div>
        </section>

        <section className="section" id="plans">
          <h2>Choose your plan</h2>
          <p className="lead">Pick the option that fits you. Renew when it suits you.</p>
          <div className="plans">
            {order.map((p) => (
              <div className="card" key={p.code} style={{ display: "flex", flexDirection: "column", gap: 16, borderColor: p.is_recurring ? "var(--blue)" : undefined }}>
                <div className="row"><h3 style={{ fontSize: 22 }}>{p.name}</h3>{p.is_recurring && <span className="pill info">Recurring</span>}</div>
                <p className="lead" style={{ fontSize: 15 }}>{p.is_recurring ? "Renew every month. Cancel any time." : "Pay once. No automatic renewal."}</p>
                <div><span className="price">{naira(p.price_ngn_kobo)}</span> <span className="hint">{p.is_recurring ? "per month" : "one payment"}</span></div>
                {p.price_esp && <span className="hint">Espees coming soon · {esp(p.price_esp)}</span>}
                <ul className="list">
                  <li>{p.duration_days} days of validity</li>
                  <li>Your NetAccess access code right after payment</li>
                  <li>Reminders before your plan ends</li>
                </ul>
                <Link href={`/checkout?plan=${p.code}`} className="btn" style={{ marginTop: "auto" }}>
                  Choose {p.is_recurring ? "monthly" : "one-time"} plan
                </Link>
              </div>
            ))}
          </div>
        </section>

        <section className="section" id="how">
          <h2>How it works</h2>
          <div className="how">
            <div className="card"><div className="num">1</div><h3>Choose a plan</h3><p className="lead" style={{ fontSize: 15, marginTop: 6 }}>Pick one-time or monthly and review the total before you pay.</p></div>
            <div className="card"><div className="num">2</div><h3>Pay your way</h3><p className="lead" style={{ fontSize: 15, marginTop: 6 }}>Pay with Flutterwave today. Espees payments are coming soon.</p></div>
            <div className="card"><div className="num">3</div><h3>Get your code</h3><p className="lead" style={{ fontSize: 15, marginTop: 6 }}>Your access code appears as soon as the payment is confirmed. See it again any time in your profile.</p></div>
          </div>
        </section>
      </main>
      <footer className="footer">NetAccess Systems Nigeria · Flutterwave available · Espees coming soon</footer>
    </>
  );
}
