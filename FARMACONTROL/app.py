import pymysql
import time
import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from pymysql.cursors import DictCursor 
from functools import wraps
from collections import defaultdict

app = Flask(__name__)
app.secret_key = "131004131004"

# ==========================================
# CONFIGURACIÓN DE AUTENTICACIÓN
# ==========================================
login_manager = LoginManager(app)
login_manager.login_view = 'login'

def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.rol != 1:
            flash('Acceso restringido: Solo para Administradores', 'danger')
            return redirect(url_for('inicio_farmacia_route'))
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def session_management():
    if not current_user.is_authenticated and request.endpoint not in ['login', 'static']:
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'message': 'Sesión expirada'}), 401
        return redirect(url_for('login'))
    session.permanent = False

class User(UserMixin):
    def __init__(self, data):
        self.id = data['id']
        self.nombre = data['nombre']
        self.rol = data['rol']

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, nombre, rol FROM usuarios WHERE id = %s AND status = 1", (user_id,))
            data = cursor.fetchone()
            return User(data) if data else None
    finally:
        conn.close()

# ==========================================
# CONEXIÓN A BASE DE DATOS (MÉTODO PYMYSQL)
# ==========================================
def get_db_connection():
    return pymysql.connect(
        host='localhost', 
        user='root', 
        password='131004131004',
        db='medicalife', 
        charset='utf8mb4', 
        cursorclass=DictCursor, 
        autocommit=True
    )

# ==========================================
# RUTAS DE ACCESO Y LOGIN
# ==========================================
@app.route('/')
def index():
    if not current_user.is_authenticated:
        # Limpiar sesión si existe
        session.clear()
        return redirect(url_for('login'))
    
    # Verificar que el usuario aún exista en la BD
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM usuarios WHERE id = %s AND status = 1", (current_user.id,))
            if not cursor.fetchone():
                # Usuario eliminado o inactivo
                logout_user()
                session.clear()
                flash('Tu cuenta ha sido desactivada', 'danger')
                return redirect(url_for('login'))
    finally:
        conn.close()
    
    return redirect(url_for('inicio')) if current_user.rol == 1 else redirect(url_for('inicio_farmacia_route'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('correo') 
        pwd = request.form.get('password')
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, nombre, rol FROM usuarios WHERE username = %s AND password = %s AND status = 1", (username, pwd))
                u = cursor.fetchone()
                if u:
                    login_user(User(u), remember=False)
                    return redirect(url_for('inicio')) if u['rol'] == 1 else redirect(url_for('inicio_farmacia_route'))
                flash('Credenciales incorrectas o cuenta inactiva', 'danger')
        finally:
            conn.close()
    return render_template('login.html')

@app.route('/inicio')
@login_required
@admin_only
def inicio():
    # Dashboard mejorado con estadísticas
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            hoy = datetime.now().date()
            
            # Estadísticas del día
            cursor.execute("""
                SELECT 
                    COUNT(*) as ventas_hoy,
                    IFNULL(SUM(total), 0) as ingresos_hoy,
                    IFNULL(SUM(CASE WHEN metodo_pago_id = 1 THEN total ELSE 0 END), 0) as efectivo_hoy,
                    IFNULL(SUM(CASE WHEN metodo_pago_id = 2 THEN total ELSE 0 END), 0) as tarjeta_hoy,
                    IFNULL(SUM(CASE WHEN metodo_pago_id = 3 THEN total ELSE 0 END), 0) as transferencia_hoy
                FROM ventas 
                WHERE DATE(fecha) = %s AND status = 1
            """, (hoy,))
            estadisticas = cursor.fetchone()
            
            # Productos con stock bajo
            cursor.execute("""
                SELECT COUNT(*) as stock_bajo
                FROM productos 
                WHERE stock_actual <= stock_minimo AND status = 1
            """)
            stock_bajo = cursor.fetchone()
            
            # Próximos a caducar (15 días)
            cursor.execute("""
                SELECT COUNT(*) as proximos_caducar
                FROM productos 
                WHERE fecha_caducidad <= CURDATE() + INTERVAL 15 DAY 
                AND fecha_caducidad >= CURDATE()
                AND status = 1
            """)
            caducidad = cursor.fetchone()
            
            # Antibióticos bajos en stock
            cursor.execute("""
                SELECT COUNT(*) as antibioticos_bajo
                FROM productos 
                WHERE antibiotico = 1 AND stock_actual <= stock_minimo AND status = 1
            """)
            antibioticos_bajo = cursor.fetchone()
            
            # Ventas recientes (últimas 10)
            cursor.execute("""
                SELECT v.folio, v.fecha, u.nombre as vendedor, v.total 
                FROM ventas v
                JOIN usuarios u ON v.usuario_id = u.id
                WHERE DATE(v.fecha) = %s AND v.status = 1
                ORDER BY v.fecha DESC LIMIT 10
            """, (hoy,))
            ventas_recientes = cursor.fetchall()
            
            # Top 5 productos más vendidos hoy
            cursor.execute("""
                SELECT p.nombre, SUM(dv.cantidad) as cantidad_vendida
                FROM detalle_ventas dv
                JOIN productos p ON dv.producto_id = p.id
                JOIN ventas v ON dv.venta_id = v.id
                WHERE DATE(v.fecha) = %s AND v.status = 1
                GROUP BY p.id, p.nombre
                ORDER BY cantidad_vendida DESC
                LIMIT 5
            """, (hoy,))
            top_productos = cursor.fetchall()
            
            # Cortes abiertos
            cursor.execute("""
                SELECT COUNT(*) as cortes_abiertos
                FROM cortes_caja 
                WHERE cerrado = 0 AND status = 1
            """)
            cortes_abiertos = cursor.fetchone()
            
        return render_template('inicio.html', 
                             estadisticas=estadisticas,
                             stock_bajo=stock_bajo['stock_bajo'],
                             proximos_caducar=caducidad['proximos_caducar'],
                             antibioticos_bajo=antibioticos_bajo['antibioticos_bajo'],
                             ventas_recientes=ventas_recientes,
                             top_productos=top_productos,
                             cortes_abiertos=cortes_abiertos['cortes_abiertos'])
    finally:
        conn.close()

@app.route('/inicio_farmacia')
@login_required
def inicio_farmacia_route():
    if current_user.rol == 1:
        return render_template('inicio.html')
    
    # Dashboard para farmacéuticos
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            hoy = datetime.now().date()
            
            # Estadísticas personales del día
            cursor.execute("""
                SELECT 
                    COUNT(*) as ventas_hoy,
                    IFNULL(SUM(total), 0) as ingresos_hoy,
                    IFNULL(SUM(CASE WHEN metodo_pago_id = 1 THEN total ELSE 0 END), 0) as efectivo_hoy,
                    IFNULL(SUM(CASE WHEN metodo_pago_id = 2 THEN total ELSE 0 END), 0) as tarjeta_hoy
                FROM ventas 
                WHERE DATE(fecha) = %s AND usuario_id = %s AND status = 1
            """, (hoy, current_user.id))
            estadisticas = cursor.fetchone()
            
            # Verificar si hay corte de caja abierto
            cursor.execute("""
                SELECT COUNT(*) as corte_abierto
                FROM cortes_caja 
                WHERE usuario_id = %s AND cerrado = 0 AND status = 1
            """, (current_user.id,))
            corte = cursor.fetchone()
            
            # Últimas 5 ventas del usuario
            cursor.execute("""
                SELECT v.folio, v.fecha, v.total, v.metodo_pago_id
                FROM ventas v
                WHERE DATE(v.fecha) = %s AND v.usuario_id = %s AND v.status = 1
                ORDER BY v.fecha DESC LIMIT 5
            """, (hoy, current_user.id))
            mis_ventas = cursor.fetchall()
            
        return render_template('inicio_farmaceutico.html', 
                             estadisticas=estadisticas,
                             corte_abierto=corte['corte_abierto'],
                             mis_ventas=mis_ventas)
    finally:
        conn.close()

# ==========================================
# MÓDULO DE INVENTARIO (MEJORADO)
# ==========================================
@app.route('/inventario')
@login_required
def listar_productos():
    search_query = request.args.get('search', '')
    alerta_stock = request.args.get('alerta', '')
    seccion_id = request.args.get('seccion_id', '')
    
    hoy = datetime.now().date()
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Obtener secciones para el filtro
            cursor.execute("SELECT id, nombre FROM secciones WHERE status = 1")
            secciones = cursor.fetchall()
            
            sql = """
                SELECT p.*, s.nombre AS nombre_seccion 
                FROM productos p 
                LEFT JOIN secciones s ON p.seccion_id = s.id 
                WHERE p.status = 1
            """
            params = []
            
            if search_query:
                sql += " AND (p.nombre LIKE %s OR p.codigo_barras LIKE %s OR p.lote LIKE %s)"
                term = f"%{search_query}%"
                params.extend([term, term, term])
            
            if alerta_stock == 'bajo':
                sql += " AND p.stock_actual <= p.stock_minimo"
            elif alerta_stock == 'caducidad':
                sql += " AND p.fecha_caducidad <= CURDATE() + INTERVAL 15 DAY"
            
            if seccion_id and seccion_id != '':
                sql += " AND p.seccion_id = %s"
                params.append(seccion_id)
            
            sql += " ORDER BY p.nombre ASC"
            cursor.execute(sql, params)
            productos = cursor.fetchall()
            
            # Calcular totales
            total_productos = len(productos)
            total_stock = sum(p['stock_actual'] for p in productos)
            total_valor = sum(p['stock_actual'] * p['precio_costo'] for p in productos)
            
    except Exception as e:
        flash(f"Error al cargar inventario: {str(e)}", "danger")
        productos = []
        total_productos = 0
        total_stock = 0
        total_valor = 0
    finally:
        conn.close()
    
    return render_template('inventario.html', 
                           productos=productos, 
                           secciones=secciones,
                           search_query=search_query, 
                           alerta_stock=alerta_stock,
                           seccion_id=seccion_id,
                           hoy=hoy,
                           total_productos=total_productos,
                           total_stock=total_stock,
                           total_valor=total_valor)

@app.route('/producto/gestion', defaults={'id': None}, methods=['GET', 'POST'])
@app.route('/producto/gestion/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_only
def agregar_editar_producto(id=None):
    conn = get_db_connection()
    producto = None
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, nombre FROM secciones WHERE status = 1")
            secciones = cursor.fetchall()
            if id:
                cursor.execute("SELECT * FROM productos WHERE id = %s", (id,))
                producto = cursor.fetchone()
        if request.method == 'POST':
            nombre = request.form.get('nombre')
            codigo_barras = request.form.get('codigo_barras')
            lote = request.form.get('lote')
            stock_entrada = int(request.form.get('stock_entrada', 0))
            stock_minimo = int(request.form.get('stock_minimo', 0))
            precio_costo = float(request.form.get('precio_costo', 0))
            precio_publico = float(request.form.get('precio_publico', 0))
            fecha_caducidad = request.form.get('fecha_caducidad')
            antibiotico = 1 if request.form.get('antibiotico') else 0
            seccion_id = request.form.get('seccion_id')
            
            with conn.cursor() as cursor:
                if id:
                    # Verificar si se está agregando stock o solo editando
                    if stock_entrada > 0:
                        sql = """UPDATE productos SET nombre=%s, codigo_barras=%s, lote=%s, 
                                 stock_actual = stock_actual + %s, stock_minimo=%s, precio_costo=%s, 
                                 precio_publico=%s, fecha_caducidad=%s, antibiotico=%s, seccion_id=%s
                                 WHERE id=%s"""
                        cursor.execute(sql, (nombre, codigo_barras, lote, stock_entrada, 
                                             stock_minimo, precio_costo, precio_publico, 
                                             fecha_caducidad, antibiotico, seccion_id, id))
                    else:
                        sql = """UPDATE productos SET nombre=%s, codigo_barras=%s, lote=%s, 
                                 stock_minimo=%s, precio_costo=%s, 
                                 precio_publico=%s, fecha_caducidad=%s, antibiotico=%s, seccion_id=%s
                                 WHERE id=%s"""
                        cursor.execute(sql, (nombre, codigo_barras, lote, 
                                             stock_minimo, precio_costo, precio_publico, 
                                             fecha_caducidad, antibiotico, seccion_id, id))
                else:
                    sql = """INSERT INTO productos (nombre, codigo_barras, lote, stock_actual, 
                             stock_minimo, precio_costo, precio_publico, fecha_caducidad, 
                             antibiotico, seccion_id, status) 
                             VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)"""
                    cursor.execute(sql, (nombre, codigo_barras, lote, stock_entrada, 
                                         stock_minimo, precio_costo, precio_publico, 
                                         fecha_caducidad, antibiotico, seccion_id))
            conn.commit()
            flash('¡Producto guardado correctamente!', 'success')
            return redirect(url_for('listar_productos'))
    except Exception as e:
        flash(f'Error en la operación: {str(e)}', 'danger')
    finally:
        conn.close()
    return render_template('agregar_producto.html', producto=producto, secciones=secciones)

@app.route('/producto/eliminar/<int:id>', methods=['POST'])
@login_required
@admin_only
def eliminar_producto(id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE productos SET status = 0 WHERE id = %s", (id,))
        conn.commit()
        flash('Producto removido del inventario.', 'success')
    except Exception as e:
        flash(f'Error al eliminar: {str(e)}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('listar_productos'))

# ==========================================
# MÓDULO DE USUARIOS (MEJORADO)
# ==========================================
@app.route('/usuarios')
@login_required
@admin_only
def listar_usuarios():
    search_query = request.args.get('search', '')
    rol_filter = request.args.get('rol', '')
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT id, nombre, username as correo, rol, status FROM usuarios WHERE status = 1"
            params = []
            
            if search_query:
                sql += " AND (nombre LIKE %s OR username LIKE %s)"
                params.extend([f"%{search_query}%", f"%{search_query}%"])
            
            if rol_filter and rol_filter != '':
                sql += " AND rol = %s"
                params.append(rol_filter)
            
            sql += " ORDER BY nombre ASC"
            cursor.execute(sql, params)
            usuarios = cursor.fetchall()
            
            # Estadísticas
            cursor.execute("SELECT COUNT(*) as total FROM usuarios WHERE status = 1")
            total_usuarios = cursor.fetchone()['total']
            
            cursor.execute("SELECT COUNT(*) as admin FROM usuarios WHERE status = 1 AND rol = 1")
            total_admin = cursor.fetchone()['admin']
            
            cursor.execute("SELECT COUNT(*) as farmaceuticos FROM usuarios WHERE status = 1 AND rol = 2")
            total_farmaceuticos = cursor.fetchone()['farmaceuticos']
            
        return render_template('usuarios.html', 
                               usuarios=usuarios, 
                               search_query=search_query,
                               rol_filter=rol_filter,
                               total_usuarios=total_usuarios,
                               total_admin=total_admin,
                               total_farmaceuticos=total_farmaceuticos)
    finally:
        conn.close()

@app.route('/usuario/nuevo', methods=['GET', 'POST'])
@app.route('/usuario/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_only
def agregar_editar_usuario(id=None):
    conn = get_db_connection()
    usuario = None
    if id:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, nombre, username, rol FROM usuarios WHERE id = %s", (id,))
            usuario = cursor.fetchone()
    
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        username = request.form.get('correo') 
        contrasena = request.form.get('password')
        rol = int(request.form.get('rol'))
        
        try:
            with conn.cursor() as cursor:
                if id:
                    if contrasena and contrasena.strip():
                        sql = "UPDATE usuarios SET nombre=%s, username=%s, password=%s, rol=%s WHERE id=%s"
                        cursor.execute(sql, (nombre, username, contrasena, rol, id))
                    else:
                        sql = "UPDATE usuarios SET nombre=%s, username=%s, rol=%s WHERE id=%s"
                        cursor.execute(sql, (nombre, username, rol, id))
                else:
                    if not contrasena or not contrasena.strip():
                        flash('La contraseña es obligatoria para nuevos usuarios', 'danger')
                        return redirect(url_for('agregar_editar_usuario', id=id))
                    
                    sql = "INSERT INTO usuarios (nombre, username, password, rol, status) VALUES (%s, %s, %s, %s, 1)"
                    cursor.execute(sql, (nombre, username, contrasena, rol))
                
                conn.commit()
                flash('Operación exitosa.', 'success')
                return redirect(url_for('listar_usuarios'))
                
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
        finally:
            conn.close()
    
    return render_template('agregar_usuario.html', usuario=usuario)

@app.route('/usuario/eliminar/<int:id>', methods=['POST'])
@login_required
@admin_only
def eliminar_usuario(id):
    if id == current_user.id:
        flash('No puedes eliminarte a ti mismo', 'danger')
        return redirect(url_for('listar_usuarios'))
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE usuarios SET status = 0 WHERE id = %s", (id,))
        conn.commit()
        flash('Usuario eliminado correctamente', 'success')
    except Exception as e:
        flash(f'Error al eliminar usuario: {str(e)}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('listar_usuarios'))

# ==========================================
# MÓDULO DE CORTE DE CAJA COMPLETAMENTE MEJORADO
# ==========================================
@app.route('/corte_caja')
@login_required
def corte_caja():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Verificar si hay corte abierto
            cursor.execute("""
                SELECT id, monto_inicial, fecha_apertura 
                FROM cortes_caja 
                WHERE usuario_id = %s AND cerrado = 0 AND status = 1 
                LIMIT 1
            """, (current_user.id,))
            corte = cursor.fetchone()
            
            if not corte:
                # Mostrar historial de cortes cerrados del usuario
                cursor.execute("""
                    SELECT id, fecha_apertura, fecha_cierre, monto_inicial, monto_final
                    FROM cortes_caja 
                    WHERE usuario_id = %s AND cerrado = 1 AND status = 1
                    ORDER BY fecha_cierre DESC
                    LIMIT 10
                """, (current_user.id,))
                historial = cursor.fetchall()
                return render_template('corte.html', datos=None, corte_abierto=False, historial=historial)
            
            # Calcular ventas durante el corte
            cursor.execute("""
                SELECT 
                    IFNULL(SUM(CASE WHEN metodo_pago_id = 1 THEN total ELSE 0 END), 0) as efectivo,
                    IFNULL(SUM(CASE WHEN metodo_pago_id = 2 THEN total ELSE 0 END), 0) as tarjeta,
                    IFNULL(SUM(CASE WHEN metodo_pago_id = 3 THEN total ELSE 0 END), 0) as transferencia,
                    IFNULL(SUM(CASE WHEN metodo_pago_id = 4 THEN total ELSE 0 END), 0) as otros,
                    COUNT(*) as total_ventas,
                    IFNULL(SUM(total), 0) as total_general
                FROM ventas 
                WHERE usuario_id = %s 
                AND fecha >= %s 
                AND status = 1
            """, (current_user.id, corte['fecha_apertura']))
            
            ventas = cursor.fetchone()
            
            # Obtener detalle de ventas para el corte
            cursor.execute("""
                SELECT v.folio, v.fecha, v.total, mp.nombre as metodo_pago, c.nombre as cliente
                FROM ventas v
                JOIN metodos_pago mp ON v.metodo_pago_id = mp.id
                LEFT JOIN clientes c ON v.cliente_id = c.id
                WHERE v.usuario_id = %s 
                AND v.fecha >= %s 
                AND v.status = 1
                ORDER BY v.fecha DESC
            """, (current_user.id, corte['fecha_apertura']))
            detalle_ventas = cursor.fetchall()
            
            # Preparar datos para el template
            datos = {
                'corte_id': corte['id'],
                'vendedor': current_user.nombre,
                'fecha_apertura': corte['fecha_apertura'].strftime('%d/%m/%Y %H:%M'),
                'fondo_inicial': corte['monto_inicial'],
                'ventas_efectivo': ventas['efectivo'],
                'ventas_tarjeta': ventas['tarjeta'],
                'ventas_transferencia': ventas['transferencia'],
                'ventas_otros': ventas['otros'],
                'total_ventas': ventas['total_ventas'],
                'total_general': float(corte['monto_inicial']) + float(ventas['total_general']),
                'monto_final_estimado': float(corte['monto_inicial']) + float(ventas['total_general'])
            }
            
            return render_template('corte.html', 
                                   datos=datos, 
                                   corte_abierto=True, 
                                   detalle_ventas=detalle_ventas)
    finally: 
        conn.close()

@app.route('/abrir_caja', methods=['POST'])
@login_required
def abrir_caja():
    monto = float(request.form.get('monto_inicial', 0))
    if monto < 0:
        flash('El monto inicial no puede ser negativo', 'danger')
        return redirect(url_for('corte_caja'))
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor: 
            # Verificar si ya hay un corte abierto
            cursor.execute("""
                SELECT id FROM cortes_caja 
                WHERE usuario_id = %s AND cerrado = 0 AND status = 1 
                LIMIT 1
            """, (current_user.id,))
            
            if cursor.fetchone():
                flash('Ya tienes un corte de caja abierto', 'warning')
                return redirect(url_for('corte_caja'))
            
            # Crear nuevo corte
            cursor.execute("""
                INSERT INTO cortes_caja (usuario_id, monto_inicial, cerrado, status) 
                VALUES (%s, %s, 0, 1)
            """, (current_user.id, monto))
            
            conn.commit()
            flash('Corte de caja abierto correctamente', 'success')
    except Exception as e:
        flash(f'Error al abrir caja: {str(e)}', 'danger')
    finally: 
        conn.close()
    return redirect(url_for('corte_caja'))

@app.route('/cerrar_caja', methods=['POST'])
@login_required
def cerrar_caja():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Obtener corte abierto
            cursor.execute("""
                SELECT id, monto_inicial, fecha_apertura 
                FROM cortes_caja 
                WHERE usuario_id = %s AND cerrado = 0 AND status = 1 
                LIMIT 1
            """, (current_user.id,))
            corte = cursor.fetchone()
            
            if not corte:
                flash('No hay un corte de caja abierto', 'danger')
                return redirect(url_for('corte_caja'))
            
            # Calcular ventas detalladas
            cursor.execute("""
                SELECT 
                    IFNULL(SUM(CASE WHEN metodo_pago_id = 1 THEN total ELSE 0 END), 0) as efectivo,
                    IFNULL(SUM(CASE WHEN metodo_pago_id = 2 THEN total ELSE 0 END), 0) as tarjeta,
                    IFNULL(SUM(CASE WHEN metodo_pago_id = 3 THEN total ELSE 0 END), 0) as transferencia,
                    IFNULL(SUM(CASE WHEN metodo_pago_id = 4 THEN total ELSE 0 END), 0) as otros,
                    IFNULL(SUM(total), 0) as total_ventas,
                    COUNT(*) as numero_ventas
                FROM ventas 
                WHERE usuario_id = %s 
                AND fecha >= %s 
                AND status = 1
            """, (current_user.id, corte['fecha_apertura']))
            
            ventas = cursor.fetchone()
            monto_final = corte['monto_inicial'] + ventas['total_ventas']
            
            # Actualizar corte
            cursor.execute("""
                UPDATE cortes_caja 
                SET cerrado = 1, fecha_cierre = NOW(), monto_final = %s 
                WHERE id = %s
            """, (monto_final, corte['id']))
            
            # Registrar en auditoría
            cursor.execute("""
                INSERT INTO auditoria_cortes 
                (corte_id, usuario_id, fecha_apertura, fecha_cierre, monto_inicial, monto_final, 
                 ventas_efectivo, ventas_tarjeta, ventas_transferencia, total_ventas) 
                VALUES (%s, %s, %s, NOW(), %s, %s, %s, %s, %s, %s)
            """, (corte['id'], current_user.id, corte['fecha_apertura'], 
                  corte['monto_inicial'], monto_final, 
                  ventas['efectivo'], ventas['tarjeta'], ventas['transferencia'], 
                  ventas['total_ventas']))
            
            conn.commit()
            
            # Preparar datos para el ticket
            datos_ticket = {
                'corte_id': corte['id'],
                'vendedor': current_user.nombre,
                'fecha_apertura': corte['fecha_apertura'].strftime('%d/%m/%Y %H:%M'),
                'fecha_cierre': datetime.now().strftime('%d/%m/%Y %H:%M'),
                'fondo_inicial': corte['monto_inicial'],
                'ventas_efectivo': ventas['efectivo'],
                'ventas_tarjeta': ventas['tarjeta'],
                'ventas_transferencia': ventas['transferencia'],
                'numero_ventas': ventas['numero_ventas'],
                'total_ventas': ventas['total_ventas'],
                'monto_final': monto_final,
                'diferencia': (corte['monto_inicial'] + ventas['total_ventas']) - monto_final
            }
            
            # Guardar en sesión para imprimir
            session['corte_ticket'] = datos_ticket
            
            # Cerrar sesión automáticamente
            logout_user()
            
            flash('Corte de caja cerrado exitosamente. La sesión se ha cerrado.', 'success')
            return render_template('ticket_corte.html', datos=datos_ticket)
            
    except Exception as e:
        if conn: conn.rollback()
        flash(f'Error al cerrar caja: {str(e)}', 'danger')
        return redirect(url_for('corte_caja'))
    finally:
        if conn: conn.close()

# ==========================================
# MÓDULO DE REIMPRESIÓN DE CORTES (NUEVO Y COMPLETO)
# ==========================================
@app.route('/reportes/reimpresion_cortes')
@login_required
@admin_only
def reimpresion_cortes():
    """Página principal para reimpresión de cortes de turno"""
    # Obtener parámetros de filtro
    fecha_inicio = request.args.get('fecha_inicio', '')
    fecha_fin = request.args.get('fecha_fin', '')
    usuario_id = request.args.get('usuario_id', '')
    tipo_filtro = request.args.get('tipo_filtro', 'todos')  # todos, hoy, semana, mes
    
    # Ajustar fechas según el tipo de filtro
    hoy = datetime.now().date()
    if tipo_filtro == 'hoy':
        fecha_inicio = hoy.strftime('%Y-%m-%d')
        fecha_fin = hoy.strftime('%Y-%m-%d')
    elif tipo_filtro == 'semana':
        fecha_inicio = (hoy - timedelta(days=7)).strftime('%Y-%m-%d')
        fecha_fin = hoy.strftime('%Y-%m-%d')
    elif tipo_filtro == 'mes':
        fecha_inicio = (hoy - timedelta(days=30)).strftime('%Y-%m-%d')
        fecha_fin = hoy.strftime('%Y-%m-%d')
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Obtener lista de usuarios (farmacéuticos)
            cursor.execute("SELECT id, nombre FROM usuarios WHERE status = 1 AND rol = 2 ORDER BY nombre")
            usuarios = cursor.fetchall()
            
            # Construir consulta para cortes cerrados
            sql = """
                SELECT 
                    cc.id as corte_id,
                    cc.fecha_apertura,
                    cc.fecha_cierre,
                    cc.monto_inicial,
                    cc.monto_final,
                    u.id as usuario_id,
                    u.nombre as usuario_nombre,
                    ac.ventas_efectivo,
                    ac.ventas_tarjeta,
                    ac.ventas_transferencia,
                    ac.total_ventas,
                    (cc.monto_final - cc.monto_inicial) as diferencia,
                    TIMESTAMPDIFF(MINUTE, cc.fecha_apertura, cc.fecha_cierre) as duracion_minutos,
                    (SELECT COUNT(*) FROM ventas v WHERE v.usuario_id = u.id 
                     AND v.fecha BETWEEN cc.fecha_apertura AND cc.fecha_cierre) as total_ventas_corte
                FROM cortes_caja cc
                JOIN usuarios u ON cc.usuario_id = u.id
                LEFT JOIN auditoria_cortes ac ON cc.id = ac.corte_id
                WHERE cc.cerrado = 1 
                AND cc.status = 1
            """
            params = []
            
            if fecha_inicio:
                sql += " AND DATE(cc.fecha_cierre) >= %s"
                params.append(fecha_inicio)
            if fecha_fin:
                sql += " AND DATE(cc.fecha_cierre) <= %s"
                params.append(fecha_fin)
            if usuario_id and usuario_id != '':
                sql += " AND cc.usuario_id = %s"
                params.append(usuario_id)
            
            sql += " ORDER BY cc.fecha_cierre DESC"
            cursor.execute(sql, params)
            cortes = cursor.fetchall()
            
            # Calcular estadísticas
            total_cortes = len(cortes)
            total_ventas = sum(c['total_ventas_corte'] or 0 for c in cortes)
            total_efectivo = sum(c['ventas_efectivo'] or 0 for c in cortes)
            total_tarjeta = sum(c['ventas_tarjeta'] or 0 for c in cortes)
            total_transferencia = sum(c['ventas_transferencia'] or 0 for c in cortes)
            total_monto_final = sum(c['monto_final'] or 0 for c in cortes)
            
            # Agrupar por usuario para estadísticas
            cortes_por_usuario = {}
            for corte in cortes:
                usuario = corte['usuario_nombre']
                if usuario not in cortes_por_usuario:
                    cortes_por_usuario[usuario] = {
                        'cortes': 0,
                        'total_ventas': 0,
                        'total_efectivo': 0,
                        'total_tarjeta': 0,
                        'total_transferencia': 0,
                        'total_monto': 0
                    }
                cortes_por_usuario[usuario]['cortes'] += 1
                cortes_por_usuario[usuario]['total_ventas'] += corte['total_ventas_corte'] or 0
                cortes_por_usuario[usuario]['total_efectivo'] += corte['ventas_efectivo'] or 0
                cortes_por_usuario[usuario]['total_tarjeta'] += corte['ventas_tarjeta'] or 0
                cortes_por_usuario[usuario]['total_transferencia'] += corte['ventas_transferencia'] or 0
                cortes_por_usuario[usuario]['total_monto'] += corte['monto_final'] or 0
            
        return render_template('reimpresion_cortes.html', 
                               cortes=cortes,
                               usuarios=usuarios,
                               fecha_inicio=fecha_inicio,
                               fecha_fin=fecha_fin,
                               usuario_id=usuario_id,
                               tipo_filtro=tipo_filtro,
                               total_cortes=total_cortes,
                               total_ventas=total_ventas,
                               total_efectivo=total_efectivo,
                               total_tarjeta=total_tarjeta,
                               total_transferencia=total_transferencia,
                               total_monto_final=total_monto_final,
                               cortes_por_usuario=cortes_por_usuario,
                               hoy=hoy)
    except Exception as e:
        flash(f'Error al cargar cortes: {str(e)}', 'danger')
        return render_template('reimpresion_cortes.html', 
                               cortes=[],
                               usuarios=[],
                               fecha_inicio=fecha_inicio,
                               fecha_fin=fecha_fin,
                               usuario_id=usuario_id)
    finally:
        conn.close()

@app.route('/reportes/detalle_corte/<int:corte_id>')
@login_required
@admin_only
def detalle_corte(corte_id):
    """Muestra el detalle completo de un corte específico"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Obtener información básica del corte
            cursor.execute("""
                SELECT 
                    cc.*,
                    u.nombre as usuario_nombre,
                    ac.ventas_efectivo,
                    ac.ventas_tarjeta,
                    ac.ventas_transferencia,
                    ac.ventas_otros,
                    ac.total_ventas
                FROM cortes_caja cc
                JOIN usuarios u ON cc.usuario_id = u.id
                LEFT JOIN auditoria_cortes ac ON cc.id = ac.corte_id
                WHERE cc.id = %s AND cc.cerrado = 1
            """, (corte_id,))
            
            corte = cursor.fetchone()
            if not corte:
                flash('Corte no encontrado o aún no está cerrado', 'danger')
                return redirect(url_for('reimpresion_cortes'))
            
            # Obtener todas las ventas de este corte
            cursor.execute("""
                SELECT 
                    v.folio,
                    v.fecha,
                    v.total,
                    v.pago_recibido,
                    v.cambio_entregado,
                    mp.nombre as metodo_pago,
                    c.nombre as cliente_nombre,
                    (
                        SELECT GROUP_CONCAT(CONCAT(dv.cantidad, 'x ', IFNULL(p.nombre, 'Servicio')) SEPARATOR ', ')
                        FROM detalle_ventas dv
                        LEFT JOIN productos p ON dv.producto_id = p.id
                        WHERE dv.venta_id = v.id
                        LIMIT 3
                    ) as productos_resumen
                FROM ventas v
                JOIN metodos_pago mp ON v.metodo_pago_id = mp.id
                LEFT JOIN clientes c ON v.cliente_id = c.id
                WHERE v.usuario_id = %s 
                AND v.fecha BETWEEN %s AND %s
                AND v.status = 1
                ORDER BY v.fecha DESC
            """, (corte['usuario_id'], corte['fecha_apertura'], corte['fecha_cierre']))
            
            ventas = cursor.fetchall()
            
            # Estadísticas detalladas de ventas
            total_ventas = len(ventas)
            total_monto_ventas = sum(v['total'] for v in ventas)
            
            # Ventas por método de pago
            ventas_por_metodo = {}
            for venta in ventas:
                metodo = venta['metodo_pago']
                if metodo not in ventas_por_metodo:
                    ventas_por_metodo[metodo] = {
                        'cantidad': 0,
                        'monto': 0
                    }
                ventas_por_metodo[metodo]['cantidad'] += 1
                ventas_por_metodo[metodo]['monto'] += venta['total']
            
            # Productos vendidos en este corte
            cursor.execute("""
                SELECT 
                    p.nombre,
                    p.codigo_barras,
                    SUM(dv.cantidad) as cantidad_vendida,
                    SUM(dv.subtotal) as total_vendido,
                    COUNT(DISTINCT dv.venta_id) as veces_vendido
                FROM detalle_ventas dv
                JOIN ventas v ON dv.venta_id = v.id
                LEFT JOIN productos p ON dv.producto_id = p.id
                WHERE v.usuario_id = %s 
                AND v.fecha BETWEEN %s AND %s
                AND v.status = 1
                GROUP BY p.id, p.nombre, p.codigo_barras
                ORDER BY cantidad_vendida DESC
                LIMIT 10
            """, (corte['usuario_id'], corte['fecha_apertura'], corte['fecha_cierre']))
            
            productos_vendidos = cursor.fetchall()
            
        return render_template('detalle_corte.html',
                               corte=corte,
                               ventas=ventas,
                               ventas_por_metodo=ventas_por_metodo,
                               productos_vendidos=productos_vendidos,
                               total_ventas=total_ventas,
                               total_monto_ventas=total_monto_ventas)
    except Exception as e:
        flash(f'Error al cargar detalle del corte: {str(e)}', 'danger')
        return redirect(url_for('reimpresion_cortes'))
    finally:
        conn.close()

@app.route('/reportes/imprimir_corte/<int:corte_id>')
@login_required
@admin_only
def imprimir_corte(corte_id):
    """Genera el formato de impresión para un corte específico"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Obtener información básica del corte
            cursor.execute("""
                SELECT 
                    cc.*,
                    u.nombre as usuario_nombre,
                    ac.ventas_efectivo,
                    ac.ventas_tarjeta,
                    ac.ventas_transferencia,
                    ac.ventas_otros,
                    ac.total_ventas
                FROM cortes_caja cc
                JOIN usuarios u ON cc.usuario_id = u.id
                LEFT JOIN auditoria_cortes ac ON cc.id = ac.corte_id
                WHERE cc.id = %s AND cc.cerrado = 1
            """, (corte_id,))
            
            corte = cursor.fetchone()
            if not corte:
                flash('Corte no encontrado o aún no está cerrado', 'danger')
                return redirect(url_for('reimpresion_cortes'))
            
            # Obtener ventas del corte para el ticket detallado
            cursor.execute("""
                SELECT 
                    v.folio,
                    v.fecha,
                    v.total,
                    mp.nombre as metodo_pago,
                    (
                        SELECT GROUP_CONCAT(CONCAT(dv.cantidad, 'x ', IFNULL(p.nombre, 'Servicio')) SEPARATOR '\n')
                        FROM detalle_ventas dv
                        LEFT JOIN productos p ON dv.producto_id = p.id
                        WHERE dv.venta_id = v.id
                    ) as detalle_productos
                FROM ventas v
                JOIN metodos_pago mp ON v.metodo_pago_id = mp.id
                WHERE v.usuario_id = %s 
                AND v.fecha BETWEEN %s AND %s
                AND v.status = 1
                ORDER BY v.fecha
            """, (corte['usuario_id'], corte['fecha_apertura'], corte['fecha_cierre']))
            
            ventas = cursor.fetchall()
            
            # Preparar datos para la impresión
            datos_impresion = {
                'corte_id': corte_id,
                'usuario': corte['usuario_nombre'],
                'fecha_apertura': corte['fecha_apertura'].strftime('%d/%m/%Y %H:%M:%S'),
                'fecha_cierre': corte['fecha_cierre'].strftime('%d/%m/%Y %H:%M:%S'),
                'fondo_inicial': corte['monto_inicial'],
                'ventas_efectivo': corte['ventas_efectivo'] or 0,
                'ventas_tarjeta': corte['ventas_tarjeta'] or 0,
                'ventas_transferencia': corte['ventas_transferencia'] or 0,
                'ventas_otros': corte['ventas_otros'] or 0,
                'total_ventas': corte['total_ventas'] or 0,
                'monto_final': corte['monto_final'],
                'diferencia': corte['monto_final'] - corte['monto_inicial'],
                'duracion': str(corte['fecha_cierre'] - corte['fecha_apertura']).split('.')[0],
                'ventas_detalle': ventas,
                'fecha_impresion': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                'reimpresion': True
            }
            
        return render_template('ticket_corte_completo.html', datos=datos_impresion)
    except Exception as e:
        flash(f'Error al generar impresión: {str(e)}', 'danger')
        return redirect(url_for('reimpresion_cortes'))
    finally:
        conn.close()

@app.route('/api/cortes/exportar', methods=['POST'])
@login_required
@admin_only
def exportar_cortes():
    """API para exportar cortes a diferentes formatos"""
    data = request.json
    formato = data.get('formato', 'csv')
    filtros = data.get('filtros', {})
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Construir consulta con filtros
            sql = """
                SELECT 
                    cc.id as corte_id,
                    cc.fecha_apertura,
                    cc.fecha_cierre,
                    cc.monto_inicial,
                    cc.monto_final,
                    u.nombre as usuario,
                    ac.ventas_efectivo,
                    ac.ventas_tarjeta,
                    ac.ventas_transferencia,
                    ac.total_ventas,
                    (cc.monto_final - cc.monto_inicial) as diferencia,
                    TIMESTAMPDIFF(MINUTE, cc.fecha_apertura, cc.fecha_cierre) as duracion_minutos
                FROM cortes_caja cc
                JOIN usuarios u ON cc.usuario_id = u.id
                LEFT JOIN auditoria_cortes ac ON cc.id = ac.corte_id
                WHERE cc.cerrado = 1 AND cc.status = 1
            """
            params = []
            
            if filtros.get('fecha_inicio'):
                sql += " AND DATE(cc.fecha_cierre) >= %s"
                params.append(filtros['fecha_inicio'])
            if filtros.get('fecha_fin'):
                sql += " AND DATE(cc.fecha_cierre) <= %s"
                params.append(filtros['fecha_fin'])
            if filtros.get('usuario_id'):
                sql += " AND cc.usuario_id = %s"
                params.append(filtros['usuario_id'])
            
            sql += " ORDER BY cc.fecha_cierre DESC"
            cursor.execute(sql, params)
            cortes = cursor.fetchall()
            
            if formato == 'csv':
                # Generar CSV
                import csv
                from io import StringIO
                
                output = StringIO()
                writer = csv.writer(output)
                
                # Encabezados
                writer.writerow([
                    'ID Corte', 'Usuario', 'Fecha Apertura', 'Fecha Cierre',
                    'Fondo Inicial', 'Ventas Efectivo', 'Ventas Tarjeta',
                    'Ventas Transferencia', 'Total Ventas', 'Monto Final',
                    'Diferencia', 'Duración (min)'
                ])
                
                # Datos
                for corte in cortes:
                    writer.writerow([
                        corte['corte_id'],
                        corte['usuario'],
                        corte['fecha_apertura'].strftime('%Y-%m-%d %H:%M:%S'),
                        corte['fecha_cierre'].strftime('%Y-%m-%d %H:%M:%S'),
                        corte['monto_inicial'],
                        corte['ventas_efectivo'] or 0,
                        corte['ventas_tarjeta'] or 0,
                        corte['ventas_transferencia'] or 0,
                        corte['total_ventas'] or 0,
                        corte['monto_final'],
                        corte['diferencia'],
                        corte['duracion_minutos']
                    ])
                
                return jsonify({
                    'success': True,
                    'formato': 'csv',
                    'data': output.getvalue(),
                    'filename': f'cortes_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
                })
                
            elif formato == 'excel':
                # Para Excel se necesitaría pandas o similar
                return jsonify({
                    'success': False,
                    'message': 'Exportación a Excel no disponible en este momento'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Formato no soportado'
                })
                
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error al exportar: {str(e)}'
        })
    finally:
        conn.close()

# ==========================================
# AUDITORÍA DE CORTES DE CAJA (NUEVO - ADMIN ONLY)
# ==========================================
@app.route('/auditoria_cortes')
@login_required
@admin_only
def auditoria_cortes():
    # Filtros
    usuario_id = request.args.get('usuario_id', '')
    fecha_inicio = request.args.get('fecha_inicio', '')
    fecha_fin = request.args.get('fecha_fin', '')
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Obtener lista de usuarios para el filtro
            cursor.execute("SELECT id, nombre FROM usuarios WHERE status = 1 AND rol = 2 ORDER BY nombre")
            usuarios = cursor.fetchall()
            
            # Construir consulta para auditoría
            sql = """
                SELECT 
                    ac.*,
                    u.nombre as usuario_nombre,
                    cc.fecha_apertura,
                    cc.fecha_cierre,
                    cc.monto_inicial,
                    cc.monto_final
                FROM auditoria_cortes ac
                JOIN usuarios u ON ac.usuario_id = u.id
                JOIN cortes_caja cc ON ac.corte_id = cc.id
                WHERE 1=1
            """
            params = []
            
            if usuario_id:
                sql += " AND ac.usuario_id = %s"
                params.append(usuario_id)
            if fecha_inicio:
                sql += " AND DATE(ac.fecha_cierre) >= %s"
                params.append(fecha_inicio)
            if fecha_fin:
                sql += " AND DATE(ac.fecha_cierre) <= %s"
                params.append(fecha_fin)
            
            sql += " ORDER BY ac.fecha_cierre DESC"
            cursor.execute(sql, params)
            cortes = cursor.fetchall()
            
            # Calcular totales
            total_cortes = len(cortes)
            total_ventas = sum(c['total_ventas'] for c in cortes)
            total_efectivo = sum(c['ventas_efectivo'] for c in cortes)
            total_tarjeta = sum(c['ventas_tarjeta'] for c in cortes)
            
        return render_template('auditoria_cortes.html', 
                               cortes=cortes, 
                               usuarios=usuarios,
                               usuario_id=usuario_id, 
                               fecha_inicio=fecha_inicio, 
                               fecha_fin=fecha_fin,
                               total_cortes=total_cortes,
                               total_ventas=total_ventas,
                               total_efectivo=total_efectivo,
                               total_tarjeta=total_tarjeta)
    finally:
        conn.close()

@app.route('/reimprimir_corte/<int:corte_id>')
@login_required
@admin_only
def reimprimir_corte(corte_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Obtener datos del corte desde auditoría
            cursor.execute("""
                SELECT 
                    ac.*,
                    u.nombre as usuario_nombre,
                    cc.fecha_apertura,
                    cc.fecha_cierre,
                    cc.monto_inicial
                FROM auditoria_cortes ac
                JOIN usuarios u ON ac.usuario_id = u.id
                JOIN cortes_caja cc ON ac.corte_id = cc.id
                WHERE ac.corte_id = %s
                LIMIT 1
            """, (corte_id,))
            
            corte = cursor.fetchone()
            if not corte:
                flash('Corte no encontrado en auditoría', 'danger')
                return redirect(url_for('auditoria_cortes'))
            
            # Obtener detalle de ventas del corte
            cursor.execute("""
                SELECT v.folio, v.fecha, v.total, mp.nombre as metodo_pago
                FROM ventas v
                JOIN metodos_pago mp ON v.metodo_pago_id = mp.id
                WHERE v.usuario_id = %s 
                AND v.fecha >= %s 
                AND v.fecha <= %s
                AND v.status = 1
                ORDER BY v.fecha
            """, (corte['usuario_id'], corte['fecha_apertura'], corte['fecha_cierre']))
            detalle_ventas = cursor.fetchall()
            
            datos = {
                'corte_id': corte_id,
                'usuario': corte['usuario_nombre'],
                'fecha_apertura': corte['fecha_apertura'].strftime('%d/%m/%Y %H:%M'),
                'fecha_cierre': corte['fecha_cierre'].strftime('%d/%m/%Y %H:%M'),
                'fondo_inicial': corte['monto_inicial'],
                'ventas_efectivo': corte['ventas_efectivo'],
                'ventas_tarjeta': corte['ventas_tarjeta'],
                'ventas_transferencia': corte['ventas_transferencia'],
                'total_ventas': corte['total_ventas'],
                'monto_final': corte['monto_final'],
                'detalle_ventas': detalle_ventas
            }
            
        return render_template('ticket_corte.html', datos=datos, reimpresion=True)
    finally:
        conn.close()

# ==========================================
# REIMPRESIÓN DE TICKETS (NUEVO)
# ==========================================
@app.route('/reimprimir_tickets')
@login_required
def reimprimir_tickets():
    # Filtros
    usuario_id = request.args.get('usuario_id', '')
    fecha_inicio = request.args.get('fecha_inicio', '')
    fecha_fin = request.args.get('fecha_fin', '')
    folio = request.args.get('folio', '')
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Obtener lista de usuarios para el filtro (solo farmacéuticos si es admin)
            if current_user.rol == 1:
                cursor.execute("SELECT id, nombre FROM usuarios WHERE status = 1 AND rol = 2 ORDER BY nombre")
            else:
                cursor.execute("SELECT id, nombre FROM usuarios WHERE id = %s", (current_user.id,))
            usuarios = cursor.fetchall()
            
            # Construir consulta para ventas
            sql = """
                SELECT 
                    v.id,
                    v.folio,
                    v.fecha,
                    v.total,
                    v.pago_recibido,
                    v.cambio_entregado,
                    u.nombre as vendedor,
                    c.nombre as cliente,
                    mp.nombre as metodo_pago
                FROM ventas v
                JOIN usuarios u ON v.usuario_id = u.id
                LEFT JOIN clientes c ON v.cliente_id = c.id
                JOIN metodos_pago mp ON v.metodo_pago_id = mp.id
                WHERE v.status = 1
            """
            params = []
            
            if current_user.rol != 1:  # Solo farmacéutico ve sus propias ventas
                sql += " AND v.usuario_id = %s"
                params.append(current_user.id)
            
            if usuario_id and current_user.rol == 1:  # Admin puede filtrar por usuario
                sql += " AND v.usuario_id = %s"
                params.append(usuario_id)
            if fecha_inicio:
                sql += " AND DATE(v.fecha) >= %s"
                params.append(fecha_inicio)
            if fecha_fin:
                sql += " AND DATE(v.fecha) <= %s"
                params.append(fecha_fin)
            if folio:
                sql += " AND v.folio LIKE %s"
                params.append(f'%{folio}%')
            
            sql += " ORDER BY v.fecha DESC"
            cursor.execute(sql, params)
            ventas = cursor.fetchall()
            
            # Calcular estadísticas
            total_ventas = len(ventas)
            total_importe = sum(v['total'] for v in ventas)
            
        return render_template('reimprimir_tickets.html', 
                               ventas=ventas, 
                               usuarios=usuarios,
                               usuario_id=usuario_id, 
                               fecha_inicio=fecha_inicio, 
                               fecha_fin=fecha_fin,
                               folio=folio,
                               total_ventas=total_ventas,
                               total_importe=total_importe)
    finally:
        conn.close()

@app.route('/ver_detalle_venta/<int:venta_id>')
@login_required
def ver_detalle_venta(venta_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Verificar permisos
            cursor.execute("SELECT usuario_id FROM ventas WHERE id = %s", (venta_id,))
            venta_usuario = cursor.fetchone()
            
            if not venta_usuario:
                flash('Venta no encontrada', 'danger')
                return redirect(url_for('reimprimir_tickets'))
            
            # Si no es admin, solo puede ver sus propias ventas
            if current_user.rol != 1 and venta_usuario['usuario_id'] != current_user.id:
                flash('No tienes permiso para ver esta venta', 'danger')
                return redirect(url_for('reimprimir_tickets'))
            
            # Obtener cabecera de venta
            cursor.execute("""
                SELECT 
                    v.*,
                    u.nombre as vendedor,
                    c.nombre as cliente,
                    c.rfc_nit,
                    c.telefono,
                    c.direccion,
                    mp.nombre as metodo_pago
                FROM ventas v
                JOIN usuarios u ON v.usuario_id = u.id
                LEFT JOIN clientes c ON v.cliente_id = c.id
                JOIN metodos_pago mp ON v.metodo_pago_id = mp.id
                WHERE v.id = %s
            """, (venta_id,))
            venta = cursor.fetchone()
            
            if not venta:
                flash('Venta no encontrada', 'danger')
                return redirect(url_for('reimprimir_tickets'))
            
            # Obtener detalles de venta
            cursor.execute("""
                SELECT 
                    dv.*,
                    p.nombre as producto_nombre,
                    p.codigo_barras,
                    p.antibiotico,
                    p.lote
                FROM detalle_ventas dv
                LEFT JOIN productos p ON dv.producto_id = p.id
                WHERE dv.venta_id = %s
                ORDER BY dv.id
            """, (venta_id,))
            detalles = cursor.fetchall()
            
            # Calcular totales
            total_productos = sum(d['cantidad'] for d in detalles)
            total_costo = sum(d['cantidad'] * d['precio_costo_momento'] for d in detalles)
            utilidad = venta['total'] - total_costo
            
        return render_template('detalle_venta.html', 
                               venta=venta, 
                               detalles=detalles,
                               total_productos=total_productos,
                               total_costo=total_costo,
                               utilidad=utilidad)
    finally:
        conn.close()

@app.route('/ticket/reimprimir/<int:venta_id>')
@login_required
def reimprimir_ticket(venta_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Verificar permisos
            cursor.execute("SELECT usuario_id FROM ventas WHERE id = %s", (venta_id,))
            venta_usuario = cursor.fetchone()
            
            if not venta_usuario:
                flash('Venta no encontrada', 'danger')
                return redirect(url_for('reimprimir_tickets'))
            
            # Si no es admin, solo puede reimprimir sus propias ventas
            if current_user.rol != 1 and venta_usuario['usuario_id'] != current_user.id:
                flash('No tienes permiso para reimprimir esta venta', 'danger')
                return redirect(url_for('reimprimir_tickets'))
            
            cursor.execute("""
                SELECT v.*, u.nombre as farmaceutico, c.nombre as cliente, 
                       c.rfc_nit, c.direccion, mp.nombre as metodo 
                FROM ventas v 
                JOIN usuarios u ON v.usuario_id = u.id 
                LEFT JOIN clientes c ON v.cliente_id = c.id 
                JOIN metodos_pago mp ON v.metodo_pago_id = mp.id 
                WHERE v.id = %s AND v.status = 1
            """, (venta_id,))
            venta = cursor.fetchone()
            
            cursor.execute("""
                SELECT dv.*, IFNULL(p.nombre, 'Servicio/Consulta') as producto_nombre,
                       p.codigo_barras, p.lote, p.antibiotico
                FROM detalle_ventas dv 
                LEFT JOIN productos p ON dv.producto_id = p.id 
                WHERE dv.venta_id = %s
            """, (venta_id,))
            detalles = cursor.fetchall()
            
        return render_template('ticket_formato.html', 
                               venta=venta, 
                               detalles=detalles, 
                               pago=venta['pago_recibido'], 
                               cambio=venta['cambio_entregado'])
    finally:
        conn.close()

# ==========================================
# MÓDULO DE REPORTES COMPLETAMENTE MEJORADO
# ==========================================
@app.route('/reportes_farmacia_principal')
@login_required
@admin_only  
def modulo_reportes_dashboard():
    # Estadísticas para la tarjeta de reportes
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            hoy = datetime.now().date()
            
            # Ventas del día
            cursor.execute("""
                SELECT COUNT(*) as ventas_hoy, IFNULL(SUM(total), 0) as ingresos_hoy
                FROM ventas WHERE DATE(fecha) = %s AND status = 1
            """, (hoy,))
            ventas_hoy = cursor.fetchone()
            
            # Productos bajos en stock
            cursor.execute("SELECT COUNT(*) as stock_bajo FROM productos WHERE stock_actual <= stock_minimo AND status = 1")
            stock_bajo = cursor.fetchone()
            
            # Antibióticos vendidos hoy
            cursor.execute("""
                SELECT IFNULL(SUM(dv.cantidad), 0) as antibioticos_hoy
                FROM detalle_ventas dv
                JOIN productos p ON dv.producto_id = p.id
                JOIN ventas v ON dv.venta_id = v.id
                WHERE p.antibiotico = 1 AND DATE(v.fecha) = %s AND v.status = 1
            """, (hoy,))
            antibioticos_hoy = cursor.fetchone()
            
            # Cortes abiertos
            cursor.execute("SELECT COUNT(*) as cortes_abiertos FROM cortes_caja WHERE cerrado = 0 AND status = 1")
            cortes_abiertos = cursor.fetchone()
            
        return render_template('reportes.html', 
                               titulo="Panel de Analytics",
                               ventas_hoy=ventas_hoy,
                               stock_bajo=stock_bajo,
                               antibioticos_hoy=antibioticos_hoy,
                               cortes_abiertos=cortes_abiertos)
    finally:
        conn.close()

# ==========================================
# 1. REPORTE FINANCIERO MEJORADO
# ==========================================
@app.route('/reportes/financiero')
@login_required
@admin_only
def reporte_financiero():
    f_inicio = request.args.get('inicio', datetime.now().strftime('%Y-%m-01'))
    f_fin = request.args.get('fin', datetime.now().strftime('%Y-%m-%d'))
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # KPIs
            cursor.execute("""
                SELECT 
                    IFNULL(SUM(v.total), 0) as ingresos,
                    IFNULL(SUM(dv.subtotal - (dv.cantidad * dv.precio_costo_momento)), 0) as utilidad,
                    COUNT(DISTINCT v.id) as total_ventas,
                    IFNULL(AVG(v.total), 0) as ticket_promedio
                FROM ventas v
                JOIN detalle_ventas dv ON v.id = dv.venta_id
                WHERE v.status = 1 AND DATE(v.fecha) BETWEEN %s AND %s
            """, (f_inicio, f_fin))
            kpis = cursor.fetchone()

            # Gráfica Lineal - Ventas diarias
            cursor.execute("""
                SELECT DATE(fecha) as fecha, SUM(total) as total_dia 
                FROM ventas 
                WHERE status = 1 AND DATE(fecha) BETWEEN %s AND %s 
                GROUP BY DATE(fecha) ORDER BY DATE(fecha) ASC
            """, (f_inicio, f_fin))
            v_diaria = cursor.fetchall()

            # Gráfica Dona - Métodos de pago
            cursor.execute("""
                SELECT mp.nombre as metodo, COUNT(v.id) as cantidad, SUM(v.total) as monto
                FROM ventas v 
                JOIN metodos_pago mp ON v.metodo_pago_id = mp.id
                WHERE v.status = 1 AND DATE(v.fecha) BETWEEN %s AND %s 
                GROUP BY mp.nombre
            """, (f_inicio, f_fin))
            metodos = cursor.fetchall()

            # Tabla Detallada
            cursor.execute("""
                SELECT 
                    DATE_FORMAT(v.fecha, '%%Y-%%m-%%d %%H:%%i') as fecha, 
                    v.folio,
                    u.nombre as vendedor, 
                    IFNULL(c.nombre, 'Público General') as cliente, 
                    mp.nombre as metodo,
                    v.total,
                    v.pago_recibido,
                    v.cambio_entregado
                FROM ventas v
                LEFT JOIN usuarios u ON v.usuario_id = u.id
                LEFT JOIN clientes c ON v.cliente_id = c.id
                LEFT JOIN metodos_pago mp ON v.metodo_pago_id = mp.id
                WHERE v.status = 1 AND DATE(v.fecha) BETWEEN %s AND %s 
                ORDER BY v.fecha DESC
            """, (f_inicio, f_fin))
            tabla = cursor.fetchall()

            # Ventas por hora
            cursor.execute("""
                SELECT HOUR(fecha) as hora, COUNT(*) as cantidad, SUM(total) as monto
                FROM ventas 
                WHERE status = 1 AND DATE(fecha) BETWEEN %s AND %s 
                GROUP BY HOUR(fecha) ORDER BY hora ASC
            """, (f_inicio, f_fin))
            por_hora = cursor.fetchall()

        return render_template('reporte_financiero.html', 
                               ingresos=float(kpis['ingresos']), 
                               ganancias=float(kpis['utilidad']),
                               total_ventas=kpis['total_ventas'],
                               ticket_promedio=float(kpis['ticket_promedio']),
                               v_diaria=v_diaria, 
                               metodos=metodos, 
                               tabla=tabla,
                               por_hora=por_hora,
                               f_inicio=f_inicio, 
                               f_fin=f_fin)
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
        return redirect(url_for('modulo_reportes_dashboard'))
    finally:
        conn.close()

# ==========================================
# 2. REPORTE DE ANTIBIÓTICOS COMPLETAMENTE MEJORADO
# ==========================================
@app.route('/reportes/antibioticos_mejorado')
@login_required
@admin_only
def reporte_antibioticos_mejorado():
    # Filtros
    fecha_inicio = request.args.get('fecha_inicio', datetime.now().strftime('%Y-%m-01'))
    fecha_fin = request.args.get('fecha_fin', datetime.now().strftime('%Y-%m-%d'))
    usuario_id = request.args.get('usuario_id', '')
    producto_id = request.args.get('producto_id', '')
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Obtener lista de usuarios
            cursor.execute("SELECT id, nombre FROM usuarios WHERE status = 1 AND rol = 2 ORDER BY nombre")
            usuarios = cursor.fetchall()
            
            # Obtener lista de antibióticos
            cursor.execute("SELECT id, nombre FROM productos WHERE antibiotico = 1 AND status = 1 ORDER BY nombre")
            antibioticos = cursor.fetchall()
            
            # Construir consulta principal
            sql = """
                SELECT 
                    v.fecha,
                    v.folio,
                    u.nombre as vendedor,
                    p.nombre as producto,
                    p.lote,
                    dv.cantidad,
                    dv.precio_unitario,
                    dv.precio_costo_momento,
                    dv.subtotal,
                    (dv.subtotal - (dv.cantidad * dv.precio_costo_momento)) as utilidad,
                    c.nombre as cliente
                FROM detalle_ventas dv
                JOIN productos p ON dv.producto_id = p.id
                JOIN ventas v ON dv.venta_id = v.id
                JOIN usuarios u ON v.usuario_id = u.id
                LEFT JOIN clientes c ON v.cliente_id = c.id
                WHERE p.antibiotico = 1 
                AND v.status = 1
            """
            params = []
            
            if fecha_inicio:
                sql += " AND DATE(v.fecha) >= %s"
                params.append(fecha_inicio)
            if fecha_fin:
                sql += " AND DATE(v.fecha) <= %s"
                params.append(fecha_fin)
            if usuario_id:
                sql += " AND v.usuario_id = %s"
                params.append(usuario_id)
            if producto_id:
                sql += " AND p.id = %s"
                params.append(producto_id)
            
            sql += " ORDER BY v.fecha DESC"
            cursor.execute(sql, params)
            registros = cursor.fetchall()
            
            # Consulta para estadísticas
            sql_stats = """
                SELECT 
                    COUNT(DISTINCT v.id) as total_ventas,
                    SUM(dv.cantidad) as total_unidades,
                    SUM(dv.subtotal) as total_venta,
                    SUM(dv.subtotal - (dv.cantidad * dv.precio_costo_momento)) as total_utilidad
                FROM detalle_ventas dv
                JOIN productos p ON dv.producto_id = p.id
                JOIN ventas v ON dv.venta_id = v.id
                WHERE p.antibiotico = 1 
                AND v.status = 1
            """
            stats_params = []
            
            if fecha_inicio:
                sql_stats += " AND DATE(v.fecha) >= %s"
                stats_params.append(fecha_inicio)
            if fecha_fin:
                sql_stats += " AND DATE(v.fecha) <= %s"
                stats_params.append(fecha_fin)
            if usuario_id:
                sql_stats += " AND v.usuario_id = %s"
                stats_params.append(usuario_id)
            if producto_id:
                sql_stats += " AND p.id = %s"
                stats_params.append(producto_id)
            
            cursor.execute(sql_stats, stats_params)
            estadisticas = cursor.fetchone()
            
            # Consulta para top productos
            sql_top = """
                SELECT 
                    p.nombre,
                    SUM(dv.cantidad) as cantidad_vendida,
                    SUM(dv.subtotal) as total_venta
                FROM detalle_ventas dv
                JOIN productos p ON dv.producto_id = p.id
                JOIN ventas v ON dv.venta_id = v.id
                WHERE p.antibiotico = 1 
                AND v.status = 1
            """
            top_params = []
            
            if fecha_inicio:
                sql_top += " AND DATE(v.fecha) >= %s"
                top_params.append(fecha_inicio)
            if fecha_fin:
                sql_top += " AND DATE(v.fecha) <= %s"
                top_params.append(fecha_fin)
            
            sql_top += " GROUP BY p.id, p.nombre ORDER BY cantidad_vendida DESC LIMIT 10"
            cursor.execute(sql_top, top_params)
            top_productos = cursor.fetchall()
            
            # Consulta para ventas por vendedor
            sql_vendedor = """
                SELECT 
                    u.nombre as vendedor,
                    COUNT(DISTINCT v.id) as ventas_realizadas,
                    SUM(dv.cantidad) as unidades_vendidas,
                    SUM(dv.subtotal) as total_venta
                FROM detalle_ventas dv
                JOIN productos p ON dv.producto_id = p.id
                JOIN ventas v ON dv.venta_id = v.id
                JOIN usuarios u ON v.usuario_id = u.id
                WHERE p.antibiotico = 1 
                AND v.status = 1
            """
            vendedor_params = []
            
            if fecha_inicio:
                sql_vendedor += " AND DATE(v.fecha) >= %s"
                vendedor_params.append(fecha_inicio)
            if fecha_fin:
                sql_vendedor += " AND DATE(v.fecha) <= %s"
                vendedor_params.append(fecha_fin)
            
            sql_vendedor += " GROUP BY u.id, u.nombre ORDER BY unidades_vendidas DESC"
            cursor.execute(sql_vendedor, vendedor_params)
            por_vendedor = cursor.fetchall()
            
        return render_template('reporte_antibioticos_mejorado.html', 
                               registros=registros,
                               usuarios=usuarios,
                               antibioticos=antibioticos,
                               fecha_inicio=fecha_inicio,
                               fecha_fin=fecha_fin,
                               usuario_id=usuario_id,
                               producto_id=producto_id,
                               estadisticas=estadisticas,
                               top_productos=top_productos,
                               por_vendedor=por_vendedor)
    finally:
        conn.close()

# ==========================================
# 3. REPORTE DE VENTAS DETALLADAS (NUEVO)
# ==========================================
@app.route('/reportes/ventas_detalladas')
@login_required
@admin_only
def reporte_ventas_detalladas():
    # Filtros
    fecha_inicio = request.args.get('fecha_inicio', datetime.now().strftime('%Y-%m-01'))
    fecha_fin = request.args.get('fecha_fin', datetime.now().strftime('%Y-%m-%d'))
    usuario_id = request.args.get('usuario_id', '')
    metodo_pago = request.args.get('metodo_pago', '')
    cliente_id = request.args.get('cliente_id', '')
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Obtener listas para filtros
            cursor.execute("SELECT id, nombre FROM usuarios WHERE status = 1 AND rol = 2 ORDER BY nombre")
            usuarios = cursor.fetchall()
            
            cursor.execute("SELECT id, nombre FROM metodos_pago WHERE status = 1")
            metodos = cursor.fetchall()
            
            cursor.execute("SELECT id, nombre FROM clientes WHERE status = 1 ORDER BY nombre LIMIT 50")
            clientes = cursor.fetchall()
            
            # Construir consulta principal
            sql = """
                SELECT 
                    v.id,
                    v.folio,
                    v.fecha,
                    v.total,
                    v.pago_recibido,
                    v.cambio_entregado,
                    u.nombre as vendedor,
                    c.nombre as cliente,
                    mp.nombre as metodo_pago,
                    (
                        SELECT GROUP_CONCAT(CONCAT(IFNULL(p.nombre, 'Servicio'), ' (', dv2.cantidad, ')') SEPARATOR ', ')
                        FROM detalle_ventas dv2
                        LEFT JOIN productos p ON dv2.producto_id = p.id
                        WHERE dv2.venta_id = v.id
                        LIMIT 3
                    ) as productos_resumen
                FROM ventas v
                JOIN usuarios u ON v.usuario_id = u.id
                LEFT JOIN clientes c ON v.cliente_id = c.id
                JOIN metodos_pago mp ON v.metodo_pago_id = mp.id
                WHERE v.status = 1
            """
            params = []
            
            if fecha_inicio:
                sql += " AND DATE(v.fecha) >= %s"
                params.append(fecha_inicio)
            if fecha_fin:
                sql += " AND DATE(v.fecha) <= %s"
                params.append(fecha_fin)
            if usuario_id:
                sql += " AND v.usuario_id = %s"
                params.append(usuario_id)
            if metodo_pago:
                sql += " AND v.metodo_pago_id = %s"
                params.append(metodo_pago)
            if cliente_id:
                sql += " AND v.cliente_id = %s"
                params.append(cliente_id)
            
            sql += " ORDER BY v.fecha DESC"
            cursor.execute(sql, params)
            ventas = cursor.fetchall()
            
            # Calcular estadísticas
            total_general = sum(v['total'] for v in ventas)
            total_ventas = len(ventas)
            total_efectivo = sum(v['pago_recibido'] for v in ventas if v['metodo_pago'] == 'Efectivo')
            total_tarjeta = sum(v['total'] for v in ventas if v['metodo_pago'] == 'Tarjeta de Crédito' or v['metodo_pago'] == 'Tarjeta de Débito')
            
            # Ventas por día
            cursor.execute("""
                SELECT DATE(fecha) as fecha, COUNT(*) as cantidad, SUM(total) as monto
                FROM ventas 
                WHERE status = 1 AND DATE(fecha) BETWEEN %s AND %s 
                GROUP BY DATE(fecha) ORDER BY fecha DESC LIMIT 15
            """, (fecha_inicio, fecha_fin))
            ventas_por_dia = cursor.fetchall()
            
            # Ventas por vendedor
            cursor.execute("""
                SELECT u.nombre as vendedor, COUNT(*) as ventas, SUM(v.total) as monto
                FROM ventas v
                JOIN usuarios u ON v.usuario_id = u.id
                WHERE v.status = 1 AND DATE(v.fecha) BETWEEN %s AND %s
                GROUP BY u.id, u.nombre ORDER BY monto DESC
            """, (fecha_inicio, fecha_fin))
            ventas_por_vendedor = cursor.fetchall()
            
        return render_template('reporte_ventas_detalladas.html',
                               ventas=ventas,
                               usuarios=usuarios,
                               metodos=metodos,
                               clientes=clientes,
                               fecha_inicio=fecha_inicio,
                               fecha_fin=fecha_fin,
                               usuario_id=usuario_id,
                               metodo_pago=metodo_pago,
                               cliente_id=cliente_id,
                               total_general=total_general,
                               total_ventas=total_ventas,
                               total_efectivo=total_efectivo,
                               total_tarjeta=total_tarjeta,
                               ventas_por_dia=ventas_por_dia,
                               ventas_por_vendedor=ventas_por_vendedor)
    finally:
        conn.close()

# ==========================================
# 4. REPORTE DE PRODUCTOS (MÁS VENDIDOS)
# ==========================================
@app.route('/reportes/productos')
@login_required
@admin_only
def ruta_reporte_productos():
    fecha_inicio = request.args.get('fecha_inicio', datetime.now().strftime('%Y-%m-01'))
    fecha_fin = request.args.get('fecha_fin', datetime.now().strftime('%Y-%m-%d'))
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Productos más vendidos
            cursor.execute("""
                SELECT 
                    p.nombre,
                    p.codigo_barras,
                    s.nombre as seccion,
                    SUM(dv.cantidad) as cantidad_vendida,
                    SUM(dv.subtotal) as total_venta,
                    AVG(dv.precio_unitario) as precio_promedio,
                    COUNT(DISTINCT dv.venta_id) as veces_vendido
                FROM detalle_ventas dv
                JOIN productos p ON dv.producto_id = p.id
                LEFT JOIN secciones s ON p.seccion_id = s.id
                JOIN ventas v ON dv.venta_id = v.id
                WHERE v.status = 1 AND DATE(v.fecha) BETWEEN %s AND %s
                GROUP BY p.id, p.nombre, p.codigo_barras, s.nombre
                ORDER BY cantidad_vendida DESC
                LIMIT 20
            """, (fecha_inicio, fecha_fin))
            top_productos = cursor.fetchall()
            
            # Antibióticos vs General
            cursor.execute("""
                SELECT 
                    CASE WHEN p.antibiotico = 1 THEN 'Antibióticos' ELSE 'General' END as categoria,
                    SUM(dv.cantidad) as cantidad,
                    SUM(dv.subtotal) as venta_total,
                    COUNT(DISTINCT dv.venta_id) as transacciones
                FROM detalle_ventas dv
                JOIN productos p ON dv.producto_id = p.id
                JOIN ventas v ON dv.venta_id = v.id
                WHERE v.status = 1 AND DATE(v.fecha) BETWEEN %s AND %s
                GROUP BY p.antibiotico
                ORDER BY p.antibiotico DESC
            """, (fecha_inicio, fecha_fin))
            comparativa = cursor.fetchall()
            
            # Por sección
            cursor.execute("""
                SELECT 
                    IFNULL(s.nombre, 'Sin Sección') as seccion,
                    SUM(dv.cantidad) as cantidad,
                    SUM(dv.subtotal) as venta_total
                FROM detalle_ventas dv
                JOIN productos p ON dv.producto_id = p.id
                LEFT JOIN secciones s ON p.seccion_id = s.id
                JOIN ventas v ON dv.venta_id = v.id
                WHERE v.status = 1 AND DATE(v.fecha) BETWEEN %s AND %s
                GROUP BY s.id, s.nombre
                ORDER BY venta_total DESC
                LIMIT 10
            """, (fecha_inicio, fecha_fin))
            por_seccion = cursor.fetchall()
            
            # Estadísticas generales
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT p.id) as productos_vendidos,
                    SUM(dv.cantidad) as unidades_vendidas,
                    SUM(dv.subtotal) as venta_total,
                    AVG(dv.cantidad) as promedio_unidades
                FROM detalle_ventas dv
                JOIN productos p ON dv.producto_id = p.id
                JOIN ventas v ON dv.venta_id = v.id
                WHERE v.status = 1 AND DATE(v.fecha) BETWEEN %s AND %s
            """, (fecha_inicio, fecha_fin))
            estadisticas = cursor.fetchone()
            
        return render_template('reporte_productos.html', 
                               top_productos=top_productos,
                               comparativa=comparativa,
                               por_seccion=por_seccion,
                               estadisticas=estadisticas,
                               fecha_inicio=fecha_inicio,
                               fecha_fin=fecha_fin)
    except Exception as e:
        print(f"Error en reporte productos: {e}")
        flash("No se pudieron cargar los datos del reporte", "danger")
        return redirect(url_for('modulo_reportes_dashboard'))
    finally:
        conn.close()

# ==========================================
# 5. REPORTE DE STOCK BAJO
# ==========================================
@app.route('/reportes/bajo-stock')
@login_required
@admin_only
def ruta_reporte_stock():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    p.codigo_barras, 
                    p.nombre,
                    s.nombre as seccion,
                    p.stock_actual, 
                    p.stock_minimo,
                    p.precio_costo,
                    p.precio_publico,
                    (p.stock_minimo - p.stock_actual) as faltante,
                    ROUND((p.stock_actual / p.stock_minimo) * 100, 2) as porcentaje
                FROM productos p
                LEFT JOIN secciones s ON p.seccion_id = s.id
                WHERE p.status = 1 AND p.stock_actual <= p.stock_minimo
                ORDER BY porcentaje ASC
            """)
            productos = cursor.fetchall()
            
            # Estadísticas
            total_productos = len(productos)
            total_faltante = sum(p['faltante'] for p in productos if p['faltante'] > 0)
            valor_faltante = sum(p['faltante'] * p['precio_costo'] for p in productos if p['faltante'] > 0)
        
        return render_template('reporte_stock.html', 
                               productos=productos,
                               total_productos=total_productos,
                               total_faltante=total_faltante,
                               valor_faltante=valor_faltante)
    except Exception as e:
        print(f"Error en stock: {e}")
        flash(f"Error en el servidor: {e}", "danger")
        return redirect(url_for('modulo_reportes_dashboard'))
    finally:
        conn.close()

# ==========================================
# 6. REPORTE DE CADUCIDAD
# ==========================================
@app.route('/reportes/caducidad')
@login_required
def ruta_reporte_caducidad():
    # 1. Preparar fechas
    hoy_dt = datetime.now()
    fecha_limite_dt = hoy_dt + timedelta(days=15)
    
    # Formato para MySQL
    limite_str = fecha_limite_dt.strftime('%Y-%m-%d')
    
    try:
        conexion = get_db_connection()
        with conexion.cursor(DictCursor) as cursor:
            # Filtramos productos con stock que vencen en 15 días o ya vencieron
            sql = """
                SELECT 
                    p.id, 
                    p.nombre, 
                    p.stock_actual, 
                    p.fecha_caducidad, 
                    p.lote, 
                    p.codigo_barras,
                    s.nombre as seccion,
                    p.precio_costo,
                    p.precio_publico,
                    DATEDIFF(p.fecha_caducidad, CURDATE()) as dias_restantes,
                    (p.stock_actual * p.precio_costo) as valor_inventario
                FROM productos p
                LEFT JOIN secciones s ON p.seccion_id = s.id
                WHERE p.stock_actual > 0 
                AND p.fecha_caducidad IS NOT NULL
                AND p.fecha_caducidad <= %s
                AND p.status = 1
                ORDER BY p.fecha_caducidad ASC
            """
            cursor.execute(sql, (limite_str,))
            productos = cursor.fetchall()
            
            # Estadísticas
            total_productos = len(productos)
            total_unidades = sum(p['stock_actual'] for p in productos)
            total_valor = sum(p['valor_inventario'] for p in productos)
            ya_vencidos = len([p for p in productos if p['dias_restantes'] < 0])
            por_vencer = len([p for p in productos if p['dias_restantes'] >= 0])
            
    except Exception as e:
        print(f"Error: {e}")
        productos = []
        total_productos = 0
        total_unidades = 0
        total_valor = 0
        ya_vencidos = 0
        por_vencer = 0
    finally:
        if 'conexion' in locals(): conexion.close()

    return render_template('reporte_caducidad.html', 
                           productos=productos, 
                           hoy=hoy_dt.date(),
                           limite=fecha_limite_dt.date(),
                           total_productos=total_productos,
                           total_unidades=total_unidades,
                           total_valor=total_valor,
                           ya_vencidos=ya_vencidos,
                           por_vencer=por_vencer)

# ==========================================
# 7. REPORTE DE USUARIOS (RENDIMIENTO)
# ==========================================
@app.route('/reportes/personal')
@login_required
@admin_only
def ruta_reporte_usuarios():
    # Filtros de fecha
    f_inicio = request.args.get('inicio', datetime.now().strftime('%Y-%m-01'))
    f_fin = request.args.get('fin', datetime.now().strftime('%Y-%m-%d'))
    
    conn = get_db_connection()
    try:
        with conn.cursor(DictCursor) as cursor:
            # Rendimiento de usuarios
            sql = """
                SELECT 
                    u.nombre, 
                    u.username as usuario,
                    COUNT(DISTINCT v.id) as num_ventas, 
                    IFNULL(SUM(v.total), 0) as total_vendido,
                    IFNULL(AVG(v.total), 0) as ticket_promedio,
                    (
                        SELECT COUNT(DISTINCT DATE(v2.fecha))
                        FROM ventas v2 
                        WHERE v2.usuario_id = u.id 
                        AND DATE(v2.fecha) BETWEEN %s AND %s
                    ) as dias_trabajados,
                    (
                        SELECT p.nombre 
                        FROM detalle_ventas dv
                        JOIN productos p ON dv.producto_id = p.id
                        JOIN ventas v2 ON dv.venta_id = v2.id
                        WHERE v2.usuario_id = u.id 
                        AND DATE(v2.fecha) BETWEEN %s AND %s
                        GROUP BY p.id 
                        ORDER BY SUM(dv.cantidad) DESC 
                        LIMIT 1
                    ) as producto_top,
                    (
                        SELECT COUNT(*) 
                        FROM cortes_caja cc
                        WHERE cc.usuario_id = u.id 
                        AND DATE(cc.fecha_apertura) BETWEEN %s AND %s
                        AND cc.cerrado = 1
                    ) as cortes_realizados
                FROM usuarios u
                LEFT JOIN ventas v ON u.id = v.usuario_id 
                    AND DATE(v.fecha) BETWEEN %s AND %s
                WHERE u.status = 1 AND u.rol = 2
                GROUP BY u.id, u.nombre, u.username
                ORDER BY total_vendido DESC
            """
            cursor.execute(sql, (f_inicio, f_fin, f_inicio, f_fin, f_inicio, f_fin, f_inicio, f_fin))
            ventas_usuario = cursor.fetchall()
            
            # Estadísticas generales
            total_ventas = sum(u['num_ventas'] for u in ventas_usuario)
            total_vendido = sum(u['total_vendido'] for u in ventas_usuario)
            promedio_general = total_vendido / len(ventas_usuario) if ventas_usuario else 0
            
    finally:
        conn.close()

    return render_template('reporte_personal.html', 
                           tabla=ventas_usuario, 
                           f_inicio=f_inicio, 
                           f_fin=f_fin,
                           total_ventas=total_ventas,
                           total_vendido=total_vendido,
                           promedio_general=promedio_general)

# ==========================================
# 8. REPORTE DE CLIENTES (FIDELIDAD)
# ==========================================
@app.route('/reportes/clientes')
@login_required
@admin_only
def ruta_reporte_clientes():
    f_inicio = request.args.get('inicio', datetime.now().strftime('%Y-%m-01'))
    f_fin = request.args.get('fin', datetime.now().strftime('%Y-%m-%d'))
    min_compras = int(request.args.get('min_compras', 1))
    
    conn = get_db_connection()
    try:
        with conn.cursor(DictCursor) as cursor:
            # Clientes con sus compras
            sql = """
                SELECT 
                    c.id,
                    c.nombre as cliente_nombre,
                    c.telefono,
                    c.email,
                    c.rfc_nit,
                    COUNT(v.id) as total_compras,
                    IFNULL(SUM(v.total), 0) as total_gastado,
                    IFNULL(AVG(v.total), 0) as promedio_compra,
                    MIN(v.fecha) as primera_compra,
                    MAX(v.fecha) as ultima_compra,
                    CASE WHEN c.nombre LIKE '%%General%%' THEN 1 ELSE 0 END as es_general,
                    (
                        SELECT p.nombre 
                        FROM detalle_ventas dv
                        JOIN productos p ON dv.producto_id = p.id
                        JOIN ventas v2 ON dv.venta_id = v2.id
                        WHERE v2.cliente_id = c.id 
                        AND DATE(v2.fecha) BETWEEN %s AND %s
                        GROUP BY p.id 
                        ORDER BY SUM(dv.cantidad) DESC 
                        LIMIT 1
                    ) as producto_favorito
                FROM clientes c
                LEFT JOIN ventas v ON c.id = v.cliente_id
                    AND DATE(v.fecha) BETWEEN %s AND %s
                WHERE c.status = 1
                GROUP BY c.id, c.nombre, c.telefono, c.email, c.rfc_nit
                HAVING total_compras >= %s
                ORDER BY es_general ASC, total_gastado DESC
            """
            cursor.execute(sql, (f_inicio, f_fin, f_inicio, f_fin, min_compras))
            todos_los_clientes = cursor.fetchall()

            # Separar clientes reales
            clientes_reales = [c for c in todos_los_clientes if not c['es_general']]
            
            # Estadísticas
            total_clientes = len(todos_los_clientes)
            total_clientes_reales = len(clientes_reales)
            total_ventas = sum(c['total_compras'] for c in todos_los_clientes)
            total_gastado = sum(c['total_gastado'] for c in todos_los_clientes)
            
    finally:
        conn.close()

    return render_template('reporte_clientes.html', 
                           tabla=todos_los_clientes,      # Para el listado completo
                           top_reales=clientes_reales,    # Para gráficas y Cliente del Mes
                           f_inicio=f_inicio, 
                           f_fin=f_fin,
                           min_compras=min_compras,
                           total_clientes=total_clientes,
                           total_clientes_reales=total_clientes_reales,
                           total_ventas=total_ventas,
                           total_gastado=total_gastado)

# ==========================================
# MÓDULO PUNTO DE VENTA (POS) - MEJORADO CON FILTRO DE CADUCIDAD
# ==========================================
@app.route('/punto_venta')
@login_required
def punto_venta():
    if current_user.rol != 1:
        return redirect(url_for('inicio_farmacia_route'))
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM metodos_pago WHERE status = 1")
            metodos = cursor.fetchall()
            cursor.execute("SELECT id, nombre, rfc_nit FROM clientes WHERE status = 1 LIMIT 20")
            clientes = cursor.fetchall()
        return render_template('punto_venta.html', metodos=metodos, clientes=clientes)
    finally:
        conn.close()

@app.route('/punto_farmacia')
@login_required
def punto_farmacia():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM metodos_pago WHERE status = 1")
            metodos = cursor.fetchall()
            cursor.execute("SELECT id, nombre, rfc_nit FROM clientes WHERE status = 1 LIMIT 20")
            clientes = cursor.fetchall()
        return render_template('punto_farmacia.html', metodos=metodos, clientes=clientes)
    finally:
        conn.close()

# ==========================================
# APIS PARA PUNTO DE VENTA - MODIFICADAS CON FILTRO DE CADUCIDAD
# ==========================================
@app.route('/api/buscar_producto')
@login_required
def buscar_producto():
    query = request.args.get('query', '')
    # Parámetro para determinar si mostrar productos caducados o próximos a caducar
    mostrar_caducados = request.args.get('mostrar_caducados', 'false')
    
    if not query:
        return jsonify({'success': False, 'message': 'Consulta vacía'})
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Condición para excluir productos en riesgo de caducidad o ya caducados
            condicion_caducidad = ""
            if mostrar_caducados.lower() != 'true':
                # Excluir productos que caducan en los próximos 15 días o ya caducaron
                condicion_caducidad = """
                    AND (
                        p.fecha_caducidad IS NULL 
                        OR p.fecha_caducidad > CURDATE() + INTERVAL 15 DAY
                    )
                """
            
            # 1. Búsqueda exacta por código (para el lector)
            sql_exacto = f"""
                SELECT id, nombre, precio_publico, stock_actual, antibiotico, 
                       fecha_caducidad,
                       CASE 
                           WHEN fecha_caducidad IS NULL THEN 'Sin fecha'
                           WHEN fecha_caducidad < CURDATE() THEN 'CADUCADO'
                           WHEN fecha_caducidad <= CURDATE() + INTERVAL 15 DAY THEN 'PRÓXIMO A CADUCAR'
                           ELSE 'VIGENTE'
                       END as estado_caducidad
                FROM productos 
                WHERE codigo_barras = %s 
                AND status = 1 
                AND stock_actual > 0
                {condicion_caducidad}
            """
            cursor.execute(sql_exacto, (query,))
            producto = cursor.fetchone()
            
            if producto:
                # Verificar si está caducado o próximo a caducar (aunque se haya encontrado)
                if producto['estado_caducidad'] in ['CADUCADO', 'PRÓXIMO A CADUCAR']:
                    return jsonify({
                        'success': False,
                        'message': f'Producto {producto["estado_caducidad"].lower()}. No se puede vender.',
                        'estado': producto['estado_caducidad']
                    })
                
                return jsonify({
                    'success': True,
                    'tipo': 'exacto',
                    'data': {
                        'id': producto['id'], 
                        'nombre': producto['nombre'], 
                        'precio': float(producto['precio_publico']),
                        'stock': producto['stock_actual'],
                        'antibiotico': bool(producto['antibiotico']),
                        'estado_caducidad': producto['estado_caducidad']
                    }
                })
            
            # 2. Búsqueda por nombre (para el buscador manual)
            sql_lista = f"""
                SELECT id, nombre, precio_publico, stock_actual, antibiotico,
                       fecha_caducidad,
                       CASE 
                           WHEN fecha_caducidad IS NULL THEN 'Sin fecha'
                           WHEN fecha_caducidad < CURDATE() THEN 'CADUCADO'
                           WHEN fecha_caducidad <= CURDATE() + INTERVAL 15 DAY THEN 'PRÓXIMO A CADUCAR'
                           ELSE 'VIGENTE'
                       END as estado_caducidad
                FROM productos 
                WHERE nombre LIKE %s 
                AND status = 1 
                AND stock_actual > 0
                {condicion_caducidad}
                ORDER BY 
                    CASE WHEN estado_caducidad = 'VIGENTE' THEN 1
                         ELSE 2
                    END,
                    nombre
                LIMIT 10
            """
            cursor.execute(sql_lista, (f"%{query}%",))
            resultados = cursor.fetchall()
            
            if resultados:
                # Filtrar solo los vigentes para la lista
                resultados_vigentes = [r for r in resultados if r['estado_caducidad'] == 'VIGENTE']
                
                if resultados_vigentes:
                    return jsonify({
                        'success': True,
                        'tipo': 'lista',
                        'data': [{
                            'id': r['id'], 
                            'nombre': r['nombre'], 
                            'precio': float(r['precio_publico']),
                            'stock': r['stock_actual'],
                            'antibiotico': bool(r['antibiotico']),
                            'estado_caducidad': r['estado_caducidad']
                        } for r in resultados_vigentes]
                    })
                else:
                    # Si todos están caducados o próximos a caducar
                    return jsonify({
                        'success': False,
                        'message': 'Todos los productos encontrados están caducados o próximos a caducar',
                        'encontrados_caducados': len(resultados)
                    })
        
        return jsonify({'success': False, 'message': 'No encontrado o sin stock'})
    finally:
        conn.close()

@app.route('/api/clientes', methods=['GET'])
@login_required
def api_get_clientes():
    query = request.args.get('q', '')
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT id, nombre, rfc_nit, telefono FROM clientes WHERE status = 1"
            params = []
            if query:
                sql += " AND (nombre LIKE %s OR rfc_nit LIKE %s OR telefono LIKE %s)"
                params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])
            sql += " LIMIT 15"
            cursor.execute(sql, params)
            return jsonify(cursor.fetchall())
    finally:
        conn.close()

@app.route('/api/clientes/nuevo', methods=['POST'])
@login_required
def api_nuevo_cliente():
    nombre = request.form.get('nombre')
    rfc_nit = request.form.get('rfc_nit')
    direccion = request.form.get('direccion')
    telefono = request.form.get('telefono')
    email = request.form.get('email')
    if not nombre: 
        return jsonify({'success': False, 'message': 'Nombre requerido'})
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = """INSERT INTO clientes (nombre, rfc_nit, direccion, telefono, email, status) 
                     VALUES (%s, %s, %s, %s, %s, 1)"""
            cursor.execute(sql, (nombre, rfc_nit, direccion, telefono, email))
            return jsonify({'success': True, 'id': cursor.lastrowid, 'nombre': nombre})
    finally:
        conn.close()

@app.route('/api/items/<tipo>')
@login_required
def api_get_items(tipo):
    # Parámetro para mostrar productos caducados (solo para administradores)
    mostrar_caducados = request.args.get('mostrar_caducados', 'false')
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if tipo == 'productos':
                # Condición para excluir productos en riesgo de caducidad
                condicion_caducidad = ""
                if mostrar_caducados.lower() != 'true' or current_user.rol != 1:
                    # Por defecto, no mostrar caducados o próximos a caducar
                    # Admin puede forzar a ver todos con parámetro mostrar_caducados=true
                    condicion_caducidad = """
                        AND (
                            fecha_caducidad IS NULL 
                            OR fecha_caducidad > CURDATE() + INTERVAL 15 DAY
                        )
                    """
                
                sql = f"""
                    SELECT id, nombre, precio_publico AS precio, stock_actual, antibiotico,
                           fecha_caducidad,
                           CASE 
                               WHEN fecha_caducidad IS NULL THEN 'Sin fecha'
                               WHEN fecha_caducidad < CURDATE() THEN 'CADUCADO'
                               WHEN fecha_caducidad <= CURDATE() + INTERVAL 15 DAY THEN 'PRÓXIMO A CADUCAR'
                               ELSE 'VIGENTE'
                           END as estado_caducidad
                    FROM productos 
                    WHERE status = 1 
                    AND stock_actual > 0
                    {condicion_caducidad}
                    ORDER BY 
                        CASE WHEN estado_caducidad = 'VIGENTE' THEN 1
                             ELSE 2
                        END,
                        nombre
                """
                cursor.execute(sql)
                productos = cursor.fetchall()
                
                # Procesar para agregar indicador visual
                for producto in productos:
                    if producto['estado_caducidad'] != 'VIGENTE':
                        producto['nombre'] = f"{producto['nombre']} ⚠️ ({producto['estado_caducidad']})"
                
                return jsonify(productos)
                
            elif tipo == 'procedimientos':
                cursor.execute("SELECT id, nombre, precio FROM servicios WHERE status = 1")
            elif tipo == 'consultas':
                cursor.execute("SELECT id, nombre, precio FROM consultas WHERE status = 1")
            else: 
                return jsonify([])
            return jsonify(cursor.fetchall())
    finally:
        conn.close()

@app.route('/api/validar_producto_caducidad/<int:producto_id>')
@login_required
def validar_producto_caducidad(producto_id):
    """API para validar si un producto está en riesgo de caducidad"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    nombre,
                    fecha_caducidad,
                    CASE 
                        WHEN fecha_caducidad IS NULL THEN 'Sin fecha'
                        WHEN fecha_caducidad < CURDATE() THEN 'CADUCADO'
                        WHEN fecha_caducidad <= CURDATE() + INTERVAL 15 DAY THEN 'PRÓXIMO A CADUCAR'
                        ELSE 'VIGENTE'
                    END as estado_caducidad,
                    DATEDIFF(fecha_caducidad, CURDATE()) as dias_restantes
                FROM productos 
                WHERE id = %s AND status = 1
            """, (producto_id,))
            
            producto = cursor.fetchone()
            if not producto:
                return jsonify({'success': False, 'message': 'Producto no encontrado'})
            
            return jsonify({
                'success': True,
                'producto': producto['nombre'],
                'estado_caducidad': producto['estado_caducidad'],
                'dias_restantes': producto['dias_restantes'],
                'es_valido': producto['estado_caducidad'] == 'VIGENTE' or producto['estado_caducidad'] == 'Sin fecha'
            })
    finally:
        conn.close()

@app.route('/api/procesar_venta', methods=['POST'])
@login_required
def api_procesar_venta():
    data = request.json
    carrito = data.get('carrito', [])
    total = float(data.get('total', 0))
    metodo_id = int(data.get('metodo_pago_id'))
    cliente_id = data.get('cliente_id') if data.get('cliente_id') else 1
    
    # Si no es efectivo (ID 1), el pago es exacto y el cambio es 0
    if metodo_id != 1:
        pago_recibido = total
        cambio_entregado = 0
    else:
        pago_recibido = float(data.get('pago', total))
        cambio_entregado = float(data.get('cambio', 0))

    if not carrito: 
        return jsonify({'success': False, 'message': 'El carrito está vacío'})

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. Validar Stock y Caducidad de todos los productos
            for item in carrito:
                if item.get('esProducto'): # Solo validar si es producto, no servicio
                    # Validar stock
                    cursor.execute("SELECT nombre, stock_actual FROM productos WHERE id = %s", (item['id'],))
                    prod_check = cursor.fetchone()
                    
                    if not prod_check:
                        return jsonify({'success': False, 'message': f"Producto ID {item['id']} no encontrado"})
                    
                    if prod_check['stock_actual'] < int(item['cant']):
                        return jsonify({
                            'success': False, 
                            'message': f"Stock insuficiente para: {prod_check['nombre']}. Disponible: {prod_check['stock_actual']}"
                        })
                    
                    # Validar caducidad (nueva validación)
                    cursor.execute("""
                        SELECT 
                            nombre,
                            fecha_caducidad,
                            CASE 
                                WHEN fecha_caducidad IS NULL THEN 'Sin fecha'
                                WHEN fecha_caducidad < CURDATE() THEN 'CADUCADO'
                                WHEN fecha_caducidad <= CURDATE() + INTERVAL 15 DAY THEN 'PRÓXIMO A CADUCAR'
                                ELSE 'VIGENTE'
                            END as estado_caducidad
                        FROM productos 
                        WHERE id = %s
                    """, (item['id'],))
                    
                    caducidad_check = cursor.fetchone()
                    if caducidad_check and caducidad_check['estado_caducidad'] in ['CADUCADO', 'PRÓXIMO A CADUCAR']:
                        return jsonify({
                            'success': False,
                            'message': f"Producto '{caducidad_check['nombre']}' está {caducidad_check['estado_caducidad'].lower()}. No se puede vender."
                        })

            # 2. Verificar o abrir corte de caja
            cursor.execute("SELECT id FROM cortes_caja WHERE usuario_id = %s AND cerrado = 0 AND status = 1 LIMIT 1", (current_user.id,))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO cortes_caja (usuario_id, fecha_apertura, monto_inicial, cerrado, status) VALUES (%s, NOW(), 0, 0, 1)", (current_user.id,))
            
            # 3. Registrar Venta Cabeza
            folio = f"TICK-{int(time.time())}"
            cursor.execute("""
                INSERT INTO ventas (folio, usuario_id, cliente_id, metodo_pago_id, total, pago_recibido, cambio_entregado, fecha, status) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), 1)
            """, (folio, current_user.id, cliente_id, metodo_id, total, pago_recibido, cambio_entregado))
            venta_id = cursor.lastrowid

            # 4. Registrar Detalle y Actualizar Stock
            for item in carrito:
                # Obtener costo del producto
                costo = 0
                if item.get('esProducto'):
                    cursor.execute("SELECT precio_costo FROM productos WHERE id = %s", (item['id'],))
                    res_prod = cursor.fetchone()
                    costo = res_prod['precio_costo'] if res_prod else 0
                
                cursor.execute("""
                    INSERT INTO detalle_ventas (venta_id, producto_id, cantidad, precio_unitario, precio_costo_momento, subtotal, status) 
                    VALUES (%s, %s, %s, %s, %s, %s, 1)
                """, (venta_id, item['id'], item['cant'], item['precio'], costo, (float(item['precio']) * int(item['cant']))))
                
                # Actualizar stock solo si es producto
                if item.get('esProducto'):
                    cursor.execute("UPDATE productos SET stock_actual = stock_actual - %s WHERE id = %s", (item['cant'], item['id']))

            conn.commit()
            
            # 5. Obtener datos para el ticket
            cursor.execute("""
                SELECT v.*, u.nombre as farmaceutico, c.nombre as cliente, mp.nombre as metodo 
                FROM ventas v 
                JOIN usuarios u ON v.usuario_id = u.id 
                LEFT JOIN clientes c ON v.cliente_id = c.id 
                JOIN metodos_pago mp ON v.metodo_pago_id = mp.id 
                WHERE v.id = %s
            """, (venta_id,))
            venta_info = cursor.fetchone()
            
            return jsonify({
                'success': True, 
                'venta_id': venta_id, 
                'folio': folio,
                'total_vendido': total,
                'monto_entrega': total,
                'venta_info': venta_info
            })

    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': f"Error en servidor: {str(e)}"})
    finally:
        if conn: conn.close()

# ==========================================
# GESTIÓN DE SERVICIOS (SIN CAMBIOS)
# ==========================================
@app.route('/gestion_servicios')
@login_required
def gestion_servicios():
    if current_user.rol != 1: 
        return redirect(url_for('inicio_farmacia_route'))
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM servicios WHERE status = 1 ORDER BY nombre ASC")
            servicios = cursor.fetchall()
            cursor.execute("SELECT * FROM consultas WHERE status = 1 ORDER BY nombre ASC")
            consultas = cursor.fetchall()
        return render_template('gestion_servicios.html', servicios=servicios, consultas=consultas)
    finally:
        conn.close()

@app.route('/gestion/guardar', methods=['POST'])
@login_required
def guardar_item():
    tipo = request.form.get('tipo')
    id_item = request.form.get('id')
    nombre = request.form.get('nombre')
    precio = request.form.get('precio')
    
    if not nombre or not precio:
        flash('Nombre y precio son obligatorios', 'danger')
        return redirect(url_for('gestion_servicios'))
    
    tabla = "servicios" if tipo == "servicio" else "consultas"
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if id_item: 
                cursor.execute(f"UPDATE {tabla} SET nombre=%s, precio=%s WHERE id=%s", (nombre, precio, id_item))
            else: 
                cursor.execute(f"INSERT INTO {tabla} (nombre, precio, status) VALUES (%s, %s, 1)", (nombre, precio))
        
        conn.commit()
        flash('Registro guardado exitosamente.', 'success')
    except Exception as e:
        flash(f'Error al guardar: {str(e)}', 'danger')
    finally: 
        conn.close()
    
    return redirect(url_for('gestion_servicios'))

# ==========================================
# LOGOUT
# ==========================================
@app.route('/logout')
@login_required
def Salir():
    # Verificar si hay corte abierto antes de salir
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM cortes_caja WHERE usuario_id = %s AND cerrado = 0 AND status = 1", (current_user.id,))
            if cursor.fetchone():
                flash('Tienes un corte de caja abierto. Debes cerrarlo antes de salir.', 'warning')
                return redirect(url_for('corte_caja'))
    finally:
        conn.close()
    
    logout_user()
    session.clear()
    flash('Sesión cerrada exitosamente', 'success')
    return redirect(url_for('login'))

# ==========================================
# RUTAS DE PRUEBA Y DESARROLLO
# ==========================================
@app.route('/test_db')
def test_db():
    """Ruta para probar la conexión a la base de datos"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as total FROM usuarios WHERE status = 1")
            usuarios = cursor.fetchone()
            cursor.execute("SELECT COUNT(*) as total FROM productos WHERE status = 1")
            productos = cursor.fetchone()
            cursor.execute("SELECT COUNT(*) as total FROM ventas WHERE status = 1")
            ventas = cursor.fetchone()
        
        return jsonify({
            'success': True,
            'usuarios': usuarios['total'],
            'productos': productos['total'],
            'ventas': ventas['total']
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        if 'conn' in locals():
            conn.close()

# ==========================================
# INICIALIZACIÓN DE LA APLICACIÓN
# ==========================================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5010, debug=True)