import { useEffect, useState } from "react";
import { generatePlan, reschedulePlan, listInterventions, listContracts, listClients } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Switch } from "../components/ui/switch";
import { Route, Play, MapPin, CalendarClock, RefreshCw } from "lucide-react";
import { toast } from "sonner";

export default function Planning() {
  const [contracts, setContracts] = useState([]);
  const [clients, setClients] = useState([]);
  const [ivs, setIvs] = useState([]);
  const [startFrom, setStartFrom] = useState("");
  const [workdaysOnly, setWorkdaysOnly] = useState(true);
  const [maxBlock, setMaxBlock] = useState(3);
  const [running, setRunning] = useState(false);

  const load = () => Promise.all([listContracts(), listClients(), listInterventions()])
    .then(([cs, cls, iv]) => { setContracts(cs); setClients(cls); setIvs(iv); }).catch(() => {});
  useEffect(() => { load(); }, []);

  const clientFor = (id) => clients.find((c) => c.id === id);
  const contractFor = (id) => contracts.find((c) => c.id === id);

  const remainingByContract = contracts
    .filter((c) => c.status === "active" || c.status === "planned")
    .map((c) => {
      const done = ivs.filter((iv) => iv.contract_id === c.id).length;
      return { c, done, rem: c.total_days - done };
    })
    .filter((r) => r.rem > 0);

  const run = async () => {
    setRunning(true);
    try {
      const res = await generatePlan({
        start_from: startFrom || null,
        workdays_only: workdaysOnly,
        max_days_per_client_block: Number(maxBlock),
      });
      toast.success(`${res.planned} interventi pianificati`);
      load();
    } catch (_e) { toast.error("Errore generazione piano"); }
    finally { setRunning(false); }
  };

  return (
    <div data-testid="planning-generator-section" className="max-w-7xl mx-auto">
      <div className="mb-8">
        <div className="text-xs font-medium tracking-wider uppercase text-slate-500">Ottimizzazione</div>
        <h1 className="mt-1 text-3xl sm:text-4xl font-extrabold font-display text-slate-900">Planning</h1>
        <p className="mt-2 text-slate-600">Genera automaticamente gli interventi raggruppati per prossimità geografica, rispettando priorità e scadenze.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="p-6 border-slate-200 bg-white lg:col-span-1">
          <h2 className="font-bold font-display text-lg text-slate-900 mb-4 flex items-center gap-2">
            <Route className="w-5 h-5 text-blue-700" /> Parametri
          </h2>
          <div className="space-y-4">
            <div>
              <Label>Data di partenza</Label>
              <Input data-testid="planning-start-date" type="date" value={startFrom} onChange={(e) => setStartFrom(e.target.value)} />
              <div className="text-xs text-slate-500 mt-1">Default: domani</div>
            </div>
            <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg border border-slate-100">
              <div>
                <div className="text-sm font-medium text-slate-900">Solo giorni feriali</div>
                <div className="text-xs text-slate-500">Salta sabato e domenica</div>
              </div>
              <Switch data-testid="planning-workdays-only" checked={workdaysOnly} onCheckedChange={setWorkdaysOnly} />
            </div>
            <div>
              <Label>Max giorni consecutivi per cliente</Label>
              <Input data-testid="planning-max-block" type="number" min="1" max="10" value={maxBlock} onChange={(e) => setMaxBlock(e.target.value)} />
              <div className="text-xs text-slate-500 mt-1">Suddivide contratti lunghi in blocchi</div>
            </div>
            <Button data-testid="planning-run-button" disabled={running || remainingByContract.length === 0} onClick={run} className="w-full bg-slate-900 hover:bg-slate-800 text-white h-11">
              <Play className="w-4 h-4 mr-2" />
              {running ? "Generazione…" : "Genera planning ottimizzato"}
            </Button>
            <Button
              data-testid="planning-reschedule-button"
              variant="outline"
              disabled={running}
              onClick={async () => {
                if (!confirm("Cancellare TUTTI gli interventi già pianificati e riprogrammarli da zero? Gli appuntamenti extra saranno rispettati.")) return;
                setRunning(true);
                try {
                  const r = await reschedulePlan({
                    start_from: startFrom || null, workdays_only: workdaysOnly,
                    max_days_per_client_block: Number(maxBlock),
                  });
                  toast.success(`Riprogrammati ${r.planned} interventi`);
                  load();
                } catch (_e) { toast.error("Errore"); }
                finally { setRunning(false); }
              }}
              className="w-full h-11"
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${running ? "animate-spin" : ""}`} />
              Riprogramma tutto da capo
            </Button>
            <div className="text-xs text-slate-500 leading-relaxed">
              Usa "Riprogramma tutto" dopo aver inserito nuovi appuntamenti extra dal calendario o aggiunto contratti prioritari.
            </div>
          </div>
        </Card>

        <Card className="p-6 border-slate-200 bg-white lg:col-span-2">
          <h2 className="font-bold font-display text-lg text-slate-900 mb-4 flex items-center gap-2">
            <CalendarClock className="w-5 h-5 text-blue-700" /> Contratti da pianificare
          </h2>
          {remainingByContract.length === 0 ? (
            <div className="text-sm text-slate-500 py-8 text-center">Tutti i contratti sono già pianificati o non ci sono contratti attivi.</div>
          ) : (
            <div className="space-y-2">
              {remainingByContract.map(({ c, done, rem }) => {
                const cli = clientFor(c.client_id);
                return (
                  <div key={c.id} data-testid={`plan-item-${c.id}`} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg border border-slate-100">
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-semibold text-slate-900 truncate">{c.title}</div>
                      <div className="text-xs text-slate-500 flex items-center gap-1 mt-0.5">
                        <MapPin className="w-3 h-3" /> {cli?.name} • {cli?.city || cli?.address}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-bold text-slate-900">{rem}g</div>
                      <div className="text-[10px] text-slate-500">di {c.total_days} tot</div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      </div>

      {ivs.length > 0 && (
        <Card className="mt-6 p-6 border-slate-200 bg-white">
          <h2 className="font-bold font-display text-lg text-slate-900 mb-4">Interventi programmati ({ivs.length})</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wider text-slate-500">
                  <th className="py-2 pr-4">Data</th>
                  <th className="py-2 pr-4">Cliente</th>
                  <th className="py-2 pr-4">Contratto</th>
                  <th className="py-2 pr-4">Giorno</th>
                </tr>
              </thead>
              <tbody>
                {ivs.slice(0, 30).map((iv) => {
                  const c = contractFor(iv.contract_id);
                  const cli = clientFor(iv.client_id);
                  return (
                    <tr key={iv.id} className="border-b border-slate-100">
                      <td className="py-2 pr-4 font-mono text-xs">{iv.date}</td>
                      <td className="py-2 pr-4">{cli?.name || "—"}</td>
                      <td className="py-2 pr-4 text-slate-600">{c?.title || "—"}</td>
                      <td className="py-2 pr-4">{iv.day_index}/{c?.total_days || "?"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
