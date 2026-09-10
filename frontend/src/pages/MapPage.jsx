import { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup, Polyline } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { listClients, listInterventions, listContracts } from "../lib/api";
import { Card } from "../components/ui/card";
import { Switch } from "../components/ui/switch";
import { MapPin, Route as RouteIcon } from "lucide-react";

// Fix default icon paths for webpack builds
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

const ITALY_CENTER = [41.9, 12.5];

export default function MapPage() {
  const [clients, setClients] = useState([]);
  const [ivs, setIvs] = useState([]);
  const [contracts, setContracts] = useState([]);
  const [showRoute, setShowRoute] = useState(false);

  useEffect(() => {
    Promise.all([listClients(), listInterventions(), listContracts()])
      .then(([cl, iv, c]) => { setClients(cl); setIvs(iv); setContracts(c); })
      .catch(() => {});
  }, []);

  const geoClients = clients.filter((c) => c.lat && c.lng);
  const clientById = useMemo(() => {
    const m = {}; for (const c of clients) m[c.id] = c; return m;
  }, [clients]);
  const contractById = useMemo(() => {
    const m = {}; for (const c of contracts) m[c.id] = c; return m;
  }, [contracts]);

  // Compute upcoming route: chronological interventions from today onwards
  const today = new Date().toISOString().slice(0, 10);
  const upcoming = useMemo(() => {
    return ivs
      .filter((iv) => iv.date >= today)
      .sort((a, b) => a.date.localeCompare(b.date))
      .map((iv) => {
        const cli = clientById[iv.client_id];
        return cli && cli.lat && cli.lng ? { ...iv, client: cli } : null;
      })
      .filter(Boolean)
      .slice(0, 20);
  }, [ivs, clientById, today]);

  const routeCoords = upcoming.map((iv) => [iv.client.lat, iv.client.lng]);

  // Fit bounds: use average of client coords
  const center = geoClients.length
    ? [
        geoClients.reduce((s, c) => s + c.lat, 0) / geoClients.length,
        geoClients.reduce((s, c) => s + c.lng, 0) / geoClients.length,
      ]
    : ITALY_CENTER;

  const clientIvCount = (id) => ivs.filter((iv) => iv.client_id === id && iv.date >= today).length;

  return (
    <div data-testid="map-section" className="max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-6">
        <div>
          <div className="text-xs font-medium tracking-wider uppercase text-slate-500">Geografia</div>
          <h1 className="mt-1 text-3xl sm:text-4xl font-extrabold font-display text-slate-900">Mappa clienti</h1>
          <p className="mt-2 text-slate-600">{geoClients.length} clienti geolocalizzati · {upcoming.length} interventi imminenti</p>
        </div>
        <div className="flex items-center gap-3 p-3 bg-white border border-slate-200 rounded-lg">
          <RouteIcon className="w-4 h-4 text-blue-700" />
          <span className="text-sm font-medium text-slate-900">Percorso interventi imminenti</span>
          <Switch data-testid="toggle-route" checked={showRoute} onCheckedChange={setShowRoute} />
        </div>
      </div>

      {geoClients.length === 0 ? (
        <Card className="p-12 text-center border-slate-200 bg-white">
          <MapPin className="w-8 h-8 text-slate-400 mx-auto mb-3" />
          <p className="text-slate-600">Nessun cliente geolocalizzato ancora. Aggiungi clienti con indirizzo valido per vederli sulla mappa.</p>
        </Card>
      ) : (
        <Card className="p-0 border-slate-200 bg-white overflow-hidden">
          <div style={{ height: "70vh", minHeight: "500px" }}>
            <MapContainer center={center} zoom={6} style={{ height: "100%", width: "100%" }} scrollWheelZoom>
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              {geoClients.map((c) => {
                const count = clientIvCount(c.id);
                return (
                  <Marker key={c.id} position={[c.lat, c.lng]}>
                    <Popup>
                      <div style={{ minWidth: 180 }}>
                        <div style={{ fontWeight: 700, marginBottom: 4 }}>{c.name}</div>
                        <div style={{ fontSize: 12, color: "#475569" }}>
                          {c.address}{c.city ? `, ${c.city}` : ""}
                        </div>
                        {c.contact_name && <div style={{ fontSize: 12, marginTop: 4 }}>{c.contact_name}</div>}
                        {c.phone && <div style={{ fontSize: 12 }}>{c.phone}</div>}
                        <div style={{ fontSize: 11, marginTop: 6, padding: "3px 6px", background: "#EFF6FF", color: "#1D4ED8", borderRadius: 4, display: "inline-block" }}>
                          {count} interventi programmati
                        </div>
                      </div>
                    </Popup>
                  </Marker>
                );
              })}
              {showRoute && routeCoords.length > 1 && (
                <Polyline positions={routeCoords} pathOptions={{ color: "#1E40AF", weight: 3, opacity: 0.7, dashArray: "8, 4" }} />
              )}
            </MapContainer>
          </div>
          {showRoute && upcoming.length > 0 && (
            <div className="p-4 border-t border-slate-100 bg-slate-50/50">
              <div className="text-xs font-medium tracking-wider uppercase text-slate-500 mb-2">Ordine visite (prossimi {upcoming.length})</div>
              <div className="flex flex-wrap gap-2">
                {upcoming.map((iv, idx) => (
                  <div key={iv.id} className="flex items-center gap-1.5 text-xs bg-white border border-slate-200 rounded px-2 py-1">
                    <span className="w-5 h-5 bg-blue-700 text-white rounded-full flex items-center justify-center text-[10px] font-bold">{idx + 1}</span>
                    <span className="font-medium text-slate-900">{iv.client.name}</span>
                    <span className="text-slate-500 font-mono">{iv.date}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
