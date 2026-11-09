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
  const [f, setF] = useState({ full_name: "", phone: "", email: "" });
  const [country, setCountry] = useState<CountryCode>("NG");
  const [policiesAccepted, setPoliciesAccepted] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    const phone = toE164PhoneNumber(f.phone, country);
    if (!phone) return setErr("Enter a valid phone number for the selected country.");
    setBusy(true);
    try {
      await api("/api/auth/otp/send", { body: { phone, email: f.email, purpose: "signup" } });
      sessionStorage.setItem("netacess_signup", JSON.stringify({
        full_name: f.full_name,
        phone,
        email: f.email,
        mode: "signup",
        policies_accepted: policiesAccepted,
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
          <p className="lead">Create your account with your email and phone number. We email a 6-digit verification code.</p>
          <Steps at={1} />
        </div>
        <form className="card authcard" onSubmit={submit}>
          <h2>Your details</h2>
          <div className="field"><label htmlFor="n">Full name</label><input id="n" required value={f.full_name} onChange={set("full_name")} /></div>
          <div className="field"><label htmlFor="p">Phone number</label><PhoneNumberField value={f.phone} country={country} onValueChange={(phone) => setF({ ...f, phone })} onCountryChange={setCountry} /><span className="hint">Choose your country code. We send the code to this number by SMS.</span></div>
          <div className="field"><label htmlFor="e">Email</label><input id="e" type="email" autoComplete="email" required placeholder="you@example.com" value={f.email} onChange={set("email")} /><span className="hint">Your verification code will be sent here. Payment access codes will be sent to your phone.</span></div>
          <label className="consent-field" htmlFor="policies">
            <input id="policies" type="checkbox" required checked={policiesAccepted} onChange={(e) => setPoliciesAccepted(e.target.checked)} />
            <span>I agree to the <Link href="/terms" target="_blank">Terms of Service</Link> and acknowledge the <Link href="/privacy" target="_blank">Privacy Notice</Link>.</span>
          </label>
          {err && <div className="alert bad" role="alert"><div>{err}</div></div>}
          <button className="btn" disabled={busy}>{busy ? "Sending…" : "Send me a code"}</button>
          <span className="hint" style={{ textAlign: "center" }}>Draft policies require review before launch.</span>
        </form>
      </div>
    </>
  );
}
