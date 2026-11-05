"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, auth } from "@/lib/api";
import { Logo } from "./Logo";

export function Header({ landing = false }: { landing?: boolean }) {
  const [signedIn, setSignedIn] = useState(false);
  const [isStaff, setIsStaff] = useState(false);
  useEffect(() => {
    const token = auth.get();
    setSignedIn(!!token);
    if (token) {
      api<{ is_staff: boolean }>("/api/me")
        .then((me) => setIsStaff(me.is_staff))
        .catch(() => { setSignedIn(false); setIsStaff(false); });
    }
  }, []);
  return (
    <header className="header">
      <Logo />
      <nav className="nav">
        {landing && <a href="#plans" className="hide">Plans</a>}
        {landing && <Link href="/how-it-works" className="hide">How it works</Link>}
        {(!signedIn || isStaff) && <Link href="/admin" className="btn ghost sm staff-link">{isStaff ? "Admin" : <><span className="staff-full">Staff sign in</span><span className="staff-compact">Staff</span></>}</Link>}
        {signedIn ? (
          <Link href="/profile" className="btn sm">My profile</Link>
        ) : (
          <>
            <Link href="/login">Log in</Link>
            <Link href="/signup" className="btn sm">Get started</Link>
          </>
        )}
      </nav>
    </header>
  );
}
