/* FarmaControl · utilidades de interfaz compartidas */
(function (window, document) {
  'use strict';

  var FC = window.FC = window.FC || {};

  /* ---------- Formato ---------- */
  var fmt = new Intl.NumberFormat('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  FC.money = function (n) { return '$' + fmt.format(Number(n) || 0); };
  FC.escape = function (s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  };

  /* ---------- Tema claro / oscuro ---------- */
  var KEY = 'fc-theme';
  function storedTheme() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function applyTheme(t) {
    document.documentElement.setAttribute('data-theme', t);
    document.querySelectorAll('[data-theme-icon]').forEach(function (i) {
      i.className = t === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
    });
    document.dispatchEvent(new CustomEvent('fc:theme', { detail: t }));
  }
  FC.theme = function () { return document.documentElement.getAttribute('data-theme') || 'light'; };
  FC.toggleTheme = function () {
    var t = FC.theme() === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem(KEY, t); } catch (e) { /* almacenamiento no disponible */ }
    applyTheme(t);
  };
  (function initTheme() {
    var t = storedTheme();
    if (!t) t = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    applyTheme(t);
  })();

  /* ---------- Toasts ---------- */
  var ICONS = { success: 'fa-check', danger: 'fa-xmark', error: 'fa-xmark', warning: 'fa-exclamation', info: 'fa-info' };
  var BG = { success: 'bg-success', danger: 'bg-danger', error: 'bg-danger', warning: 'bg-warning', info: 'bg-info' };
  FC.toast = function (msg, type, ms) {
    type = type || 'info';
    var box = document.getElementById('toasts');
    if (!box) { box = document.createElement('div'); box.id = 'toasts'; box.className = 'toasts'; document.body.appendChild(box); }
    var el = document.createElement('div');
    el.className = 'toast-glass';
    el.setAttribute('role', 'status');
    el.innerHTML = '<span class="t-ico ' + (BG[type] || 'bg-info') + '"><i class="fas ' + (ICONS[type] || 'fa-info') + '"></i></span>' +
      '<div>' + FC.escape(msg) + '</div><button class="t-close" aria-label="Cerrar">&times;</button>';
    box.appendChild(el);
    var close = function () { el.classList.add('out'); setTimeout(function () { el.remove(); }, 350); };
    el.querySelector('.t-close').addEventListener('click', close);
    setTimeout(close, ms || (type === 'danger' || type === 'error' ? 7000 : 4500));
  };

  /* ---------- SweetAlert2 con estilo vidrio ---------- */
  FC.swal = function (opts) {
    if (!window.Swal) { return Promise.resolve({ isConfirmed: window.confirm(opts.text || opts.title || '¿Continuar?') }); }
    return window.Swal.fire(Object.assign({
      customClass: { popup: 'glass-swal', confirmButton: 'btn btn-primary', cancelButton: 'btn btn-glass', denyButton: 'btn btn-danger' },
      buttonsStyling: false,
      reverseButtons: true,
      cancelButtonText: 'Cancelar'
    }, opts));
  };
  FC.confirm = function (title, text, opts) {
    return FC.swal(Object.assign({ title: title, text: text || '', icon: 'question', showCancelButton: true, confirmButtonText: 'Sí, continuar' }, opts || {}))
      .then(function (r) { return r.isConfirmed; });
  };

  /* ---------- Fetch JSON ---------- */
  FC.json = function (url, options) {
    options = options || {};
    var init = { method: options.method || 'GET', headers: { 'Accept': 'application/json' }, credentials: 'same-origin' };
    if (options.body !== undefined) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(options.body);
    }
    return fetch(url, init).then(function (r) {
      if (r.status === 401) { window.location.href = '/login'; throw new Error('Sesión expirada'); }
      return r.json();
    });
  };
  FC.qs = function (params) {
    return Object.keys(params).filter(function (k) { return params[k] !== undefined && params[k] !== null; })
      .map(function (k) { return encodeURIComponent(k) + '=' + encodeURIComponent(params[k]); }).join('&');
  };

  FC.download = function (filename, content, mime) {
    var blob = new Blob(['﻿' + content], { type: mime || 'text/csv;charset=utf-8' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = filename;
    document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  };

  /* ---------- Paleta para gráficas (Chart.js) ---------- */
  FC.chartColors = function () {
    var dark = FC.theme() === 'dark';
    return {
      text: dark ? '#a9b8c0' : '#4a5b66',
      grid: dark ? 'rgba(255,255,255,.06)' : 'rgba(15,40,55,.06)',
      accent: dark ? '#22c3a8' : '#0e8a78',
      series: ['#0e8a78', '#2f7bf6', '#8b5cf6', '#e8961c', '#e5484d', '#2a92d4', '#1aa86b', '#d9468f']
    };
  };
  FC.chartDefaults = function () {
    if (!window.Chart) return;
    var c = FC.chartColors();
    Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
    Chart.defaults.color = c.text;
    Chart.defaults.borderColor = c.grid;
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(13,27,36,.88)';
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.plugins.tooltip.cornerRadius = 10;
    Chart.defaults.maintainAspectRatio = false;
  };

  /* ---------- Comportamientos declarativos ---------- */
  document.addEventListener('DOMContentLoaded', function () {
    // Mensajes flash -> toasts
    document.querySelectorAll('[data-flash]').forEach(function (n) {
      FC.toast(n.getAttribute('data-flash'), n.getAttribute('data-type'));
      n.remove();
    });

    // Botones de tema
    document.querySelectorAll('[data-toggle-theme]').forEach(function (b) {
      b.addEventListener('click', function (e) { e.preventDefault(); FC.toggleTheme(); });
    });

    // Formularios con confirmación: <form data-confirm="¿Seguro?">
    document.querySelectorAll('form[data-confirm]').forEach(function (f) {
      f.addEventListener('submit', function (e) {
        if (f.dataset.confirmed === '1') return;
        e.preventDefault();
        FC.confirm(f.getAttribute('data-confirm'), f.getAttribute('data-confirm-text') || '', {
          icon: f.getAttribute('data-confirm-icon') || 'warning',
          confirmButtonText: f.getAttribute('data-confirm-ok') || 'Sí, continuar',
          customClass: { popup: 'glass-swal', confirmButton: 'btn ' + (f.getAttribute('data-confirm-class') || 'btn-danger'), cancelButton: 'btn btn-glass' }
        }).then(function (ok) {
          if (ok) { f.dataset.confirmed = '1'; if (f.requestSubmit) f.requestSubmit(); else f.submit(); }
        });
      });
    });

    // Estado de carga en formularios
    document.querySelectorAll('form[data-loading]').forEach(function (f) {
      f.addEventListener('submit', function () {
        var b = f.querySelector('[type="submit"]');
        if (b && !b.disabled) {
          setTimeout(function () { b.disabled = true; b.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> Procesando…'; }, 0);
        }
      });
    });

    // Selects que envían el formulario al cambiar
    document.querySelectorAll('select[data-autosubmit]').forEach(function (s) {
      s.addEventListener('change', function () { s.form.submit(); });
    });

    // Filtro instantáneo en tablas: <input data-table-filter="#idTabla">
    document.querySelectorAll('[data-table-filter]').forEach(function (inp) {
      var table = document.querySelector(inp.getAttribute('data-table-filter'));
      if (!table) return;
      inp.addEventListener('input', function () {
        var q = inp.value.trim().toLowerCase();
        table.querySelectorAll('tbody tr').forEach(function (tr) {
          if (tr.hasAttribute('data-empty')) return;
          tr.style.display = !q || tr.textContent.toLowerCase().indexOf(q) !== -1 ? '' : 'none';
        });
      });
    });

    FC.chartDefaults();
  });
})(window, document);
