import { useEffect, useMemo, useState } from "react";
import {
  listInterventions, listContracts, listClients, getSubscribeUrl,
  listManualEvents, createManualEvent, deleteManualEvent, reschedulePlan,
} from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from "../components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "../components/ui/dialog";
import { Download, ChevronLeft, ChevronRight, ExternalLink, Plus, Trash2, RefreshCw } from "lucide-react";
import { toast } from "sonner";

const MONTHS = ["Gennaio","Febbraio","Marzo","Aprile","Maggio","Giugno","Luglio","Agosto","Settembre","Ottobre","Novembre","Dicembre"];
const DAYS = ["Lun","Mar","Mer","Gio","Ven","Sab","Dom"];

export default function CalendarPage() {
  const [ivs, setIvs] = useState([]);
  const [contracts, setContracts] = useState([]);
  const [clients, setClients] = useState([]);
  const [manual, setManual] = useState([]);
  const [subUrl, setSubUrl] = useState("");
  const [monthDate, setMonthDate] = useState(() => { const d = new Date(); d.setDate(1); return d; });
  const [addOpen, setAddOpen] = useState(false);
  const [rescheduling, setRescheduling] = useState(false);
  const [form, setForm] = useState({ date: "", title: "", client_id: "none", notes: "" });

  const load = () => Promise.all([listInterventions(), listContracts(), listClients(), listManualEvents(), getSubscribeUrl()])
    .then(([i, c, cl, m, s]) => { setIvs(i); setContracts(c); setClients(cl); setManual(m); setSubUrl(s.url); })
    .catch(() => {});
  useEffect(() => { load(); }, []);

  const byDate = useMemo(() => {
    const m = {};
    for (const iv of ivs) { (m[iv.date] = m[iv.date] || []).push({ ...iv, _kind: "iv" }); }
    for (const ev of manual) { (m[ev.date] = m[ev.date] || []).push({ ...ev, _kind: "manual" }); }
    return m;
  }, [ivs, manual]);

  const cli = (id) => clients.find((c) => c.id === id);
  const ctr = (id) => contracts.find((c) => c.id === id);

  const grid = useMemo(() => {
    const y = monthDate.getFullYear(), m = monthDate.getMonth();
    const first = new Date(y, m, 1);
    const shift = (first.getDay() + 6) % 7;
    const days = new Date(y, m + 1, 0).getDate();
    const cells = [];
    for (let i = 0; i < shift; i++) cells.push(null);
    for (let d = 1; d <= days; d++) {
      const iso = `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
      cells.push({ d, iso });
    }
    while (cells.length % 7 !== 0) cells.push(null);
    return cells;
  }, [monthDate]);

  const changeMonth = (delta) => { const d = new Date(monthDate); d.setMonth(d.getMonth() + delta); setMonthDate(d); };
  const downloadIcs = () => subUrl && window.open(subUrl, "_blank");
  const openInGoogle = () => window.open("https://calendar.google.com/calendar/u/0/r/settings/addbyurl", "_blank");

  const openAdd = (iso) => { setForm({ date: iso || "", title: "", client_id: "none", notes: "" }); setAddOpen(true); };

  const submit = async () => {
    if (!form.date || !form.title) { toast.error("Data e titolo obbligatori"); return; }
    try {
      await createManualEvent({
        date: form.date, title: form.title, notes: form.notes,
        client_id: form.client_id === "none" ? null : form.client_id, all_day: true,
      });
      toast.success("Appuntamento aggiunto");
      setAddOpen(false); load();
    } catch (_e) { toast.error("Errore"); }
  };

  const removeManual = async (id) => {
    if (!confirm("Rimuovere questo appuntamento?")) return;
    await deleteManualEvent(id); toast.success("Rimosso"); load();
  };

  const reschedule = async () => {
    if (!confirm("Riprogrammare tutti gli interventi da capo? Gli appuntamenti extra saranno rispettati.")) return;
    setRescheduling(true);
    try {
      const r = await reschedulePlan({ workdays_only: true, max_days_per_client_block: 3 });
      toast.success(`Riprogrammati ${r.planned} interventi`);
      load();
    } catch (_e) { toast.error("Errore riprogrammazione"); }
    finally { setRescheduling(false); }
  };

  return (
    <div data-testid="calendar-view-section" className="max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-8">
        <div>
          <div className="text-xs font-medium tracking-wider uppercase text-slate-500">Vista mensile</div>
          <h1 className="mt-1 text-3xl sm:text-4xl font-extrabold font-display text-slate-900">Calendario</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button data-testid="add-manual-event-button" variant="outline" onClick={() => openAdd("")}>
            <Plus className="w-4 h-4 mr-2" /> Appuntamento extra
          </Button>
          <Button data-testid="reschedule-all-button" variant="outline" onClick={reschedule} disabled={rescheduling}>
            <RefreshCw className={`w-4 h-4 mr-2 ${rescheduling ? "animate-spin" : ""}`} /> Riprogramma tutto
          </Button>
          <Button data-testid="download-ics-button" variant="outline" onClick={downloadIcs}>
            <Download className="w-4 h-4 mr-2" /> .ics
          </Button>
          <Button data-testid="open-gcal-button" onClick={openInGoogle} className="bg-slate-900 hover:bg-slate-800 text-white">
            <ExternalLink className="w-4 h-4 mr-2" /> Google Cal.
          </Button>
        </div>
      </div>

      <Card className="p-4 sm:p-6 border-slate-200 bg-white">
        <div className="flex items-center justify-between mb-4">
          <Button data-testid="prev-month" variant="ghost" size="sm" onClick={() => changeMonth(-1)}>
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <div className="font-bold font-display text-lg text-slate-900">
            {MONTHS[monthDate.getMonth()]} {monthDate.getFullYear()}
          </div>
          <Button data-testid="next-month" variant="ghost" size="sm" onClick={() => changeMonth(1)}>
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
        <div className="grid grid-cols-7 gap-1 sm:gap-2">
          {DAYS.map((d) => (
            <div key={d} className="text-[10px] sm:text-xs font-semibold uppercase text-slate-500 text-center py-2 tracking-wider">{d}</div>
          ))}
          {grid.map((cell, idx) => {
            if (!cell) return <div key={idx} className="min-h-[72px] sm:min-h-[110px]" />;
            const items = byDate[cell.iso] || [];
            const isToday = cell.iso === new Date().toISOString().slice(0, 10);
            return (
              <button
                key={idx}
                type="button"
                data-testid={`day-cell-${cell.iso}`}
                onClick={() => openAdd(cell.iso)}
                className={`min-h-[72px] sm:min-h-[110px] p-1.5 sm:p-2 rounded-md border text-left overflow-hidden hover:border-slate-400 transition-colors ${
                  isToday ? "border-blue-600 bg-blue-50/50" : "border-slate-100 bg-slate-50/40"
                }`}
              >
                <div className={`text-xs font-semibold ${isToday ? "text-blue-700" : "text-slate-700"}`}>{cell.d}</div>
                <div className="mt-1 space-y-1">
                  {items.slice(0, 3).map((it) => {
                    if (it._kind === "manual") {
                      return (
                        <div key={it.id} className="text-[10px] leading-tight px-1.5 py-1 bg-amber-100 text-amber-900 rounded truncate flex items-center gap-1">
                          <span className="font-semibold truncate flex-1">★ {it.title}</span>
                          <span
                            role="button"
                            tabIndex={0}
                            onClick={(e) => { e.stopPropagation(); removeManual(it.id); }}
                            onKeyDown={(e) => { if (e.key === "Enter") { e.stopPropagation(); removeManual(it.id); } }}
                            className="opacity-60 hover:opacity-100 cursor-pointer"
                            data-testid={`remove-manual-${it.id}`}
                          >
                            <Trash2 className="w-3 h-3" />
                          </span>
                        </div>
                      );
                    }
                    const clic = cli(it.client_id);
                    const c = ctr(it.contract_id);
                    const slot = it.slot || "full";
                    const timeShort = slot === "morning" ? "AM" : slot === "afternoon" ? "PM" : "GG";
                    const isConfirmed = it.status === "confirmed";
                    const cls = isConfirmed
                      ? "bg-emerald-100 text-emerald-800"
                      : "bg-blue-100 text-blue-800";
                    return (
                      <div key={it.id} className={`text-[10px] leading-tight px-1.5 py-1 rounded truncate ${cls}`}>
                        <span className="font-mono mr-1">{timeShort}</span>
                        <span className="font-semibold">{clic?.name?.slice(0, 12) || "—"}</span>
                        <span className="hidden sm:inline"> · g{it.day_index}/{c?.total_days}</span>
                        {isConfirmed && <span className="ml-1">✓</span>}
                      </div>
                    );
                  })}
                  {items.length > 3 && (
                    <div className="text-[10px] text-slate-500 px-1.5">+{items.length - 3}</div>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </Card>

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="bg-white sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Nuovo appuntamento extra</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>Data *</Label>
              <Input data-testid="manual-event-date" type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
            </div>
            <div>
              <Label>Titolo *</Label>
              <Input data-testid="manual-event-title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="es. Riunione con avvocato" />
            </div>
            <div>
              <Label>Cliente (opzionale)</Label>
              <Select value={form.client_id} onValueChange={(v) => setForm({ ...form, client_id: v })}>
                <SelectTrigger data-testid="manual-event-client" className="bg-white"><SelectValue placeholder="Nessuno" /></SelectTrigger>
                <SelectContent className="bg-white">
                  <SelectItem value="none">— Nessuno —</SelectItem>
                  {clients.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Note</Label>
              <Textarea data-testid="manual-event-notes" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            </div>
            <div className="text-xs text-slate-500 bg-amber-50 border border-amber-200 rounded p-2">
              Questa data verrà bloccata: i futuri planning e le riprogrammazioni la eviteranno automaticamente.
            </div>
          </div>
          <DialogFooter>
            <Button data-testid="manual-event-save" onClick={submit} className="bg-slate-900 hover:bg-slate-800 text-white">
              Aggiungi
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
