/* FarmaControl · Punto de venta */
(function (window, document, $) {
  'use strict';

  var CFG = window.POS_CONFIG;
  var esc = FC.escape;
  var TITULOS = { productos: 'Productos', procedimientos: 'Servicios médicos', consultas: 'Consultas' };

  var state = {
    carrito: [],
    cliente: { id: null, nombre: 'PÚBLICO GENERAL' },
    total: 0,
    itemsModal: [],
    tipoModal: null,
    ventaActual: null,
    cuenta: null,         // cuenta de paciente del consultorio (receta / honorarios)
    registroAb: null      // datos de la receta de antibióticos (control sanitario)
  };
  var TIPO_PILL = { servicio: ['Servicio', 'info'], consulta: ['Consulta', 'info'], honorario: ['Honorarios', 'accent'] };

  /* ---------------- utilidades ---------------- */
  function metodo(id) { return CFG.metodos.filter(function (m) { return m.id === id; })[0]; }
  function esEfectivo(m) { return m && /efectivo/i.test(m.nombre); }
  function antibioticos() { return state.carrito.filter(function (i) { return i.esAntibiotico; }); }
  function focusScan() { setTimeout(function () { $('#barcode-input').trigger('focus'); }, 60); }
  function modalAbierto() { return $('.modal.show').length > 0; }

  /* ---------------- carrito ---------------- */
  function agregar(item, cantidad, silencioso) {
    var key = item.tipo + ':' + item.id;
    var cant = Math.max(1, Math.floor(Number(cantidad) || 1));
    var max = item.tipo === 'producto' ? Number(item.stock) : Infinity;
    if (item.tipo === 'producto' && !(max > 0)) {
      FC.swal({ icon: 'warning', title: 'Sin existencias', text: '«' + item.nombre + '» no tiene stock disponible.' });
      return;
    }
    var ex = state.carrito.filter(function (i) { return i.key === key; })[0];
    if (ex) {
      if (item.tipo === 'honorario') { FC.toast('Esa consulta ya está en el carrito', 'info'); return; }
      if (ex.cant + cant > ex.stockMax) { FC.toast('Solo hay ' + ex.stockMax + ' unidades de «' + ex.nombre + '»', 'warning'); return; }
      ex.cant += cant;
    } else {
      state.carrito.unshift({
        key: key, id: item.id, tipo: item.tipo, nombre: item.nombre,
        precio: Number(item.precio), cant: Math.min(cant, max), stockMax: item.tipo === 'honorario' ? 1 : max,
        esAntibiotico: !!item.antibiotico
      });
      if (item.antibiotico && !silencioso) FC.toast('«' + item.nombre + '» es antibiótico: solicita la receta médica.', 'warning', 6000);
    }
    render(key);
    $('#modalSeleccion').modal('hide');
    focusScan();
  }

  function cambiarCantidad(idx, valor) {
    var it = state.carrito[idx]; if (!it) return;
    var n = Math.floor(Number(valor));
    if (!(n >= 1)) { eliminar(idx); return; }
    if (it.tipo === 'honorario' && n > 1) { FC.toast('Los honorarios de una consulta se cobran una sola vez', 'info'); n = 1; it.cant = 1; render(); return; }
    if (n > it.stockMax) { FC.toast('Límite de existencia: ' + it.stockMax + ' unidades', 'warning'); n = it.stockMax; }
    it.cant = n; render();
  }
  function eliminar(idx) { state.carrito.splice(idx, 1); render(); focusScan(); }

  function render(flashKey) {
    var tbody = document.getElementById('carrito-table');
    var resumen = document.getElementById('ticket-items');
    var total = 0, unidades = 0, filas = '', lineas = '';

    state.carrito.forEach(function (it, idx) {
      var sub = it.precio * it.cant; total += sub; unidades += it.cant;
      var tp = TIPO_PILL[it.tipo];
      var tipoPill = tp ? '<span class="pill pill-' + tp[1] + '" style="margin-left:6px">' + tp[0] + '</span>' : '';
      var abPill = it.esAntibiotico ? '<span class="pill pill-purple" style="margin-left:6px"><i class="fas fa-prescription"></i> Antibiótico</span>' : '';
      filas += '<tr class="' + (it.key === flashKey ? 'flash' : '') + '">' +
        '<td><div class="cell-title">' + esc(it.nombre) + tipoPill + abPill + '</div>' +
        (it.tipo === 'producto' ? '<div class="cell-sub">Disponible: ' + it.stockMax + '</div>' : '') + '</td>' +
        '<td class="text-center"><div class="qty">' +
          '<button type="button" data-act="menos" data-idx="' + idx + '" aria-label="Menos">−</button>' +
          '<input type="number" min="1" value="' + it.cant + '" data-act="cant" data-idx="' + idx + '" aria-label="Cantidad">' +
          '<button type="button" data-act="mas" data-idx="' + idx + '" aria-label="Más">+</button></div></td>' +
        '<td class="num text-2">' + FC.money(it.precio) + '</td>' +
        '<td class="num fw-800">' + FC.money(sub) + '</td>' +
        '<td class="num"><button type="button" class="btn btn-icon danger btn-ghost" data-act="quitar" data-idx="' + idx + '" title="Quitar"><i class="fas fa-xmark"></i></button></td>' +
        '</tr>';
      lineas += '<div class="summary-line"><span>' + it.cant + ' × ' + esc(it.nombre) + '</span><b>' + FC.money(sub) + '</b></div>';
    });

    if (!state.carrito.length) {
      filas = '<tr data-empty><td colspan="5"><div class="empty"><i class="fas fa-barcode"></i><b>Escanea un producto para comenzar</b><span>o usa F1 · F2 · F3 para buscar en el catálogo</span></div></td></tr>';
      lineas = '<div class="text-muted text-center" style="padding:18px 0;font-size:.88rem">Carrito vacío</div>';
    }
    tbody.innerHTML = filas;
    resumen.innerHTML = lineas;
    state.total = Math.round(total * 100) / 100;
    document.getElementById('total-ticket').textContent = FC.money(state.total);
    document.getElementById('items-count').textContent = state.carrito.length;
    document.getElementById('summary-units').textContent = unidades + (unidades === 1 ? ' unidad' : ' unidades');
    document.getElementById('btn-cobrar').disabled = !state.carrito.length;
    document.getElementById('btn-vaciar').disabled = !state.carrito.length;
    document.getElementById('antibiotico-box').style.display = antibioticos().length ? 'flex' : 'none';
  }

  $(document).on('click', '#carrito-table [data-act]', function () {
    var idx = Number(this.getAttribute('data-idx')), act = this.getAttribute('data-act'), it = state.carrito[idx];
    if (act === 'mas') cambiarCantidad(idx, it.cant + 1);
    else if (act === 'menos') cambiarCantidad(idx, it.cant - 1);
    else if (act === 'quitar') eliminar(idx);
  });
  $(document).on('change', '#carrito-table input[data-act="cant"]', function () {
    cambiarCantidad(Number(this.getAttribute('data-idx')), this.value);
  });

  /* ---------------- búsqueda / lector ---------------- */
  $('#barcode-input').on('keydown', function (e) {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    var q = this.value.trim(); if (!q) return;
    var input = this;
    FC.json(CFG.urls.buscar + '?' + FC.qs({ query: q })).then(function (res) {
      input.value = '';
      if (!res.success) { FC.toast(res.message || 'No encontrado', 'danger'); return; }
      if (res.tipo === 'exacto') { agregar(res.data); return; }
      abrirModalConDatos('productos', res.data, 'Resultados para «' + q + '»');
    }).catch(function () { FC.toast('No se pudo conectar con el servidor', 'danger'); });
  });

  function itemHTML(item, i) {
    var esProd = item.tipo === 'producto';
    var stock = esProd ? '<span class="cell-sub">Stock: ' + item.stock + (item.codigo_barras ? ' · <span class="mono">' + esc(item.codigo_barras) + '</span>' : '') + '</span>' : '';
    var ab = item.antibiotico ? ' <span class="pill pill-purple"><i class="fas fa-prescription"></i> Antibiótico</span>' : '';
    return '<button type="button" class="item-row" data-i="' + i + '">' +
      '<span class="avatar sm" style="background:linear-gradient(135deg,var(--accent-2),var(--blue))"><i class="fas ' + (esProd ? 'fa-capsules' : 'fa-stethoscope') + '"></i></span>' +
      '<span class="grow"><span class="cell-title d-block truncate">' + esc(item.nombre) + ab + '</span>' + stock + '</span>' +
      '<span class="price">' + FC.money(item.precio) + '</span></button>';
  }
  function pintarModal(filtro) {
    var q = (filtro || '').toLowerCase(), html = '';
    state.itemsModal.forEach(function (it, i) {
      if (q && (it.nombre + ' ' + (it.codigo_barras || '')).toLowerCase().indexOf(q) === -1) return;
      html += itemHTML(it, i);
    });
    document.getElementById('modal-body-items').innerHTML = html || '<div class="empty"><i class="fas fa-magnifying-glass"></i><b>Sin resultados</b></div>';
  }
  function abrirModalConDatos(tipo, datos, titulo) {
    state.itemsModal = datos; state.tipoModal = tipo;
    document.getElementById('modal-title-dynamic').textContent = titulo || TITULOS[tipo];
    $('#filtro-modal').val('');
    pintarModal('');
    $('#modalSeleccion').modal('show');
  }
  function abrirSeleccion(tipo) {
    document.getElementById('modal-title-dynamic').textContent = TITULOS[tipo];
    document.getElementById('modal-body-items').innerHTML = '<div class="empty"><i class="fas fa-circle-notch fa-spin"></i><b>Cargando…</b></div>';
    $('#filtro-modal').val('');
    $('#modalSeleccion').modal('show');
    FC.json(CFG.urls.items.replace('__T__', tipo)).then(function (data) {
      state.itemsModal = data; state.tipoModal = tipo; pintarModal($('#filtro-modal').val());
    });
  }
  $('#modalSeleccion').on('shown.bs.modal', function () { $('#filtro-modal').trigger('focus'); });
  $('#modalSeleccion').on('hidden.bs.modal', focusScan);
  $('#filtro-modal').on('input', function () { pintarModal(this.value); });
  $('#filtro-modal').on('keydown', function (e) {
    if (e.key === 'Enter') { e.preventDefault(); var first = document.querySelector('#modal-body-items .item-row'); if (first) first.click(); }
  });
  $(document).on('click', '#modal-body-items .item-row', function () { agregar(state.itemsModal[Number(this.getAttribute('data-i'))]); });

  /* ---------------- clientes ---------------- */
  var tCliente;
  function cargarClientes(q) {
    FC.json(CFG.urls.clientes + '?' + FC.qs({ q: q || '' })).then(function (data) {
      var html = '';
      data.forEach(function (c) {
        html += '<button type="button" class="item-row" data-id="' + c.id + '" data-nombre="' + esc(c.nombre) + '">' +
          '<span class="avatar sm">' + esc((c.nombre || '?').split(' ').map(function (p) { return p[0]; }).slice(0, 2).join('').toUpperCase()) + '</span>' +
          '<span class="grow"><span class="cell-title d-block">' + esc(c.nombre) + '</span><span class="cell-sub">' + esc([c.rfc_nit, c.telefono].filter(Boolean).join(' · ') || 'Sin datos fiscales') + '</span></span>' +
          (state.cliente.id === c.id ? '<i class="fas fa-circle-check text-accent"></i>' : '') + '</button>';
      });
      document.getElementById('modal-body-clientes').innerHTML = html || '<div class="empty"><i class="fas fa-user-slash"></i><b>No hay clientes</b><span>Registra uno nuevo con el botón “Nuevo”.</span></div>';
    });
  }
  function abrirClientes() { $('#modalClientes').modal('show'); $('#filtro-cliente').val(''); cargarClientes(''); }
  function seleccionarCliente(id, nombre) {
    state.cliente = { id: id, nombre: nombre };
    document.getElementById('client-name-display').textContent = nombre;
    $('#modalClientes').modal('hide');
    if (id) FC.toast('Cliente: ' + nombre, 'info', 2500);
  }
  $('#modalClientes').on('shown.bs.modal', function () { $('#filtro-cliente').trigger('focus'); });
  $('#modalClientes').on('hidden.bs.modal', focusScan);
  $('#filtro-cliente').on('input', function () { var v = this.value; clearTimeout(tCliente); tCliente = setTimeout(function () { cargarClientes(v); }, 250); });
  $(document).on('click', '#modal-body-clientes .item-row', function () {
    seleccionarCliente(Number(this.getAttribute('data-id')), this.getAttribute('data-nombre'));
  });

  function nuevoCliente() {
    $('#modalClientes').modal('hide');
    FC.swal({
      title: 'Nuevo cliente',
      html: '<div style="text-align:left">' +
        '<label>Nombre completo *</label><input id="sw-nombre" class="form-control" placeholder="Ej. Juan Pérez" style="margin-bottom:12px">' +
        '<div class="row"><div class="col-6"><label>RFC</label><input id="sw-rfc" class="form-control" placeholder="Opcional" style="margin-bottom:12px"></div>' +
        '<div class="col-6"><label>Teléfono</label><input id="sw-tel" class="form-control" placeholder="10 dígitos" style="margin-bottom:12px"></div></div>' +
        '<label>Correo</label><input id="sw-email" type="email" class="form-control" placeholder="usuario@correo.com" style="margin-bottom:12px">' +
        '<label>Dirección</label><textarea id="sw-dir" class="form-control" rows="2" placeholder="Calle, número, colonia…"></textarea></div>',
      showCancelButton: true, confirmButtonText: 'Guardar cliente', focusConfirm: false,
      didOpen: function () { document.getElementById('sw-nombre').focus(); },
      preConfirm: function () {
        var nombre = document.getElementById('sw-nombre').value.trim();
        if (!nombre) { Swal.showValidationMessage('El nombre es obligatorio'); return false; }
        return FC.json(CFG.urls.nuevoCliente, { method: 'POST', body: {
          nombre: nombre, rfc_nit: document.getElementById('sw-rfc').value, telefono: document.getElementById('sw-tel').value,
          email: document.getElementById('sw-email').value, direccion: document.getElementById('sw-dir').value
        } }).then(function (r) { if (!r.success) throw new Error(r.message); return r; })
          .catch(function (e) { Swal.showValidationMessage(e.message || 'Error de conexión'); });
      }
    }).then(function (r) {
      if (r.isConfirmed && r.value) { seleccionarCliente(r.value.id, r.value.nombre); FC.toast('Cliente guardado', 'success'); }
      else $('#modalClientes').modal('show');
    });
  }

  /* ---------------- cobro ---------------- */
  function cobrar() {
    if (!state.carrito.length || modalAbierto()) return;
    var seguir = function () {
      document.getElementById('modal-total-display').textContent = FC.money(state.total);
      $('#modalMetodoPago').modal('show');
    };
    if (!antibioticos().length) { state.registroAb = null; seguir(); return; }
    abrirRegistroAb(seguir);
  }

  /* ---------------- control de antibióticos ---------------- */
  var abContinuar = null;
  function abForm() { return document.getElementById('formAntibiotico'); }
  function abSet(nombre, valor) { var el = abForm().elements[nombre]; if (el && el.type !== 'checkbox' && valor != null && !el.value) el.value = valor; }
  function abPacienteTag() {
    var f = abForm(), interno = !!f.elements.paciente_id.value;
    document.getElementById('abPacienteTag').innerHTML = interno
      ? '<span class="pill pill-success"><i class="fas fa-hospital-user"></i> De la clínica</span>' : '';
  }
  function abrirRegistroAb(alTerminar) {
    abContinuar = alTerminar;
    var f = abForm(), abs = antibioticos();
    if (state.registroAb) Object.keys(state.registroAb).forEach(function (k) {
      var el = f.elements[k]; if (!el) return;
      if (k === 'vale_salida') el.checked = !!state.registroAb[k];
      else if (k === 'destino_receta') f.querySelectorAll('[name="destino_receta"]').forEach(function (r) { r.checked = r.value === state.registroAb[k]; });
      else el.value = state.registroAb[k] || '';
    });
    // Prellenado: cuenta del consultorio (paciente y médico de la receta interna) o cliente seleccionado
    var c = state.cuenta;
    if (c) {
      abSet('paciente_nombre', c.paciente.nombre.toUpperCase()); abSet('paciente_id', c.paciente.id);
      if (c.medico) {
        abSet('medico_nombre', c.medico.nombre); abSet('medico_cedula', c.medico.cedula); abSet('medico_domicilio', c.medico.domicilio);
        abSet('institucion', c.medico.institucion); abSet('receta_folio', c.medico.receta_folio); abSet('receta_fecha', c.medico.receta_fecha);
        abSet('receta_clinica_id', c.medico.receta_clinica_id);
      }
    } else if (state.cliente.id && !f.elements.paciente_nombre.value) {
      abSet('paciente_nombre', state.cliente.nombre);
    }
    if (!f.elements.receta_fecha.value) f.elements.receta_fecha.value = new Date().toISOString().slice(0, 10);
    abPacienteTag();
    // Sustancia en automático desde el inventario (compuesto + producto)
    var caja = document.getElementById('abProductos');
    var linea = function (a, x) {
      x = x || {};
      var compuesto = (x.compuesto || a.nombre).toUpperCase(), prod = a.nombre.toUpperCase();
      return '<div class="ab-linea"><b>' + esc(compuesto === prod ? prod : compuesto + '  ' + prod) + '</b>' +
        '<span>' + a.cant + ' u.' + (x.lote ? ' · Lote ' + esc(x.lote) : '') + (x.tipo_antibiotico ? ' · ' + esc(x.tipo_antibiotico) : '') + '</span></div>';
    };
    caja.innerHTML = abs.map(function (a) { return linea(a); }).join('');
    FC.json(CFG.urls.abProductos + '?ids=' + abs.map(function (a) { return a.id; }).join(',')).then(function (info) {
      var porId = {}; info.forEach(function (x) { porId[x.id] = x; });
      caja.innerHTML = abs.map(function (a) { return linea(a, porId[a.id]); }).join('');
    }).catch(function () {});
    $('#modalAntibiotico').modal('show');
  }

  function sugerencias(input, caja, url, pintar, elegir) {
    var t;
    input.addEventListener('input', function () {
      if (input.name === 'paciente_nombre') { abForm().elements.paciente_id.value = ''; abPacienteTag(); }
      clearTimeout(t);
      var q = input.value.trim();
      if (q.length < 2) { caja.innerHTML = ''; return; }
      t = setTimeout(function () {
        FC.json(url + '?q=' + encodeURIComponent(q)).then(function (lista) {
          caja.innerHTML = lista.slice(0, 8).map(function (x, i) { return '<button type="button" data-i="' + i + '">' + pintar(x) + '</button>'; }).join('');
          caja.querySelectorAll('button').forEach(function (b) { b.addEventListener('mousedown', function (e) { e.preventDefault(); elegir(lista[Number(b.getAttribute('data-i'))]); caja.innerHTML = ''; }); });
        }).catch(function () {});
      }, 220);
    });
    input.addEventListener('blur', function () { setTimeout(function () { caja.innerHTML = ''; }, 150); });
  }
  (function iniciarRegistroAb() {
    var f = abForm(); if (!f) return;
    var llenarMedico = function (m) {
      f.elements.medico_nombre.value = m.nombre || ''; f.elements.medico_cedula.value = m.cedula || '';
      if (m.domicilio) f.elements.medico_domicilio.value = m.domicilio;
      if (m.institucion) f.elements.institucion.value = m.institucion;
    };
    var pintarMedico = function (m) { return '<b>' + esc(m.nombre) + '</b><small>Céd. ' + esc(m.cedula || '—') + (m.institucion ? ' · ' + esc(m.institucion) : '') + (m.veces ? ' · ' + m.veces + ' receta(s)' : '') + '</small>'; };
    sugerencias(f.elements.medico_nombre, f.querySelector('[data-sug="medico"]'), CFG.urls.abMedicos, pintarMedico, llenarMedico);
    sugerencias(f.elements.medico_cedula, f.querySelector('[data-sug="cedula"]'), CFG.urls.abMedicos, pintarMedico, llenarMedico);
    sugerencias(f.elements.paciente_nombre, f.querySelector('[data-sug="paciente"]'), CFG.urls.abPacientes,
      function (p) { return '<b>' + esc(p.nombre) + '</b><small>' + (p.interno ? 'Clínica · ' + esc(p.expediente || '') : 'Registrado en ventas anteriores') + '</small>'; },
      function (p) { f.elements.paciente_nombre.value = (p.nombre || '').toUpperCase(); f.elements.paciente_id.value = p.id || ''; abPacienteTag(); });
    f.addEventListener('submit', function (e) {
      e.preventDefault();
      var datos = {};
      Array.prototype.forEach.call(f.elements, function (el) {
        if (!el.name || el.type === 'radio') return;
        datos[el.name] = el.type === 'checkbox' ? (el.checked ? el.value : '') : el.value.trim();
      });
      var recoge = f.querySelector('[name="destino_receta"]:checked');
      datos.destino_receta = recoge ? recoge.value : 'retenida';
      if (!datos.paciente_nombre || !datos.medico_nombre || !datos.medico_cedula) { FC.toast('Completa paciente, médico y cédula profesional', 'warning'); return; }
      state.registroAb = datos;
      $('#modalAntibiotico').modal('hide');
      var sig = abContinuar; abContinuar = null;
      if (sig) setTimeout(sig, 350);
    });
    $('#modalAntibiotico').on('shown.bs.modal', function () {
      var vacio = ['medico_cedula', 'medico_nombre', 'paciente_nombre'].filter(function (n) { return !f.elements[n].value; })[0];
      (f.elements[vacio || 'paciente_nombre']).focus();
    });
  })();
  function limpiarRegistroAb() {
    state.registroAb = null;
    var f = abForm(); if (f) { f.reset(); f.elements.paciente_id.value = ''; f.elements.receta_clinica_id.value = ''; }
  }

  function elegirMetodo(id) {
    var m = metodo(id);
    $('#modalMetodoPago').modal('hide');
    if (esEfectivo(m)) { pedirEfectivo(m); return; }
    FC.swal({ icon: 'question', title: 'Cobrar con ' + m.nombre, text: 'Se registrará la venta por ' + FC.money(state.total),
      showCancelButton: true, confirmButtonText: 'Confirmar pago' })
      .then(function (r) { if (r.isConfirmed) procesar(m, state.total); else $('#modalMetodoPago').modal('show'); });
  }

  function pedirEfectivo(m) {
    var total = state.total;
    var sugeridos = [total, Math.ceil(total / 50) * 50, Math.ceil(total / 100) * 100, Math.ceil(total / 500) * 500]
      .filter(function (v, i, a) { return a.indexOf(v) === i && v >= total; }).slice(0, 4);
    FC.swal({
      title: 'Cobro en efectivo',
      html: '<div class="text-muted fw-700" style="font-size:.75rem;text-transform:uppercase">Total</div>' +
        '<div class="hero-amount text-accent" style="margin-bottom:18px">' + FC.money(total) + '</div>' +
        '<label style="text-align:left">Cantidad recibida</label>' +
        '<input id="sw-pago" type="number" step="0.01" min="0" class="form-control cash-input" inputmode="decimal">' +
        '<div class="cash-quick">' + sugeridos.map(function (v) { return '<button type="button" class="btn btn-glass btn-sm" data-pago="' + v + '">' + FC.money(v) + '</button>'; }).join('') + '</div>' +
        '<div class="cash-change" id="sw-cambio">Cambio: <span class="text-muted">—</span></div>',
      showCancelButton: true, confirmButtonText: 'Procesar pago', focusConfirm: false,
      didOpen: function () {
        var inp = document.getElementById('sw-pago'), out = document.getElementById('sw-cambio');
        var upd = function () {
          var v = parseFloat(inp.value);
          if (isNaN(v)) { out.innerHTML = 'Cambio: <span class="text-muted">—</span>'; return; }
          out.innerHTML = v < total ? '<span class="text-danger">Faltan ' + FC.money(total - v) + '</span>' : 'Cambio: <span class="text-success">' + FC.money(v - total) + '</span>';
        };
        inp.addEventListener('input', upd);
        inp.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); Swal.clickConfirm(); } });
        document.querySelectorAll('[data-pago]').forEach(function (b) { b.addEventListener('click', function () { inp.value = b.getAttribute('data-pago'); upd(); inp.focus(); }); });
        inp.focus();
      },
      preConfirm: function () {
        var v = parseFloat(document.getElementById('sw-pago').value);
        if (isNaN(v) || v + 0.001 < total) { Swal.showValidationMessage('Faltan ' + FC.money(total - (v || 0))); return false; }
        return v;
      }
    }).then(function (r) {
      if (r.isConfirmed) procesar(m, r.value); else $('#modalMetodoPago').modal('show');
    });
  }

  function procesar(m, pago) {
    FC.swal({ title: 'Procesando venta…', allowOutsideClick: false, showConfirmButton: false, didOpen: function () { Swal.showLoading(); } });
    FC.json(CFG.urls.procesar, { method: 'POST', body: {
      carrito: state.carrito.map(function (i) { return { id: i.id, tipo: i.tipo, cant: i.cant, precio: i.precio, esProducto: i.tipo === 'producto' }; }),
      total: state.total, metodo_pago_id: m.id, pago: pago, cambio: Math.max(0, pago - state.total),
      cliente_id: state.cliente.id, contiene_antibioticos: antibioticos().length > 0,
      receta_id: state.cuenta && state.cuenta.receta && !state.cuenta.receta.surtida ? state.cuenta.receta.id : null,
      paciente_id: state.cuenta ? state.cuenta.paciente.id : null,
      antibiotico: antibioticos().length ? state.registroAb : null
    } }).then(function (res) {
      Swal.close();
      if (!res.success) { FC.swal({ icon: 'error', title: 'No se pudo registrar', text: res.message }); return; }
      state.ventaActual = res;
      mostrarTicket(res, m);
    }).catch(function () { Swal.close(); FC.swal({ icon: 'error', title: 'Sin conexión', text: 'No se pudo conectar con el servidor.' }); });
  }

  function mostrarTicket(res, m) {
    document.getElementById('ticket-resumen').textContent = res.folio + ' · ' + FC.money(res.total_vendido) + ' · ' + m.nombre;
    var cambioBox = document.getElementById('cambio-box');
    if (esEfectivo(m) && res.cambio > 0) { cambioBox.style.display = 'block'; document.getElementById('cambio-display').textContent = FC.money(res.cambio); }
    else cambioBox.style.display = 'none';
    var frame = document.getElementById('ticket-iframe');
    frame.onload = function () { imprimirTicket(); frame.onload = null; };
    frame.src = CFG.urls.ticket.replace(/0$/, res.venta_id);
    $('#modalTicket').modal('show');
  }

  function imprimirTicket() {
    var f = document.getElementById('ticket-iframe');
    try { f.contentWindow.focus(); f.contentWindow.print(); } catch (e) { FC.toast('No se pudo abrir la impresión', 'warning'); }
  }

  function nuevaVenta() {
    $('#modalTicket').modal('hide');
    state.carrito = []; state.ventaActual = null;
    quitarCuenta(true); limpiarRegistroAb();
    seleccionarCliente(null, 'PÚBLICO GENERAL');
    document.getElementById('ticket-iframe').src = 'about:blank';
    render(); focusScan();
  }

  function vaciar() {
    if (!state.carrito.length) return;
    FC.confirm('¿Vaciar el carrito?', 'Se quitarán todos los artículos de la venta actual.', { icon: 'warning', confirmButtonText: 'Sí, vaciar' })
      .then(function (ok) { if (ok) { state.carrito = []; quitarCuenta(true); limpiarRegistroAb(); render(); focusScan(); } });
  }

  /* ---------------- cuenta de paciente (consultorio) ---------------- */
  function pintarCuenta() {
    var box = document.getElementById('cuenta-paciente');
    var c = state.cuenta;
    if (!c) { box.hidden = true; box.innerHTML = ''; return; }
    var chips = [];
    if (c.consulta) chips.push('<span class="pill pill-' + (c.consulta.pagada ? 'success' : 'accent') + '"><i class="fas fa-stethoscope"></i> ' + esc(c.consulta.folio) + (c.consulta.pagada ? ' · cobrada' : '') + '</span>');
    if (c.receta) chips.push('<span class="pill pill-' + (c.receta.surtida ? 'success' : 'info') + '"><i class="fas fa-prescription"></i> ' + esc(c.receta.folio) + (c.receta.surtida ? ' · surtida' : '') + '</span>');
    if (c.alergias.length) chips.push('<span class="pill pill-danger"><i class="fas fa-triangle-exclamation"></i> Alergias: ' + esc(c.alergias.join(', ')) + '</span>');
    var notas = c.faltantes.map(function (f) { return '<li><b>' + esc(f.medicamento) + '</b>: ' + esc(f.motivo) + '</li>'; })
      .concat(c.avisos.map(function (a) { return '<li>' + esc(a) + '</li>'; }));
    box.innerHTML = '<span class="cuenta-ico"><i class="fas fa-hospital-user"></i></span><div class="grow">' +
      '<b class="nombre">' + esc(c.paciente.nombre) + '</b><div class="meta">Cuenta del consultorio · expediente ' + esc(c.paciente.expediente || '') + '</div>' +
      '<div class="chips">' + chips.join('') + '</div>' + (notas.length ? '<ul>' + notas.join('') + '</ul>' : '') + '</div>' +
      '<button type="button" class="btn btn-icon btn-ghost" title="Quitar cuenta" onclick="POS.quitarCuenta()"><i class="fas fa-xmark"></i></button>';
    box.hidden = false;
  }

  function cargarCuenta(params) {
    return FC.json(CFG.urls.cuenta + '?' + FC.qs(params)).then(function (res) {
      if (!res.success) { FC.swal({ icon: 'warning', title: 'No se pudo cargar', text: res.message }); return; }
      var c = res.data;
      state.carrito = state.carrito.filter(function (i) { return i.tipo !== 'honorario'; });
      c.items.forEach(function (it) { agregar(it, it.cant, true); });
      state.cuenta = c;
      seleccionarCliente(c.paciente.cliente_id || null, c.paciente.nombre.toUpperCase());
      pintarCuenta(); render();
      if (!c.items.length) FC.toast('No hay artículos por cobrar en esta cuenta', 'info', 5000);
      else FC.toast('Cuenta de ' + c.paciente.nombre + ' cargada', 'success');
      if (c.items.some(function (i) { return i.antibiotico; })) FC.toast('La receta incluye antibiótico(s): conserva la copia de la receta.', 'warning', 7000);
    }).catch(function () { FC.toast('No se pudo conectar con el servidor', 'danger'); });
  }

  function quitarCuenta(silencioso) {
    if (!state.cuenta) return;
    state.cuenta = null;
    state.carrito = state.carrito.filter(function (i) { return i.tipo !== 'honorario'; });
    pintarCuenta();
    if (silencioso !== true) { seleccionarCliente(null, 'PÚBLICO GENERAL'); render(); }
  }

  function surtirReceta() {
    if (modalAbierto()) return;
    FC.swal({
      title: 'Surtir receta', input: 'text', inputPlaceholder: 'Folio de la receta (R000123 o 123)',
      text: 'Se cargan los medicamentos ligados al inventario y, si está pendiente, la consulta.',
      showCancelButton: true, confirmButtonText: 'Cargar', inputValidator: function (v) { if (!v || !v.trim()) return 'Escribe el folio'; }
    }).then(function (r) { if (r.isConfirmed) cargarCuenta({ folio: r.value.trim() }); else focusScan(); });
  }

  /* ---------------- atajos ---------------- */
  document.addEventListener('keydown', function (e) {
    if (e.key === 'F1') { e.preventDefault(); abrirSeleccion('productos'); }
    else if (e.key === 'F2') { e.preventDefault(); abrirSeleccion('procedimientos'); }
    else if (e.key === 'F3') { e.preventDefault(); abrirSeleccion('consultas'); }
    else if (e.key === 'F4') { e.preventDefault(); abrirClientes(); }
    else if (e.key === 'F6') { e.preventDefault(); surtirReceta(); }
    else if (e.key === 'F12') {
      e.preventDefault();
      if ($('#modalTicket').hasClass('show')) nuevaVenta(); else if (!window.Swal || !Swal.isVisible()) cobrar();
    }
  });

  // Avisar si se intenta salir con artículos en el carrito
  window.addEventListener('beforeunload', function (e) {
    if (state.carrito.length && !state.ventaActual) { e.preventDefault(); e.returnValue = ''; }
  });

  window.POS = {
    abrirSeleccion: abrirSeleccion, abrirClientes: abrirClientes, seleccionarCliente: seleccionarCliente,
    nuevoCliente: nuevoCliente, cobrar: cobrar, elegirMetodo: elegirMetodo, imprimirTicket: imprimirTicket,
    nuevaVenta: nuevaVenta, vaciar: vaciar, surtirReceta: surtirReceta, quitarCuenta: quitarCuenta
  };

  render();
  if (CFG.cuentaInicial && Object.keys(CFG.cuentaInicial).length) cargarCuenta(CFG.cuentaInicial);
})(window, document, jQuery);
