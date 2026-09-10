import { Button } from "../components/ui/button";
import { CalendarClock, Route, MapPin, FileText } from "lucide-react";

export default function Login() {
  const handleLogin = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + "/dashboard";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="min-h-screen bg-grid bg-[#FAFAFC] relative overflow-hidden">
      <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-blue-100/40 blur-3xl rounded-full -translate-y-1/2 translate-x-1/2" />
      <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-indigo-100/40 blur-3xl rounded-full translate-y-1/2 -translate-x-1/2" />

      <div className="relative z-10 max-w-6xl mx-auto px-6 sm:px-10 py-8 sm:py-12">
        <div className="flex items-center gap-2">
          <div className="w-9 h-9 bg-slate-900 rounded-md flex items-center justify-center">
            <Route className="w-5 h-5 text-white" strokeWidth={2.5} />
          </div>
          <span className="font-display font-extrabold text-xl text-slate-900 tracking-tight">PlanOp</span>
          <span className="text-xs text-slate-500 hidden sm:inline">— Planning & Contratti</span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center mt-16 sm:mt-24">
          <div>
            <div className="inline-block px-3 py-1 bg-slate-900/5 border border-slate-200 rounded-full text-xs font-medium text-slate-700 uppercase tracking-wider mb-6">
              Per consulenti e freelance
            </div>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold font-display tracking-tight text-slate-900 leading-[1.05]">
              Dal contratto firmato al <span className="text-blue-700">Google Calendar</span> in un click.
            </h1>
            <p className="mt-6 text-lg text-slate-600 leading-relaxed max-w-xl">
              PlanOp legge i tuoi contratti, ottimizza gli interventi per prossimità geografica,
              rispetta le scadenze e crea il planning direttamente sul tuo calendario.
              A fine lavori, genera la fattura in PDF.
            </p>
            <div className="mt-8 flex flex-col sm:flex-row gap-3">
              <Button
                data-testid="login-google-button"
                onClick={handleLogin}
                className="bg-slate-900 hover:bg-slate-800 text-white h-12 px-6 text-base font-medium"
              >
                Accedi con Google
              </Button>
              <div className="flex items-center text-sm text-slate-500 px-2">
                Nessuna installazione. Uso personale.
              </div>
            </div>

            <div className="mt-10 grid grid-cols-2 gap-4 max-w-md">
              {[
                { icon: MapPin, label: "Ottimizzazione geografica" },
                { icon: CalendarClock, label: "Sync Google Calendar" },
                { icon: Route, label: "Rispetto scadenze" },
                { icon: FileText, label: "Fattura PDF finale" },
              ].map((it) => (
                <div key={it.label} className="flex items-center gap-2 text-sm text-slate-700">
                  <it.icon className="w-4 h-4 text-blue-700" />
                  <span>{it.label}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="relative">
            <div className="bg-white border border-slate-200 rounded-2xl shadow-xl p-6 sm:p-8">
              <div className="flex items-center justify-between mb-4">
                <div className="text-sm font-medium text-slate-500 uppercase tracking-wide">Planning settimana</div>
                <div className="text-xs px-2 py-1 bg-emerald-50 text-emerald-700 rounded-md font-mono">Ottimizzato</div>
              </div>
              <div className="space-y-3">
                {[
                  { day: "Lun 24", client: "Rossi SRL - Milano", type: "Consulenza IT", tag: "bg-blue-50 text-blue-700" },
                  { day: "Mar 25", client: "Bianchi SPA - Monza", type: "Formazione", tag: "bg-emerald-50 text-emerald-700" },
                  { day: "Mer 26", client: "Verdi SNC - Bergamo", type: "Audit", tag: "bg-amber-50 text-amber-700" },
                  { day: "Gio 27", client: "Neri SRL - Brescia", type: "Consulenza IT", tag: "bg-blue-50 text-blue-700" },
                  { day: "Ven 28", client: "Colombo - Roma", type: "Kickoff", tag: "bg-indigo-50 text-indigo-700" },
                ].map((r) => (
                  <div key={r.day} className="flex items-center justify-between p-3 bg-slate-50 border border-slate-100 rounded-lg">
                    <div>
                      <div className="text-sm font-semibold text-slate-900">{r.day}</div>
                      <div className="text-xs text-slate-600">{r.client}</div>
                    </div>
                    <div className={`text-xs px-2 py-1 rounded-md ${r.tag}`}>{r.type}</div>
                  </div>
                ))}
              </div>
              <div className="mt-4 flex items-center justify-between text-xs text-slate-500 pt-3 border-t border-slate-100">
                <span>~248 km percorsi</span>
                <span className="text-emerald-700 font-medium">-42% rispetto al piano lineare</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
