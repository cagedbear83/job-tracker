import { useEffect, useState, useCallback } from "react";
import { api, formatApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { MagnifyingGlassIcon } from "@phosphor-icons/react";

const ACTION_COLORS = {
  LOGIN: "text-foreground",
  LOGOUT: "text-foreground",
  REGISTER: "text-primary",
  REGISTER_INVITE: "text-primary",
  CREATE: "text-[#16A34A]",
  UPDATE: "text-[#EAB308]",
  DELETE: "text-[#DC2626]",
  SWITCH: "text-foreground",
  IMPORT_CSV: "text-primary",
  IMPORT_OCR: "text-primary",
  EXPORT_CSV: "text-primary",
  EXPORT_PDF: "text-primary",
  FORGOT_PW: "text-foreground",
  RESET_PW: "text-[#EAB308]",
  INVITE_CREATE: "text-primary",
  INVITE_REVOKE: "text-[#DC2626]",
  REMINDER_SUNDAY: "text-muted-foreground",
  REMINDER_WEDNESDAY: "text-muted-foreground",
  REMINDER_FRIDAY: "text-muted-foreground",
  REMINDER_SATURDAY: "text-muted-foreground",
  SMS_SUNDAY: "text-muted-foreground",
  SMS_WEDNESDAY: "text-muted-foreground",
  SMS_FRIDAY: "text-muted-foreground",
  SMS_SATURDAY: "text-muted-foreground",
};

const ENTITY_OPTIONS = [
  "ALL",
  "user",
  "claimant",
  "benefit_week",
  "contact",
  "invite",
];

export default function AuditLog() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [action, setAction] = useState("ALL");
  const [entity, setEntity] = useState("ALL");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (query) params.set("q", query);
      if (action !== "ALL") params.set("action", action);
      if (entity !== "ALL") params.set("entity", entity);
      const { data } = await api.get(`/audit-log?${params.toString()}`);
      setItems(data);
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setLoading(false);
    }
  }, [query, action, entity]);
  useEffect(() => {
    load();
  }, [load]);

  const onSearch = (e) => {
    e.preventDefault();
    load();
  };

  // gather unique actions from current results for filter pills
  const actionOptions = [
    "ALL",
    ...Array.from(new Set(items.map((i) => i.action))),
  ];

  return (
    <div className="space-y-6" data-testid="audit-page">
      <div>
        <div className="kbd-label">Activity Trail</div>
        <h1 className="font-display font-black text-4xl tracking-tighter mt-1">
          Audit Log
        </h1>
        <p className="text-sm text-muted-foreground mt-2">
          Every action you take is recorded for compliance. Edits include
          field-level old → new diffs.
        </p>
      </div>

      <div className="border border-border bg-background p-4 grid grid-cols-1 md:grid-cols-12 gap-3">
        <form onSubmit={onSearch} className="md:col-span-6">
          <Label className="kbd-label">Search detail</Label>
          <div className="flex gap-2 mt-2">
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. employer name, week date, claimant label"
              className="rounded-none"
              data-testid="audit-search-input"
            />
            <button
              type="submit"
              aria-label="Search audit log"
              className="px-4 border border-primary bg-primary text-white"
              data-testid="audit-search-button"
            >
              <MagnifyingGlassIcon size={16} weight="bold" />
            </button>
          </div>
        </form>
        <div className="md:col-span-3">
          <Label className="kbd-label">Action</Label>
          <Select value={action} onValueChange={setAction}>
            <SelectTrigger
              className="rounded-none mt-2"
              data-testid="audit-action-filter"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {actionOptions.map((a) => (
                <SelectItem key={a} value={a}>
                  {a}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="md:col-span-3">
          <Label className="kbd-label">Entity</Label>
          <Select value={entity} onValueChange={setEntity}>
            <SelectTrigger
              className="rounded-none mt-2"
              data-testid="audit-entity-filter"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ENTITY_OPTIONS.map((a) => (
                <SelectItem key={a} value={a}>
                  {a}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="border border-border bg-background overflow-x-auto">
        <table className="w-full compliance-table text-sm">
          <thead className="bg-secondary border-b border-border">
            <tr className="text-left">
              <th className="kbd-label">Timestamp</th>
              <th className="kbd-label">Action</th>
              <th className="kbd-label">Entity</th>
              <th className="kbd-label">Detail</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={4} className="text-center text-muted-foreground py-12">
                  Loading…
                </td>
              </tr>
            )}
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={4} className="text-center text-muted-foreground py-12">
                  No audit entries match your filters.
                </td>
              </tr>
            )}
            {items.map((it) => (
              <tr
                key={it.id}
                className="border-b border-border"
                data-testid={`audit-row-${it.id}`}
              >
                <td className="font-mono-data text-xs text-muted-foreground whitespace-nowrap">
                  {new Date(it.timestamp).toLocaleString()}
                </td>
                <td
                  className={`text-xs font-bold tracking-wider ${ACTION_COLORS[it.action] || "text-foreground"}`}
                >
                  {it.action}
                </td>
                <td className="text-xs text-muted-foreground">{it.entity}</td>
                <td className="text-xs text-foreground max-w-[600px]">
                  {it.detail}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="text-xs text-muted-foreground" data-testid="audit-count">
        Showing {items.length} entries
      </div>
    </div>
  );
}