/**
 * app.js — Main controller: auth, navigation, data loading, call center.
 */

function formatLocalDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function shiftDays(date, days) {
  const shifted = new Date(date);
  shifted.setDate(shifted.getDate() + days);
  return shifted;
}

function startOfWeekMonday(date) {
  const start = new Date(date);
  const day = start.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  start.setDate(start.getDate() + diff);
  start.setHours(0, 0, 0, 0);
  return start;
}

const todayLocal = new Date();

/* ═══════════════════════════ STATE ═════════════════════════════════ */
const state = {
  filters: { 
    date_from: formatLocalDate(shiftDays(todayLocal, -29)),
    date_to: formatLocalDate(todayLocal),
    estatus: null 
  },
  activeTab: 'dashboard',
  currentUser: null,
  callFilter: 'all',
};

/* ═══════════════════════════ BOOT ══════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
  if (API.isLoggedIn()) {
    showApp();
  } else {
    showLogin();
  }
});

/* ═══════════════════════════ LOGIN ════════════════════════════════ */
function showLogin() {
  document.getElementById('login-screen').classList.remove('hidden');
  document.getElementById('app').classList.add('hidden');
}

function showApp() {
  document.getElementById('login-screen').classList.add('hidden');
  document.getElementById('app').classList.remove('hidden');

  // Decode username from JWT payload (middle segment)
  try {
    const payload = JSON.parse(atob(API.getToken().split('.')[1]));
    state.currentUser = payload;
    document.getElementById('sidebar-username').textContent = payload.sub;

    if (payload.role === 'admin') {
      document.getElementById('nav-users').classList.remove('hidden');
      document.getElementById('nav-projection').classList.remove('hidden');
    }
  } catch (_) {}

  initFilters();
  loadDashboard();
  loadCallsPending();
}

document.getElementById('login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = document.getElementById('login-btn');
  const err = document.getElementById('login-error');
  err.classList.add('hidden');
  btn.textContent = 'Ingresando...';
  btn.disabled = true;

  try {
    const res = await API.login(
      document.getElementById('login-user').value.trim(),
      document.getElementById('login-pass').value,
    );
    API.setToken(res.access_token);
    showApp();
  } catch (ex) {
    err.textContent = ex.message;
    err.classList.remove('hidden');
  } finally {
    btn.textContent = 'Ingresar';
    btn.disabled = false;
  }
});

document.getElementById('logout-btn').addEventListener('click', () => {
  API.clearToken();
  showLogin();
});

/* ═══════════════════════════ NAVIGATION ═══════════════════════════ */
document.querySelectorAll('.nav-item').forEach(link => {
  link.addEventListener('click', (e) => {
    e.preventDefault();
    switchTab(link.dataset.tab);
  });
});

function switchTab(tab) {
  state.activeTab = tab;
  document.querySelectorAll('.nav-item').forEach(l => l.classList.toggle('active', l.dataset.tab === tab));
  document.querySelectorAll('.tab-content').forEach(s => s.classList.toggle('hidden', s.id !== `tab-${tab}`));
  document.getElementById('page-title').textContent =
    { dashboard: 'Dashboard', calls: 'Panel de Llamadas', users: 'Gestión de Usuarios', control: 'Control Diario', mappings: 'Asignación de Campañas', projection: 'Supuestos de Proyección' }[tab];

  if (tab === 'users') {
    loadUsers();
  } else if (tab === 'mappings') {
    loadMappings();
  } else if (tab === 'projection') {
    loadProjectionConfigs();
  }
}

/* ═══════════════════════════ FILTERS ══════════════════════════════ */
async function initFilters() {
  try {
    const opts = await API.getFilterOptions();
    const sel = document.getElementById('filter-estatus');
    sel.innerHTML = '<option value="">Todos los estados</option>';
    (opts.estatus || []).forEach(s => {
      const opt = document.createElement('option');
      opt.value = s;
      opt.textContent = s;
      sel.appendChild(opt);
    });
  } catch (_) {}
}

document.getElementById('filter-preset').addEventListener('change', (e) => {
  const df = document.getElementById('filter-date-from');
  const dt = document.getElementById('filter-date-to');
  const val = e.target.value;

  df.classList.add('hidden');
  dt.classList.add('hidden');

  const today = new Date();
  const setClosedWeek = (weeksAgo) => {
    const currentWeekStart = startOfWeekMonday(today);
    const from = shiftDays(currentWeekStart, -7 * weeksAgo);
    const to = shiftDays(from, 6);
    state.filters.date_from = formatLocalDate(from);
    state.filters.date_to = formatLocalDate(to);
  };

  if (val === 'today') {
    state.filters.date_from = formatLocalDate(today);
    state.filters.date_to   = formatLocalDate(today);
  } else if (val === '7d') {
    const from = shiftDays(today, -6);
    state.filters.date_from = formatLocalDate(from);
    state.filters.date_to   = formatLocalDate(today);
  } else if (val === '1w_ago') {
    setClosedWeek(1);
  } else if (val === '2w_ago') {
    setClosedWeek(2);
  } else if (val === '3w_ago') {
    setClosedWeek(3);
  } else if (val === '30d') {
    const from = shiftDays(today, -29);
    state.filters.date_from = formatLocalDate(from);
    state.filters.date_to   = formatLocalDate(today);
  } else if (val === 'custom') {
    df.classList.remove('hidden');
    dt.classList.remove('hidden');
    return;
  }

  loadDashboard();
});

['filter-date-from', 'filter-date-to'].forEach(id => {
  document.getElementById(id).addEventListener('change', (e) => {
    state.filters[id === 'filter-date-from' ? 'date_from' : 'date_to'] = e.target.value || null;
    loadDashboard();
  });
});

document.getElementById('filter-estatus').addEventListener('change', (e) => {
  state.filters.estatus = e.target.value || null;
  loadDashboard();
});

/* ═══════════════════════════ DASHBOARD ════════════════════════════ */
async function loadDashboard() {
  const f = state.filters;
  const params = { date_from: f.date_from, date_to: f.date_to, estatus: f.estatus };

  try {
    const [kpis, status, trend, products, carriers, daily] = await Promise.all([
      API.getKpis(params),
      API.getStatusChart({ date_from: f.date_from, date_to: f.date_to }),
      API.getTrendChart({ date_from: f.date_from, date_to: f.date_to }),
      API.getProductsChart({ date_from: f.date_from, date_to: f.date_to }),
      API.getCarriersChart({ date_from: f.date_from, date_to: f.date_to }),
      API.getDailyControl({ date_from: f.date_from, date_to: f.date_to }),
    ]);

    renderKpis(kpis);
    CHARTS.renderStatus(status);
    CHARTS.renderTrend(trend);
    renderProductsTable(products);
    CHARTS.renderCarriers(carriers);
    renderDailyControl(daily);

    document.getElementById('last-updated').textContent =
      'Actualizado: ' + new Date().toLocaleTimeString('es-CO');
  } catch (err) {
    console.error('Dashboard load error:', err);
  }
}

function renderKpis(k) {
  const fmt = CHARTS.formatCOP;

  const valProy = k.ganancia_proyectada || 0;
  const valConf = k.ganancia_real || 0;

  document.getElementById('val-ganancia').textContent    = fmt(valProy);
  document.getElementById('val-confirmada').textContent  = fmt(valConf);
  document.getElementById('val-ads').textContent         = fmt(k.ad_spend || 0);
  document.getElementById('val-pedidos').textContent     = k.volumen_pedidos ?? '—';
  document.getElementById('val-tasa').textContent        = k.tasa_entrega != null ? `${k.tasa_entrega}%` : '—';
  document.getElementById('val-devolucion').textContent  = k.tasa_devolucion != null ? `${k.tasa_devolucion}%` : '—';
  document.getElementById('val-cancelacion').textContent = k.tasa_cancelacion != null ? `${k.tasa_cancelacion}%` : '—';
  document.getElementById('val-cierre').textContent      = k.tasa_cierre_logistico != null ? `${k.tasa_cierre_logistico}%` : '—';

  // Dynamic colors
  const cardProy = document.getElementById('kpi-ganancia');
  const cardConf = document.getElementById('kpi-confirmada');
  const cardClosure = document.getElementById('kpi-cierre');

  cardProy.classList.toggle('kpi-green', valProy >= 0);
  cardProy.classList.toggle('kpi-red', valProy < 0);
  
  cardConf.classList.toggle('kpi-green', valConf >= 0);
  cardConf.classList.toggle('kpi-red', valConf < 0);

  const closureRate = k.tasa_cierre_logistico ?? 0;
  cardClosure.classList.toggle('kpi-green', closureRate >= 100);
  cardClosure.classList.toggle('kpi-amber', closureRate < 100 && closureRate > 0);
  cardClosure.classList.toggle('kpi-red', closureRate === 0);

  document.getElementById('sub-ads').textContent = 
    `Inversión Meta Ads ${k.ads_iva > 0 ? `(+${k.ads_iva.toFixed(0)}% IVA)` : ''}`;

  document.getElementById('sub-pedidos').textContent =
    `${k.entregados ?? 0} entregados · ${k.requieren_accion ?? 0} requieren gestión`;
  document.getElementById('sub-tasa').textContent =
    `${k.entregados ?? 0} entregados / ${(k.entregados ?? 0) + (k.devoluciones ?? 0)} cierres logísticos`;
  document.getElementById('sub-devolucion').textContent =
    `${k.devoluciones ?? 0} devoluciones / ${(k.entregados ?? 0) + (k.devoluciones ?? 0)} cierres logísticos`;
  document.getElementById('sub-cancelacion').textContent =
    `${k.cancelados ?? 0} cancelados / ${k.volumen_pedidos ?? 0} pedidos totales`;
  document.getElementById('sub-cierre').textContent =
    `${k.en_curso_logistico ?? 0} en curso / ${Math.max((k.volumen_pedidos ?? 0) - (k.cancelados ?? 0), 0)} no cancelados`;

  // Update calls badge
  const badge = document.getElementById('calls-badge');
  if (k.requieren_accion > 0) {
    badge.textContent = k.requieren_accion;
    badge.classList.remove('hidden');
  } else {
    badge.classList.add('hidden');
  }
}

function renderDailyControl(data) {
  const tbody = document.querySelector('#control-table tbody');
  if (!data || data.length === 0) {
    tbody.innerHTML = '<tr><td colspan="12" class="empty-row">No hay datos en el período</td></tr>';
    return;
  }
  
  const fmt = CHARTS.formatCOP;
  const fmtPct = (val) => (val != null && isFinite(val) ? (val * 100).toFixed(1) : '0.0') + '%';
  const fmtNum = (val) => (val != null && isFinite(val) ? Number(val).toFixed(2).replace(/\.00$/, '') : '0');
  const fmtDate = (iso) => {
    if (!iso || !iso.includes('-')) return iso || '—';
    const [y, m, d] = iso.split('-');
    return `${d}/${m}/${y}`;
  };

  const rows = data.map(r => `
    <tr>
      <td>${fmtDate(r.fecha)}</td>
      <td title="${r.producto}" style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
        ${r.producto}
      </td>
      <td>${r.ventas_dia}</td>
      <td>${r.ventas_canceladas}</td>
      <td>${fmtPct(r.pct_cancelado)}</td>
      <td>${fmtPct(r.pct_devolucion)}</td>
      <td>${fmtNum(r.ventas_efectivas)}</td>
      <td style="color: var(--amber)">${fmt(r.ad_spend)}</td>
      <td>${fmt(r.cpa)}</td>
      <td>${fmt(r.utilidad_unitaria)}</td>
      <td style="color: ${r.utilidad_total >= 0 ? 'var(--green)' : 'var(--red)'}; font-weight: 600;">
        ${fmt(r.utilidad_total)}
      </td>
      <td>${fmtPct(r.roi)}</td>
    </tr>
  `).join('');

  // Totals row
  const tot = data.reduce((acc, r) => {
    acc.ventas_dia         += r.ventas_dia || 0;
    acc.ventas_canceladas  += r.ventas_canceladas || 0;
    acc.ventas_efectivas   += r.ventas_efectivas || 0;
    acc.ad_spend           += r.ad_spend || 0;
    acc.utilidad_total     += r.utilidad_total || 0;
    return acc;
  }, { ventas_dia:0, ventas_canceladas:0, ventas_efectivas:0, ad_spend:0, utilidad_total:0 });

  const totPctCancelado = tot.ventas_dia > 0 ? tot.ventas_canceladas / tot.ventas_dia : 0;
  const weightedDevNumerator = data.reduce((sum, r) => sum + ((r.pct_devolucion || 0) * (r.ventas_dia || 0)), 0);
  const totPctDevolucion = tot.ventas_dia > 0 ? weightedDevNumerator / tot.ventas_dia : 0;
  const totCpa = tot.ventas_efectivas > 0 ? tot.ad_spend / tot.ventas_efectivas : 0;
  const totUtilidadUnit = tot.ventas_efectivas > 0 ? tot.utilidad_total / tot.ventas_efectivas : 0;
  const totRoi = tot.ad_spend > 0 ? tot.utilidad_total / tot.ad_spend : 0;

  const totalsRow = `
    <tr style="font-weight:700; background: rgba(255,255,255,0.05); border-top: 2px solid rgba(255,255,255,0.2);">
      <td colspan="2" style="text-align:right; padding-right: 12px;">TOTAL</td>
      <td>${tot.ventas_dia}</td>
      <td>${tot.ventas_canceladas}</td>
      <td>${fmtPct(totPctCancelado)}</td>
      <td>${fmtPct(totPctDevolucion)}</td>
      <td>${fmtNum(tot.ventas_efectivas)}</td>
      <td style="color: var(--amber)">${fmt(tot.ad_spend)}</td>
      <td>${fmt(totCpa)}</td>
      <td>${fmt(totUtilidadUnit)}</td>
      <td style="color: ${tot.utilidad_total >= 0 ? 'var(--green)' : 'var(--red)'};">${fmt(tot.utilidad_total)}</td>
      <td>${fmtPct(totRoi)}</td>
    </tr>
  `;

  tbody.innerHTML = rows + totalsRow;
}

async function loadProjectionConfigs() {
  try {
    const rows = await API.getProjectionConfigs();
    const tbody = document.querySelector('#projection-table tbody');
    if (!rows || rows.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="empty-row">No hay productos disponibles.</td></tr>';
      return;
    }

    tbody.innerHTML = rows.map((r, i) => `
      <tr>
        <td title="${r.producto}">${r.producto}</td>
        <td><input class="table-input projection-input" data-field="pct_devolucion" data-index="${i}" type="number" min="0" max="0.99" step="0.01" value="${Number(r.effective_pct_devolucion || 0).toFixed(2)}"></td>
        <td><input class="table-input projection-input" data-field="flete_base_dev" data-index="${i}" type="number" min="0" step="1" value="${Math.round(r.effective_flete_base_dev || 0)}"></td>
        <td><input class="table-input projection-input" data-field="precio_venta" data-index="${i}" type="number" min="0" step="1" value="${Math.round(r.effective_precio_venta || 0)}"></td>
        <td><input class="table-input projection-input" data-field="costo_proveedor" data-index="${i}" type="number" min="0" step="1" value="${Math.round(r.effective_costo_proveedor || 0)}"></td>
        <td><span class="chip ${r.has_custom_config ? 'chip-green' : 'chip-gray'}">${r.has_custom_config ? 'Manual' : 'Fallback'}</span></td>
        <td>
          <button class="btn btn-primary btn-sm projection-save-btn" data-index="${i}">Guardar</button>
        </td>
      </tr>
    `).join('');

    document.querySelectorAll('.projection-save-btn').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const idx = Number(btn.dataset.index);
        const row = rows[idx];
        const getInput = (field) => document.querySelector(`.projection-input[data-index="${idx}"][data-field="${field}"]`);
        const payload = {
          producto: row.producto,
          pct_devolucion: Number(getInput('pct_devolucion').value || 0),
          flete_base_dev: Number(getInput('flete_base_dev').value || 0),
          precio_venta: Number(getInput('precio_venta').value || 0),
          costo_proveedor: Number(getInput('costo_proveedor').value || 0),
        };

        btn.disabled = true;
        const previous = btn.textContent;
        btn.textContent = 'Guardando...';
        try {
          await API.saveProjectionConfig(payload);
          btn.textContent = 'Guardado';
          setTimeout(() => {
            btn.textContent = previous;
            loadProjectionConfigs();
            loadDashboard();
          }, 700);
        } catch (err) {
          btn.textContent = 'Error';
          setTimeout(() => {
            btn.textContent = previous;
          }, 1200);
          alert('Error guardando supuestos: ' + err.message);
        } finally {
          btn.disabled = false;
        }
      });
    });
  } catch (err) {
    console.error(err);
    document.querySelector('#projection-table tbody').innerHTML =
      `<tr><td colspan="7" class="empty-row">Error al cargar supuestos: ${err.message}</td></tr>`;
  }
}

async function loadMappings() {
  try {
    const data = await API.getMappings();
    const tbody = document.querySelector('#mappings-table tbody');
    if (!data.mappings || data.mappings.length === 0) {
      tbody.innerHTML = '<tr><td colspan="2" class="empty-row">No hay campañas registradas aún.</td></tr>';
      return;
    }

    const productsHtml = `<option value="">-- Sin asignar --</option>` + 
      data.products.map(p => `<option value="${p}">${p}</option>`).join('');

    tbody.innerHTML = data.mappings.map(m => `
      <tr>
        <td><strong>${m.campaign_name}</strong></td>
        <td>
          <select class="select-input product-mapping-select" data-campaign="${m.campaign_name}">
            ${productsHtml}
          </select>
        </td>
      </tr>
    `).join('');

    // Set selected values and add event listeners
    document.querySelectorAll('.product-mapping-select').forEach((sel, i) => {
      sel.value = data.mappings[i].producto || "";
      sel.addEventListener('change', async (e) => {
        const campaign = e.target.dataset.campaign;
        const producto = e.target.value;
        sel.disabled = true;
        try {
          await API.saveMapping(campaign, producto);
          // show a tiny success check next to it? or just flash green
          sel.style.borderColor = 'var(--green)';
          setTimeout(() => sel.style.borderColor = 'var(--border)', 1500);
        } catch(err) {
          alert("Error guardando asignación: " + err.message);
          sel.style.borderColor = 'var(--red)';
        } finally {
          sel.disabled = false;
        }
      });
    });
  } catch (err) {
    console.error(err);
  }
}

function renderProductsTable(products) {
  const tbody = document.getElementById('table-products-body');
  if (!products.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="empty-row">Sin datos</td></tr>';
    return;
  }
  tbody.innerHTML = products.map((p, i) => `
    <tr>
      <td style="color:var(--text-3)">${i + 1}</td>
      <td style="font-weight:500">${p.producto || '—'}</td>
      <td style="font-variant-numeric:tabular-nums">${p.unidades ?? 0}</td>
      <td style="color:var(--text-2)">${p.pedidos ?? 0}</td>
      <td>${CHARTS.formatCOP(p.ingresos)}</td>
    </tr>`).join('');
}

/* ═══════════════════════════ FILE UPLOAD ══════════════════════════ */
function setupUploadHandler(inputId) {
  const el = document.getElementById(inputId);
  if (!el) return;
  
  el.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    await doUpload(file);
    e.target.value = ''; // Reset input after upload
  });
}
setupUploadHandler('upload-dropi');
setupUploadHandler('upload-meta');

async function doUpload(file) {
  const statusEl = document.getElementById('upload-status');

  statusEl.className = 'upload-status';
  statusEl.textContent = `Procesando ${file.name}...`;
  statusEl.classList.remove('hidden');

  try {
    const res = await API.uploadFile(file);

    statusEl.className = 'upload-status';
    statusEl.textContent = `✓ ${res.filename}: ${res.rows_upserted} registros procesados`;
    
    // Refresh everything
    loadDashboard();
    loadCallsPending();
  } catch (err) {
    statusEl.className = 'upload-status error';
    statusEl.textContent = `✗ Error: ${err.message}`;
  }
}


/* ═══════════════════════════ CALL CENTER ══════════════════════════ */
document.querySelectorAll('.call-filter-btn').forEach(btn => {
  btn.addEventListener('click', (e) => {
    state.callFilter = e.target.dataset.filter;
    document.querySelectorAll('.call-filter-btn').forEach(b => {
      b.classList.remove('btn-primary');
      b.classList.add('btn-ghost');
    });
    e.target.classList.remove('btn-ghost');
    e.target.classList.add('btn-primary');
    if (callsData) renderCalls(callsData);
  });
});

let callsData = [];

async function loadCallsPending() {
  try {
    const orders = await API.getPendingCalls();
    callsData = orders;
    renderCalls(callsData);
  } catch (err) {
    document.getElementById('calls-list').innerHTML =
      `<div class="empty-state">Error al cargar: ${err.message}</div>`;
  }
}

document.getElementById('calls-refresh-btn').addEventListener('click', loadCallsPending);

function renderCalls(data) {
  const container = document.getElementById('calls-list');
  document.getElementById('calls-badge').textContent = data.length || '';
  document.getElementById('calls-badge').classList.toggle('hidden', !data.length);

  let filtered = data;
  if (state.callFilter === 'pending') {
    filtered = data.filter(o => 
      !o.ultima_gestion || 
      (['NO_CONTESTO', 'BUZON', 'OTRO'].includes(o.ultima_gestion) && o.intentos < 2)
    );
  } else if (state.callFilter === 'ready') {
    filtered = data.filter(o => 
      ['CONTACTADO', 'SOLUCIONADO', 'DEVOLUCION'].includes(o.ultima_gestion) || 
      o.intentos >= 2
    );
  }

  if (!filtered.length) {
    container.innerHTML = '<div class="empty-state">No hay órdenes en esta categoría.</div>';
    return;
  }

  const resultChip = (r) => {
    if (!r) return '';
    const map = {
      CONTACTADO:  'chip-green',
      SOLUCIONADO: 'chip-green',
      NO_CONTESTO: 'chip-gray',
      BUZON:       'chip-gray',
      DEVOLUCION:  'chip-red',
      OTRO:        'chip-blue',
    };
    return `<span class="chip ${map[r] || 'chip-gray'}">${r}</span>`;
  };

  const statusChip = (s) => {
    const map = {
      'PENDIENTE CONFIRMACION': 'chip-amber',
      'NOVEDAD':                'chip-red',
    };
    return `<span class="chip ${map[s] || 'chip-gray'}">${s}</span>`;
  };

  container.innerHTML = filtered.map(o => {
    let dropiWarning = '';
    if (['CONTACTADO', 'SOLUCIONADO', 'DEVOLUCION'].includes(o.ultima_gestion)) {
      dropiWarning = `<div style="font-size: 0.75rem; color: var(--amber); margin-top: 6px; font-weight: 600;">⚠️ Falta actualizar estado en Dropi</div>`;
    } else if (o.intentos >= 2) {
      dropiWarning = `<div style="font-size: 0.75rem; color: var(--red); margin-top: 6px; font-weight: 600;">🛑 Alcanzó ${o.intentos} intentos. Cancelar orden en Dropi</div>`;
    }

    return `
    <div class="call-card ${o.ultima_gestion ? 'has-note' : 'no-note'}" id="call-card-${o.id}">
      <div class="call-info">
        <div class="call-name">
          ${o.nombre_cliente || 'Cliente sin nombre'}
          ${statusChip(o.estatus)}
          ${resultChip(o.ultima_gestion)}
        </div>
        <div class="call-phone">
          📞 ${o.telefono || 'Sin teléfono'}
          <button class="btn-ghost btn-icon" style="padding: 2px 6px; font-size: 14px; margin-left: 4px;" title="Copiar ID para Dropi" onclick="navigator.clipboard.writeText('${o.id}'); alert('ID ${o.id} copiado al portapapeles. ¡Pégalo en Dropi!');">📋 Copiar ID: ${o.id}</button>
        </div>
        <div class="call-meta">
          <span>📦 ${o.producto || '—'} × ${o.cantidad || 1}</span>
          <span>📍 ${o.ciudad_destino || '—'}, ${o.departamento_destino || '—'}</span>
          <span>🚚 ${o.transportadora || '—'}</span>
          <span>💰 ${CHARTS.formatCOP(o.total_orden)}</span>
          <span>🗓 ${formatIsoDate(o.fecha)}</span>
        </div>
        ${o.novedad ? `<div class="call-meta" style="color:var(--amber)">⚠ Novedad: ${o.novedad}</div>` : ''}
        ${o.ultima_gestion ? `
          <div class="call-note-preview">
            <strong>${o.agente}</strong> · ${formatDatetime(o.fecha_gestion)}<br/>
            ${o.nota_llamada || '(sin notas adicionales)'}
          </div>
          ${dropiWarning}
        ` : ''}
      </div>
      <div class="call-actions">
        ${o.intentos > 0 ? `<div style="font-size: .8rem; color: ${o.intentos >= 2 ? 'var(--red)' : 'var(--text-2)'}; text-align: right; margin-bottom: 4px;">Intentos de llamada: <strong>${o.intentos}</strong></div>` : ''}
        <button class="btn btn-primary btn-sm" onclick="openCallModal(${JSON.stringify(o).replace(/"/g, '&quot;')})">
          ${o.ultima_gestion ? '↻ Actualizar' : '📝 Registrar'}
        </button>
        <a href="tel:${o.telefono}" class="btn btn-green btn-sm">Llamar</a>
      </div>
    </div>`;
  }).join('');
}

/* ═══════════════════════════ CALL MODAL ═══════════════════════════ */
function openCallModal(order) {
  document.getElementById('modal-order-id').value = order.id;
  document.getElementById('modal-resultado').value = '';
  document.getElementById('modal-notas').value = '';

  document.getElementById('modal-order-info').innerHTML = `
    <strong>${order.nombre_cliente}</strong> — ${order.producto}<br/>
    <span>📞 ${order.telefono}</span> &nbsp;|&nbsp;
    <span>📍 ${order.ciudad_destino}</span> &nbsp;|&nbsp;
    <span>Estado: ${order.estatus}</span>
    ${order.novedad ? `<br/><span style="color:var(--amber)">⚠ ${order.novedad}</span>` : ''}
  `;

  document.getElementById('call-modal').classList.remove('hidden');
}

document.getElementById('modal-close').addEventListener('click', closeModal);
document.getElementById('modal-cancel-btn').addEventListener('click', closeModal);
document.getElementById('call-modal').addEventListener('click', (e) => {
  if (e.target === e.currentTarget) closeModal();
});

function closeModal() {
  document.getElementById('call-modal').classList.add('hidden');
}

document.getElementById('call-note-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const orderId  = parseInt(document.getElementById('modal-order-id').value);
  const resultado = document.getElementById('modal-resultado').value;
  const notas     = document.getElementById('modal-notas').value.trim();

  const btn = e.target.querySelector('[type=submit]');
  btn.textContent = 'Guardando...';
  btn.disabled = true;

  try {
    await API.saveCallNote(orderId, resultado, notas);
    closeModal();
    loadCallsPending();  // refresh list
    loadDashboard();     // refresh KPIs
  } catch (err) {
    alert('Error al guardar: ' + err.message);
  } finally {
    btn.textContent = 'Guardar';
    btn.disabled = false;
  }
});

/* ═══════════════════════════ HELPERS ═══════════════════════════════ */
function formatIsoDate(iso) {
  if (!iso) return '—';
  const [y, m, d] = iso.split('-');
  return `${d}/${m}/${y}`;
}

function formatDatetime(dt) {
  if (!dt) return '—';
  return dt.replace('T', ' ').substring(0, 16);
}

/* ═══════════════════════════ USERS MANAGEMENT ═════════════════════ */
async function loadUsers() {
  try {
    const users = await API.listUsers();
    const tbody = document.getElementById('users-body');
    if (!users.length) {
      tbody.innerHTML = '<tr><td colspan="3" class="empty-row">No hay usuarios</td></tr>';
      return;
    }

    const roleMap = { admin: 'Administrador', agent: 'Agente' };
    const roleColor = (r) => r === 'admin' ? 'color:var(--violet-light)' : 'color:var(--text-1)';

    tbody.innerHTML = users.map(u => `
      <tr>
        <td style="color:var(--text-3)">#${u.id}</td>
        <td style="font-weight:500">${u.username}</td>
        <td style="${roleColor(u.role)}">${roleMap[u.role] || u.role}</td>
      </tr>`).join('');
  } catch (err) {
    document.getElementById('users-body').innerHTML = `<tr><td colspan="3" class="empty-row">Error al cargar</td></tr>`;
  }
}

document.getElementById('create-user-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const username = document.getElementById('new-user-name').value.trim();
  const password = document.getElementById('new-user-pass').value;
  const role = document.getElementById('new-user-role').value;
  const msgEl = document.getElementById('new-user-msg');
  const btn = e.target.querySelector('[type=submit]');

  btn.disabled = true;
  msgEl.classList.add('hidden');

  try {
    await API.createUser(username, password, role);
    msgEl.textContent = '¡Usuario creado exitosamente!';
    msgEl.style.color = 'var(--green)';
    msgEl.classList.remove('hidden');
    e.target.reset();
    loadUsers();
  } catch (err) {
    msgEl.textContent = err.message;
    msgEl.style.color = 'var(--red)';
    msgEl.classList.remove('hidden');
  } finally {
    btn.disabled = false;
  }
});
