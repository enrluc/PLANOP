import { useEffect, useRef, useState } from "react";
import { aiPlanningChat, aiChatHistory, aiAnalyzeContract, aiAnalyzeContractPdf, listClients, createClient, createContract } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import { Sparkles, Send, FileSearch, Wand2, Loader2, User, Upload, FileText } from "lucide-react";
import { toast } from "sonner";

function Chat() {
  const [session] = useState(() => `plan-${Date.now()}`);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const listRef = useRef(null);

  useEffect(() => {
    aiChatHistory(session).then(setMessages).catch(() => {});
  }, [session]);

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages]);

  const send = async () => {
    if (!input.trim()) return;
    const msg = input; setInput("");
    setMessages((m) => [...m, { role: "user", content: msg }]);
    setLoading(true);
    try {
      const r = await aiPlanningChat(msg, session);
      setMessages((m) => [...m, { role: "assistant", content: r.reply }]);
    } catch (_e) { toast.error("Errore AI"); }
    finally { setLoading(false); }
  };

  return (
    <Card className="p-0 border-slate-200 bg-white overflow-hidden">
      <div className="p-4 border-b border-slate-100 flex items-center gap-2">
        <Sparkles className="w-4 h-4 text-blue-700" />
        <span className="font-bold font-display text-slate-900">Assistente Planning</span>
        <span className="text-xs text-slate-500 ml-auto font-mono">Claude Haiku 4.5</span>
      </div>
      <div ref={listRef} className="p-4 h-[420px] overflow-y-auto space-y-3 bg-slate-50/50">
        {messages.length === 0 && (
          <div className="text-center text-sm text-slate-500 py-8">
            Fai una domanda: <span className="italic">"Quando ho spazio per un nuovo contratto di 4 giorni a Milano?"</span>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} data-testid={`chat-msg-${i}`} className={`flex gap-2 ${m.role === "user" ? "justify-end" : ""}`}>
            {m.role === "assistant" && (
              <div className="w-7 h-7 rounded-full bg-slate-900 flex items-center justify-center flex-shrink-0">
                <Sparkles className="w-3.5 h-3.5 text-white" />
              </div>
            )}
            <div className={`max-w-[80%] px-3 py-2 rounded-lg text-sm whitespace-pre-wrap ${
              m.role === "user" ? "bg-slate-900 text-white" : "bg-white border border-slate-200 text-slate-900"
            }`}>
              {m.content}
            </div>
            {m.role === "user" && (
              <div className="w-7 h-7 rounded-full bg-slate-200 flex items-center justify-center flex-shrink-0">
                <User className="w-3.5 h-3.5 text-slate-700" />
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="flex gap-2">
            <div className="w-7 h-7 rounded-full bg-slate-900 flex items-center justify-center">
              <Loader2 className="w-3.5 h-3.5 text-white animate-spin" />
            </div>
            <div className="px-3 py-2 rounded-lg text-sm bg-white border border-slate-200 text-slate-500">Sto pensando…</div>
          </div>
        )}
      </div>
      <div className="p-3 border-t border-slate-100 flex gap-2">
        <Input
          data-testid="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
          placeholder="Scrivi una domanda…"
          disabled={loading}
        />
        <Button data-testid="chat-send" onClick={send} disabled={loading || !input.trim()} className="bg-slate-900 hover:bg-slate-800 text-white">
          <Send className="w-4 h-4" />
        </Button>
      </div>
    </Card>
  );
}

function Analyze() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [meta, setMeta] = useState(null);
  const [clients, setClients] = useState([]);
  const fileRef = useRef(null);

  useEffect(() => { listClients().then(setClients).catch(() => {}); }, []);

  const analyze = async () => {
    if (!text.trim()) return;
    setLoading(true); setResult(null); setMeta(null);
    try {
      const r = await aiAnalyzeContract(text);
      setResult(r.extracted);
      toast.success("Contratto analizzato");
    } catch (_e) { toast.error("Estrazione fallita"); }
    finally { setLoading(false); }
  };

  const analyzePdf = async (file) => {
    if (!file) return;
    if (file.size > 15 * 1024 * 1024) { toast.error("PDF troppo grande (max 15MB)"); return; }
    setLoading(true); setResult(null); setMeta(null); setText("");
    try {
      const r = await aiAnalyzeContractPdf(file);
      setResult(r.extracted);
      setMeta({ pages: r.pages, chars: r.chars_extracted, filename: file.name });
      toast.success(`PDF letto (${r.pages} pagine) e analizzato`);
    } catch (e) {
      const msg = e?.response?.data?.detail || "Estrazione PDF fallita";
      toast.error(String(msg));
    }
    finally { setLoading(false); if (fileRef.current) fileRef.current.value = ""; }
  };

  const createFromResult = async () => {
    if (!result) return;
    try {
      // Match/create client
      let client = clients.find((c) => c.name.toLowerCase() === (result.client_name || "").toLowerCase());
      if (!client && result.client_name) {
        client = await createClient({
          name: result.client_name,
          address: result.address || result.city || "N/D",
          city: result.city || "",
          contact_name: result.contact_name || "",
          phone: result.phone || "",
          email: result.email || "",
          notes: "",
        });
        toast.success("Cliente creato");
      }
      if (!client) { toast.error("Nome cliente mancante"); return; }
      await createContract({
        client_id: client.id,
        title: result.title || "Attività",
        total_days: Number(result.total_days) || 1,
        daily_rate: Number(result.daily_rate) || 0,
        intervention_type: result.intervention_type || "consulenza",
        priority: ["high","medium","low"].includes(result.priority) ? result.priority : "medium",
        start_date: result.start_date || null,
        deadline: result.deadline || null,
        signed_date: result.signed_date || null,
        notes: result.notes || "",
      });
      toast.success("Contratto creato dal PDF");
      setText(""); setResult(null);
    } catch (_e) { toast.error("Creazione fallita"); }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <Card className="p-5 border-slate-200 bg-white">
        <div className="flex items-center gap-2 mb-3">
          <FileSearch className="w-4 h-4 text-blue-700" />
          <span className="font-bold font-display text-slate-900">Contratto</span>
        </div>
        <input
          ref={fileRef}
          type="file"
          accept="application/pdf,.pdf"
          data-testid="analyze-pdf-input"
          className="hidden"
          onChange={(e) => analyzePdf(e.target.files?.[0])}
        />
        <Button
          data-testid="analyze-pdf-button"
          variant="outline"
          onClick={() => fileRef.current?.click()}
          disabled={loading}
          className="w-full mb-3 border-dashed border-2 h-16 text-slate-700 hover:bg-slate-50"
        >
          <Upload className="w-5 h-5 mr-2 text-blue-700" />
          <div className="text-left">
            <div className="text-sm font-semibold">Carica PDF firmato</div>
            <div className="text-xs text-slate-500 font-normal">Claude lo legge e estrae i dati</div>
          </div>
        </Button>
        {meta && (
          <div className="mb-3 text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded p-2 flex items-center gap-2">
            <FileText className="w-3.5 h-3.5" />
            <span>{meta.filename} · {meta.pages} pagine · {meta.chars} caratteri estratti</span>
          </div>
        )}
        <div className="text-xs text-slate-400 text-center my-2">— oppure —</div>
        <Textarea
          data-testid="analyze-text-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Incolla qui il testo del contratto…"
          className="min-h-[200px] font-mono text-xs"
        />
        <Button
          data-testid="analyze-run"
          onClick={analyze}
          disabled={loading || !text.trim()}
          className="mt-3 w-full bg-slate-900 hover:bg-slate-800 text-white"
        >
          {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Wand2 className="w-4 h-4 mr-2" />}
          {loading ? "Analisi in corso…" : "Analizza testo con AI"}
        </Button>
      </Card>
      <Card className="p-5 border-slate-200 bg-white">
        <div className="flex items-center gap-2 mb-3">
          <Sparkles className="w-4 h-4 text-blue-700" />
          <span className="font-bold font-display text-slate-900">Dati estratti</span>
        </div>
        {!result ? (
          <div className="text-sm text-slate-500 py-12 text-center">L'estrazione apparirà qui.</div>
        ) : (
          <div className="space-y-2 text-sm">
            {[
              ["Cliente", result.client_name],
              ["Città", result.city],
              ["Indirizzo", result.address],
              ["Referente", result.contact_name],
              ["Telefono", result.phone],
              ["Email", result.email],
              ["Titolo attività", result.title],
              ["Giorni totali", result.total_days],
              ["Tariffa €/g", result.daily_rate],
              ["Tipologia", result.intervention_type],
              ["Priorità", result.priority],
              ["Inizio", result.start_date],
              ["Scadenza", result.deadline],
              ["Firmato il", result.signed_date],
              ["Note", result.notes],
            ].map(([k, v]) => (v ? (
              <div key={k} className="flex justify-between gap-2 py-1 border-b border-slate-100">
                <span className="text-slate-500 text-xs uppercase tracking-wider">{k}</span>
                <span className="text-slate-900 font-medium text-right">{String(v)}</span>
              </div>
            ) : null))}
            <Button data-testid="analyze-create" onClick={createFromResult} className="w-full mt-4 bg-slate-900 hover:bg-slate-800 text-white">
              Crea cliente e contratto
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}

export default function AIAssistant() {
  return (
    <div data-testid="ai-assistant-section" className="max-w-7xl mx-auto">
      <div className="mb-8">
        <div className="text-xs font-medium tracking-wider uppercase text-slate-500 flex items-center gap-2">
          <Sparkles className="w-3 h-3" /> Powered by Claude Haiku 4.5
        </div>
        <h1 className="mt-1 text-3xl sm:text-4xl font-extrabold font-display text-slate-900">Assistente AI</h1>
        <p className="mt-2 text-slate-600">Chatta con Claude sul tuo planning o incolla un contratto per estrarne i dati automaticamente.</p>
      </div>
      <Tabs defaultValue="chat">
        <TabsList data-testid="ai-tabs" className="bg-white border border-slate-200">
          <TabsTrigger data-testid="tab-chat" value="chat">Chat Planning</TabsTrigger>
          <TabsTrigger data-testid="tab-analyze" value="analyze">Analizza Contratto</TabsTrigger>
        </TabsList>
        <TabsContent value="chat" className="mt-4">
          <Chat />
        </TabsContent>
        <TabsContent value="analyze" className="mt-4">
          <Analyze />
        </TabsContent>
      </Tabs>
    </div>
  );
}
