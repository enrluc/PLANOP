import { useEffect, useState } from "react";
import {
  getReminderPrefs, setReminderPrefs, testReminder, getReminderLog,
  getGcalSettings, setGcalSettings, gcalSyncNow,
  getIssuer, setIssuer,
  getApiKeys, setApiKeys, weeklyBackupUrl,
} from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Switch } from "../components/ui/switch";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "../components/ui/select";
import { Bell, Send, Loader2, CheckCircle2, CalendarSync, RefreshCw, FileSpreadsheet, KeyRound, Archive, Eye, EyeOff, Trash2, Download } from "lucide-react";
import { toast } from "sonner";

export default function Settings() {
  const [prefs, setPrefs] = useState({ enabled: true, send_to_client_email: true, cc_owner: false, owner_email: "" });
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [log, setLog] = useState([]);
  const [gcal, setGcal] = useState({ ics_url: "", enabled: false, last_sync: null, last_count: 0 });
  const [gcalSaving, setGcalSaving] = useState(false);
  const [gcalSyncing, setGcalSyncing] = useState(false);
  const [issuer, setIssuerState] = useState({
    denominazione: "", nome: "", cognome: "", piva: "", codice_fiscale: "",
    regime_fiscale: "RF01", codice_ateco: "",
    address: "", cap: "", city: "", provincia: "", nazione: "IT",
    telefono: "", email: "", id_paese_trasmittente: "IT", id_codice_trasmittente: "",
  });
  const [issuerSaving, setIssuerSaving] = useState(false);
  const [apiKeys, setApiKeysState] = useState({ anthropic_api_key: "", resend_api_key: "", resend_from_email: "", has_anthropic: false, has_resend: false });
  const [apiKeysDraft, setApiKeysDraft] = useState({ anthropic_api_key: "", resend_api_key: "", resend_from_email: "" });
  const [apiKeysSaving, setApiKeysSaving] = useState(false);
  const [showAnthropic, setShowAnthropic] = useState(false);
  const [showResend, setShowResend] = useState(false);

  useEffect(() => {
    getReminderPrefs().then(setPrefs).catch(() => {});
    getReminderLog().then(setLog).catch(() => {});
    getGcalSettings().then(setGcal).catch(() => {});
    getIssuer().then(setIssuerState).catch(() => {});
    getApiKeys().then((d) => {
      setApiKeysState(d);
      setApiKeysDraft({ anthropic_api_key: "", resend_api_key: "", resend_from_email: d.resend_from_email || "" });
    }).catch(() => {});
  }, []);

  const save = async () => {
    setSaving(true);
    try { await setReminderPrefs(prefs); toast.success("Preferenze salvate"); }
    catch (_e) { toast.error("Errore salvataggio"); }
    finally { setSaving(false); }
  };

  const test = async () => {
    setTesting(true);
    try { await testReminder(); toast.success("Email di test inviata al tuo indirizzo"); }
    catch (e) { toast.error(e?.response?.data?.detail || "Invio fallito"); }
    finally { setTesting(false); }
  };

  const saveGcal = async () => {
    setGcalSaving(true);
    try {
      const r = await setGcalSettings({ ics_url: gcal.ics_url || "", enabled: !!gcal.enabled });
      setGcal((g) => ({ ...g, ics_url: r.ics_url }));
      toast.success("Impostazioni Google Calendar salvate");
    } catch (e) { toast.error(e?.response?.data?.detail || "Errore"); }
    finally { setGcalSaving(false); }
  };

  const syncNow = async () => {
    setGcalSyncing(true);
    try {
      const r = await gcalSyncNow();
      toast.success(`${r.synced} eventi sincronizzati da Google Calendar`);
      const fresh = await getGcalSettings();
      setGcal(fresh);
    } catch (e) { toast.error(e?.response?.data?.detail || "Sync fallito"); }
    finally { setGcalSyncing(false); }
  };

  const saveIssuer = async () => {
    setIssuerSaving(true);
    try { await setIssuer(issuer); toast.success("Dati emittente salvati"); }
    catch (_e) { toast.error("Errore salvataggio"); }
    finally { setIssuerSaving(false); }
  };

  const saveApiKeys = async () => {
    setApiKeysSaving(true);
    try {
      const payload = {
        anthropic_api_key: apiKeysDraft.anthropic_api_key || "",
        resend_api_key: apiKeysDraft.resend_api_key || "",
        resend_from_email: apiKeysDraft.resend_from_email || "",
      };
      const r = await setApiKeys(payload);
      toast.success("Chiavi API salvate");
      const fresh = await getApiKeys();
      setApiKeysState(fresh);
      setApiKeysDraft({ anthropic_api_key: "", resend_api_key: "", resend_from_email: fresh.resend_from_email || "" });
    } catch (_e) { toast.error("Errore salvataggio chiavi"); }
    finally { setApiKeysSaving(false); }
  };

  const clearOneKey = async (which) => {
    try {
      const payload = { anthropic_api_key: "", resend_api_key: "", resend_from_email: apiKeys.resend_from_email || "" };
      payload[which] = "__clear__";
      await setApiKeys(payload);
      toast.success("Chiave rimossa");
      const fresh = await getApiKeys();
      setApiKeysState(fresh);
      setApiKeysDraft({ anthropic_api_key: "", resend_api_key: "", resend_from_email: fresh.resend_from_email || "" });
    } catch (_e) { toast.error("Errore"); }
  };

  return (
    <div data-testid="settings-section" className="max-w-4xl mx-auto">
      <div className="mb-8">
        <div className="text-xs font-medium tracking-wider uppercase text-slate-500">Configurazione</div>
        <h1 className="mt-1 text-3xl sm:text-4xl font-extrabold font-display text-slate-900">Impostazioni</h1>
        <p className="mt-2 text-slate-600">Reminder automatici via email 24h prima di ogni intervento.</p>
      </div>

      <Card className="p-6 border-slate-200 bg-white mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Bell className="w-5 h-5 text-blue-700" />
          <h2 className="font-bold font-display text-lg text-slate-900">Reminder Email</h2>
        </div>
        <div className="space-y-4">
          <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg border border-slate-100">
            <div>
              <div className="text-sm font-medium text-slate-900">Reminder attivi</div>
              <div className="text-xs text-slate-500">Ogni giorno alle 09:00 (Italia), invia email per gli interventi di domani</div>
            </div>
            <Switch data-testid="reminder-enabled" checked={prefs.enabled} onCheckedChange={(v) => setPrefs({ ...prefs, enabled: v })} />
          </div>
          <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg border border-slate-100">
            <div>
              <div className="text-sm font-medium text-slate-900">Invia al cliente</div>
              <div className="text-xs text-slate-500">Usa l'email presente in anagrafica cliente</div>
            </div>
            <Switch data-testid="reminder-client" checked={prefs.send_to_client_email} onCheckedChange={(v) => setPrefs({ ...prefs, send_to_client_email: v })} />
          </div>
          <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg border border-slate-100">
            <div>
              <div className="text-sm font-medium text-slate-900">Invia una copia a me</div>
              <div className="text-xs text-slate-500">Fallback se il cliente non ha email</div>
            </div>
            <Switch data-testid="reminder-cc" checked={prefs.cc_owner} onCheckedChange={(v) => setPrefs({ ...prefs, cc_owner: v })} />
          </div>
          {prefs.cc_owner && (
            <div>
              <Label>La tua email</Label>
              <Input data-testid="reminder-owner-email" value={prefs.owner_email || ""} onChange={(e) => setPrefs({ ...prefs, owner_email: e.target.value })} placeholder="tu@dominio.it" />
            </div>
          )}
          <div className="flex gap-2 pt-2">
            <Button data-testid="reminder-save" onClick={save} disabled={saving} className="bg-slate-900 hover:bg-slate-800 text-white">
              {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <CheckCircle2 className="w-4 h-4 mr-2" />}
              Salva
            </Button>
            <Button data-testid="reminder-test" onClick={test} disabled={testing} variant="outline">
              {testing ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Send className="w-4 h-4 mr-2" />}
              Invia email di test
            </Button>
          </div>
        </div>
      </Card>

      <Card className="p-6 border-slate-200 bg-white mb-6">
        <div className="flex items-center gap-2 mb-4">
          <CalendarSync className="w-5 h-5 text-blue-700" />
          <h2 className="font-bold font-display text-lg text-slate-900">Sincronizzazione Google Calendar</h2>
        </div>
        <p className="text-sm text-slate-600 mb-4 leading-relaxed">
          Su Google Calendar → Impostazioni → seleziona il tuo calendario → <b>Indirizzo segreto in formato iCal</b>. Copia l'URL (inizia con https://calendar.google.com/…/basic.ics) e incollalo qui. PlanOp lo leggerà ogni giorno alle 08:00 (Italia) per bloccare quelle date nel planning.
        </p>
        <div className="space-y-4">
          <div>
            <Label>URL iCal privato</Label>
            <Input
              data-testid="gcal-url-input"
              value={gcal.ics_url || ""}
              onChange={(e) => setGcal({ ...gcal, ics_url: e.target.value })}
              placeholder="https://calendar.google.com/calendar/ical/…/private-…/basic.ics"
              className="font-mono text-xs"
            />
          </div>
          <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg border border-slate-100">
            <div>
              <div className="text-sm font-medium text-slate-900">Sync automatica attiva</div>
              <div className="text-xs text-slate-500">Esegue ogni giorno alle 08:00 (Europe/Rome)</div>
            </div>
            <Switch data-testid="gcal-enabled" checked={!!gcal.enabled} onCheckedChange={(v) => setGcal({ ...gcal, enabled: v })} />
          </div>
          {gcal.last_sync && (
            <div className="text-xs text-slate-500 bg-emerald-50 border border-emerald-200 rounded p-2">
              Ultima sync: <b>{new Date(gcal.last_sync).toLocaleString("it-IT")}</b> · <b>{gcal.last_count}</b> eventi importati
            </div>
          )}
          <div className="flex gap-2">
            <Button data-testid="gcal-save" onClick={saveGcal} disabled={gcalSaving} className="bg-slate-900 hover:bg-slate-800 text-white">
              {gcalSaving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <CheckCircle2 className="w-4 h-4 mr-2" />}
              Salva
            </Button>
            <Button data-testid="gcal-sync-now" onClick={syncNow} disabled={gcalSyncing || !gcal.ics_url} variant="outline">
              {gcalSyncing ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <RefreshCw className="w-4 h-4 mr-2" />}
              Sincronizza ora
            </Button>
          </div>
        </div>
      </Card>

      <Card className="p-6 border-slate-200 bg-white mb-6">
        <div className="flex items-center gap-2 mb-4">
          <FileSpreadsheet className="w-5 h-5 text-blue-700" />
          <h2 className="font-bold font-display text-lg text-slate-900">Dati emittente per FatturaPA / Invoicex</h2>
        </div>
        <p className="text-sm text-slate-600 mb-4">
          Necessari per generare l'XML FatturaPA importabile in Invoicex e per il tuo Sistema di Interscambio (SdI).
        </p>
        <div className="space-y-3">
          <div>
            <Label>Denominazione (o Nome Cognome)</Label>
            <Input data-testid="issuer-denominazione" value={issuer.denominazione || ""} onChange={(e) => setIssuerState({ ...issuer, denominazione: e.target.value })} placeholder="Es. Enrico Lucchese o Studio Lucchese SRL" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>P.IVA</Label>
              <Input data-testid="issuer-piva" value={issuer.piva || ""} onChange={(e) => setIssuerState({ ...issuer, piva: e.target.value.replace(/\s/g, "") })} />
            </div>
            <div>
              <Label>Codice Fiscale</Label>
              <Input data-testid="issuer-cf" value={issuer.codice_fiscale || ""} onChange={(e) => setIssuerState({ ...issuer, codice_fiscale: e.target.value.toUpperCase() })} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Regime fiscale</Label>
              <Select value={issuer.regime_fiscale || "RF01"} onValueChange={(v) => setIssuerState({ ...issuer, regime_fiscale: v })}>
                <SelectTrigger data-testid="issuer-regime" className="bg-white"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-white">
                  <SelectItem value="RF01">RF01 - Ordinario</SelectItem>
                  <SelectItem value="RF19">RF19 - Forfettario</SelectItem>
                  <SelectItem value="RF02">RF02 - Contribuenti minimi</SelectItem>
                  <SelectItem value="RF04">RF04 - Agricoltura</SelectItem>
                  <SelectItem value="RF18">RF18 - Altro</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Codice ATECO</Label>
              <Input data-testid="issuer-ateco" value={issuer.codice_ateco || ""} onChange={(e) => setIssuerState({ ...issuer, codice_ateco: e.target.value })} placeholder="es. 70.22.09" />
            </div>
          </div>
          <div>
            <Label>Indirizzo</Label>
            <Input data-testid="issuer-address" value={issuer.address || ""} onChange={(e) => setIssuerState({ ...issuer, address: e.target.value })} />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <Label>CAP</Label>
              <Input data-testid="issuer-cap" maxLength={5} value={issuer.cap || ""} onChange={(e) => setIssuerState({ ...issuer, cap: e.target.value })} />
            </div>
            <div>
              <Label>Città</Label>
              <Input data-testid="issuer-city" value={issuer.city || ""} onChange={(e) => setIssuerState({ ...issuer, city: e.target.value })} />
            </div>
            <div>
              <Label>Provincia</Label>
              <Input data-testid="issuer-provincia" maxLength={2} value={issuer.provincia || ""} onChange={(e) => setIssuerState({ ...issuer, provincia: e.target.value.toUpperCase() })} />
            </div>
          </div>
          <Button data-testid="issuer-save" onClick={saveIssuer} disabled={issuerSaving} className="bg-slate-900 hover:bg-slate-800 text-white">
            {issuerSaving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <CheckCircle2 className="w-4 h-4 mr-2" />}
            Salva dati emittente
          </Button>
        </div>
      </Card>

      <Card className="p-6 border-slate-200 bg-white mb-6">
        <div className="flex items-center gap-2 mb-4">
          <KeyRound className="w-5 h-5 text-blue-700" />
          <h2 className="font-bold font-display text-lg text-slate-900">Chiavi API personali (Desktop / Self-hosted)</h2>
        </div>
        <p className="text-sm text-slate-600 mb-4 leading-relaxed">
          Nella build desktop di PlanOp puoi inserire qui le <b>tue</b> chiavi Anthropic e Resend. Se impostate, l'app le usa al posto della chiave Emergent condivisa. Lascia il campo vuoto per non modificare quello già salvato. Costo indicativo mensile: Anthropic ~$0,50-2, Resend gratis fino a 3000 email/mese.
        </p>
        <div className="space-y-4">
          <div>
            <Label>Chiave Anthropic (Claude Haiku 4.5)</Label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Input
                  data-testid="anthropic-key-input"
                  type={showAnthropic ? "text" : "password"}
                  value={apiKeysDraft.anthropic_api_key}
                  onChange={(e) => setApiKeysDraft({ ...apiKeysDraft, anthropic_api_key: e.target.value })}
                  placeholder={apiKeys.has_anthropic ? apiKeys.anthropic_api_key : "sk-ant-…"}
                  className="font-mono text-xs pr-10"
                />
                <button type="button" onClick={() => setShowAnthropic((v) => !v)} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-900" data-testid="anthropic-key-toggle">
                  {showAnthropic ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {apiKeys.has_anthropic && (
                <Button data-testid="anthropic-key-clear" variant="outline" onClick={() => clearOneKey("anthropic_api_key")} title="Rimuovi chiave Anthropic personale">
                  <Trash2 className="w-4 h-4" />
                </Button>
              )}
            </div>
            <div className="text-xs text-slate-500 mt-1">
              Ottienila su <a className="text-blue-700 underline" href="https://console.anthropic.com/settings/keys" target="_blank" rel="noreferrer">console.anthropic.com</a>.
            </div>
          </div>

          <div>
            <Label>Chiave Resend (email)</Label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Input
                  data-testid="resend-key-input"
                  type={showResend ? "text" : "password"}
                  value={apiKeysDraft.resend_api_key}
                  onChange={(e) => setApiKeysDraft({ ...apiKeysDraft, resend_api_key: e.target.value })}
                  placeholder={apiKeys.has_resend ? apiKeys.resend_api_key : "re_…"}
                  className="font-mono text-xs pr-10"
                />
                <button type="button" onClick={() => setShowResend((v) => !v)} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-900" data-testid="resend-key-toggle">
                  {showResend ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {apiKeys.has_resend && (
                <Button data-testid="resend-key-clear" variant="outline" onClick={() => clearOneKey("resend_api_key")} title="Rimuovi chiave Resend personale">
                  <Trash2 className="w-4 h-4" />
                </Button>
              )}
            </div>
            <div className="text-xs text-slate-500 mt-1">
              Ottienila su <a className="text-blue-700 underline" href="https://resend.com/api-keys" target="_blank" rel="noreferrer">resend.com/api-keys</a>. Serve verificare il dominio del mittente qui sotto.
            </div>
          </div>

          <div>
            <Label>Indirizzo "mittente" per Resend (dominio verificato)</Label>
            <Input
              data-testid="resend-from-input"
              value={apiKeysDraft.resend_from_email}
              onChange={(e) => setApiKeysDraft({ ...apiKeysDraft, resend_from_email: e.target.value })}
              placeholder="es. noreply@tuodominio.it — vuoto = usa onboarding@resend.dev"
            />
          </div>

          <Button data-testid="api-keys-save" onClick={saveApiKeys} disabled={apiKeysSaving} className="bg-slate-900 hover:bg-slate-800 text-white">
            {apiKeysSaving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <CheckCircle2 className="w-4 h-4 mr-2" />}
            Salva chiavi
          </Button>
        </div>
      </Card>

      <Card className="p-6 border-slate-200 bg-white mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Archive className="w-5 h-5 text-blue-700" />
          <h2 className="font-bold font-display text-lg text-slate-900">Backup automatico</h2>
        </div>
        <p className="text-sm text-slate-600 mb-4 leading-relaxed">
          Ogni <b>domenica alle 22:00</b> ricevi via email uno zip con <code>clients.csv</code>, <code>contracts.csv</code>, <code>interventions.csv</code>. Conservalo in un posto sicuro: se un giorno perdi accesso all'app, puoi reimportare tutto in un istante.
        </p>
        <a href={weeklyBackupUrl()} target="_blank" rel="noreferrer">
          <Button data-testid="weekly-backup-download" variant="outline">
            <Download className="w-4 h-4 mr-2" />
            Scarica backup adesso
          </Button>
        </a>
      </Card>

      <Card className="p-6 border-slate-200 bg-white">
        <h2 className="font-bold font-display text-lg text-slate-900 mb-3">Ultimi reminder inviati</h2>
        {log.length === 0 ? (
          <div className="text-sm text-slate-500 py-6 text-center">Nessun reminder ancora inviato.</div>
        ) : (
          <div className="space-y-2 text-sm">
            {log.slice(0, 20).map((r, i) => (
              <div key={i} className="flex items-center justify-between p-2 border-b border-slate-100">
                <div>
                  <span className="font-mono text-xs">{r.date}</span> · <span>{r.recipient}</span>
                </div>
                <span className="text-xs text-slate-400 font-mono">{new Date(r.sent_at).toLocaleString("it-IT")}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
