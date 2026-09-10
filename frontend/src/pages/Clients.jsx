import { useEffect, useRef, useState } from "react";
import { listClients, createClient, updateClient, deleteClient, aiAnalyzeContractPdf } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger,
} from "../components/ui/dialog";
import { Plus, MapPin, Phone, Mail, Trash2, Edit3, Upload, Loader2, Download, FileDown } from "lucide-react";
import { toast } from "sonner";
import { exportClientsCsvUrl, clientsTemplateCsvUrl, importClientsCsv } from "../lib/api";

const empty = { codice_cliente: "", name: "", address: "", city: "", cap: "", provincia: "", contact_name: "", phone: "", email: "", piva: "", codice_fiscale: "", codice_destinatario: "", pec: "", notes: "" };

export default function Clients() {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [editId, setEditId] = useState(null);
  const [importing, setImporting] = useState(false);
  const fileRef = useRef(null);
  const csvRef = useRef(null);

  const load = () => listClients().then(setItems).catch(() => {});
  useEffect(() => { load(); }, []);

  const handleImportCsv = async (file) => {
    if (!file) return;
    setImporting(true);
    try {
      const r = await importClientsCsv(file);
      toast.success(`${r.imported} nuovi, ${r.updated} aggiornati${r.errors?.length ? " · alcuni errori" : ""}`);
      if (r.errors?.length) console.warn("CSV import errors:", r.errors);
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
      setEditId(null);
      setForm({
        codice_cliente: "",
        name: d.client_name || "",
        address: d.address || "",
        city: d.city || "",
        cap: "", provincia: "",
        contact_name: d.contact_name || "",
        phone: d.phone || "",
        email: d.email || "",
        piva: "", codice_fiscale: "",
        codice_destinatario: "", pec: "",
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

  const submit = async () => {
    if (!form.name || !form.address) { toast.error("Nome e indirizzo obbligatori"); return; }
    try {
      if (editId) {
        await updateClient(editId, form);
        toast.success("Cliente aggiornato");
      } else {
        await createClient(form);
        toast.success("Cliente aggiunto");
      }
      setOpen(false); setForm(empty); setEditId(null);
      load();
    } catch (_e) { toast.error("Errore salvataggio"); }
  };

  const edit = (c) => {
    setEditId(c.id);
    setForm({
      codice_cliente: c.codice_cliente || "",
      name: c.name, address: c.address, city: c.city || "", cap: c.cap || "", provincia: c.provincia || "",
      contact_name: c.contact_name || "", phone: c.phone || "", email: c.email || "",
      piva: c.piva || "", codice_fiscale: c.codice_fiscale || "",
      codice_destinatario: c.codice_destinatario || "", pec: c.pec || "",
      notes: c.notes || "",
    });
    setOpen(true);
  };

  const remove = async (id) => {
    if (!confirm("Eliminare cliente?")) return;
    await deleteClient(id);
    toast.success("Eliminato");
    load();
  };

  return (
    <div data-testid="client-registry-section" className="max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <div className="text-xs font-medium tracking-wider uppercase text-slate-500">Anagrafica</div>
          <h1 className="mt-1 text-3xl sm:text-4xl font-extrabold font-display text-slate-900">Clienti</h1>
        </div>
        <div className="flex gap-2">
          <input
            ref={fileRef}
            type="file"
            accept="application/pdf,.pdf"
            className="hidden"
            data-testid="client-pdf-input"
            onChange={(e) => handleImportPdf(e.target.files?.[0])}
          />
          <input
            ref={csvRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            data-testid="client-csv-input"
            onChange={(e) => handleImportCsv(e.target.files?.[0])}
          />
          <Button
            data-testid="clients-template-button"
            variant="outline"
            onClick={() => window.open(clientsTemplateCsvUrl(), "_blank")}
          >
            <FileDown className="w-4 h-4 mr-2" />
            Modello CSV
          </Button>
          <Button
            data-testid="import-clients-csv-button"
            variant="outline"
            onClick={() => csvRef.current?.click()}
            disabled={importing}
          >
            {importing ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Upload className="w-4 h-4 mr-2" />}
            Importa CSV
          </Button>
          <Button
            data-testid="import-client-pdf-button"
            variant="outline"
            onClick={() => fileRef.current?.click()}
            disabled={importing}
          >
            <Upload className="w-4 h-4 mr-2" /> PDF
          </Button>
          <Button
            data-testid="export-invoicex-csv-button"
            variant="outline"
            onClick={() => window.open(exportClientsCsvUrl(), "_blank")}
          >
            <Download className="w-4 h-4 mr-2" />
            Export Invoicex CSV
          </Button>
        <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) { setEditId(null); setForm(empty); } }}>
          <DialogTrigger asChild>
            <Button data-testid="add-client-button" className="bg-slate-900 hover:bg-slate-800 text-white">
              <Plus className="w-4 h-4 mr-2" /> Nuovo cliente
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-white sm:max-w-lg">
            <DialogHeader>
              <DialogTitle>{editId ? "Modifica cliente" : "Nuovo cliente"}</DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <Label>Codice Cliente</Label>
                  <Input data-testid="client-code-input" value={form.codice_cliente} onChange={(e) => setForm({ ...form, codice_cliente: e.target.value })} placeholder="C001" />
                </div>
                <div className="col-span-2">
                  <Label>Ragione sociale *</Label>
                  <Input data-testid="client-name-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Indirizzo *</Label>
                  <Input data-testid="client-address-input" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
                </div>
                <div>
                  <Label>Città</Label>
                  <Input data-testid="client-city-input" value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} />
                </div>
              </div>
              <div>
                <Label>Referente</Label>
                <Input data-testid="client-contact-input" value={form.contact_name} onChange={(e) => setForm({ ...form, contact_name: e.target.value })} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Telefono</Label>
                  <Input data-testid="client-phone-input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
                </div>
                <div>
                  <Label>Email</Label>
                  <Input data-testid="client-email-input" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
                </div>
              </div>
              <div>
                <Label>Note</Label>
                <Textarea data-testid="client-notes-input" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
              </div>
              <div className="pt-3 border-t border-slate-100">
                <div className="text-xs font-medium tracking-wider uppercase text-slate-500 mb-2">Dati fiscali (per FatturaPA / Invoicex)</div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label>P.IVA</Label>
                    <Input data-testid="client-piva-input" value={form.piva} onChange={(e) => setForm({ ...form, piva: e.target.value })} />
                  </div>
                  <div>
                    <Label>Codice Fiscale</Label>
                    <Input data-testid="client-cf-input" value={form.codice_fiscale} onChange={(e) => setForm({ ...form, codice_fiscale: e.target.value })} />
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-3 mt-3">
                  <div>
                    <Label>CAP</Label>
                    <Input data-testid="client-cap-input" value={form.cap} onChange={(e) => setForm({ ...form, cap: e.target.value })} />
                  </div>
                  <div>
                    <Label>Provincia</Label>
                    <Input data-testid="client-prov-input" maxLength={2} value={form.provincia} onChange={(e) => setForm({ ...form, provincia: e.target.value.toUpperCase() })} placeholder="MI" />
                  </div>
                  <div>
                    <Label>Cod. Destinatario</Label>
                    <Input data-testid="client-coddest-input" maxLength={7} value={form.codice_destinatario} onChange={(e) => setForm({ ...form, codice_destinatario: e.target.value.toUpperCase() })} placeholder="0000000" />
                  </div>
                </div>
                <div className="mt-3">
                  <Label>PEC</Label>
                  <Input data-testid="client-pec-input" value={form.pec} onChange={(e) => setForm({ ...form, pec: e.target.value })} />
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button data-testid="client-save-button" onClick={submit} className="bg-slate-900 hover:bg-slate-800 text-white">
                {editId ? "Salva" : "Crea"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {items.length === 0 && (
          <div className="col-span-full text-center text-slate-500 py-12">Nessun cliente. Aggiungine uno per iniziare.</div>
        )}
        {items.map((c) => (
          <Card key={c.id} data-testid={`client-card-${c.id}`} className="p-5 card-hover border-slate-200 bg-white">
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <h3 className="font-bold font-display text-slate-900 truncate">{c.name}</h3>
                <div className="mt-1.5 text-xs text-slate-600 flex items-center gap-1.5">
                  <MapPin className="w-3.5 h-3.5" /> {c.address}{c.city ? `, ${c.city}` : ""}
                </div>
                {c.contact_name && (
                  <div className="mt-1 text-xs text-slate-600">{c.contact_name}</div>
                )}
                {c.phone && (
                  <div className="mt-1 text-xs text-slate-600 flex items-center gap-1.5"><Phone className="w-3.5 h-3.5" /> {c.phone}</div>
                )}
                {c.email && (
                  <div className="mt-1 text-xs text-slate-600 flex items-center gap-1.5"><Mail className="w-3.5 h-3.5" /> {c.email}</div>
                )}
              </div>
              <div className="flex gap-1">
                <Button data-testid={`edit-client-${c.id}`} variant="ghost" size="sm" onClick={() => edit(c)}>
                  <Edit3 className="w-4 h-4" />
                </Button>
                <Button data-testid={`delete-client-${c.id}`} variant="ghost" size="sm" onClick={() => remove(c.id)}>
                  <Trash2 className="w-4 h-4 text-red-600" />
                </Button>
              </div>
            </div>
            {c.lat && (
              <div className="mt-3 pt-3 border-t border-slate-100 text-[10px] text-slate-500 font-mono">
                {c.lat.toFixed(4)}, {c.lng.toFixed(4)}
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
