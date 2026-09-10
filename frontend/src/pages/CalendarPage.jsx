import { useEffect, useMemo, useState } from "react";
import {
  listInterventions, listContracts, listClients, getSubscribeUrl,
  listManualEvents, createManualEvent, deleteManualEvent, reschedulePlan,
  confirmIntervention, unconfirmIntervention, updateIntervention,
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
import {
  Download, ChevronLeft, ChevronRight, ExternalLink, Plus, Trash2, RefreshCw,
  CheckCircle2, Mail, MapPin, Phone, User, Clock, Star,
} from "lucide-react";
import { toast } from "sonner";

const MONTHS = ["Gennaio","Febbraio","Marzo","Aprile","Maggio","Giugno","Luglio","Agosto","Settembre","Ottobre","Novembre","Dicembre"];
const DAYS = ["Lun","Mar","Mer","Gio","Ven","Sab","Dom"];
const SLOT_LABEL = { full: "Giornata intera (09:00 - 18:00)", morning: "Mattina (09:00 - 13:30)", afternoon: "Pomeriggio (14:30 - 18:00)" };
const SLOT_SHORT = { full: "GG", morning: "AM", afternoon: "PM" };

export default function CalendarPage() {
  const [ivs, setIvs] = useState([]);
  const [contracts, setContracts] = useState([]);
  const [clients, setClients] = useState([]);
  const [manual, setManual] = useState([]);
  const [subUrl, setSubUrl] = useState("");
  const [monthDate, setMonthDate] = useState(() => { const d = new Date(); d.setDate(1); return d; });
  const [addOpen, setAddOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailItem, setDetailItem] = useState(null);
  const [rescheduling, setRescheduling] = useState(false);
  const [form, setForm] = useState({ date: "", title: "", client_id: "none", notes: "", slot: "full" });

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

  const openAdd = (iso) => { setForm({ date: iso || "", title: "", client_id: "none", notes: "", slot: "full" }); setAddOpen(true); };
  const openDetail = (item) => { setDetailItem(item); setDetailOpen(true); };

  const submit = async () => {
    if (!form.date || !form.title) { toast.error("Data e titolo obbligatori"); return; }
    try {
      await createManualEvent({
        date: form.date, title: form.title, notes: form.notes,
        client_id: form.client_id === "none" ? null : form.client_id,
        slot: form.slot, all_day: form.slot === "full",
      });
      toast.success("Appuntamento aggiunto");
      setAddOpen(false); load();
    } catch (_e) { toast.error("Errore"); }
  };

  const removeManual = async (id) => {
    if (!confirm("Rimuovere questo appuntamento?")) return;
    await deleteManualEvent(id); toast.success("Rimosso"); setDetailOpen(false); load();
  };

  const doConfirm = async () => {
    try {
      const r = await confirmIntervention(detailItem.id);
      if (r.warning) toast.warning(r.warning);
      else toast.success("Confermato ed email inviata al cliente");
      const fresh = await listInterventions();
      setIvs(fresh);
      const updated = fresh.find((x) => x.id === detailItem.id);
      if (updated) setDetailItem({ ...updated, _kind: "iv" });
    } catch (e) { toast.error(e?.response?.data?.detail || "Errore"); }
  };

  const doUnconfirm = async () => {
    try {
      await unconfirmIntervention(detailItem.id);
      toast.success("Riportato a pianificato");
      const fresh = await listInterventions();
      setIvs(fresh);
      const updated = fresh.find((x) => x.id === detailItem.id);
      if (updated) setDetailItem({ ...updated, _kind: "iv" });
    } catch (_e) { toast.error("Errore"); }
  };

  const changeSlotInDetail = async (newSlot) => {
    try {
      await updateIntervention(detailItem.id, { slot: newSlot });
      toast.success("Fascia oraria aggiornata");
      setDetailItem({ ...detailItem, slot: newSlot });
      load();
    } catch (_e) { toast.error("Errore"); }
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
              <div
                key={idx}
                data-testid={`day-cell-${cell.iso}`}
                className={`min-h-[72px] sm:min-h-[110px] p-1.5 sm:p-2 rounded-md border text-left overflow-hidden transition-colors ${
                  isToday ? "border-blue-600 bg-blue-50/50" : "border-slate-100 bg-slate-50/40"
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className={`text-xs font-semibold ${isToday ? "text-blue-700" : "text-slate-700"}`}>{cell.d}</div>
                  <button
                    type="button"
                    data-testid={`add-day-${cell.iso}`}
                    onClick={() => openAdd(cell.iso)}
                    className="opacity-40 hover:opacity-100 transition-opacity"
                    title="Aggiungi appuntamento extra"
                  >
                    <Plus className="w-3 h-3 text-slate-600" />
                  </button>
                </div>
                <div className="mt-1 space-y-1">
                  {items.slice(0, 3).map((it) => {
                    if (it._kind === "manual") {
                      return (
                        <button
                          type="button"
                          key={it.id}
                          onClick={() => openDetail(it)}
                          data-testid={`event-${it.id}`}
                          className="w-full text-[10px] leading-tight px-1.5 py-1 bg-amber-100 text-amber-900 rounded truncate flex items-center gap-1 hover:bg-amber-200"
                        >
                          <span className="font-mono mr-1">{SLOT_SHORT[it.slot || "full"]}</span>
                          <span className="font-semibold truncate flex-1 text-left">★ {it.title}</span>
                        </button>
                      );
                    }
                    const clic = cli(it.client_id);
                    const c = ctr(it.contract_id);
                    const isConfirmed = it.status === "confirmed";
                    const cls = isConfirmed ? "bg-emerald-100 text-emerald-800 hover:bg-emerald-200" : "bg-blue-100 text-blue-800 hover:bg-blue-200";
                    return (
                      <button
                        type="button"
                        key={it.id}
                        onClick={() => openDetail(it)}
                        data-testid={`event-${it.id}`}
                        className={`w-full text-[10px] leading-tight px-1.5 py-1 rounded truncate text-left ${cls}`}
                      >
                        <span className="font-mono mr-1">{SLOT_SHORT[it.slot || "full"]}</span>
                        <span className="font-semibold">{clic?.name?.slice(0, 12) || "—"}</span>
                        <span className="hidden sm:inline"> · g{it.day_index}/{c?.total_days}</span>
                        {isConfirmed && <span className="ml-1">✓</span>}
                      </button>
                    );
                  })}
                  {items.length > 3 && (
                    <div className="text-[10px] text-slate-500 px-1.5">+{items.length - 3}</div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      {/* Add manual event dialog */}
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
              <Label>Fascia oraria</Label>
              <Select value={form.slot} onValueChange={(v) => setForm({ ...form, slot: v })}>
                <SelectTrigger data-testid="manual-event-slot" className="bg-white"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-white">
                  <SelectItem value="full">Giornata intera (09:00 - 18:00)</SelectItem>
                  <SelectItem value="morning">Mattina (09:00 - 13:30)</SelectItem>
                  <SelectItem value="afternoon">Pomeriggio (14:30 - 18:00)</SelectItem>
                </SelectContent>
              </Select>
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
              Il planning e la riprogrammazione automatica rispetteranno questa fascia oraria come occupata.
            </div>
          </div>
          <DialogFooter>
            <Button data-testid="manual-event-save" onClick={submit} className="bg-slate-900 hover:bg-slate-800 text-white">
              Aggiungi
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Detail panel */}
      <Dialog open={detailOpen} onOpenChange={setDetailOpen}>
        <DialogContent data-testid="event-detail-dialog" className="bg-white sm:max-w-lg">
          {detailItem && detailItem._kind === "iv" ? (() => {
            const clic = cli(detailItem.client_id);
            const c = ctr(detailItem.contract_id);
            const confirmed = detailItem.status === "confirmed";
            return (
              <>
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2">
                    {confirmed ? (
                      <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded-md font-medium uppercase tracking-wide">
                        <CheckCircle2 className="w-3 h-3" /> Confermato
                      </span>
                    ) : (
                      <span className="text-xs px-2 py-0.5 bg-blue-50 text-blue-700 rounded-md font-medium uppercase tracking-wide">Pianificato</span>
                    )}
                    <span className="text-slate-900">{c?.title || "Intervento"}</span>
                  </DialogTitle>
                </DialogHeader>
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3 pb-3 border-b border-slate-100">
                    <div>
                      <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Data</div>
                      <div className="text-sm font-mono font-semibold text-slate-900">{detailItem.date}</div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Giornata</div>
                      <div className="text-sm font-semibold text-slate-900">{detailItem.day_index}/{c?.total_days || "?"}</div>
                    </div>
                  </div>
                  <div>
                    <Label className="text-xs uppercase tracking-wider text-slate-500 flex items-center gap-1 mb-1">
                      <Clock className="w-3 h-3" /> Fascia oraria
                    </Label>
                    <Select value={detailItem.slot || "full"} onValueChange={changeSlotInDetail} disabled={confirmed}>
                      <SelectTrigger data-testid="detail-slot-select" className="bg-white"><SelectValue /></SelectTrigger>
                      <SelectContent className="bg-white">
                        <SelectItem value="full">{SLOT_LABEL.full}</SelectItem>
                        <SelectItem value="morning">{SLOT_LABEL.morning}</SelectItem>
                        <SelectItem value="afternoon">{SLOT_LABEL.afternoon}</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  {clic && (
                    <div className="p-3 bg-slate-50 rounded-lg border border-slate-100 space-y-1.5">
                      <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Cliente</div>
                      <div className="text-sm font-bold text-slate-900">{clic.name}</div>
                      {clic.address && <div className="text-xs text-slate-600 flex items-center gap-1.5"><MapPin className="w-3 h-3" /> {clic.address}{clic.city ? `, ${clic.city}` : ""}</div>}
                      {clic.contact_name && <div className="text-xs text-slate-600 flex items-center gap-1.5"><User className="w-3 h-3" /> {clic.contact_name}</div>}
                      {clic.phone && <div className="text-xs text-slate-600 flex items-center gap-1.5"><Phone className="w-3 h-3" /> <a href={`tel:${clic.phone}`} className="underline">{clic.phone}</a></div>}
                      {clic.email && <div className="text-xs text-slate-600 flex items-center gap-1.5"><Mail className="w-3 h-3" /> <a href={`mailto:${clic.email}`} className="underline">{clic.email}</a></div>}
                    </div>
                  )}
                  {c?.notes && (
                    <div>
                      <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Note contratto</div>
                      <div className="text-xs text-slate-700 bg-slate-50 p-2 rounded border border-slate-100">{c.notes}</div>
                    </div>
                  )}
                  {confirmed && detailItem.confirmed_at && (
                    <div className="text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded p-2">
                      Email di conferma inviata il {new Date(detailItem.confirmed_at).toLocaleString("it-IT")}
                    </div>
                  )}
                </div>
                <DialogFooter>
                  {confirmed ? (
                    <Button data-testid="detail-unconfirm" variant="outline" onClick={doUnconfirm}>Annulla conferma</Button>
                  ) : (
                    <Button data-testid="detail-confirm" onClick={doConfirm} className="bg-emerald-700 hover:bg-emerald-800 text-white">
                      <Mail className="w-4 h-4 mr-2" /> Conferma + invia email
                    </Button>
                  )}
                </DialogFooter>
              </>
            );
          })() : detailItem && detailItem._kind === "manual" ? (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <Star className="w-4 h-4 text-amber-600" />
                  <span className="text-xs px-2 py-0.5 bg-amber-100 text-amber-800 rounded-md font-medium uppercase tracking-wide">Extra</span>
                  <span className="text-slate-900">{detailItem.title}</span>
                </DialogTitle>
              </DialogHeader>
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3 pb-3 border-b border-slate-100">
                  <div>
                    <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Data</div>
                    <div className="text-sm font-mono font-semibold text-slate-900">{detailItem.date}</div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Fascia oraria</div>
                    <div className="text-sm font-semibold text-slate-900">{SLOT_LABEL[detailItem.slot || "full"]}</div>
                  </div>
                </div>
                {detailItem.client_id && cli(detailItem.client_id) && (
                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
                    <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Cliente</div>
                    <div className="text-sm font-bold text-slate-900">{cli(detailItem.client_id).name}</div>
                  </div>
                )}
                {detailItem.notes && (
                  <div>
                    <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Note</div>
                    <div className="text-xs text-slate-700 bg-slate-50 p-2 rounded border border-slate-100 whitespace-pre-wrap">{detailItem.notes}</div>
                  </div>
                )}
              </div>
              <DialogFooter>
                <Button data-testid="detail-remove-manual" variant="outline" onClick={() => removeManual(detailItem.id)} className="text-red-700 border-red-200 hover:bg-red-50">
                  <Trash2 className="w-4 h-4 mr-2" /> Rimuovi
                </Button>
              </DialogFooter>
            </>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}
