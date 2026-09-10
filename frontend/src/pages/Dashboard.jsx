import { useEffect, useState } from "react";
import { getStats, getSubscribeUrl } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import {
  FileText, Users, CalendarClock, Euro, Copy, CheckCircle2,
} from "lucide-react";
import { toast } from "sonner";

const Metric = ({ icon: Icon, label, value, hint, testid }) => (
  <Card data-testid={testid} className="p-5 card-hover border-slate-200 bg-white">
    <div className="flex items-center justify-between">
      <div className="text-xs font-medium tracking-wider uppercase text-slate-500">{label}</div>
      <Icon className="w-4 h-4 text-slate-400" />
    </div>
    <div className="mt-3 text-3xl font-extrabold font-display text-slate-900">{value}</div>
    {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
  </Card>
);

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [subUrl, setSubUrl] = useState("");

  useEffect(() => {
    getStats().then(setStats).catch(() => {});
    getSubscribeUrl().then((d) => setSubUrl(d.url)).catch(() => {});
  }, []);

  const copyUrl = () => {
    navigator.clipboard.writeText(subUrl);
    toast.success("URL calendario copiato. Incollalo su Google Calendar → 'Da URL'.");
  };

  return (
    <div data-testid="dashboard-overview-container" className="max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <div className="text-xs font-medium tracking-wider uppercase text-slate-500">Panoramica</div>
          <h1 className="mt-1 text-3xl sm:text-4xl font-extrabold font-display text-slate-900">Dashboard</h1>
          <p className="mt-2 text-slate-600">Contratti attivi, interventi programmati e sincronizzazione con Google Calendar.</p>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mt-8">
        <Metric testid="stat-active-contracts" icon={FileText} label="Contratti attivi" value={stats?.active_contracts ?? "—"} hint={`${stats?.total_contracts ?? 0} totali`} />
        <Metric testid="stat-clients" icon={Users} label="Clienti" value={stats?.clients_count ?? "—"} />
        <Metric testid="stat-interventions" icon={CalendarClock} label="Interventi pianificati" value={stats?.interventions_planned ?? "—"} hint={`su ${stats?.total_workdays ?? 0} giorni`} />
        <Metric testid="stat-revenue" icon={Euro} label="Fatturato previsto" value={`€ ${Number(stats?.projected_revenue ?? 0).toFixed(0)}`} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-8">
        <Card className="p-6 lg:col-span-2 border-slate-200 bg-white">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold font-display text-slate-900">Prossimi interventi</h2>
            <span className="text-xs text-slate-500">Da oggi in avanti</span>
          </div>
          <div className="space-y-2">
            {(stats?.upcoming || []).length === 0 && (
              <div className="text-sm text-slate-500 py-6 text-center">Nessun intervento pianificato. Vai su <b>Planning</b> per generarlo.</div>
            )}
            {(stats?.upcoming || []).map((iv) => (
              <div key={iv.id} data-testid={`upcoming-item-${iv.id}`} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg border border-slate-100">
                <div className="flex items-center gap-3">
                  <div className="w-11 h-11 bg-white border border-slate-200 rounded-md flex flex-col items-center justify-center">
                    <span className="text-[10px] font-medium text-slate-500 uppercase">
                      {new Date(iv.date).toLocaleDateString("it-IT", { month: "short" })}
                    </span>
                    <span className="text-sm font-bold text-slate-900 -mt-0.5">
                      {new Date(iv.date).getDate()}
                    </span>
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-slate-900">Giorno {iv.day_index}</div>
                    <div className="text-xs text-slate-500 font-mono">{iv.contract_id.slice(0, 8)}</div>
                  </div>
                </div>
                <span className="text-xs px-2 py-1 bg-blue-50 text-blue-700 rounded-md font-medium">Pianificato</span>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-6 border-slate-200 bg-white">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <h2 className="text-lg font-bold font-display text-slate-900">Sync Google Calendar</h2>
          </div>
          <p className="text-sm text-slate-600 mb-4">
            Iscrivi il tuo Google Calendar all'URL sotto. Ogni nuovo intervento comparirà automaticamente.
          </p>
          <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 mb-3">
            <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">URL Calendario</div>
            <div data-testid="calendar-subscribe-url" className="text-xs font-mono text-slate-800 break-all">{subUrl || "…"}</div>
          </div>
          <Button data-testid="copy-subscribe-url" onClick={copyUrl} className="w-full bg-slate-900 hover:bg-slate-800 text-white">
            <Copy className="w-4 h-4 mr-2" /> Copia URL
          </Button>
          <div className="mt-4 text-xs text-slate-500 leading-relaxed">
            Su Google Calendar: <b>+ Altri calendari → Da URL</b>, incolla e conferma. In alternativa scarica il file .ics dal pulsante nella pagina Calendario.
          </div>
        </Card>
      </div>
    </div>
  );
}
