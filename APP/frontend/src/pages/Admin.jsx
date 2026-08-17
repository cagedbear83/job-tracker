import { useEffect, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  ShieldCheckIcon,
  CheckCircleIcon,
  WarningIcon,
  EnvelopeSimpleIcon,
  DeviceMobileIcon,
  PlusIcon,
  CopySimpleIcon,
  TrashIcon,
  ArrowSquareOutIcon,
} from "@phosphor-icons/react";

export default function AdminPage() {
  const { user } = useAuth();
  const [users, setUsers] = useState([]);
  const [invites, setInvites] = useState([]);
  const [status, setStatus] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);

  // Invite form
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteForm, setInviteForm] = useState({
    email: "",
    claimant_label: "Primary",
    note: "",
  });
  const [busy, setBusy] = useState(false);

  // Bulk invite
  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkCsv, setBulkCsv] = useState("email,claimant_label,note\n");
  const [bulkResult, setBulkResult] = useState(null);
  const [bulkBusy, setBulkBusy] = useState(false);

  const runBulk = async () => {
    setBulkBusy(true);
    try {
      const { data } = await api.post("/admin/invites/bulk", {
        csv_text: bulkCsv,
      });
      setBulkResult(data);
      toast.success(
        `Created ${data.created.length}, skipped ${data.skipped.length}`,
      );
      await loadAll();
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setBulkBusy(false);
    }
  };

  const loadAll = async () => {
    try {
      const [u, i, s] = await Promise.all([
        api.get("/admin/users"),
        api.get("/admin/invites"),
        api.get("/admin/integrations/status"),
      ]);
      setUsers(u.data);
      setInvites(i.data);
      setStatus(s.data);
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user?.role === "admin") loadAll();
  }, [user]);

  const openDetail = async (uid) => {
    try {
      const { data } = await api.get(`/admin/users/${uid}`);
      setDetail(data);
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };

  const createInvite = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/admin/invites", inviteForm);
      toast.success(`Invite sent to ${data.email}`);
      setInviteOpen(false);
      setInviteForm({ email: "", claimant_label: "Primary", note: "" });
      await loadAll();
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };

  const revokeInvite = async (code) => {
    try {
      await api.delete(`/admin/invites/${code}`);
      toast.success("Invite revoked");
      await loadAll();
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };

  const copyLink = (link) => {
    navigator.clipboard
      .writeText(link)
      .then(() => toast.success("Link copied"));
  };

  if (user?.role !== "admin") {
    return (
      <div
        className="border border-[#DC2626] bg-destructive/10 p-6 text-sm text-[#DC2626] font-semibold"
        data-testid="admin-forbidden"
      >
        Admin access only.
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="admin-page">
      <div className="flex items-center gap-3">
        <ShieldCheckIcon size={32} weight="bold" className="text-primary" />
        <div>
          <div className="kbd-label">Case-Worker View</div>
          <h1 className="font-display font-black text-4xl tracking-tighter">
            Admin Console
          </h1>
        </div>
      </div>

      <Tabs defaultValue="users" className="space-y-4">
        <TabsList className="rounded-none bg-secondary p-0 h-auto">
          <TabsTrigger
            value="users"
            className="rounded-none data-[state=active]:bg-primary data-[state=active]:text-white px-4 py-2 text-xs font-semibold uppercase tracking-wider"
            data-testid="admin-tab-users"
          >
            Users
          </TabsTrigger>
          <TabsTrigger
            value="invites"
            className="rounded-none data-[state=active]:bg-primary data-[state=active]:text-white px-4 py-2 text-xs font-semibold uppercase tracking-wider"
            data-testid="admin-tab-invites"
          >
            Invites
          </TabsTrigger>
          <TabsTrigger
            value="integrations"
            className="rounded-none data-[state=active]:bg-primary data-[state=active]:text-white px-4 py-2 text-xs font-semibold uppercase tracking-wider"
            data-testid="admin-tab-integrations"
          >
            Integrations
          </TabsTrigger>
        </TabsList>

        <TabsContent value="users" className="space-y-4">
          <div className="border border-border bg-background overflow-x-auto">
            <table className="w-full compliance-table text-sm">
              <thead className="bg-secondary border-b">
                <tr className="text-left">
                  <th className="kbd-label">Email</th>
                  <th className="kbd-label">Name</th>
                  <th className="kbd-label">Role</th>
                  <th className="kbd-label">Claimants</th>
                  <th className="kbd-label">Weeks</th>
                  <th className="kbd-label">Contacts</th>
                  <th className="kbd-label text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading && (
                  <tr>
                    <td colSpan={7} className="text-center text-muted-foreground py-12">
                      Loading…
                    </td>
                  </tr>
                )}
                {users.map((u) => (
                  <tr
                    key={u.id}
                    className="border-b border-border"
                    data-testid={`admin-row-${u.id}`}
                  >
                    <td className="font-mono-data text-xs">{u.email}</td>
                    <td>{u.name}</td>
                    <td>
                      <span className="kbd-label">{u.role}</span>
                    </td>
                    <td className="font-mono-data">{u.claimants_count}</td>
                    <td className="font-mono-data">{u.weeks_count}</td>
                    <td className="font-mono-data">{u.contacts_count}</td>
                    <td className="text-right">
                      <button
                        type="button"
                        onClick={() => openDetail(u.id)}
                        className="text-xs font-semibold uppercase border border-border px-3 py-1 hover:border-primary hover:text-primary"
                        data-testid={`admin-view-${u.id}`}
                      >
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {detail && (
            <div
              className="border border-primary bg-background p-6"
              data-testid="admin-detail"
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <div className="kbd-label">User Detail (read-only)</div>
                  <h3 className="font-display font-bold text-xl tracking-tight">
                    {detail.user.email}
                  </h3>
                </div>
                <button
                  type="button"
                  aria-label="Close detail panel"
                  onClick={() => setDetail(null)}
                  className="kbd-label text-muted-foreground"
                >
                  Close ×
                </button>
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div>
                  <div className="kbd-label mb-2">
                    Claimants ({detail.claimants.length})
                  </div>
                  {detail.claimants.map((c) => (
                    <div
                      key={c.id}
                      className="border border-border p-3 mb-2 text-sm"
                    >
                      <b>{c.label || "Untitled"}</b> — {c.first_name}{" "}
                      {c.last_name} (•••{c.claimant_id_last4})
                    </div>
                  ))}
                </div>
                <div>
                  <div className="kbd-label mb-2">
                    Benefit Weeks ({detail.weeks.length})
                  </div>
                  <div className="max-h-96 overflow-y-auto">
                    {detail.weeks.map((w) => (
                      <div
                        key={w.id}
                        className="flex items-center justify-between border-b border-border py-2 text-sm"
                      >
                        <span className="font-mono-data">
                          {w.week_start} → {w.week_end}
                        </span>
                        {w.contact_count >= 3 ? (
                          <span className="inline-flex items-center gap-1 text-xs text-[#16A34A] font-semibold">
                            <CheckCircleIcon size={12} weight="fill" />{" "}
                            {w.contact_count}/3
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-xs text-[#DC2626] font-semibold">
                            <WarningIcon size={12} weight="fill" />{" "}
                            {w.contact_count}/3
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </TabsContent>

        <TabsContent value="invites" className="space-y-4">
          <div className="flex items-end justify-between">
            <div>
              <div className="kbd-label">Single-Use Signup Links</div>
              <h2 className="font-display font-bold text-2xl tracking-tight mt-1">
                Invitations
              </h2>
              <p className="text-sm text-muted-foreground mt-1">
                Send a pre-configured signup link. Expires in 14 days.
              </p>
            </div>
            <div className="flex gap-2">
              <Dialog open={bulkOpen} onOpenChange={setBulkOpen}>
                <DialogTrigger asChild>
                  <Button
                    variant="outline"
                    className="rounded-none border-border"
                    data-testid="bulk-invite-button"
                  >
                    Bulk import
                  </Button>
                </DialogTrigger>
                <DialogContent
                  className="rounded-none max-w-2xl"
                  data-testid="bulk-invite-dialog"
                >
                  <DialogHeader>
                    <DialogTitle className="font-display tracking-tight">
                      Bulk invite (CSV)
                    </DialogTitle>
                  </DialogHeader>
                  <div className="space-y-3">
                    <p className="text-xs text-muted-foreground">
                      Paste a CSV with header row:{" "}
                      <code>email,claimant_label,note</code>
                    </p>
                    <textarea
                      value={bulkCsv}
                      onChange={(e) => setBulkCsv(e.target.value)}
                      rows={10}
                      className="w-full font-mono text-xs border border-border p-3 rounded-none"
                      data-testid="bulk-csv-input"
                    />
                    {bulkResult && (
                      <div className="text-xs space-y-2">
                        <div className="border border-[#16A34A] bg-[#16A34A]/10 p-2">
                          <b>Created:</b> {bulkResult.created.length}
                        </div>
                        {bulkResult.skipped.length > 0 && (
                          <div className="border border-[#EAB308] bg-[#EAB308]/10 p-2">
                            <b>Skipped:</b> {bulkResult.skipped.length}
                            <ul className="mt-1 ml-3 list-disc">
                              {bulkResult.skipped.slice(0, 5).map((s, i) => (
                                <li key={i}>
                                  {s.email || JSON.stringify(s.row)} —{" "}
                                  {s.reason}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                  <DialogFooter>
                    <Button
                      variant="outline"
                      className="rounded-none"
                      onClick={() => {
                        setBulkOpen(false);
                        setBulkResult(null);
                      }}
                    >
                      Close
                    </Button>
                    <Button
                      className="rounded-none bg-primary hover:bg-primary/90"
                      onClick={runBulk}
                      disabled={bulkBusy}
                      data-testid="bulk-import-button"
                    >
                      {bulkBusy ? "Importing..." : "Import & email"}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
              <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
                <DialogTrigger asChild>
                  <Button
                    className="rounded-none bg-primary hover:bg-primary/90"
                    data-testid="new-invite-button"
                  >
                    <PlusIcon size={16} weight="bold" className="mr-2" /> New
                    Invite
                  </Button>
                </DialogTrigger>
                <DialogContent
                  className="rounded-none"
                  data-testid="invite-dialog"
                >
                  <DialogHeader>
                    <DialogTitle className="font-display tracking-tight">
                      Send an invite
                    </DialogTitle>
                  </DialogHeader>
                  <div className="space-y-3">
                    <div>
                      <Label className="kbd-label">Claimant Email</Label>
                      <Input
                        type="email"
                        required
                        value={inviteForm.email}
                        onChange={(e) =>
                          setInviteForm({
                            ...inviteForm,
                            email: e.target.value,
                          })
                        }
                        className="rounded-none mt-2"
                        data-testid="invite-email-input"
                      />
                    </div>
                    <div>
                      <Label className="kbd-label">
                        Claimant Label (e.g. "Self", "Spouse")
                      </Label>
                      <Input
                        value={inviteForm.claimant_label}
                        onChange={(e) =>
                          setInviteForm({
                            ...inviteForm,
                            claimant_label: e.target.value,
                          })
                        }
                        className="rounded-none mt-2"
                        data-testid="invite-label-input"
                      />
                    </div>
                    <div>
                      <Label className="kbd-label">Note (optional)</Label>
                      <Input
                        value={inviteForm.note}
                        onChange={(e) =>
                          setInviteForm({ ...inviteForm, note: e.target.value })
                        }
                        placeholder="Welcome message"
                        className="rounded-none mt-2"
                        data-testid="invite-note-input"
                      />
                    </div>
                  </div>
                  <DialogFooter>
                    <Button
                      variant="outline"
                      className="rounded-none"
                      onClick={() => setInviteOpen(false)}
                    >
                      Cancel
                    </Button>
                    <Button
                      className="rounded-none bg-primary hover:bg-primary/90"
                      onClick={createInvite}
                      disabled={busy}
                      data-testid="invite-create-button"
                    >
                      {busy ? "Sending..." : "Create & email invite"}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>
          </div>

          <div className="border border-border bg-background overflow-x-auto">
            <table className="w-full compliance-table text-sm">
              <thead className="bg-secondary border-b">
                <tr className="text-left">
                  <th className="kbd-label">Email</th>
                  <th className="kbd-label">Label</th>
                  <th className="kbd-label">Status</th>
                  <th className="kbd-label">Expires</th>
                  <th className="kbd-label text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {invites.length === 0 && (
                  <tr>
                    <td colSpan={5} className="text-center text-muted-foreground py-12">
                      No invitations yet.
                    </td>
                  </tr>
                )}
                {invites.map((inv) => (
                  <tr
                    key={inv.code}
                    className="border-b border-border"
                    data-testid={`invite-row-${inv.code}`}
                  >
                    <td className="font-mono-data text-xs">{inv.email}</td>
                    <td className="text-xs">{inv.claimant_label}</td>
                    <td>
                      {inv.used ? (
                        <span className="text-xs font-bold text-[#16A34A]">
                          REDEEMED
                        </span>
                      ) : (
                        <span className="text-xs font-bold text-primary">
                          PENDING
                        </span>
                      )}
                    </td>
                    <td className="font-mono-data text-xs text-muted-foreground">
                      {new Date(inv.expires_at).toLocaleDateString()}
                    </td>
                    <td className="text-right">
                      <div className="inline-flex gap-1">
                        <button
                          type="button"
                          onClick={() => copyLink(inv.invite_link)}
                          className="text-xs font-semibold uppercase border border-border px-2 py-1 hover:border-primary hover:text-primary inline-flex items-center gap-1"
                          data-testid={`invite-copy-${inv.code}`}
                        >
                          <CopySimpleIcon size={12} weight="bold" /> Copy
                        </button>
                        <a
                          href={inv.invite_link}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs font-semibold uppercase border border-border px-2 py-1 hover:border-primary hover:text-primary inline-flex items-center gap-1"
                        >
                          <ArrowSquareOutIcon size={12} weight="bold" /> Open
                        </a>
                        {!inv.used && (
                          <button
                            type="button"
                            onClick={() => revokeInvite(inv.code)}
                            className="text-xs font-semibold uppercase border border-border px-2 py-1 hover:border-[#DC2626] hover:text-[#DC2626] inline-flex items-center gap-1"
                            data-testid={`invite-revoke-${inv.code}`}
                          >
                            <TrashIcon size={12} weight="bold" /> Revoke
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </TabsContent>

        <TabsContent value="integrations" className="space-y-4">
          {!status && <div className="kbd-label">Loading…</div>}
          {status && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="border border-border bg-background p-6">
                <div className="flex items-center gap-3 mb-3">
                  <EnvelopeSimpleIcon
                    size={26}
                    weight="bold"
                    className="text-primary"
                  />
                  <div>
                    <div className="kbd-label">Email Provider</div>
                    <h3 className="font-display font-bold text-xl tracking-tight">
                      Mailgun
                    </h3>
                  </div>
                  <div className="ml-auto">
                    {status.mailgun.configured ? (
                      <span className="inline-flex items-center gap-1 text-xs font-bold text-[#16A34A]">
                        <CheckCircleIcon size={12} weight="fill" /> CONFIGURED
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs font-bold text-[#DC2626]">
                        <WarningIcon size={12} weight="fill" /> MISSING KEY
                      </span>
                    )}
                  </div>
                </div>
                <div className="text-sm space-y-2">
                  <div>
                    <span className="kbd-label">Active sender:</span>{" "}
                    <code className="font-mono text-xs">
                      {status.mailgun.from}
                    </code>
                  </div>
                  <div>
                    <span className="kbd-label">Sending domain:</span>{" "}
                    <code className="font-mono text-xs">
                      {status.mailgun.domain || "—"}
                    </code>
                  </div>
                </div>
                <div className="mt-4 border border-border bg-secondary p-3 text-xs">
                  <div className="kbd-label mb-2">
                    DNS records to add at your registrar
                  </div>
                  <p className="text-foreground">
                    Add these records at name.com for your Mailgun sending
                    domain:
                  </p>
                  <ul className="mt-2 space-y-1 font-mono">
                    <li>
                      <b>TXT</b> · name <code>mail.illinoisjobtracker.app</code>{" "}
                      · value <code>v=spf1 include:mailgun.org ~all</code>
                    </li>
                    <li>
                      <b>TXT</b> · name{" "}
                      <code>mailo._domainkey.mail.illinoisjobtracker.app</code>{" "}
                      · value from Mailgun dashboard
                    </li>
                    <li>
                      <b>CNAME</b> · name{" "}
                      <code>email.mail.illinoisjobtracker.app</code> · value{" "}
                      <code>mailgun.org</code>
                    </li>
                    <li>
                      <b>MX</b> · name <code>mail.illinoisjobtracker.app</code>{" "}
                      · value <code>mxa.mailgun.org</code> priority 10
                    </li>
                  </ul>
                  <a
                    href={status.mailgun.dns_records_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-primary font-semibold underline mt-3"
                  >
                    Open Mailgun dashboard{" "}
                    <ArrowSquareOutIcon size={12} weight="bold" />
                  </a>
                </div>
              </div>

              <div className="border border-border bg-background p-6">
                <div className="flex items-center gap-3 mb-3">
                  <DeviceMobileIcon
                    size={26}
                    weight="bold"
                    className="text-primary"
                  />
                  <div>
                    <div className="kbd-label">SMS Provider</div>
                    <h3 className="font-display font-bold text-xl tracking-tight">
                      ClickSend
                    </h3>
                  </div>
                  <div className="ml-auto">
                    {status.clicksend.configured ? (
                      <span className="inline-flex items-center gap-1 text-xs font-bold text-[#16A34A]">
                        <CheckCircleIcon size={12} weight="fill" /> CONFIGURED
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs font-bold text-[#DC2626]">
                        <WarningIcon size={12} weight="fill" /> MISSING CREDS
                      </span>
                    )}
                  </div>
                </div>
                <div className="text-sm space-y-2">
                  <div>
                    <span className="kbd-label">From number:</span>{" "}
                    <code className="font-mono text-xs">
                      {status.clicksend.from_number || "—"}
                    </code>
                  </div>
                  <div className="border border-border bg-secondary p-3 text-xs mt-2">
                    <div className="kbd-label mb-2">How it works</div>
                    <p className="text-foreground">
                      Claimants opt in to SMS from their Claimant profile by
                      enabling the toggle and adding an E.164 phone (e.g.{" "}
                      <code className="font-mono">+13125550100</code>). SMS
                      reminders fire alongside email reminders on the same
                      schedule.
                    </p>
                    <p className="text-foreground mt-2">
                      Sent via ClickSend's REST API — check the ClickSend
                      dashboard for account balance and sender configuration.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
