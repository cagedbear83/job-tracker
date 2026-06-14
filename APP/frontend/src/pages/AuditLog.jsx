import { useEffect, useState } from "react";
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
  LOGIN: "text-zinc-700",
  LOGOUT: "text-zinc-700",
  REGISTER: "text-[#0033A0]",
  REGISTER_INVITE: "text-[#0033A0]",
  CREATE: "text-[#16A34A]",
  UPDATE: "text-[#EAB308]",
  DELETE: "text-[#DC2626]",
  SWITCH: "text-zinc-700",
  IMPORT_CSV: "text-[#0033A0]",
  IMPORT_OCR: "text-[#0033A0]",
  EXPORT_CSV: "text-[#0033A0]",
  EXPORT_PDF: "text-[#0033A0]",
  FORGOT_PW: "text-zinc-700",
  RESET_PW: "text-[#EAB308]",
  INVITE_CREATE: "text-[#0033A0]",
  INVITE_REVOKE: "text-[#DC2626]",
  REMINDER_SUNDAY: "text-zinc-600",
  REMINDER_WEDNESDAY: "text-zinc-600",
  REMINDER_FRIDAY: "text-zinc-600",
  REMINDER_SATURDAY: "text-zinc-600",
  SMS_SUNDAY: "text-zinc-600",
  SMS_WEDNESDAY: "text-zinc-600",
  SMS_FRIDAY: "text-zinc-600",
  SMS_SATURDAY: "text-zinc-600",
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

  const load = async () => {
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
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    load(); /* eslint-disable-next-line */
  }, [action, entity]);

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
        <p className="text-sm text-zinc-600 mt-2">
          Every action you take is recorded for compliance. Edits include
          field-level old → new diffs.
        </p>
      </div>

      <div className="border border-zinc-200 bg-white p-4 grid grid-cols-1 md:grid-cols-12 gap-3">
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
              className="px-4 border border-[#0033A0] bg-[#0033A0] text-white"
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

      <div className="border border-zinc-200 bg-white overflow-x-auto">
        <table className="w-full compliance-table text-sm">
          <thead className="bg-[#F4F4F5] border-b border-zinc-200">
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
                <td colSpan={4} className="text-center text-zinc-500 py-12">
                  Loading…
                </td>
              </tr>
            )}
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={4} className="text-center text-zinc-500 py-12">
                  No audit entries match your filters.
                </td>
              </tr>
            )}
            {items.map((it) => (
              <tr
                key={it.id}
                className="border-b border-zinc-100"
                data-testid={`audit-row-${it.id}`}
              >
                <td className="font-mono-data text-xs text-zinc-600 whitespace-nowrap">
                  {new Date(it.timestamp).toLocaleString()}
                </td>
                <td
                  className={`text-xs font-bold tracking-wider ${ACTION_COLORS[it.action] || "text-zinc-700"}`}
                >
                  {it.action}
                </td>
                <td className="text-xs text-zinc-600">{it.entity}</td>
                <td className="text-xs text-zinc-800 max-w-[600px]">
                  {it.detail}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="text-xs text-zinc-500" data-testid="audit-count">
        Showing {items.length} entries
      </div>
    </div>
  );
}
