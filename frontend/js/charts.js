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

    const labels   = data.map(d => formatDateLabel(d.fecha));
    const ganancia = data.map(d => d.ganancia);
    const tasas    = data.map(d => d.tasa_entrega);

    instances['trend'] = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Ganancia',
            data: ganancia,
            backgroundColor: 'rgba(16,185,129,0.15)',
            borderColor: '#10b981',
            borderWidth: 2,
            pointBackgroundColor: '#10b981',
            pointRadius: 3,
            tension: 0.35,
            fill: true,
            yAxisID: 'y',
          },
          {
            label: 'Tasa de Entrega',
            data: tasas,
            backgroundColor: 'rgba(245,158,11,0.1)',
            borderColor: '#f59e0b',
            borderWidth: 2,
            pointBackgroundColor: '#f59e0b',
            pointRadius: 3,
            tension: 0.35,
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
            title: { display: true, text: 'Ganancia ($)', color: '#10b981' },
            grid: { color: 'rgba(255,255,255,0.04)' },
            ticks: {
              callback: (v) => formatCOP(v, true),
            },
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
                if (ctx.dataset.label === 'Ganancia') return ` ${ctx.dataset.label}: ${formatCOP(val)}`;
                return ` ${ctx.dataset.label}: ${val}%`;
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
