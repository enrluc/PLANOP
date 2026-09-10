import { useEffect, useState } from "react";
import { listClients, createClient, updateClient, deleteClient } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger,
} from "../components/ui/dialog";
import { Plus, MapPin, Phone, Mail, Trash2, Edit3 } from "lucide-react";
import { toast } from "sonner";

const empty = { name: "", address: "", city: "", contact_name: "", phone: "", email: "", notes: "" };

export default function Clients() {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [editId, setEditId] = useState(null);

  const load = () => listClients().then(setItems).catch(() => {});
  useEffect(() => { load(); }, []);

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
    setForm({ name: c.name, address: c.address, city: c.city || "", contact_name: c.contact_name || "",
      phone: c.phone || "", email: c.email || "", notes: c.notes || "" });
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
              <div>
                <Label>Ragione sociale *</Label>
                <Input data-testid="client-name-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
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
            </div>
            <DialogFooter>
              <Button data-testid="client-save-button" onClick={submit} className="bg-slate-900 hover:bg-slate-800 text-white">
                {editId ? "Salva" : "Crea"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
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
