"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Header } from "@/components/Header";
import { api, ApiError, auth } from "@/lib/api";
import { Steps } from "@/components/Steps";

type Pending = { phone?: string; full_name: string; email: string; mode: "signup" | "login"; login_for?: "customer" | "staff"; policies_accepted?: boolean };

export default function Verify() {
  const r = useRouter();
  const [p, setP] = useState<Pending | null>(null);
  const [digits, setDigits] = useState<string[]>(Array(6).fill(""));
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<{ title: string; body: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [wait, setWait] = useState(60);
  const refs = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => {
    try {
      const s = sessionStorage.getItem("netacess_signup");
      if (s) setP(JSON.parse(s)); else r.replace("/signup");
    } catch { r.replace("/signup"); }
  }, [r]);
  useEffect(() => {
    if (wait <= 0) return;
    const t = setTimeout(() => setWait(wait - 1), 1000);
    return () => clearTimeout(t);
  }, [wait]);

  const code = digits.join("");
  function change(i: number, v: string) {
    const d = v.replace(/\D/g, "");
    if (d.length > 1) { // paste
      const next = Array(6).fill("").map((_, k) => d[k] || "");
      setDigits(next); refs.current[Math.min(d.length, 5)]?.focus(); return;
    }
    const next = [...digits]; next[i] = d; setDigits(next);
    if (d && i < 5) refs.current[i + 1]?.focus();
  }
  function key(i: number, e: React.KeyboardEvent) {
    if (e.key === "Backspace" && !digits[i] && i > 0) refs.current[i - 1]?.focus();
  }

  async function verify(e: React.FormEvent) {
    e.preventDefault();
    if (!p || code.length !== 6) return;
    if (p.mode === "signup" && password.length < 8) {
      setErr({ title: "Password required", body: "Enter a password of at least 8 characters to create your account." });
      return;
    }
    setBusy(true); setErr(null);
    try {
      const res = await api<{ token: string; user?: { is_staff?: boolean } }>("/api/auth/otp/verify", {
        body: {
          ...(p.phone ? { phone: p.phone } : {}),
          email: p.email,
          purpose: p.mode,
          code,
          full_name: p.full_name,
          ...(p.mode === "signup" ? { password, policies_accepted: p.policies_accepted === true } : {}),
        },
      });
      auth.set(res.token);
      sessionStorage.removeItem("netacess_signup");
      const next = sessionStorage.getItem("netacess_next");
      sessionStorage.removeItem("netacess_next");
      const safeNext = next?.startsWith("/") && !next.startsWith("//") ? next : null;
      if (p.mode === "login" && res.user?.is_staff) {
        r.push(safeNext && safeNext !== "/profile" ? safeNext : "/admin");
      } else {
        r.push(safeNext && safeNext !== "/admin" ? safeNext : (p.mode === "login" ? "/profile" : "/#plans"));
      }
    } catch (x) {
      const titles: Record<string, string> = { wrong_code: "That code is not right", expired: "This code has expired", too_many_attempts: "Too many attempts", no_code: "No code found", account_not_found: p?.login_for === "staff" ? "Staff account not found" : "Account not found" };
      const e = x as ApiError;
      setErr({ title: titles[e.code] || "Could not verify", body: e.code === "wrong_code" ? "Check the SMS and try again." : e.message });
    } finally { setBusy(false); }
  }

  async function resend() {
    if (!p) return;
    setErr(null);
    try {
      await api("/api/auth/otp/send", { body: { ...(p.phone ? { phone: p.phone } : {}), email: p.email, purpose: p.mode } });
      setWait(60); setDigits(Array(6).fill("")); refs.current[0]?.focus();
    }
    catch (x) { setErr({ title: "Could not resend", body: (x as ApiError).message }); }
  }

  const masked = p ? p.email.replace(/^(.{2})[^@]*(@.*)$/, "$1•••$2") : "";
  return (
    <>
      <Header />
      <div className="authwrap">
        <div className="authintro">
          <h1>Check your email</h1>
          <p className="lead">We sent a 6-digit verification code to your email. Enter it to finish.</p>
          {p?.mode === "signup" && <Steps at={2} />}
        </div>
        <form className="card authcard" onSubmit={verify}>
          <h2>Enter the 6-digit code</h2>
          <p className="lead" style={{ fontSize: 15 }}>Sent to <b style={{ color: "var(--ink)" }}>{masked}</b>. The code is valid for 5 minutes.</p>
          <div className={`otp ${err ? "err" : ""}`}>
            {digits.map((d, i) => (
              <input key={i} ref={(el) => { refs.current[i] = el; }} value={d} inputMode="numeric" autoComplete={i === 0 ? "one-time-code" : "off"}
                aria-label={`Digit ${i + 1}`} maxLength={6} autoFocus={i === 0}
                onChange={(e) => change(i, e.target.value)} onKeyDown={(e) => key(i, e)} />
            ))}
          </div>
          {p?.mode === "signup" && <div className="field"><label htmlFor="signup-password">Create password</label><input id="signup-password" type="password" autoComplete="new-password" minLength={8} required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="At least 8 characters" /></div>}
          {err && <div className="alert bad" role="alert"><div><b>{err.title}</b>{err.body}</div></div>}
          <button className="btn" type="submit" disabled={busy || code.length !== 6 || (p?.mode === "signup" && password.length < 8)}>{busy ? "Checking…" : "Verify and continue"}</button>
          <div className="row" style={{ fontSize: 14 }}>
            {wait > 0 ? <span className="hint" style={{ fontSize: 14 }}>Resend code in 0:{String(wait).padStart(2, "0")}</span>
              : <button onClick={resend} style={{ background: "none", border: 0, color: "var(--blue)", fontWeight: 700, padding: 0, fontSize: 14 }}>Resend code</button>}
            <Link href={p?.mode === "login" ? (p.login_for === "staff" ? "/staff-login" : "/login") : "/signup"} style={{ color: "var(--blue)", fontWeight: 700 }}>Change email</Link>
          </div>
        </form>
      </div>
    </>
  );
}
