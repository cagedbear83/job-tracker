// src/pages/AdminPlatform.jsx
// Platform admin dashboard, ported from admin_portal/AdminApp.jsx and wired
// in at /admin/platform (see App.jsx) — separate from the existing
// /admin (src/pages/Admin.jsx, invites/users/integrations) rather than
// replacing it, matching the backend's /api/admin/platform namespacing.
// Route guard: RequireRole (src/components/RequireRole.jsx) hides the page
// for non-staff. It's cosmetic — the backend enforces every action via
// rbac.py regardless. `currentRole` only decides which controls to SHOW;
// until the platform_role migration (admin_rbac_migration.py) has run,
// App.jsx derives it from the legacy `role` field (role === "admin" ->
// "platform_admin", else "support_staff") to mirror rbac.py's own fallback.

import { useState, useEffect, useCallback, useRef } from "react";
import { adminApi } from "@/lib/adminApi";


const IL_BLUE = "#0033A0";
const isAdmin = (role) => role === "platform_admin";

const NAV = [
  { id: "users", label: "Users", staff: true },
  { id: "comps", label: "Comps", staff: false },
  { id: "refunds", label: "Refunds", staff: true },
  { id: "disputes", label: "Disputes", staff: true },
  { id: "system", label: "System", staff: true },
  { id: "compliance", label: "Compliance", staff: true },
];

export default function AdminApp({ currentRole = "support_staff" }) {
  const [tab, setTab] = useState("users");
  const visible = NAV.filter((n) => n.staff || isAdmin(currentRole));

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="w-56 shrink-0 border-r border-border p-4">
        <div className="mb-6 flex items-center gap-2">
          <span className="grid h-8 w-8 place-items-center rounded font-bold text-white"
                style={{ background: IL_BLUE }}>IL</span>
          <div className="text-sm font-semibold leading-tight">
            Admin<br /><span className="text-muted-foreground font-normal">Illinois Job Tracker</span>
          </div>
        </div>
        <nav className="space-y-1">
          {visible.map((n) => (
            <button key={n.id} onClick={() => setTab(n.id)}
              className={`w-full rounded px-3 py-2 text-left text-sm transition ${
                tab === n.id ? "bg-primary text-primary-foreground"
                             : "hover:bg-muted text-foreground"}`}>
              {n.label}
            </button>
          ))}
        </nav>
        <div className="mt-6 rounded border border-border p-2 text-xs text-muted-foreground">
          Signed in as<br />
          <span className="font-medium text-foreground">{currentRole.replace("_", " ")}</span>
        </div>
      </aside>

      <main className="flex-1 p-6">
        {tab === "users" && <UsersPanel role={currentRole} />}
        {tab === "comps" && <CompsPanel role={currentRole} />}
        {tab === "refunds" && <RefundsPanel role={currentRole} />}
        {tab === "disputes" && <DisputesPanel role={currentRole} />}
        {tab === "system" && <SystemPanel />}
        {tab === "compliance" && <CompliancePanel />}
      </main>
    </div>
  );
}

// ─── shared bits ─────────────────────────────────────────────────────────
function Card({ title, children, right }) {
  return (
    <section className="mb-6 rounded-lg border border-border bg-card">
      <header className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold">{title}</h2>
        {right}
      </header>
      <div className="p-4">{children}</div>
    </section>
  );
}

function ErrorNote({ error }) {
  if (!error) return null;
  return <p className="rounded bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>;
}

// Step-up modal: re-collects the admin's password for sensitive actions.
function StepUpModal({ open, title, onConfirm, onCancel, busy }) {
  const [pw, setPw] = useState("");
  const pwInputRef = useRef(null);
  useEffect(() => { if (!open) setPw(""); }, [open]);
  // Focus the password field imperatively (rather than the autoFocus prop)
  // so opening the step-up modal doesn't trip jsx-a11y/no-autofocus.
  useEffect(() => { if (open) pwInputRef.current?.focus(); }, [open]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4">
      <div className="w-full max-w-sm rounded-lg border border-border bg-card p-5 shadow-xl">
        <h3 className="mb-1 text-sm font-semibold">{title}</h3>
        <p className="mb-3 text-xs text-muted-foreground">
          Re-enter your password to confirm this action.
        </p>
        <input type="password" value={pw} ref={pwInputRef}
          onChange={(e) => setPw(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && pw && onConfirm(pw)}
          className="mb-4 w-full rounded border border-border bg-background px-3 py-2 text-sm"
          placeholder="Password" />
        <div className="flex justify-end gap-2">
          <button onClick={onCancel} disabled={busy}
            className="rounded px-3 py-1.5 text-sm hover:bg-muted">Cancel</button>
          <button onClick={() => onConfirm(pw)} disabled={!pw || busy}
            className="rounded px-3 py-1.5 text-sm text-primary-foreground disabled:opacity-50"
            style={{ background: IL_BLUE }}>
            {busy ? "Confirming…" : "Confirm"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Users ───────────────────────────────────────────────────────────────
function UsersPanel({ role }) {
  const [q, setQ] = useState("");
  const [data, setData] = useState({ users: [], total: 0 });
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    try { setError(null); setData(await adminApi.listUsers(q)); }
    catch (e) { setError(e.message); }
  }, [q]);
  useEffect(() => { load(); }, [load]);

  return (
    <>
      <Card title="Users" right={
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search email…"
          className="rounded border border-border bg-background px-2 py-1 text-sm" />
      }>
        <ErrorNote error={error} />
        <table className="w-full text-sm">
          <thead className="text-left text-muted-foreground">
            <tr><th className="pb-2">Email</th><th>Tier</th><th>Role</th><th>Claimants</th><th></th></tr>
          </thead>
          <tbody>
            {data.users.map((u) => (
              <tr key={u.id} className="border-t border-border">
                <td className="py-2">{u.email}</td>
                <td>{u.subscription_tier}</td>
                <td>{u.platform_role || "user"}</td>
                <td>{u.claimant_count}</td>
                <td className="text-right">
                  <button onClick={() => setSelected(u.id)}
                    className="text-xs underline text-muted-foreground hover:text-foreground">
                    view
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-2 text-xs text-muted-foreground">{data.total} total</p>
      </Card>
      {selected && <UserDetail id={selected} role={role} onClose={() => setSelected(null)} />}
    </>
  );
}

function UserDetail({ id, role, onClose }) {
  const [user, setUser] = useState(null);
  const [pii, setPii] = useState(null);
  const [ticket, setTicket] = useState("");
  const [error, setError] = useState(null);

  useEffect(() => {
    adminApi.getUser(id).then(setUser).catch((e) => setError(e.message));
  }, [id]);

  const loadPii = async () => {
    try {
      setError(null);
      setPii(await adminApi.getUserPii(id, isAdmin(role) ? undefined : ticket));
    } catch (e) { setError(e.message); }
  };

  return (
    <Card title={`Account · ${user?.email || id}`} right={
      <button onClick={onClose} className="text-xs text-muted-foreground hover:text-foreground">close</button>
    }>
      <ErrorNote error={error} />
      {user && (
        <div className="grid grid-cols-2 gap-3 text-sm">
          <Field k="Tier" v={user.subscription_tier} />
          <Field k="Platform role" v={user.platform_role || "user"} />
          <Field k="Verified" v={String(user.email_verified)} />
          <Field k="Claimants" v={user.claimant_count} />
          {user.subscription && <Field k="Sub status" v={user.subscription.status} />}
          {user.subscription?.comp && <Field k="Comp" v="yes" />}
        </div>
      )}
      <div className="mt-4 border-t border-border pt-3">
        <p className="mb-2 text-xs font-medium">Claimant PII (audited)</p>
        {!isAdmin(role) && (
          <input value={ticket} onChange={(e) => setTicket(e.target.value)}
            placeholder="ticket id (required for staff)"
            className="mr-2 rounded border border-border bg-background px-2 py-1 text-sm" />
        )}
        <button onClick={loadPii} disabled={!isAdmin(role) && !ticket}
          className="rounded border border-border px-3 py-1 text-sm hover:bg-muted disabled:opacity-50">
          Load contacts
        </button>
        {pii && <p className="mt-2 text-xs text-muted-foreground">{pii.contacts.length} contacts loaded</p>}
      </div>
    </Card>
  );
}

const Field = ({ k, v }) => (
  <div><span className="text-muted-foreground">{k}: </span><span className="font-medium">{v}</span></div>
);

// ─── Comps ───────────────────────────────────────────────────────────────
function CompsPanel() {
  const [status, setStatus] = useState(null);
  const [form, setForm] = useState({ user_id: "", tier: "pro", reason: "" });
  const [modal, setModal] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [ok, setOk] = useState(null);

  const load = () => adminApi.compStatus().then(setStatus).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  const confirm = async (pw) => {
    try {
      setBusy(true); setError(null);
      await adminApi.grantComp({ ...form, step_up_password: pw });
      setOk(`Comped ${form.user_id} → ${form.tier}`); setModal(false);
      setForm({ user_id: "", tier: "pro", reason: "" }); load();
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  };

  return (
    <Card title="Comps (platform admin)">
      <ErrorNote error={error} />
      {ok && <p className="mb-2 rounded bg-primary/10 px-3 py-2 text-sm">{ok}</p>}
      {status && (
        <p className="mb-4 text-sm text-muted-foreground">
          {status.active_comps} active comp{status.active_comps === 1 ? "" : "s"}
          {status.cap_enforced ? ` · cap ${status.cap}` : " · no cap set"}
          {status.test_mode && " · test mode"}
          {status.note && <span className="block text-xs">{status.note}</span>}
        </p>
      )}
      <div className="grid gap-2 sm:grid-cols-4">
        <input placeholder="user id" value={form.user_id}
          onChange={(e) => setForm({ ...form, user_id: e.target.value })}
          className="rounded border border-border bg-background px-2 py-1 text-sm" />
        <select value={form.tier} onChange={(e) => setForm({ ...form, tier: e.target.value })}
          className="rounded border border-border bg-background px-2 py-1 text-sm">
          <option value="pro">Pro</option>
          {/* value was "case_worker" in admin_portal — corrected to match
              this backend's actual subscription.Tier enum value
              ("caseworker", no underscore). See admin_platform_comps.py's
              module comment for the same fix on the backend side. */}
          <option value="caseworker">Case Worker</option>
        </select>
        <input placeholder="reason" value={form.reason}
          onChange={(e) => setForm({ ...form, reason: e.target.value })}
          className="rounded border border-border bg-background px-2 py-1 text-sm sm:col-span-2" />
      </div>
      <button onClick={() => setModal(true)}
        disabled={!form.user_id || form.reason.length < 3}
        className="mt-3 rounded px-4 py-1.5 text-sm text-primary-foreground disabled:opacity-50"
        style={{ background: IL_BLUE }}>
        Grant comp…
      </button>
      <StepUpModal open={modal} title="Confirm comp grant" busy={busy}
        onConfirm={confirm} onCancel={() => setModal(false)} />
    </Card>
  );
}

// ─── Refunds ─────────────────────────────────────────────────────────────
function RefundsPanel({ role }) {
  const [refunds, setRefunds] = useState([]);
  const [error, setError] = useState(null);
  const [modal, setModal] = useState(null); // refund id being approved
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  const load = () => adminApi.listRefunds().then((d) => setRefunds(d.refunds)).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  const approve = async (pw) => {
    try {
      setBusy(true); setError(null);
      await adminApi.approveRefund(modal, { note, step_up_password: pw });
      setModal(null); setNote(""); load();
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  };
  const execute = async (id) => {
    try { await adminApi.markRefundExecuted(id); load(); }
    catch (e) { setError(e.message); }
  };

  return (
    <Card title="Refund queue">
      <ErrorNote error={error} />
      <p className="mb-3 text-xs text-muted-foreground">
        Approvals are recorded here; execute the actual refund in the Stripe dashboard, then mark executed.
      </p>
      <table className="w-full text-sm">
        <thead className="text-left text-muted-foreground">
          <tr><th className="pb-2">User</th><th>Amount</th><th>Status</th><th>Reason</th><th></th></tr>
        </thead>
        <tbody>
          {refunds.map((r) => (
            <tr key={r.id} className="border-t border-border">
              <td className="py-2">{r.user_id}</td>
              <td>${(r.amount_cents / 100).toFixed(2)}</td>
              <td><StatusPill s={r.status} /></td>
              <td className="max-w-[16rem] truncate text-muted-foreground">{r.reason}</td>
              <td className="text-right">
                {isAdmin(role) && r.status === "requested" && (
                  <button onClick={() => setModal(r.id)} className="text-xs underline">approve</button>
                )}
                {isAdmin(role) && r.status === "approved" && (
                  <button onClick={() => execute(r.id)} className="text-xs underline">mark executed</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {refunds.length === 0 && <p className="text-sm text-muted-foreground">No refund requests.</p>}
      <StepUpModal open={!!modal} title="Approve refund" busy={busy}
        onConfirm={approve} onCancel={() => setModal(null)} />
      {modal && (
        <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="approval note"
          className="mt-2 w-full rounded border border-border bg-background px-2 py-1 text-sm" />
      )}
    </Card>
  );
}

const StatusPill = ({ s }) => {
  const map = {
    requested: "bg-amber-500/15 text-amber-600",
    approved: "bg-blue-500/15 text-blue-600",
    executed: "bg-green-500/15 text-green-600",
    denied: "bg-destructive/10 text-destructive",
  };
  return <span className={`rounded px-2 py-0.5 text-xs ${map[s] || "bg-muted"}`}>{s}</span>;
};

// ─── Disputes ────────────────────────────────────────────────────────────
// Backed by routers/admin_disputes.py + Disputes.py (fixed and wired in a
// follow-up pass — see those files' module comments). The list/metrics are
// fed by Stripe webhook events (billing.py's handle_stripe_webhook), so an
// empty list here means no disputes have occurred yet, not a broken panel.
function DisputesPanel({ role }) {
  const [data, setData] = useState({ metrics: null, disputes: [] });
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    try { setError(null); setData(await adminApi.listDisputes()); }
    catch (e) { setError(e.message); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const m = data.metrics;
  const levelColor = { none: "text-green-600", warn: "text-amber-600", critical: "text-destructive" };
  const fmtDue = (ts) => ts ? new Date(ts * 1000).toLocaleDateString() : "—";

  return (
    <>
      <Card title="Chargeback rate">
        <ErrorNote error={error} />
        {m && (
          <p className="text-sm">
            <span className={`text-lg font-semibold ${levelColor[m.level]}`}>{m.rate_pct}%</span>
            <span className="text-muted-foreground"> · {m.disputes} disputes / {m.charges} charges (last {m.window_days}d) · </span>
            <span className={levelColor[m.level]}>{m.level.toUpperCase()}</span>
            <span className="text-muted-foreground"> · warn {(m.thresholds.warn*100).toFixed(2)}% / critical {(m.thresholds.critical*100).toFixed(2)}%</span>
          </p>
        )}
      </Card>
      <Card title="Disputes">
        <table className="w-full text-sm">
          <thead className="text-left text-muted-foreground">
            <tr><th className="pb-2">Reason</th><th>Amount</th><th>Status</th><th>Evidence due</th><th></th></tr>
          </thead>
          <tbody>
            {data.disputes.map((d) => (
              <tr key={d.id} className="border-t border-border">
                <td className="py-2">{d.reason || "—"}</td>
                <td>${((d.amount_cents || 0) / 100).toFixed(2)}</td>
                <td><StatusPill s={d.status || "—"} /></td>
                <td className="text-muted-foreground">{fmtDue(d.evidence_due_by)}</td>
                <td className="text-right">
                  <button onClick={() => setSelected(d.id)} className="text-xs underline text-muted-foreground hover:text-foreground">review</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data.disputes.length === 0 && <p className="text-sm text-muted-foreground">No disputes.</p>}
      </Card>
      {selected && <DisputeDetail id={selected} role={role} onClose={() => { setSelected(null); load(); }} />}
    </>
  );
}

function DisputeDetail({ id, role, onClose }) {
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState(null);
  const [submitModal, setSubmitModal] = useState(false);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  useEffect(() => { adminApi.getDispute(id).then(setDetail).catch((e) => setError(e.message)); }, [id]);

  const submitApi = async (pw) => {
    try { setBusy(true); setError(null); await adminApi.submitDispute(id, { step_up_password: pw }); setSubmitModal(false); onClose(); }
    catch (e) { setError(e.message); setBusy(false); }
  };
  const markDash = async () => {
    try { setBusy(true); await adminApi.markDisputeSubmitted(id, { note }); onClose(); }
    catch (e) { setError(e.message); setBusy(false); }
  };

  const ev = detail?.assembled_evidence;
  return (
    <Card title="Dispute — assembled evidence" right={
      <button onClick={onClose} className="text-xs text-muted-foreground hover:text-foreground">close</button>
    }>
      <ErrorNote error={error} />
      {ev && (
        <div className="space-y-2 text-sm">
          {Object.entries(ev).map(([k, v]) => (
            <div key={k}>
              <span className="text-xs font-medium text-muted-foreground">{k}</span>
              <p className="whitespace-pre-wrap rounded border border-border bg-background p-2 text-xs">{v || "—"}</p>
            </div>
          ))}
        </div>
      )}
      {isAdmin(role) && (
        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-3">
          <button onClick={() => setSubmitModal(true)} disabled={busy}
            className="rounded px-3 py-1.5 text-sm text-primary-foreground disabled:opacity-50" style={{ background: IL_BLUE }}>
            Submit to Stripe
          </button>
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="or note dashboard submission"
            className="rounded border border-border bg-background px-2 py-1 text-sm" />
          <button onClick={markDash} disabled={busy}
            className="rounded border border-border px-3 py-1.5 text-sm hover:bg-muted disabled:opacity-50">
            Mark submitted (dashboard)
          </button>
        </div>
      )}
      <StepUpModal open={submitModal} title="Confirm dispute submission" busy={busy}
        onConfirm={submitApi} onCancel={() => setSubmitModal(false)} />
    </Card>
  );
}

// ─── System ──────────────────────────────────────────────────────────────
function SystemPanel() {
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    adminApi.systemHealth().then(setHealth).catch((e) => setError(e.message));
  }, []);
  return (
    <Card title="System health">
      <ErrorNote error={error} />
      {health && (
        <div className="space-y-2 text-sm">
          <p className={health.ok ? "text-green-600" : "text-destructive"}>
            {health.ok ? "All core systems operational" : "Attention needed"}
          </p>
          {Object.entries(health.checks).map(([k, v]) => (
            <div key={k} className="flex items-center justify-between border-t border-border py-1.5">
              <span className="capitalize">{k}</span>
              <span className="text-muted-foreground">
                {v.ok === false ? "down" : v.ok ? "ok" :
                 v.configured ? `configured${v.mode ? ` (${v.mode})` : ""}` : "not configured"}
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

// ─── Compliance ──────────────────────────────────────────────────────────
function CompliancePanel() {
  const [audit, setAudit] = useState([]);
  const [retention, setRetention] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    adminApi.auditSearch({ limit: 50 }).then((d) => setAudit(d.entries)).catch((e) => setError(e.message));
    adminApi.retention(14).then(setRetention).catch((e) => setError(e.message));
  }, []);
  return (
    <>
      <Card title="Retention — weeks approaching 53-week deletion">
        <ErrorNote error={error} />
        {retention && (
          <>
            <p className="mb-2 text-sm text-muted-foreground">
              {retention.count} week(s) delete within {retention.within_days} days
            </p>
            <table className="w-full text-sm">
              <thead className="text-left text-muted-foreground">
                <tr><th className="pb-2">User</th><th>Deletes in</th><th>Notices sent</th></tr>
              </thead>
              <tbody>
                {retention.weeks.map((w, i) => (
                  <tr key={i} className="border-t border-border">
                    <td className="py-2">{w.user_id}</td>
                    <td>{w.days_until_deletion}d</td>
                    <td className="text-muted-foreground">{(w.notices_sent || []).join(", ") || "none"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </Card>
      <Card title="Audit log (recent)">
        <table className="w-full text-sm">
          <thead className="text-left text-muted-foreground">
            <tr><th className="pb-2">When</th><th>Actor</th><th>Action</th><th>Target</th></tr>
          </thead>
          <tbody>
            {audit.map((a, i) => (
              <tr key={i} className="border-t border-border">
                <td className="py-2">{new Date(a.at).toLocaleString()}</td>
                <td>{a.actor_role}</td>
                <td>{a.action}</td>
                <td className="text-muted-foreground">{a.target_user_id || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {audit.length === 0 && <p className="text-sm text-muted-foreground">No audit entries yet.</p>}
      </Card>
    </>
  );
}
