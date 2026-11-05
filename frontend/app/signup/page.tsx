"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import Link from "next/link";
import { Header } from "@/components/Header";
import { Steps } from "@/components/Steps";
import { PhoneNumberField, toE164PhoneNumber } from "@/components/PhoneNumberField";
import { api, ApiError } from "@/lib/api";
import type { CountryCode } from "libphonenumber-js";

export default function Signup() {
  const r = useRouter();
  const [f, setF] = useState({ full_name: "", phone: "", email: "", password: "" });
  const [country, setCountry] = useState<CountryCode>("NG");
  const [policiesAccepted, setPoliciesAccepted] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    if (f.password.length < 8) return setErr("Password must be at least 8 characters.");
    const phone = toE164PhoneNumber(f.phone, country);
    if (!phone) return setErr("Enter a valid phone number for the selected country.");
    setBusy(true);
    try {
      const result = await api<{ code?: string }>("/api/auth/otp/send", { body: { phone, purpose: "signup" } });
      sessionStorage.setItem("netacess_signup", JSON.stringify({
        full_name: f.full_name,
        phone,
        email: f.email,
        mode: "signup",
        policies_accepted: policiesAccepted,
        demoCode: result.code,
      }));
      r.push("/signup/verify");
    } catch (x) {
      setErr(x instanceof ApiError ? x.message : "Something went wrong");
    } finally { setBusy(false); }
  }

  return (
    <>
      <Header />
      <div className="authwrap">
        <div className="authintro">
          <h1>Create your Netacess account</h1>
          <p className="lead">Sign up with your phone number. We text you a 6-digit code to confirm it is yours, then you can pick a plan.</p>
          <Steps at={1} />
        </div>
        <form className="card authcard" onSubmit={submit}>
          <h2>Your details</h2>
          <div className="field"><label htmlFor="n">Full name</label><input id="n" required value={f.full_name} onChange={set("full_name")} /></div>
          <div className="field"><label htmlFor="p">Phone number</label><PhoneNumberField value={f.phone} country={country} onValueChange={(phone) => setF({ ...f, phone })} onCountryChange={setCountry} /><span className="hint">Choose your country code. We send the code to this number by SMS.</span></div>
          <div className="field"><label htmlFor="e">Email</label><input id="e" type="email" placeholder="you@example.com" value={f.email} onChange={set("email")} /></div>
          <div className="field"><label htmlFor="w">Password</label><input id="w" type="password" required placeholder="At least 8 characters" value={f.password} onChange={set("password")} /></div>
          <label className="consent-field" htmlFor="policies">
            <input id="policies" type="checkbox" required checked={policiesAccepted} onChange={(e) => setPoliciesAccepted(e.target.checked)} />
            <span>I agree to the <Link href="/terms" target="_blank">Terms of Service</Link> and acknowledge the <Link href="/privacy" target="_blank">Privacy Notice</Link>.</span>
          </label>
          {err && <div className="alert bad" role="alert"><div>{err}</div></div>}
          <button className="btn" disabled={busy}>{busy ? "Sending…" : "Send me a code"}</button>
          <span className="hint" style={{ textAlign: "center" }}>Standard SMS rates from your network may apply. Draft policies require review before launch.</span>
        </form>
      </div>
    </>
  );
}
