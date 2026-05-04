/**
 * api.js — Thin wrapper around the Drop Report REST API.
 * Stores the JWT in sessionStorage so it's cleared on tab close.
 */

const API = (() => {
  const BASE = '';   // same origin (FastAPI serves frontend)
  const TOKEN_KEY = 'dr_token';

  function getToken() {
    return sessionStorage.getItem(TOKEN_KEY);
  }

  function setToken(t) {
    sessionStorage.setItem(TOKEN_KEY, t);
  }

  function clearToken() {
    sessionStorage.removeItem(TOKEN_KEY);
  }

  function isLoggedIn() {
    return !!getToken();
  }

  async function request(method, path, body = null, isFormData = false) {
    const headers = {};
    const token = getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
    if (body && !isFormData) headers['Content-Type'] = 'application/json';

    const opts = { method, headers };
    if (body) opts.body = isFormData ? body : JSON.stringify(body);

    const res = await fetch(BASE + path, opts);

    if (res.status === 401) {
      clearToken();
      window.location.reload();
      throw new Error('Session expirada');
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Error desconocido');
    }

    return res.json();
  }

  return {
    getToken,
    setToken,
    clearToken,
    isLoggedIn,

    // Auth
    login: (username, password) =>
      request('POST', '/api/auth/login', { username, password }),

    changePassword: (old_password, new_password) =>
      request('POST', '/api/auth/change-password', { old_password, new_password }),

    // Dashboard
    getKpis: (params = {}) =>
      request('GET', '/api/kpis' + toQuery(params)),

    getStatusChart: (params = {}) =>
      request('GET', '/api/charts/status' + toQuery(params)),

    getTrendChart: (params = {}) =>
      request('GET', '/api/charts/trend' + toQuery(params)),

    getProductsChart: (params = {}) =>
      request('GET', '/api/charts/products' + toQuery(params)),

    getCarriersChart: (params = {}) =>
      request('GET', '/api/charts/carriers' + toQuery(params)),

    getFilterOptions: () =>
      request('GET', '/api/filters/options'),

    // Uploads
    uploadFile: (file) => {
      const fd = new FormData();
      fd.append('file', file);
      return request('POST', '/api/upload', fd, true);
    },

    listUploads: () =>
      request('GET', '/api/uploads'),

    // Calls
    getPendingCalls: (params = {}) =>
      request('GET', '/api/calls/pending' + toQuery(params)),

    saveCallNote: (order_id, resultado, notas) =>
      request('POST', '/api/calls/notes', { order_id, resultado, notas }),

    getCallNotes: (order_id) =>
      request('GET', `/api/calls/notes/${order_id}`),
    // Users
    listUsers: () =>
      request('GET', '/api/users'),

    createUser: (username, password, role) =>
      request('POST', '/api/users', { username, password, role }),
  };

  function toQuery(params) {
    const q = Object.entries(params)
      .filter(([, v]) => v !== null && v !== undefined && v !== '')
      .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
      .join('&');
    return q ? '?' + q : '';
  }
})();
