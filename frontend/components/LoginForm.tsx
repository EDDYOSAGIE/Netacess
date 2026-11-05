"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Header } from "@/components/Header";
import { PhoneNumberField, toE164PhoneNumber } from "@/components/PhoneNumberField";
import { api, ApiError } from "@/lib/api";
import type { CountryCode } from "libphonenumber-js";

export function LoginForm({ staffMode = false }: { staffMode?: boolean }) {
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [country, setCountry] = useState<CountryCode>("NG");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    const normalizedPhone = toE164PhoneNumber(phone, country);
    if (!normalizedPhone) { setErr("Enter a valid phone number for the selected country."); return; }
    setBusy(true);
    try {
      const result = await api<{ code?: string }>("/api/auth/otp/send", { body: { phone: normalizedPhone, purpose: "login" } });
      if (staffMode) sessionStorage.setItem("netacess_next", "/admin");
      else sessionStorage.removeItem("netacess_next");
      sessionStorage.setItem("netacess_signup", JSON.stringify({
        phone: normalizedPhone,
        full_name: "",
        email: "",
        mode: "login",
        login_for: staffMode ? "staff" : "customer",
        demoCode: result.code,
      }));
      router.push("/login/verify");
    } catch (x) {
      const error = x as ApiError;
      if (error.code === "account_not_found") {
        setErr(staffMode
          ? "No staff account was found for this phone number. Ask the administrator to create or enable your staff account."
          : "No account was found for this phone number. Check the number or create an account first.");
      } else {
        setErr(error.message || "Something went wrong");
      }
    } finally { setBusy(false); }
  }

  return (
    <>
      <Header />
      <div className="authwrap">
        <form className="card authcard" onSubmit={submit}>
          <h2>{staffMode ? "Staff sign in" : "Log in"}</h2>
          <p className="lead" style={{ fontSize: 15 }}>
            {staffMode
              ? "Enter the phone number registered to your staff account. We will text you a 6-digit code."
              : "Enter your phone number and we will text you a 6-digit code."}
          </p>
          <div className="field"><label htmlFor="p">Phone number</label><PhoneNumberField value={phone} country={country} onValueChange={setPhone} onCountryChange={setCountry} /></div>
          {err && <div className="alert bad" role="alert"><div>{err}</div></div>}
          <button className="btn" disabled={busy}>{busy ? "Sending…" : "Send me a code"}</button>
          {!staffMode && <span className="hint" style={{ textAlign: "center" }}>New here? <Link href="/signup" style={{ color: "var(--blue)", fontWeight: 700 }}>Create an account</Link></span>}
          {staffMode && <span className="hint" style={{ textAlign: "center" }}>Staff access only</span>}
        </form>
      </div>
    </>
  );
}