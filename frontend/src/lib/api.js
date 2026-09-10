import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API,
  withCredentials: true,
});

export const authMe = () => api.get("/auth/me").then((r) => r.data);
export const authProcess = (session_id) =>
  api.post("/auth/session", { session_id }).then((r) => r.data);
export const authLogout = () => api.post("/auth/logout").then((r) => r.data);

export const listClients = () => api.get("/clients").then((r) => r.data);
export const createClient = (data) => api.post("/clients", data).then((r) => r.data);
export const updateClient = (id, data) => api.put(`/clients/${id}`, data).then((r) => r.data);
export const deleteClient = (id) => api.delete(`/clients/${id}`).then((r) => r.data);

export const listContracts = () => api.get("/contracts").then((r) => r.data);
export const createContract = (data) => api.post("/contracts", data).then((r) => r.data);
export const updateContract = (id, data) => api.put(`/contracts/${id}`, data).then((r) => r.data);
export const deleteContract = (id) => api.delete(`/contracts/${id}`).then((r) => r.data);
export const completeContract = (id) => api.post(`/contracts/${id}/complete`).then((r) => r.data);

export const generatePlan = (data) => api.post("/planning/generate", data).then((r) => r.data);
export const listInterventions = () => api.get("/interventions").then((r) => r.data);
export const clearContractPlan = (contract_id) =>
  api.delete(`/interventions/contract/${contract_id}`).then((r) => r.data);
export const reschedulePlan = (data) => api.post("/planning/reschedule", data).then((r) => r.data);

export const listManualEvents = () => api.get("/manual-events").then((r) => r.data);
export const createManualEvent = (data) => api.post("/manual-events", data).then((r) => r.data);
export const deleteManualEvent = (id) => api.delete(`/manual-events/${id}`).then((r) => r.data);

export const getStats = () => api.get("/dashboard/stats").then((r) => r.data);

export const getSubscribeUrl = () => api.get("/calendar/subscribe-url").then((r) => r.data);

export const generateInvoice = async (data) => {
  const resp = await api.post("/invoices/generate", data, { responseType: "blob" });
  return resp.data;
};

export const aiAnalyzeContract = (text) => api.post("/ai/analyze-contract", { text }).then(r => r.data);
export const aiPlanningChat = (message, session_id) =>
  api.post("/ai/planning-chat", { message, session_id }).then(r => r.data);
export const aiChatHistory = (session_id) =>
  api.get("/ai/chat-history", { params: { session_id } }).then(r => r.data);
export const aiDraft = (data) => api.post("/ai/draft", data).then(r => r.data);
