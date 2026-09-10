import { useEffect, useState } from "react";
import { listContracts, listClients, listInterventions, generateInvoice } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Switch } from "../components/ui/switch";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "../components/ui/select";
import { Receipt, Download, Euro } from "lucide-react";
import { toast } from "sonner";

export default function Invoices() {
  const [contracts, setContracts] = useState([]);
  const [clients, setClients] = useState([]);
  const [ivs, setIvs] = useState([]);
  const [selected, setSelected] = useState("");
  const [form, setForm] = useState({
    invoice_number: `${new Date().getFullYear()}-001`,
    invoice_date: new Date().toISOString().slice(0, 10),
    vat_rate: 22,
    withholding_rate: 20,
    regime_forfettario: false,
    marca_da_bollo: false,
    issuer_name: "",
    issuer_vat: "",
    issuer_address: "",
  });

  useEffect(() => {
    Promise.all([listContracts(), listClients(), listInterventions()])
      .then(([c, cl, i]) => { setContracts(c); setClients(cl); setIvs(i); }).catch(() => {});
  }, []);

  const eligible = contracts.filter((c) => c.status === "completed" || c.status === "planned" || c.status === "invoiced");
  const contract = contracts.find((c) => c.id === selected);
  const client = contract ? clients.find((cl) => cl.id === contract.client_id) : null;
  const workedDays = contract ? ivs.filter((iv) => iv.contract_id === contract.id).length : 0;

  const submit = async () => {
    if (!selected) { toast.error("Seleziona un contratto"); return; }
    try {
      const blob = await generateInvoice({ contract_id: selected, ...form,
        vat_rate: Number(form.vat_rate), withholding_rate: Number(form.withholding_rate) });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `fattura-${form.invoice_number}.pdf`; a.click();
      URL.revokeObjectURL(url);
      toast.success("Fattura generata");
    } catch (_e) { toast.error("Errore generazione fattura"); }
  };

  return (
    <div data-testid="invoice-generator-section" className="max-w-7xl mx-auto">
      <div className="mb-8">
        <div className="text-xs font-medium tracking-wider uppercase text-slate-500">A fine lavori</div>
        <h1 className="mt-1 text-3xl sm:text-4xl font-extrabold font-display text-slate-900">Fatture</h1>
        <p className="mt-2 text-slate-600">Genera una fattura PDF dai contratti completati o pianificati.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="p-6 border-slate-200 bg-white lg:col-span-2">
          <h2 className="font-bold font-display text-lg text-slate-900 mb-4 flex items-center gap-2">
            <Receipt className="w-5 h-5 text-blue-700" /> Dati fattura
          </h2>
          <div className="space-y-4">
            <div>
              <Label>Contratto *</Label>
              <Select value={selected} onValueChange={setSelected}>
                <SelectTrigger data-testid="invoice-contract-select" className="bg-white"><SelectValue placeholder="Seleziona contratto" /></SelectTrigger>
                <SelectContent className="bg-white">
                  {eligible.map((c) => {
                    const cl = clients.find((x) => x.id === c.client_id);
                    return <SelectItem key={c.id} value={c.id}>{cl?.name} — {c.title}</SelectItem>;
                  })}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Numero fattura *</Label>
                <Input data-testid="invoice-number-input" value={form.invoice_number} onChange={(e) => setForm({ ...form, invoice_number: e.target.value })} />
              </div>
              <div>
                <Label>Data</Label>
                <Input data-testid="invoice-date-input" type="date" value={form.invoice_date} onChange={(e) => setForm({ ...form, invoice_date: e.target.value })} />
              </div>
            </div>
            <div className="p-4 bg-slate-50 rounded-lg border border-slate-100">
              <div className="text-xs font-medium tracking-wider uppercase text-slate-500 mb-3">Dati emittente</div>
              <div className="space-y-3">
                <div>
                  <Label>Nome / Ragione sociale</Label>
                  <Input data-testid="invoice-issuer-name" value={form.issuer_name} onChange={(e) => setForm({ ...form, issuer_name: e.target.value })} />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label>P.IVA</Label>
                    <Input data-testid="invoice-issuer-vat" value={form.issuer_vat} onChange={(e) => setForm({ ...form, issuer_vat: e.target.value })} />
                  </div>
                  <div>
                    <Label>Indirizzo</Label>
                    <Input data-testid="invoice-issuer-address" value={form.issuer_address} onChange={(e) => setForm({ ...form, issuer_address: e.target.value })} />
                  </div>
                </div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>IVA %</Label>
                <Input data-testid="invoice-vat-input" type="number" value={form.vat_rate} onChange={(e) => setForm({ ...form, vat_rate: e.target.value })} disabled={form.regime_forfettario} />
              </div>
              <div>
                <Label>Ritenuta d'acconto %</Label>
                <Input data-testid="invoice-wht-input" type="number" value={form.withholding_rate} onChange={(e) => setForm({ ...form, withholding_rate: e.target.value })} disabled={form.regime_forfettario} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg border border-slate-100">
                <div className="text-sm">Regime forfettario</div>
                <Switch data-testid="invoice-forfettario-switch" checked={form.regime_forfettario} onCheckedChange={(v) => setForm({ ...form, regime_forfettario: v })} />
              </div>
              <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg border border-slate-100">
                <div className="text-sm">Marca da bollo €2</div>
                <Switch data-testid="invoice-bollo-switch" checked={form.marca_da_bollo} onCheckedChange={(v) => setForm({ ...form, marca_da_bollo: v })} />
              </div>
            </div>
            <Button data-testid="generate-invoice-button" onClick={submit} className="w-full bg-slate-900 hover:bg-slate-800 text-white h-11">
              <Download className="w-4 h-4 mr-2" /> Genera e scarica PDF
            </Button>
          </div>
        </Card>

        <Card className="p-6 border-slate-200 bg-white h-fit">
          <h3 className="font-bold font-display text-slate-900 mb-3 flex items-center gap-2">
            <Euro className="w-4 h-4 text-blue-700" /> Anteprima calcolo
          </h3>
          {contract ? (
            <div className="space-y-2 text-sm">
              <Row label="Cliente" value={client?.name || "—"} />
              <Row label="Contratto" value={contract.title} />
              <Row label="Giorni pianificati" value={workedDays || contract.total_days} />
              <Row label="Tariffa/giorno" value={`€ ${contract.daily_rate?.toFixed(2) || "0.00"}`} />
              <div className="border-t border-slate-200 my-2" />
              <Row label="Imponibile" value={`€ ${((workedDays || contract.total_days) * (contract.daily_rate || 0)).toFixed(2)}`} bold />
            </div>
          ) : (
            <div className="text-sm text-slate-500">Seleziona un contratto per vedere il totale.</div>
          )}
        </Card>
      </div>
    </div>
  );
}

const Row = ({ label, value, bold }) => (
  <div className="flex justify-between">
    <span className="text-slate-500">{label}</span>
    <span className={bold ? "font-bold text-slate-900" : "text-slate-900"}>{value}</span>
  </div>
);
