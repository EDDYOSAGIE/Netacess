"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Header } from "@/components/Header";
import { api, ApiError, auth, naira, esp, Plan } from "@/lib/api";

type Provider = "flutterwave" | "espees";

function Checkout() {
  const r = useRouter();
  const q = useSearchParams();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [code, setCode] = useState(q.get("plan") === "ONETIME" ? "ONETIME" : "MONTHLY");
  const [provider, setProvider] = useState<Provider>("flutterwave");
  const [avail, setAvail] = useState<Record<string, boolean>>({ flutterwave: true, espees: true });
  const [err, setErr] = useState<{ title: string; body: string } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!auth.get()) { // sign in first, then come straight back here
      sessionStorage.setItem("netacess_next", `/checkout?plan=${code}`);
      r.replace("/signup"); return;
    }
    Promise.all([api<Record<string, boolean>>("/api/providers").catch(() => ({ flutterwave: true, espees: true })),
      api<{ preferred_provider: string }>("/api/me").catch(() => ({ preferred_provider: "" }))]).then(([av, me]) => {
      setAvail(av);
      const want = q.get("provider") || me.preferred_provider;
      const pick = ([want, "flutterwave", "espees"] as string[]).find((v) => (v === "flutterwave" || v === "espees") && av[v]);
      if (pick) setProvider(pick as Provider);
    });
    api<Plan[]>("/api/plans").then(setPlans).catch(() => setErr({ title: "Can't load plans", body: "Check your connection and refresh." }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const plan = plans.find((p) => p.code === code);

  async function pay() {
    if (!plan) return;
    setBusy(true); setErr(null);
    // The same key for the same choice means a double tap or refresh never creates a second charge
    const k = `idem:${code}:${provider}`;
    let key = sessionStorage.getItem(k);
    if (!key) { key = crypto.randomUUID(); sessionStorage.setItem(k, key); }
    try {
      const res = await api<any>("/api/orders", { body: { plan: code, provider, idempotency_key: key } });
      const { id, checkout_url } = res.payment;
      sessionStorage.setItem("netacess_payment", id);
      window.location.href = checkout_url || `/payment/${id}`;
    } catch (x) {
      const e = x as ApiError;
      if (e.status === 401) { auth.clear(); r.replace("/login"); return; }
      sessionStorage.removeItem(k);
      setErr(e.code === "provider_unavailable"
        ? { title: `${provider === "flutterwave" ? "Flutterwave" : "Espees"} is unavailable right now`, body: "Nothing was charged. Please try the other payment method, or try again in a few minutes." }
        : { title: "Could not start your payment", body: e.message });
      setBusy(false);
    }
  }

  const amount = !plan ? "" : provider === "espees" ? esp(plan.price_esp) : naira(plan.price_ngn_kobo);
  return (
    <>
      <Header />
      <main className="center" style={{ maxWidth: 640 }}>
        <h1 style={{ fontSize: 34, fontWeight: 800, letterSpacing: -1 }}>Checkout</h1>
        <div className="card" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <b>Your plan</b>
          {plans.map((p) => (
            <button key={p.code} className={`opt ${code === p.code ? "on" : ""}`} onClick={() => setCode(p.code)}>
              <span style={{ flex: 1 }}>{p.name}<small>{p.is_recurring ? "Renews monthly" : "One payment"} · {p.duration_days} days</small></span>
              <span>{provider === "espees" ? <>{esp(p.price_esp)}{p.price_esp_ngn_kobo && <small>≈ {naira(p.price_esp_ngn_kobo)}</small>}</> : naira(p.price_ngn_kobo)}</span>
            </button>
          ))}
        </div>
        <div className="card" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <b>Pay with</b>
          {!avail.flutterwave && !avail.espees && <div className="alert warn"><div><b>Payments are paused</b>Please try again shortly.</div></div>}
          {avail.flutterwave && <button className={`opt ${provider === "flutterwave" ? "on" : ""}`} onClick={() => setProvider("flutterwave")}>
            <span>Flutterwave<small>Card, bank transfer, USSD or bank account. All Nigerian banks.</small></span>
          </button>}
          <button className={`opt ${provider === "espees" && avail.espees ? "on" : ""}`} onClick={() => avail.espees && setProvider("espees")} disabled={!avail.espees}>
            <span>Espees<small>{avail.espees ? "Pay with your Espees wallet. You will be taken to the Espees payment page." : "Available soon. Espees payments are temporarily unavailable."}</small></span>
            {!avail.espees && <span className="pill warn">Available soon</span>}
          </button>
        </div>
        <div className="card" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="row"><span className="lead" style={{ fontSize: 16 }}>Total</span><div style={{ textAlign: "right" }}><b style={{ fontSize: 28, letterSpacing: -.5 }}>{amount || "…"}</b>{provider === "espees" && plan?.price_esp_ngn_kobo && <div className="hint">≈ {naira(plan.price_esp_ngn_kobo)}</div>}</div></div>
          {err && <div className="alert bad" role="alert"><div><b>{err.title}</b>{err.body}</div></div>}
          <button className="btn" onClick={pay} disabled={busy || !plan || !avail[provider]}>{busy ? "Opening payment page…" : `Pay ${amount}`}</button>
          <span className="hint" style={{ textAlign: "center" }}>You will get your access code as soon as the payment is confirmed.</span>
        </div>
      </main>
    </>
  );
}

export default function Page() {
  return <Suspense><Checkout /></Suspense>;
}
