import { useEffect, useRef, useState } from "react";
import {
  listContracts, listClients, createContract, updateContract, deleteContract, completeContract, clearContractPlan,
  createClient, aiAnalyzeContractPdf,
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
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger,
} from "../components/ui/dialog";
import { Plus, FileText, Trash2, Edit3, CheckCircle2, RotateCcw, Upload, Loader2, FileCode, FileDown } from "lucide-react";
import { toast } from "sonner";
import { exportFatturaPaUrl, contractsTemplateCsvUrl, importContractsCsv } from "../lib/api";

const empty = {
  client_id: "", title: "", total_days: 1, daily_rate: 0, intervention_type: "consulenza",
  priority: "medium", start_date: "", deadline: "", signed_date: "", notes: "",
};

const priorityBadge = {
  high: "bg-red-50 text-red-700 border-red-200",
  medium: "bg-amber-50 text-amber-700 border-amber-200",
  low: "bg-blue-50 text-blue-700 border-blue-200",
};

const statusBadge = {
  active: "bg-slate-100 text-slate-700",
  planned: "bg-blue-50 text-blue-700",
  completed: "bg-emerald-50 text-emerald-700",
  invoiced: "bg-purple-50 text-purple-700",
};

export default function Contracts() {
  const [items, setItems] = useState([]);
  const [clients, setClients] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [editId, setEditId] = useState(null);
  const [importing, setImporting] = useState(false);
  const fileRef = useRef(null);
  const csvRef = useRef(null);

  const load = () => Promise.all([listContracts(), listClients()])
    .then(([cs, cls]) => { setItems(cs); setClients(cls); }).catch(() => {});
  useEffect(() => { load(); }, []);

  const handleImportCsv = async (file) => {
    if (!file) return;
    setImporting(true);
    try {
      const r = await importContractsCsv(file);
      toast.success(`${r.imported} preventivi importati${r.errors?.length ? ` · ${r.errors.length} errori` : ""}`);
      if (r.errors?.length) {
        r.errors.slice(0, 3).forEach((msg) => toast.error(msg));
      }
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Import CSV fallito"); }
    finally { setImporting(false); if (csvRef.current) csvRef.current.value = ""; }
  };

  const handleImportPdf = async (file) => {
    if (!file) return;
    if (file.size > 15 * 1024 * 1024) { toast.error("PDF troppo grande (max 15MB)"); return; }
    setImporting(true);
    try {
      const r = await aiAnalyzeContractPdf(file);
      const d = r.extracted || {};
      // Find or create client from extracted data
      let clientId = "";
      if (d.client_name) {
        const cls = await listClients();
        setClients(cls);
        let match = cls.find((c) => c.name.toLowerCase() === d.client_name.toLowerCase());
        if (!match) {
          match = await createClient({
            name: d.client_name,
            address: d.address || d.city || "N/D",
            city: d.city || "",
            contact_name: d.contact_name || "",
            phone: d.phone || "",
            email: d.email || "",
            notes: "",
          });
          toast.success(`Cliente "${match.name}" creato automaticamente`);
          const fresh = await listClients();
          setClients(fresh);
        }
        clientId = match.id;
      }
      setEditId(null);
      setForm({
        client_id: clientId,
        title: d.title || "",
        total_days: Number(d.total_days) || 1,
        daily_rate: Number(d.daily_rate) || 0,
        intervention_type: d.intervention_type || "consulenza",
        priority: ["high", "medium", "low"].includes(d.priority) ? d.priority : "medium",
        start_date: d.start_date || "",
        deadline: d.deadline || "",
        signed_date: d.signed_date || "",
        notes: d.notes || "",
      });
      setOpen(true);
      toast.success(`PDF letto (${r.pages || "?"} pagine) - controlla i dati e salva`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Estrazione PDF fallita");
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const clientName = (id) => clients.find((c) => c.id === id)?.name || "—";
  const clientCity = (id) => clients.find((c) => c.id === id)?.city || "";

  const submit = async () => {
    if (!form.client_id || !form.title || !form.total_days) { toast.error("Cliente, titolo e giorni obbligatori"); return; }
    const payload = {
      ...form,
      total_days: Number(form.total_days),
      daily_rate: Number(form.daily_rate) || 0,
      start_date: form.start_date || null,
      deadline: form.deadline || null,
      signed_date: form.signed_date || null,
    };
    try {
      if (editId) { await updateContract(editId, payload); toast.success("Contratto aggiornato"); }
      else { await createContract(payload); toast.success("Contratto creato"); }
      setOpen(false); setForm(empty); setEditId(null); load();
    } catch (_e) { toast.error("Errore salvataggio"); }
  };

  const edit = (c) => {
    setEditId(c.id);
    setForm({
      client_id: c.client_id, title: c.title, total_days: c.total_days, daily_rate: c.daily_rate,
      intervention_type: c.intervention_type, priority: c.priority,
      start_date: c.start_date || "", deadline: c.deadline || "", signed_date: c.signed_date || "",
      notes: c.notes || "",
    });
    setOpen(true);
  };

  const remove = async (id) => {
    if (!confirm("Eliminare contratto e piano associato?")) return;
    await deleteContract(id); toast.success("Eliminato"); load();
  };

  const doComplete = async (id) => {
    await completeContract(id); toast.success("Contratto completato"); load();
  };

  const resetPlan = async (id) => {
    if (!confirm("Rimuovere gli interventi pianificati?")) return;
    await clearContractPlan(id); toast.success("Piano azzerato"); load();
  };

  return (
    <div data-testid="contract-manager-section" className="max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <div className="text-xs font-medium tracking-wider uppercase text-slate-500">Gestione</div>
          <h1 className="mt-1 text-3xl sm:text-4xl font-extrabold font-display text-slate-900">Contratti</h1>
        </div>
        <div className="flex gap-2">
          <input
            ref={fileRef}
            type="file"
            accept="application/pdf,.pdf"
            className="hidden"
            data-testid="contract-pdf-input"
            onChange={(e) => handleImportPdf(e.target.files?.[0])}
          />
          <input
            ref={csvRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            data-testid="contract-csv-input"
            onChange={(e) => handleImportCsv(e.target.files?.[0])}
          />
          <Button
            data-testid="contracts-template-button"
            variant="outline"
            onClick={() => window.open(contractsTemplateCsvUrl(), "_blank")}
          >
            <FileDown className="w-4 h-4 mr-2" />
            Modello CSV
          </Button>
          <Button
            data-testid="import-contracts-csv-button"
            variant="outline"
            onClick={() => csvRef.current?.click()}
            disabled={importing}
          >
            {importing ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Upload className="w-4 h-4 mr-2" />}
            Importa CSV
          </Button>
          <Button
            data-testid="import-contract-pdf-button"
            variant="outline"
            onClick={() => fileRef.current?.click()}
            disabled={importing}
          >
            <Upload className="w-4 h-4 mr-2" /> PDF
          </Button>
        <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) { setEditId(null); setForm(empty); } }}>
          <DialogTrigger asChild>
            <Button data-testid="add-contract-button" className="bg-slate-900 hover:bg-slate-800 text-white">
              <Plus className="w-4 h-4 mr-2" /> Nuovo contratto
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-white sm:max-w-2xl">
            <DialogHeader>
              <DialogTitle>{editId ? "Modifica contratto" : "Nuovo contratto"}</DialogTitle>
            </DialogHeader>
            <div className="space-y-3 max-h-[70vh] overflow-y-auto pr-1">
              <div>
                <Label>Cliente *</Label>
                <Select value={form.client_id} onValueChange={(v) => setForm({ ...form, client_id: v })}>
                  <SelectTrigger data-testid="contract-client-select" className="bg-white"><SelectValue placeholder="Seleziona cliente" /></SelectTrigger>
                  <SelectContent className="bg-white">
                    {clients.map((c) => (
                      <SelectItem key={c.id} value={c.id}>{c.name} — {c.city || c.address}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Titolo attività *</Label>
                <Input data-testid="contract-title-input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="es. Migrazione ERP + formazione utenti" />
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <Label>Giorni totali *</Label>
                  <Input data-testid="contract-days-input" type="number" min="1" value={form.total_days} onChange={(e) => setForm({ ...form, total_days: e.target.value })} />
                </div>
                <div>
                  <Label>Tariffa giornaliera €</Label>
                  <Input data-testid="contract-rate-input" type="number" min="0" step="10" value={form.daily_rate} onChange={(e) => setForm({ ...form, daily_rate: e.target.value })} />
                </div>
                <div>
                  <Label>Priorità</Label>
                  <Select value={form.priority} onValueChange={(v) => setForm({ ...form, priority: v })}>
                    <SelectTrigger data-testid="contract-priority-select" className="bg-white"><SelectValue /></SelectTrigger>
                    <SelectContent className="bg-white">
                      <SelectItem value="high">Alta</SelectItem>
                      <SelectItem value="medium">Media</SelectItem>
                      <SelectItem value="low">Bassa</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div>
                <Label>Tipologia intervento</Label>
                <Input data-testid="contract-type-input" value={form.intervention_type} onChange={(e) => setForm({ ...form, intervention_type: e.target.value })} placeholder="es. Consulenza, Formazione, Audit…" />
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <Label>Firmato il</Label>
                  <Input data-testid="contract-signed-input" type="date" value={form.signed_date} onChange={(e) => setForm({ ...form, signed_date: e.target.value })} />
                </div>
                <div>
                  <Label>Inizio previsto</Label>
                  <Input data-testid="contract-start-input" type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
                </div>
                <div>
                  <Label>Scadenza</Label>
                  <Input data-testid="contract-deadline-input" type="date" value={form.deadline} onChange={(e) => setForm({ ...form, deadline: e.target.value })} />
                </div>
              </div>
              <div>
                <Label>Note</Label>
                <Textarea data-testid="contract-notes-input" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
              </div>
            </div>
            <DialogFooter>
              <Button data-testid="contract-save-button" onClick={submit} className="bg-slate-900 hover:bg-slate-800 text-white">
                {editId ? "Salva" : "Crea"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {items.length === 0 && (
          <div className="col-span-full text-center text-slate-500 py-12">Nessun contratto. Crea il primo.</div>
        )}
        {items.map((c) => (
          <Card key={c.id} data-testid={`contract-card-${c.id}`} className="p-5 card-hover border-slate-200 bg-white">
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <FileText className="w-4 h-4 text-slate-400" />
                  <div className="text-xs text-slate-500">{clientName(c.client_id)} • {clientCity(c.client_id)}</div>
                </div>
                <h3 className="font-bold font-display text-slate-900 text-lg leading-tight">{c.title}</h3>
                <div className="mt-3 flex flex-wrap gap-2">
                  <span className={`text-[10px] px-2 py-0.5 rounded-md border font-medium uppercase tracking-wide ${priorityBadge[c.priority]}`}>
                    {c.priority === "high" ? "Alta" : c.priority === "low" ? "Bassa" : "Media"}
                  </span>
                  <span className={`text-[10px] px-2 py-0.5 rounded-md font-medium uppercase tracking-wide ${statusBadge[c.status]}`}>
                    {c.status === "active" ? "Attivo" : c.status === "planned" ? "Pianificato" : c.status === "completed" ? "Completato" : "Fatturato"}
                  </span>
                  <span className="text-[10px] px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 font-medium uppercase tracking-wide">
                    {c.total_days} giorni
                  </span>
                  {c.daily_rate > 0 && (
                    <span className="text-[10px] px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 font-medium uppercase tracking-wide">
                      € {c.daily_rate}/g
                    </span>
                  )}
                </div>
                <div className="mt-3 text-xs text-slate-600 space-y-0.5">
                  {c.start_date && <div>Inizio: <b>{c.start_date}</b></div>}
                  {c.deadline && <div>Scadenza: <b>{c.deadline}</b></div>}
                </div>
              </div>
              <div className="flex flex-col gap-1">
                <Button data-testid={`edit-contract-${c.id}`} variant="ghost" size="sm" onClick={() => edit(c)}>
                  <Edit3 className="w-4 h-4" />
                </Button>
                <Button data-testid={`delete-contract-${c.id}`} variant="ghost" size="sm" onClick={() => remove(c.id)}>
                  <Trash2 className="w-4 h-4 text-red-600" />
                </Button>
              </div>
            </div>
            <div className="mt-4 pt-3 border-t border-slate-100 flex gap-2">
              {c.status !== "completed" && c.status !== "invoiced" && (
                <Button data-testid={`complete-contract-${c.id}`} variant="outline" size="sm" onClick={() => doComplete(c.id)} className="text-xs">
                  <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> Segna completato
                </Button>
              )}
              {c.status === "planned" && (
                <Button data-testid={`reset-plan-${c.id}`} variant="outline" size="sm" onClick={() => resetPlan(c.id)} className="text-xs">
                  <RotateCcw className="w-3.5 h-3.5 mr-1" /> Reset piano
                </Button>
              )}
              <Button
                data-testid={`fatturapa-${c.id}`}
                variant="outline"
                size="sm"
                onClick={() => {
                  const num = prompt("Numero fattura (per FatturaPA)", `${new Date().getFullYear()}-001`);
                  if (num !== null) window.open(exportFatturaPaUrl(c.id, num), "_blank");
                }}
                className="text-xs"
              >
                <FileCode className="w-3.5 h-3.5 mr-1" /> FatturaPA XML
              </Button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
