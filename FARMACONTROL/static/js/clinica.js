/* FarmaControl · Módulo clínico (pestañas, filas dinámicas, autocompletado, signos vitales) */
(function (window, document) {
  'use strict';
  var CL = window.CL = {};
  var esc = function (s) { return window.FC ? FC.escape(s) : String(s == null ? '' : s); };
  var STATIC = (document.querySelector('meta[name="static-url"]') || {}).content || '/static/';

  /* ---------------- Pestañas con #hash ---------------- */
  CL.tabs = function () {
    document.querySelectorAll('[data-tabs]').forEach(function (box) {
      var botones = box.querySelectorAll('[data-tab]');
      var activar = function (id, push) {
        var ok = false;
        botones.forEach(function (b) { var on = b.getAttribute('data-tab') === id; b.classList.toggle('active', on); ok = ok || on; });
        if (!ok) return false;
        document.querySelectorAll('[data-panel]').forEach(function (p) { p.hidden = p.getAttribute('data-panel') !== id; });
        if (push) history.replaceState(null, '', '#' + id);
        return true;
      };
      botones.forEach(function (b) { b.addEventListener('click', function (e) { e.preventDefault(); activar(b.getAttribute('data-tab'), true); }); });
      if (!activar((location.hash || '').slice(1)) && botones[0]) activar(botones[0].getAttribute('data-tab'));
      document.querySelectorAll('[data-goto-tab]').forEach(function (a) {
        a.addEventListener('click', function (e) { e.preventDefault(); activar(a.getAttribute('data-goto-tab'), true); window.scrollTo({ top: box.offsetTop - 20, behavior: 'smooth' }); });
      });
    });
  };

  /* ---------------- Filas dinámicas (diagnósticos, medicamentos, estudios) ---------------- */
  CL.repeater = function (nombre, opciones) {
    var lista = document.querySelector('[data-repeater="' + nombre + '"]');
    var tpl = document.getElementById('tpl-' + nombre);
    if (!lista || !tpl) return null;
    opciones = opciones || {};
    var agregar = function (datos) {
      var nodo = tpl.content.firstElementChild.cloneNode(true);
      Object.keys(datos || {}).forEach(function (k) {
        var campo = nodo.querySelector('[data-field="' + k + '"]');
        if (!campo) return;
        if (campo.type === 'checkbox') campo.checked = !!datos[k]; else campo.value = datos[k] == null ? '' : datos[k];
      });
      nodo.querySelector('.rm') && nodo.querySelector('.rm').addEventListener('click', function () { nodo.remove(); renumerar(); });
      lista.appendChild(nodo);
      renumerar();
      if (opciones.alAgregar) opciones.alAgregar(nodo);
      var primero = nodo.querySelector('input,select,textarea');
      if (primero && !datos) primero.focus();
      return nodo;
    };
    var renumerar = function () {
      lista.querySelectorAll('[data-n]').forEach(function (n, i) { n.textContent = i + 1; });
      var vacio = document.querySelector('[data-empty-for="' + nombre + '"]');
      if (vacio) vacio.hidden = lista.children.length > 0;
    };
    document.querySelectorAll('[data-add="' + nombre + '"]').forEach(function (b) { b.addEventListener('click', function () { agregar(); }); });
    var serializar = function () {
      return Array.prototype.map.call(lista.children, function (fila) {
        var o = {};
        fila.querySelectorAll('[data-field]').forEach(function (c) { o[c.getAttribute('data-field')] = c.type === 'checkbox' ? c.checked : c.value.trim(); });
        return o;
      });
    };
    var form = lista.closest('form');
    if (form) form.addEventListener('submit', function () {
      var oculto = form.querySelector('input[name="' + nombre + '_json"]');
      if (oculto) oculto.value = JSON.stringify(serializar());
    });
    renumerar();
    return { agregar: agregar, serializar: serializar, lista: lista };
  };

  /* ---------------- CIE-10 ---------------- */
  var cie10 = null;
  CL.cargarCie10 = function () {
    if (cie10) return Promise.resolve(cie10);
    return fetch(STATIC + 'data/cie10.json').then(function (r) { return r.json(); }).then(function (d) {
      cie10 = d;
      var dl = document.getElementById('cie10-list');
      if (dl) dl.innerHTML = d.map(function (x) { return '<option value="' + esc(x.d) + '">' + esc(x.c) + '</option>'; }).join('');
      var dc = document.getElementById('cie10-codes');
      if (dc) dc.innerHTML = d.map(function (x) { return '<option value="' + esc(x.c) + '">' + esc(x.d) + '</option>'; }).join('');
      return d;
    }).catch(function () { return []; });
  };
  CL.enlazarCie10 = function (fila) {
    var desc = fila.querySelector('[data-field="descripcion"], [name="nombre"][list="cie10-list"]');
    var cod = fila.querySelector('[data-field="cie10"], [name="cie10"]');
    if (!desc || !cod) return;
    desc.addEventListener('change', function () {
      var m = (cie10 || []).filter(function (x) { return x.d === desc.value; })[0];
      if (m && !cod.value) cod.value = m.c;
    });
    cod.addEventListener('change', function () {
      var m = (cie10 || []).filter(function (x) { return x.c.toUpperCase() === cod.value.toUpperCase(); })[0];
      if (m && !desc.value) desc.value = m.d;
    });
  };

  /* ---------------- Estudios frecuentes ---------------- */
  CL.cargarEstudios = function () {
    return fetch(STATIC + 'data/estudios.json').then(function (r) { return r.json(); }).then(function (d) {
      var dl = document.getElementById('estudios-list');
      if (dl) dl.innerHTML = d.map(function (x) { return '<option value="' + esc(x) + '">'; }).join('');
    }).catch(function () {});
  };

  /* ---------------- Autocompletado de medicamentos del inventario ---------------- */
  CL.enlazarMedicamento = function (fila, url) {
    var inp = fila.querySelector('[data-field="medicamento"]');
    var pid = fila.querySelector('[data-field="producto_id"]');
    var badge = fila.querySelector('[data-inv]');
    if (!inp) return;
    var dlId = 'dl-med-' + Math.random().toString(36).slice(2);
    var dl = document.createElement('datalist'); dl.id = dlId; fila.appendChild(dl); inp.setAttribute('list', dlId);
    var cache = [], t;
    inp.addEventListener('input', function () {
      if (pid) pid.value = '';
      if (badge) badge.hidden = true;
      clearTimeout(t);
      var q = inp.value.trim();
      if (q.length < 2) return;
      t = setTimeout(function () {
        fetch(url + '?q=' + encodeURIComponent(q), { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (d) {
          cache = d;
          dl.innerHTML = d.map(function (x) { return '<option value="' + esc(x.nombre) + '">' + (x.stock > 0 ? 'En inventario: ' + x.stock : 'Sin existencia') + (x.antibiotico ? ' · antibiótico' : '') + '</option>'; }).join('');
        });
      }, 220);
    });
    inp.addEventListener('change', function () {
      var m = cache.filter(function (x) { return x.nombre === inp.value; })[0];
      if (pid) pid.value = m ? m.id : '';
      if (badge) { badge.hidden = !m; if (m) badge.textContent = m.stock > 0 ? 'En farmacia (' + m.stock + ')' : 'Sin existencia'; badge.className = 'pill ' + (m && m.stock > 0 ? 'pill-success' : 'pill-warning'); }
    });
  };

  /* ---------------- Buscador de pacientes ---------------- */
  CL.buscadorPacientes = function (input, resultados, url, alElegir) {
    if (!input) return;
    var t;
    input.addEventListener('input', function () {
      clearTimeout(t);
      var q = input.value.trim();
      if (q.length < 2) { resultados.innerHTML = ''; return; }
      t = setTimeout(function () {
        fetch(url + '?q=' + encodeURIComponent(q), { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (d) {
          resultados.innerHTML = d.length ? d.map(function (p) {
            return '<button type="button" class="item-pac" data-id="' + p.id + '"><span class="avatar sm">' + esc(p.nombre.split(' ').map(function (x) { return x[0]; }).slice(0, 2).join('')) + '</span>' +
              '<span class="grow"><b>' + esc(p.nombre) + '</b><small>' + esc(p.expediente || '') + ' · ' + esc(p.edad || 'edad no registrada') + ' · ' + p.visitas + ' visita(s)</small></span><i class="fas fa-arrow-right text-accent"></i></button>';
          }).join('') : '<div class="text-muted" style="padding:12px">Sin coincidencias. Registra al paciente como nuevo.</div>';
          resultados.querySelectorAll('[data-id]').forEach(function (b) { b.addEventListener('click', function () { alElegir(b.getAttribute('data-id')); }); });
        });
      }, 250);
    });
  };

  /* ---------------- Signos vitales: IMC y presión ---------------- */
  CL.vitales = function () {
    var peso = document.querySelector('[name="peso_kg"]'), talla = document.querySelector('[name="talla_cm"]');
    var out = document.getElementById('imc-out');
    var sis = document.querySelector('[name="ta_sistolica"]'), dia = document.querySelector('[name="ta_diastolica"]');
    var taOut = document.getElementById('ta-out');
    var calc = function () {
      if (out && peso && talla) {
        var p = parseFloat(peso.value), t = parseFloat(talla.value);
        if (p > 0 && t > 0) {
          var imc = p / Math.pow(t / 100, 2), cls = imc < 18.5 ? ['Bajo peso', 'warning'] : imc < 25 ? ['Normal', 'success'] : imc < 30 ? ['Sobrepeso', 'warning'] : ['Obesidad', 'danger'];
          out.innerHTML = '<b>' + imc.toFixed(1) + '</b> <span class="pill pill-' + cls[1] + '">' + cls[0] + '</span>';
        } else out.textContent = '—';
      }
      if (taOut && sis && dia) {
        var s = parseInt(sis.value, 10), d = parseInt(dia.value, 10);
        if (s > 0 && d > 0) {
          var c = (s >= 180 || d >= 120) ? ['Crisis hipertensiva', 'danger'] : (s >= 140 || d >= 90) ? ['Hipertensión', 'danger'] : (s >= 130 || d >= 80) ? ['Elevada', 'warning'] : ['Normal', 'success'];
          taOut.innerHTML = '<span class="pill pill-' + c[1] + '">' + c[0] + '</span>';
        } else taOut.textContent = '';
      }
    };
    [peso, talla, sis, dia].forEach(function (i) { if (i) i.addEventListener('input', calc); });
    calc();
  };

  /* ---------------- Modal genérico con datos (data-modal-fill) ---------------- */
  CL.rellenarModal = function () {
    document.querySelectorAll('[data-modal-fill]').forEach(function (b) {
      b.addEventListener('click', function () {
        var datos = JSON.parse(b.getAttribute('data-modal-fill'));
        var modal = document.querySelector(b.getAttribute('data-target'));
        if (!modal) return;
        Object.keys(datos).forEach(function (k) {
          var c = modal.querySelector('[name="' + k + '"]'); if (c) c.value = datos[k] == null ? '' : datos[k];
          var t = modal.querySelector('[data-text="' + k + '"]'); if (t) t.textContent = datos[k] || '';
        });
        if (datos._action) modal.querySelector('form').setAttribute('action', datos._action);
      });
    });
  };

  document.addEventListener('DOMContentLoaded', function () { CL.tabs(); CL.rellenarModal(); });
})(window, document);
