"use client";

import { useEffect } from "react";
import { api, auth } from "@/lib/api";

const IDLE_TIMEOUT_MS = 60 * 60 * 1000;
const HEARTBEAT_INTERVAL_MS = 5 * 60 * 1000;
const ACTIVITY_KEY = "netacess_last_activity";

export function SessionGuard() {
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    let lastActivity = Date.now();
    let lastPing = 0;
    let pingPending = false;
    let wasAuthenticated = Boolean(auth.get());

    const expire = () => {
      if (!auth.get()) return;
      auth.endSession();
      window.location.assign("/login");
    };

    const scheduleExpiry = () => {
      if (timer) clearTimeout(timer);
      if (auth.get()) {
        const remaining = IDLE_TIMEOUT_MS - (Date.now() - lastActivity);
        timer = setTimeout(expire, Math.max(0, remaining));
      }
    };

    const ping = async () => {
      if (pingPending || !auth.get()) return;
      pingPending = true;
      try {
        await api("/api/me");
        lastPing = Date.now();
      } catch {
        expire();
      } finally {
        pingPending = false;
      }
    };

    const onActivity = () => {
      if (!auth.get()) return;
      lastActivity = Date.now();
      try { localStorage.setItem(ACTIVITY_KEY, String(lastActivity)); } catch {}
      scheduleExpiry();
      if (lastActivity - lastPing >= HEARTBEAT_INTERVAL_MS) void ping();
    };

    const onStorage = (event: StorageEvent) => {
      if (event.key === ACTIVITY_KEY && event.newValue) {
        const sharedActivity = Number(event.newValue);
        if (Number.isFinite(sharedActivity) && sharedActivity > lastActivity) {
          lastActivity = sharedActivity;
          scheduleExpiry();
          if (lastActivity - lastPing >= HEARTBEAT_INTERVAL_MS) void ping();
        }
      }
      if (event.key === "netacess_token" && !event.newValue && wasAuthenticated) {
        wasAuthenticated = false;
        window.location.assign("/login");
      }
      if (event.key === "netacess_token" && event.newValue) {
        wasAuthenticated = true;
        lastActivity = Date.now();
        scheduleExpiry();
        void ping();
      }
    };

    const onTokenChange = () => {
      if (auth.get()) {
        wasAuthenticated = true;
        lastActivity = Date.now();
        scheduleExpiry();
        void ping();
      } else if (wasAuthenticated) {
        wasAuthenticated = false;
        window.location.assign("/login");
      }
    };

    if (wasAuthenticated) {
      try {
        const sharedActivity = Number(localStorage.getItem(ACTIVITY_KEY));
        if (Number.isFinite(sharedActivity) && sharedActivity > 0) lastActivity = sharedActivity;
      } catch {}
      scheduleExpiry();
      void ping();
    }
    ["pointerdown", "keydown", "scroll", "touchstart"].forEach((name) =>
      window.addEventListener(name, onActivity, { passive: true }),
    );
    window.addEventListener("storage", onStorage);
    window.addEventListener("netacess:token-change", onTokenChange);

    return () => {
      if (timer) clearTimeout(timer);
      ["pointerdown", "keydown", "scroll", "touchstart"].forEach((name) =>
        window.removeEventListener(name, onActivity),
      );
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("netacess:token-change", onTokenChange);
    };
  }, []);

  return null;
}