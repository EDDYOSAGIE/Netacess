"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Header } from "@/components/Header";
import { api, ApiError } from "@/lib/api";

export function LoginForm({ staffMode = false }: { staffMode?: boolean }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    const normalizedEmail = email.trim().toLowerCase();
    if (!normalizedEmail) { setErr("Enter your email address."); return; }
    setBusy(true);
    try {
      await api("/api/auth/otp/send", { body: { email: normalizedEmail, purpose: "login" } });
      if (staffMode) sessionStorage.setItem("netacess_next", "/admin");
      else sessionStorage.removeItem("netacess_next");
      sessionStorage.setItem("netacess_signup", JSON.stringify({
        email: normalizedEmail,
        full_name: "",
        mode: "login",
        login_for: staffMode ? "staff" : "customer",
      }));
      router.push("/login/verify");
    } catch (x) {
      const error = x as ApiError;
      if (error.code === "account_not_found") {
        setErr(staffMode
          ? "No staff account was found for this email. Ask the administrator to add it to your staff account."
          : "No account was found for this email. Check the address or create an account first.");
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
                ? "Enter the email registered to your staff account. We will email you a 6-digit code."
                : "Enter your email and we will email you a 6-digit sign-in code."}
          </p>
              <div className="field"><label htmlFor="email">Email</label><input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" /></div>
          {err && <div className="alert bad" role="alert"><div>{err}</div></div>}
          <button className="btn" disabled={busy}>{busy ? "Sending…" : "Send me a code"}</button>
          {!staffMode && <span className="hint" style={{ textAlign: "center" }}>New here? <Link href="/signup" style={{ color: "var(--blue)", fontWeight: 700 }}>Create an account</Link></span>}
          {staffMode && <span className="hint" style={{ textAlign: "center" }}>Staff access only</span>}
        </form>
      </div>
    </>
  );
}