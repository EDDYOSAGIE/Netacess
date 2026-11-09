"use client";
import { useEffect, useState } from "react";
import { AdminShell } from "@/components/AdminShell";
import { api, ApiError, esp, naira, Plan } from "@/lib/api";

type AdminPlan = Plan & {
  is_active: boolean;
  espees_product_sku: string;
  espees_payment_ref: string;
};
type PlanForm = {
  name: string;
  price_ngn: string;
  price_esp: string;
  duration_days: string;
  is_recurring: boolean;
  is_active: boolean;
};
const EMPTY: PlanForm = {
  name: "",
  price_ngn: "",
  price_esp: "",
  duration_days: "30",
  is_recurring: false,
  is_active: true,
};

function formFor(plan?: AdminPlan): PlanForm {
  return plan ? {
    name: plan.name,
    price_ngn: String(plan.price_ngn_kobo / 100),
    price_esp: plan.price_esp,
    duration_days: String(plan.duration_days),
    is_recurring: plan.is_recurring,
    is_active: plan.is_active,
  } : EMPTY;
}

export default function AdminPlans() {
  const [plans, setPlans] = useState<AdminPlan[]>([]);
  const [editing, setEditing] = useState<AdminPlan | null>(null);
  const [form, setForm] = useState<PlanForm>(EMPTY);
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [productBusy, setProductBusy] = useState<string | null>(null);
  const [availabilityBusy, setAvailabilityBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    try { setPlans(await api<AdminPlan[]>("/api/admin/plans")); }
    catch (e) { setError((e as ApiError).message); }
  }
  useEffect(() => { load(); }, []);

  function startCreate() {
    setEditing(null); setForm(EMPTY); setError(""); setNotice(""); setShowForm(true);
  }
  function startEdit(plan: AdminPlan) {
    setEditing(plan); setForm(formFor(plan)); setError(""); setNotice(""); setShowForm(true);
  }
  function change<K extends keyof PlanForm>(key: K, value: PlanForm[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function save(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError(""); setNotice("");
    const body = {
      name: form.name.trim(),
      price_ngn_kobo: Math.round(Number(form.price_ngn) * 100),
      price_esp: form.price_esp,
      duration_days: Number(form.duration_days),
      is_recurring: form.is_recurring,
      is_active: form.is_active,
    };
    try {
      await api(editing ? `/api/admin/plans/${editing.id}` : "/api/admin/plans", {
        method: editing ? "PATCH" : "POST", body,
      });
      await load(); setShowForm(false); setNotice(editing ? "Plan updated." : "Plan created.");
    } catch (e) { setError((e as ApiError).message); }
    finally { setBusy(false); }
  }

  async function createEspeesProduct(plan: AdminPlan) {
    setProductBusy(plan.id); setError(""); setNotice("");
    try {
      await api(`/api/admin/plans/${plan.id}/espees-product`, { body: {} });
      await load(); setNotice(`Espees product created for ${plan.name}.`);
    } catch (e) { setError((e as ApiError).message); }
    finally { setProductBusy(null); }
  }

  async function setAvailability(plan: AdminPlan, active: boolean) {
    const action = active ? "restore" : "remove";
    if (!window.confirm(`${active ? "Restore" : "Remove"} ${plan.name} ${active ? "for" : "from"} all customers?`)) return;
    setAvailabilityBusy(plan.id); setError(""); setNotice("");
    try {
      await api(`/api/admin/plans/${plan.id}`, { method: "PATCH", body: { is_active: active } });
      await load();
      setNotice(active ? `${plan.name} is available to all customers.` : `${plan.name} was removed from all customer accounts.`);
    } catch (e) { setError((e as ApiError).message); }
    finally { setAvailabilityBusy(null); }
  }

  return (
    <AdminShell>
      <div className="row">
        <div><h1 style={{ fontSize: 28, fontWeight: 800 }}>Plans</h1>
          <p className="lead" style={{ fontSize: 15 }}>Manage customer plans and their Espees product references.</p></div>
        {!showForm && <button className="btn sm" onClick={startCreate}>Add plan</button>}
      </div>
      {error && <div className="alert bad" role="alert"><div>{error}</div></div>}
      {notice && <div className="alert info" role="status">{notice}</div>}

      {showForm && <form className="card" onSubmit={save} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <h2 style={{ fontSize: 20, fontWeight: 800 }}>{editing ? `Edit ${editing.name}` : "New plan"}</h2>
        <div className="grid2">
          <div className="field"><label htmlFor="plan-name">Name</label><input id="plan-name" required maxLength={80} value={form.name} onChange={(e) => change("name", e.target.value)} /></div>
          <div className="field"><label htmlFor="plan-ngn">Price in Naira</label><input id="plan-ngn" type="number" required min="1" step="0.01" value={form.price_ngn} onChange={(e) => change("price_ngn", e.target.value)} /></div>
          <div className="field"><label htmlFor="plan-esp">Price in Espees</label><input id="plan-esp" type="number" required min="0.0001" step="0.0001" value={form.price_esp} onChange={(e) => change("price_esp", e.target.value)} /></div>
          <div className="field"><label htmlFor="plan-duration">Validity in days</label><input id="plan-duration" type="number" required min="1" step="1" value={form.duration_days} onChange={(e) => change("duration_days", e.target.value)} /></div>
        </div>
        <label className="row" style={{ justifyContent: "flex-start" }}><input type="checkbox" checked={form.is_recurring} onChange={(e) => change("is_recurring", e.target.checked)} /> Recurring monthly plan</label>
        {editing && <label className="row" style={{ justifyContent: "flex-start" }}><input type="checkbox" checked={form.is_active} onChange={(e) => change("is_active", e.target.checked)} /> Available to customers</label>}
        <div className="row" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="btn ghost sm" onClick={() => setShowForm(false)}>Cancel</button>
          <button className="btn sm" disabled={busy}>{busy ? "Saving…" : "Save plan"}</button>
        </div>
      </form>}

      <div className="card" style={{ overflowX: "auto" }}>
        {plans.length === 0 ? <p className="hint">No plans found.</p> : <table>
          <thead><tr><th>Plan</th><th>Price</th><th>Validity</th><th>Status</th><th>Espees product</th><th>Actions</th></tr></thead>
          <tbody>{plans.map((plan) => <tr key={plan.id}>
            <td><b>{plan.name}</b><div className="hint">{plan.code}{plan.is_recurring ? " · recurring" : " · one-time"}</div></td>
            <td>{naira(plan.price_ngn_kobo)}<div className="hint">{esp(plan.price_esp)}</div></td>
            <td>{plan.duration_days} days</td>
            <td><span className={`pill ${plan.is_active ? "ok" : "bad"}`}>{plan.is_active ? "Active" : "Inactive"}</span></td>
            <td>{plan.espees_payment_ref ? <><code>{plan.espees_payment_ref}</code><div><a href={`https://payment.espees.org/pay/${encodeURIComponent(plan.espees_payment_ref)}`} target="_blank" rel="noreferrer" style={{ color: "var(--blue)", fontWeight: 700 }}>Open Espees payment page</a></div><span className="hint">SKU: {plan.espees_product_sku}</span></> : <span className="hint">Not created</span>}</td>
            <td><div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              <button className="btn ghost sm" onClick={() => startEdit(plan)}>Edit</button>
              <button className={`btn sm ${plan.is_active ? "bad" : "ghost"}`} disabled={availabilityBusy === plan.id} onClick={() => setAvailability(plan, !plan.is_active)}>{availabilityBusy === plan.id ? "Saving…" : plan.is_active ? "Remove" : "Restore"}</button>
              <button className="btn sm" disabled={productBusy === plan.id} onClick={() => createEspeesProduct(plan)}>{productBusy === plan.id ? "Creating…" : plan.espees_payment_ref ? "Recreate Espees product" : "Create Espees product"}</button>
            </div></td>
          </tr>)}</tbody>
        </table>}
        <p className="hint" style={{ marginTop: 12 }}>Creating an Espees product contacts Espees and saves its returned payment reference. Customer Espees checkout remains disabled until payment confirmation can be safely matched to an individual order.</p>
      </div>
    </AdminShell>
  );
}
