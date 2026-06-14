import { useEffect, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { FloppyDiskIcon } from "@phosphor-icons/react";

const FIELDS = [
  ["first_name", "First Name", "sm:col-span-6"],
  ["middle_initial", "MI", "sm:col-span-2"],
  ["last_name", "Last Name", "sm:col-span-4"],
  ["claimant_id", "Claimant ID", "sm:col-span-4"],
  ["phone", "Phone", "sm:col-span-4"],
  ["occupation", "Occupation", "sm:col-span-4"],
  ["address", "Address", "sm:col-span-8"],
  ["city", "City", "sm:col-span-4"],
  ["state", "State", "sm:col-span-2"],
  ["zip_code", "ZIP", "sm:col-span-2"],
];

export default function Profile() {
  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    middle_initial: "",
    claimant_id: "",
    address: "",
    city: "",
    state: "IL",
    zip_code: "",
    phone: "",
    occupation: "",
  });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .get("/profile")
      .then((r) => {
        if (r.data) setForm({ ...form, ...r.data });
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.put("/profile", form);
      toast.success("Profile saved");
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <div className="kbd-label">Loading...</div>;

  return (
    <div className="space-y-6" data-testid="profile-page">
      <div>
        <div className="kbd-label">Identity</div>
        <h1 className="font-display font-black text-4xl tracking-tighter mt-1">
          Claimant Profile
        </h1>
        <p className="text-sm text-zinc-600 mt-2 max-w-2xl">
          Your profile populates IDES work-search reports.
        </p>
      </div>

      <form
        onSubmit={save}
        className="border border-zinc-200 bg-white p-6 sm:p-8"
      >
        <div className="grid grid-cols-12 gap-4">
          {FIELDS.map(([key, label, span]) => (
            <div key={key} className={`col-span-12 ${span}`}>
              <Label className="kbd-label">{label}</Label>
              <Input
                value={form[key] || ""}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                className="rounded-none border-zinc-300 mt-2"
                data-testid={`profile-${key}-input`}
              />
            </div>
          ))}
        </div>
        <div className="mt-6 flex gap-2">
          <Button
            type="submit"
            disabled={busy}
            className="rounded-none bg-[#0033A0] hover:bg-[#002266]"
            data-testid="profile-save-button"
          >
            <FloppyDiskIcon size={16} weight="bold" className="mr-2" />{" "}
            {busy ? "Saving..." : "Save Profile"}
          </Button>
        </div>
      </form>
    </div>
  );
}
