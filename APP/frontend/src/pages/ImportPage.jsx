import { useEffect, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  UploadSimpleIcon,
  FileCsvIcon,
  ImageIcon,
  CheckCircleIcon,
} from "@phosphor-icons/react";
import { toast } from "sonner";

export default function ImportPage() {
  const [weeks, setWeeks] = useState([]);
  const [weekId, setWeekId] = useState("");
  const [csvFile, setCsvFile] = useState(null);
  const [imgFile, setImgFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState([]);

  useEffect(() => {
    api.get("/benefit-weeks").then((r) => {
      setWeeks(r.data);
      if (r.data.length && !weekId) setWeekId(r.data[0].id);
    });
    // eslint-disable-next-line
  }, []);

  const importCsv = async () => {
    if (!csvFile || !weekId)
      return toast.error("Select a benefit week and CSV file");
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", csvFile);
      fd.append("week_id", weekId);
      const { data } = await api.post("/import/csv", fd);
      toast.success(`Imported ${data.inserted} contacts`);
      setResults([
        { type: "CSV", count: data.inserted, contacts: data.contacts },
        ...results,
      ]);
      setCsvFile(null);
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };

  const importScreenshot = async () => {
    if (!imgFile || !weekId)
      return toast.error("Select a benefit week and image");
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", imgFile);
      fd.append("week_id", weekId);
      const { data } = await api.post("/import/screenshot", fd);
      if (data.inserted === 0) {
        toast.warning("No jobs extracted — try a clearer screenshot");
      } else {
        toast.success(`AI extracted ${data.inserted} job(s)`);
      }
      setResults([
        { type: "SCREENSHOT", count: data.inserted, contacts: data.contacts },
        ...results,
      ]);
      setImgFile(null);
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6" data-testid="import-page">
      <div>
        <div className="kbd-label">Bulk Entry</div>
        <h1 className="font-display font-black text-4xl tracking-tighter mt-1">
          Import Work Searches
        </h1>
        <p className="text-sm text-zinc-600 mt-2 max-w-2xl">
          Import contacts in bulk from a CSV file or extract them from a
          screenshot of Indeed, LinkedIn or other job boards using AI vision
          (Gemini).
        </p>
      </div>

      <div className="border border-zinc-200 bg-white p-6">
        <Label className="kbd-label">Target Benefit Week</Label>
        <Select value={weekId} onValueChange={setWeekId}>
          <SelectTrigger
            className="rounded-none mt-2 max-w-md"
            data-testid="import-week-select"
          >
            <SelectValue placeholder="Choose a benefit week" />
          </SelectTrigger>
          <SelectContent>
            {weeks.map((w) => (
              <SelectItem key={w.id} value={w.id}>
                {w.week_start} → {w.week_end} ({w.contact_count} contacts)
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {weeks.length === 0 && (
          <p className="text-xs text-[#DC2626] mt-2">
            Create a benefit week first.
          </p>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="border-2 border-dashed border-zinc-300 p-8 bg-white">
          <div className="flex items-center gap-3 mb-4">
            <FileCsvIcon size={28} weight="bold" className="text-[#0033A0]" />
            <div>
              <div className="kbd-label">Method 1</div>
              <h3 className="font-display font-bold text-xl tracking-tight">
                CSV Upload
              </h3>
            </div>
          </div>
          <p className="text-xs text-zinc-600 mb-4 leading-relaxed">
            Headers supported:{" "}
            <code className="font-mono">
              date, employer, address, method, position, type, contact, result,
              url
            </code>
          </p>
          <input
            type="file"
            accept=".csv"
            aria-label="Choose CSV file to import"
            onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
            className="block w-full text-sm file:mr-4 file:py-2 file:px-4 file:border file:border-zinc-300 file:bg-[#F4F4F5] file:text-zinc-900 file:font-semibold file:rounded-none hover:file:bg-zinc-200"
            data-testid="csv-file-input"
          />
          <Button
            disabled={busy || !csvFile || !weekId}
            onClick={importCsv}
            className="mt-4 w-full rounded-none bg-[#0033A0] hover:bg-[#002266]"
            data-testid="csv-import-button"
          >
            <UploadSimpleIcon size={16} weight="bold" className="mr-2" />{" "}
            {busy ? "Importing..." : "Import CSV"}
          </Button>
        </div>

        <div className="border-2 border-dashed border-zinc-300 p-8 bg-white">
          <div className="flex items-center gap-3 mb-4">
            <ImageIcon size={28} weight="bold" className="text-[#0033A0]" />
            <div>
              <div className="kbd-label">Method 2 · AI-Powered</div>
              <h3 className="font-display font-bold text-xl tracking-tight">
                Screenshot Extraction
              </h3>
            </div>
          </div>
          <p className="text-xs text-zinc-600 mb-4 leading-relaxed">
            Drop a screenshot from Indeed, LinkedIn, ZipRecruiter or any job
            board. Gemini extracts employer, position and date.
          </p>
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            aria-label="Choose screenshot image to import"
            onChange={(e) => setImgFile(e.target.files?.[0] || null)}
            className="block w-full text-sm file:mr-4 file:py-2 file:px-4 file:border file:border-zinc-300 file:bg-[#F4F4F5] file:text-zinc-900 file:font-semibold file:rounded-none hover:file:bg-zinc-200"
            data-testid="screenshot-file-input"
          />
          <Button
            disabled={busy || !imgFile || !weekId}
            onClick={importScreenshot}
            className="mt-4 w-full rounded-none bg-[#0033A0] hover:bg-[#002266]"
            data-testid="screenshot-import-button"
          >
            <UploadSimpleIcon size={16} weight="bold" className="mr-2" />{" "}
            {busy ? "Extracting..." : "Extract with AI"}
          </Button>
        </div>
      </div>

      {results.length > 0 && (
        <div className="border border-zinc-200 bg-white">
          <div className="px-6 py-4 border-b border-zinc-200">
            <div className="kbd-label">Recent Imports</div>
            <h3 className="font-display font-bold text-lg tracking-tight">
              Result Log
            </h3>
          </div>
          <div className="divide-y divide-zinc-100">
            {results.map((r, i) => (
              <div
                key={i}
                className="px-6 py-3 flex items-center gap-3 text-sm"
                data-testid={`import-result-${i}`}
              >
                <CheckCircleIcon
                  size={18}
                  weight="fill"
                  className="text-[#16A34A]"
                />
                <span className="font-semibold">{r.type}</span>
                <span className="text-zinc-600">
                  added {r.count} contact{r.count === 1 ? "" : "s"}
                </span>
                {r.contacts?.slice(0, 3).map((c, j) => (
                  <span key={j} className="kbd-label">
                    {c.employer_name}
                  </span>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
