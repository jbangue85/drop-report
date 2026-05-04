/**
 * charts.js — Chart.js wrappers for all four dashboard visualizations.
 */

const CHARTS = (() => {
  // Color palette aligned with CSS tokens
  const COLORS = {
    ENTREGADO:                    '#10b981',
    DESPACHADA:                   '#3b82f6',
    'EN REPARTO':                 '#6366f1',
    'EN ESPERA DE RUTA DOMESTICA':'#8b5cf6',
    NOVEDAD:                      '#f59e0b',
    'PENDIENTE CONFIRMACION':     '#f97316',
    PENDIENTE:                    '#64748b',
    CANCELADO:                    '#ef4444',
  };

  const DEFAULT_COLOR = '#475569';

  function statusColor(s) {
    return COLORS[s] || DEFAULT_COLOR;
  }

  Chart.defaults.color = '#94a3b8';
  Chart.defaults.borderColor = 'rgba(255,255,255,0.06)';
  Chart.defaults.font.family = "'Inter', sans-serif";

  const instances = {};

  function destroy(id) {
    if (instances[id]) {
      instances[id].destroy();
      delete instances[id];
    }
  }

  // ── Donut: Status distribution ──────────────────────────────────
  function renderStatus(data) {
    destroy('status');
    const ctx = document.getElementById('chart-status');
    if (!ctx || !data.length) return;

    const labels  = data.map(d => d.estatus);
    const values  = data.map(d => d.total);
    const colors  = labels.map(statusColor);
    const total   = values.reduce((a, b) => a + b, 0);

    instances['status'] = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{
          data: values,
          backgroundColor: colors,
          borderColor: '#080812',
          borderWidth: 3,
          hoverOffset: 6,
        }],
      },
      options: {
        cutout: '70%',
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const pct = ((ctx.parsed / total) * 100).toFixed(1);
                return ` ${ctx.label}: ${ctx.parsed} (${pct}%)`;
              },
            },
          },
        },
      },
    });

    // Center text
    const center = document.getElementById('donut-center');
    if (center) {
      const entregados = data.find(d => d.estatus === 'ENTREGADO')?.total || 0;
      const pct = total ? ((entregados / total) * 100).toFixed(0) : 0;
      center.innerHTML = `<span style="font-size:1.6rem;font-weight:700;color:#10b981">${pct}%</span><span style="font-size:.7rem;color:#64748b;margin-top:2px">Entregados</span>`;
    }

    // Legend
    const legend = document.getElementById('status-legend');
    if (legend) {
      legend.innerHTML = data.map((d, i) => `
        <div class="legend-item">
          <span class="legend-label">
            <span class="legend-dot" style="background:${colors[i]}"></span>
            ${d.estatus}
          </span>
          <span class="legend-count">${d.total}</span>
        </div>`).join('');
    }
  }

  // ── Line: Daily trend ───────────────────────────────────────────
  function renderTrend(data) {
    destroy('trend');
    const ctx = document.getElementById('chart-trend');
    if (!ctx || !data.length) return;

    const labels      = data.map(d => formatDateLabel(d.fecha));
    const despachados = data.map(d => d.despachados);
    const entregados  = data.map(d => d.entregados);
    const tasas       = data.map(d => d.tasa_entrega);

    instances['trend'] = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Despachados',
            data: despachados,
            backgroundColor: 'rgba(59,130,246,0.1)',
            borderColor: '#3b82f6',
            borderWidth: 2,
            pointBackgroundColor: '#3b82f6',
            pointRadius: 3,
            tension: 0.3,
            fill: true,
            yAxisID: 'y',
          },
          {
            label: 'Entregados',
            data: entregados,
            backgroundColor: 'rgba(16,185,129,0.1)',
            borderColor: '#10b981',
            borderWidth: 2,
            pointBackgroundColor: '#10b981',
            pointRadius: 3,
            tension: 0.3,
            fill: true,
            yAxisID: 'y',
          },
          {
            label: 'Tasa %',
            data: tasas,
            backgroundColor: 'transparent',
            borderColor: '#f59e0b',
            borderWidth: 2,
            borderDash: [5, 5],
            pointBackgroundColor: '#f59e0b',
            pointRadius: 3,
            tension: 0.3,
            fill: false,
            yAxisID: 'y1',
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        scales: {
          x: { grid: { color: 'rgba(255,255,255,0.04)' } },
          y: {
            title: { display: true, text: 'Cantidad de Pedidos', color: '#94a3b8' },
            grid: { color: 'rgba(255,255,255,0.04)' },
            beginAtZero: true,
          },
          y1: {
            title: { display: true, text: 'Tasa Entrega (%)', color: '#f59e0b' },
            position: 'right',
            min: 0,
            max: 100,
            grid: { drawOnChartArea: false },
            ticks: {
              callback: (v) => `${v}%`,
            },
          },
        },
        plugins: {
          legend: { position: 'top', labels: { boxWidth: 12, padding: 16 } },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const val = ctx.parsed.y;
                if (ctx.dataset.label === 'Tasa %') return ` ${ctx.dataset.label}: ${val}%`;
                return ` ${ctx.dataset.label}: ${val} pedidos`;
              },
            },
          },
        },
      },
    });
  }

  // ── Pie/Donut: Carrier performance ──────────────────────────────
  function renderCarriers(data) {
    destroy('carriers');
    const ctx = document.getElementById('chart-carriers');
    if (!ctx || !data.length) return;

    instances['carriers'] = new Chart(ctx, {
      type: 'pie',
      data: {
        labels: data.map(d => d.transportadora),
        datasets: [{
          data: data.map(d => d.total),
          backgroundColor: ['#7c3aed', '#10b981', '#f59e0b', '#3b82f6', '#ef4444', '#14b8a6'],
          borderColor: '#080812',
          borderWidth: 2,
        }],
      },
      options: {
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'right', labels: { boxWidth: 12, color: '#94a3b8' } },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const d = data[ctx.dataIndex];
                return ` ${d.transportadora}: ${d.total} envíos (${d.tasa_entrega}% entregados)`;
              },
            },
          },
        },
      },
    });
  }

  // ── Helpers ─────────────────────────────────────────────────────
  function formatCOP(value, short = false) {
    if (value === null || value === undefined) return '—';
    if (short && Math.abs(value) >= 1_000_000) {
      return '$' + (value / 1_000_000).toFixed(1) + 'M';
    }
    if (short && Math.abs(value) >= 1_000) {
      return '$' + (value / 1_000).toFixed(0) + 'k';
    }
    return new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 }).format(value);
  }

  function formatDateLabel(isoDate) {
    if (!isoDate) return '';
    // isoDate = YYYY-MM-DD
    const [, m, d] = isoDate.split('-');
    return `${d}/${m}`;
  }

  return {
    renderStatus,
    renderTrend,
    renderCarriers,
    formatCOP,
    statusColor,
    COLORS,
  };
})();
