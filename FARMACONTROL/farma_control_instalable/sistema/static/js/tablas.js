/* FarmaControl · Herramientas de tabla
 *
 * Cualquier <table data-tabla="Título"> recibe su propia barra:
 *   - filtro de texto y filtros por columna (<th data-filtro>) que solo afectan a ESA tabla
 *   - Imprimir (formato sobrio en negro), Excel (.xlsx) y PDF, con las filas visibles
 *
 * Atributos opcionales:
 *   data-subtitulo="Del 01/10 al 31/10"   texto bajo el título al imprimir/exportar
 *   data-orientacion="landscape"          PDF / impresión horizontal
 *   <th data-no-export>                   columna que no se imprime (botones)
 *   <th data-filtro>                      agrega un selector con los valores de esa columna
 *   <td data-export="texto">              texto a exportar en lugar del contenido visible
 *   <tr class="alerta"> / <td class="alerta">   se imprime en rojo (stock bajo, vencido…)
 */
(function (window, document) {
  'use strict';
  var CDN = {
    xlsx: 'https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js',
    jspdf: 'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js',
    autotable: 'https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.8.2/jspdf.plugin.autotable.min.js'
  };
  var NEGOCIO = (document.querySelector('meta[name="negocio"]') || {}).content || 'FarmaControl';
  var USUARIO = (document.querySelector('meta[name="usuario"]') || {}).content || '';
  var cargados = {};
  function cargar(url) {
    if (!cargados[url]) cargados[url] = new Promise(function (ok, mal) {
      var s = document.createElement('script'); s.src = url; s.onload = ok; s.onerror = mal; document.head.appendChild(s);
    });
    return cargados[url];
  }
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
  var limpio = function (t) { return String(t || '').replace(/\s*\n\s*/g, ' · ').replace(/\s+/g, ' ').replace(/^ · | · $/g, '').trim(); };
  var ahora = function () { return new Date().toLocaleString('es-MX', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }); };
  var archivo = function (t) { return (t || 'tabla').normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^\w]+/g, '_').replace(/^_|_$/g, '').toLowerCase() + '_' + new Date().toISOString().slice(0, 10); };

  function Tabla(tabla) {
    this.t = tabla;
    this.titulo = tabla.getAttribute('data-tabla') || 'Tabla';
    this.sub = tabla.getAttribute('data-subtitulo') || '';
    this.horizontal = tabla.getAttribute('data-orientacion') === 'landscape';
    this.ths = Array.prototype.slice.call(tabla.querySelectorAll('thead th'));
    this.cols = this.ths.map(function (th, i) { return th.hasAttribute('data-no-export') ? -1 : i; }).filter(function (i) { return i >= 0; });
    this.filtros = {};
    this.barra();
    this.aplicar();
  }
  Tabla.prototype.filas = function (todas) {
    return Array.prototype.filter.call(this.t.tBodies[0] ? this.t.tBodies[0].rows : [], function (tr) {
      return !tr.hasAttribute('data-empty') && (todas || tr.style.display !== 'none');
    });
  };
  Tabla.prototype.texto = function (td) {
    if (!td) return '';
    if (td.hasAttribute('data-export')) return td.getAttribute('data-export');
    return limpio(td.innerText || td.textContent);
  };
  Tabla.prototype.barra = function () {
    var self = this, caja = this.t.closest('.table-wrap') || this.t;
    var b = document.createElement('div');
    b.className = 'tabla-barra no-print';
    var selects = this.ths.map(function (th, i) {
      if (!th.hasAttribute('data-filtro')) return '';
      var vals = {};
      self.filas(true).forEach(function (tr) { var v = self.texto(tr.cells[i]); if (v) vals[v] = 1; });
      var ops = Object.keys(vals).sort(function (a, c) { return a.localeCompare(c, 'es'); });
      if (ops.length < 2) return '';
      return '<select class="form-control form-control-sm" data-col="' + i + '" title="Filtrar por ' + esc(limpio(th.textContent)) + '"><option value="">' + esc(limpio(th.textContent)) + ': todos</option>' +
        ops.map(function (v) { return '<option>' + esc(v) + '</option>'; }).join('') + '</select>';
    }).join('');
    b.innerHTML = '<div class="tabla-filtros"><div class="input-icon"><i class="fas fa-magnifying-glass"></i><input type="search" class="form-control form-control-sm" placeholder="Filtrar esta tabla…" data-q></div>' + selects +
      '<span class="tabla-cuenta" data-cuenta></span></div>' +
      '<div class="tabla-acciones"><button type="button" class="btn btn-glass btn-sm" data-act="imprimir" title="Imprimir solo esta tabla"><i class="fas fa-print"></i> Imprimir</button>' +
      '<button type="button" class="btn btn-glass btn-sm" data-act="excel" title="Descargar Excel"><i class="fas fa-file-excel"></i> Excel</button>' +
      '<button type="button" class="btn btn-glass btn-sm" data-act="pdf" title="Descargar PDF"><i class="fas fa-file-pdf"></i> PDF</button></div>';
    caja.parentNode.insertBefore(b, caja);
    this.b = b;
    b.querySelector('[data-q]').addEventListener('input', function () { self.q = this.value.trim().toLowerCase(); self.aplicar(); });
    b.querySelectorAll('select[data-col]').forEach(function (s) { s.addEventListener('change', function () { self.filtros[s.getAttribute('data-col')] = s.value; self.aplicar(); }); });
    b.querySelectorAll('[data-act]').forEach(function (btn) { btn.addEventListener('click', function () { self[btn.getAttribute('data-act')](); }); });
  };
  Tabla.prototype.buscar = function (texto) { var i = this.b.querySelector('[data-q]'); i.value = texto; this.q = texto.toLowerCase(); this.aplicar(); };
  Tabla.prototype.aplicar = function () {
    var self = this, total = 0, vis = 0;
    this.filas(true).forEach(function (tr) {
      total++;
      var ok = !self.q || (tr.innerText || tr.textContent).toLowerCase().indexOf(self.q) !== -1;
      Object.keys(self.filtros).forEach(function (c) { if (ok && self.filtros[c] && self.texto(tr.cells[c]) !== self.filtros[c]) ok = false; });
      tr.style.display = ok ? '' : 'none'; if (ok) vis++;
    });
    var c = this.b.querySelector('[data-cuenta]');
    c.textContent = total ? (vis === total ? total + ' fila' + (total === 1 ? '' : 's') : vis + ' de ' + total + ' filas') : '';
  };
  Tabla.prototype.descripcionFiltro = function () {
    var self = this, partes = [];
    if (this.q) partes.push('búsqueda «' + this.q + '»');
    Object.keys(this.filtros).forEach(function (c) { if (self.filtros[c]) partes.push(limpio(self.ths[c].textContent) + ': ' + self.filtros[c]); });
    return partes.join(' · ');
  };
  Tabla.prototype.datos = function () {
    var self = this;
    var enc = this.cols.map(function (i) { return limpio(self.ths[i].textContent); });
    var filas = this.filas().map(function (tr) {
      var roja = tr.classList.contains('alerta');
      return { roja: roja, celdas: self.cols.map(function (i) { var td = tr.cells[i]; return { v: self.texto(td), roja: roja || (td && td.classList.contains('alerta')), num: td && td.classList.contains('num') }; }) };
    });
    return { enc: enc, filas: filas };
  };

  /* ---------- Imprimir: hoja sobria en negro, rojo solo para alertas ---------- */
  Tabla.prototype.imprimir = function () {
    var d = this.datos(), self = this;
    var filtro = this.descripcionFiltro();
    var html = '<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>' + esc(this.titulo) + '</title><style>' +
      '@page{size:letter ' + (this.horizontal ? 'landscape' : 'portrait') + ';margin:12mm 10mm}' +
      '*{box-sizing:border-box}body{font-family:Arial,Helvetica,sans-serif;color:#000;margin:24px 28px 70px;font-size:9pt}@media print{body{margin:0}}' +
      'header{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:2px solid #000;padding-bottom:6px;margin-bottom:8px}' +
      'h1{font-size:14pt;margin:0}.neg{font-size:8.5pt;font-weight:bold;text-transform:uppercase;letter-spacing:.05em}.meta{text-align:right;font-size:8pt;line-height:1.4}' +
      '.sub{font-size:9pt;margin:2px 0 0}table{width:100%;border-collapse:collapse}th{background:#000;color:#fff;text-align:left;font-size:7.8pt;text-transform:uppercase;padding:4px 5px;border:1px solid #000;-webkit-print-color-adjust:exact;print-color-adjust:exact}' +
      'td{padding:3px 5px;border:1px solid #777;vertical-align:top;font-size:8.4pt}tr:nth-child(even) td{background:#f2f2f2;-webkit-print-color-adjust:exact;print-color-adjust:exact}' +
      'td.num{text-align:right;white-space:nowrap}.roja{color:#c00;font-weight:bold}thead{display:table-header-group}tr{page-break-inside:avoid}' +
      'footer{margin-top:8px;font-size:7.5pt;display:flex;justify-content:space-between}.tb{position:fixed;bottom:16px;right:16px}@media print{.tb{display:none}}' +
      '.tb button{padding:8px 16px;font-size:13px;border-radius:20px;border:1px solid #000;background:#000;color:#fff;cursor:pointer}</style></head><body>' +
      '<div class="tb"><button onclick="window.print()">Imprimir</button></div>' +
      '<header><div><div class="neg">' + esc(NEGOCIO) + '</div><h1>' + esc(this.titulo) + '</h1>' + (this.sub ? '<div class="sub">' + esc(this.sub) + '</div>' : '') +
      (filtro ? '<div class="sub">Filtro: ' + esc(filtro) + '</div>' : '') + '</div>' +
      '<div class="meta">Generado: ' + esc(ahora()) + (USUARIO ? '<br>Por: ' + esc(USUARIO) : '') + '<br>Registros: ' + d.filas.length + '</div></header>' +
      '<table><thead><tr>' + d.enc.map(function (h) { return '<th>' + esc(h) + '</th>'; }).join('') + '</tr></thead><tbody>' +
      (d.filas.length ? d.filas.map(function (f) { return '<tr>' + f.celdas.map(function (c) { return '<td class="' + (c.num ? 'num ' : '') + (c.roja ? 'roja' : '') + '">' + esc(c.v) + '</td>'; }).join('') + '</tr>'; }).join('')
        : '<tr><td colspan="' + d.enc.length + '" style="text-align:center;padding:14px">Sin registros</td></tr>') +
      '</tbody></table><footer><span>' + esc(self.titulo) + '</span><span>' + esc(NEGOCIO) + '</span></footer>' +
      '<script>window.onload=function(){setTimeout(function(){window.print()},250)}<\/script></body></html>';
    var w = window.open('', '_blank');
    if (!w) { (window.FC && FC.toast) ? FC.toast('Permite ventanas emergentes para imprimir', 'warning') : alert('Permite ventanas emergentes para imprimir'); return; }
    w.document.open(); w.document.write(html); w.document.close();
  };

  /* ---------- Excel (.xlsx). Sin internet: CSV que Excel abre igual ---------- */
  Tabla.prototype.excel = function () {
    var d = this.datos(), self = this, nombre = archivo(this.titulo);
    var aoa = [[NEGOCIO], [this.titulo]];
    if (this.sub) aoa.push([this.sub]);
    var f = this.descripcionFiltro(); if (f) aoa.push(['Filtro: ' + f]);
    aoa.push(['Generado: ' + ahora()]); aoa.push([]);
    var inicio = aoa.length;
    aoa.push(d.enc);
    d.filas.forEach(function (fila) { aoa.push(fila.celdas.map(function (c) { return c.num && /^-?\$?[\d,]+(\.\d+)?$/.test(c.v.replace(/\s/g, '')) ? Number(c.v.replace(/[$,\s]/g, '')) : c.v; })); });
    cargar(CDN.xlsx).then(function () {
      var ws = XLSX.utils.aoa_to_sheet(aoa);
      ws['!cols'] = d.enc.map(function (h, i) { var m = h.length; d.filas.forEach(function (r) { m = Math.max(m, String(r.celdas[i].v).length); }); return { wch: Math.min(Math.max(m + 2, 8), 50) }; });
      ws['!autofilter'] = { ref: XLSX.utils.encode_range({ s: { r: inicio, c: 0 }, e: { r: inicio + d.filas.length, c: d.enc.length - 1 } }) };
      var wb = XLSX.utils.book_new(); XLSX.utils.book_append_sheet(wb, ws, self.titulo.slice(0, 31).replace(/[\\\/\?\*\[\]:]/g, ' '));
      XLSX.writeFile(wb, nombre + '.xlsx');
    }).catch(function () {
      var csv = '﻿' + aoa.map(function (r) { return r.map(function (v) { v = String(v == null ? '' : v); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; }).join(','); }).join('\r\n');
      var a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' })); a.download = nombre + '.csv'; a.click();
    });
  };

  /* ---------- PDF descargable. Sin internet: ventana de impresión (Guardar como PDF) ---------- */
  Tabla.prototype.pdf = function () {
    var d = this.datos(), self = this;
    cargar(CDN.jspdf).then(function () { return cargar(CDN.autotable); }).then(function () {
      var doc = new window.jspdf.jsPDF({ orientation: self.horizontal ? 'landscape' : 'portrait', unit: 'pt', format: 'letter' });
      var ancho = doc.internal.pageSize.getWidth(), y = 34;
      doc.setFont('helvetica', 'bold'); doc.setFontSize(8); doc.text(NEGOCIO.toUpperCase(), 30, y);
      doc.setFontSize(14); doc.text(self.titulo, 30, y + 16);
      doc.setFont('helvetica', 'normal'); doc.setFontSize(8);
      doc.text('Generado: ' + ahora() + (USUARIO ? ' · ' + USUARIO : ''), ancho - 30, y, { align: 'right' });
      doc.text('Registros: ' + d.filas.length, ancho - 30, y + 11, { align: 'right' });
      var lineaY = y + 22;
      if (self.sub) { doc.setFontSize(9); doc.text(self.sub, 30, y + 29); lineaY = y + 34; }
      var f = self.descripcionFiltro(); if (f) { doc.setFontSize(8); doc.text('Filtro: ' + f, 30, lineaY + 6); lineaY += 12; }
      doc.setLineWidth(1.5); doc.line(30, lineaY, ancho - 30, lineaY);
      doc.autoTable({
        startY: lineaY + 8, margin: { left: 30, right: 30 },
        head: [d.enc], body: d.filas.map(function (r) { return r.celdas.map(function (c) { return c.v; }); }),
        styles: { font: 'helvetica', fontSize: 7.6, textColor: 0, lineColor: [120, 120, 120], lineWidth: .4, cellPadding: 3 },
        headStyles: { fillColor: [0, 0, 0], textColor: 255, fontStyle: 'bold', fontSize: 7.2 },
        alternateRowStyles: { fillColor: [242, 242, 242] },
        didParseCell: function (h) {
          if (h.section !== 'body') return;
          var c = d.filas[h.row.index].celdas[h.column.index];
          if (c.roja) { h.cell.styles.textColor = [200, 0, 0]; h.cell.styles.fontStyle = 'bold'; }
          if (c.num) h.cell.styles.halign = 'right';
        },
        didDrawPage: function () {
          var p = doc.internal.getNumberOfPages(), alto = doc.internal.pageSize.getHeight();
          doc.setFontSize(7); doc.setTextColor(0); doc.text(self.titulo + ' · ' + NEGOCIO, 30, alto - 16);
          doc.text('Página ' + p, ancho - 30, alto - 16, { align: 'right' });
        }
      });
      doc.save(archivo(self.titulo) + '.pdf');
    }).catch(function () { self.imprimir(); });
  };

  var instancias = [];
  window.FCTablas = {
    iniciar: function (raiz) {
      (raiz || document).querySelectorAll('table[data-tabla]').forEach(function (t) { if (!t._fcTabla) { t._fcTabla = new Tabla(t); instancias.push(t._fcTabla); } });
    },
    de: function (sel) { var t = typeof sel === 'string' ? document.querySelector(sel) : sel; return t && t._fcTabla; }
  };
  document.addEventListener('DOMContentLoaded', function () { window.FCTablas.iniciar(); });
})(window, document);
