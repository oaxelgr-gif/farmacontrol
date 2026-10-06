-- =================================================================
-- FarmaControl · inicialización del contenedor MySQL (imagen farmacontrol-db)
-- Se ejecuta automáticamente SOLO la primera vez (volumen vacío).
-- INSTALACIÓN LIMPIA: 1 administrador, 3 productos de prueba, catálogos base.
-- =================================================================
SET NAMES utf8mb4;
-- =================================================================
-- SCRIPT SQL UNIFICADO PARA FARMACIA - VERSION MIGRABLE
-- =================================================================

CREATE DATABASE IF NOT EXISTS medicalife CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE medicalife;

-- =================================================================
-- TABLA DE ROLES
-- =================================================================
CREATE TABLE roles (
    id INT PRIMARY KEY AUTO_INCREMENT,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    status BOOLEAN DEFAULT TRUE
);

-- =================================================================
-- TABLA DE USUARIOS
-- =================================================================
CREATE TABLE usuarios (
    id INT PRIMARY KEY AUTO_INCREMENT,
    nombre VARCHAR(100) NOT NULL,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    rol INT NOT NULL,
    status BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (rol) REFERENCES roles(id)
);

-- =================================================================
-- TABLA DE SECCIONES
-- =================================================================
CREATE TABLE secciones (
    id INT PRIMARY KEY AUTO_INCREMENT,
    nombre VARCHAR(100) NOT NULL,
    status BOOLEAN DEFAULT TRUE
);

-- =================================================================
-- TABLA DE PRODUCTOS
-- =================================================================
CREATE TABLE productos (
    id INT PRIMARY KEY AUTO_INCREMENT,
    nombre VARCHAR(200) NOT NULL,
    codigo_barras VARCHAR(50) UNIQUE,
    lote VARCHAR(50),
    stock_actual INT DEFAULT 0,
    stock_minimo INT DEFAULT 5,
    precio_costo DECIMAL(10,2) NOT NULL,
    precio_publico DECIMAL(10,2) NOT NULL,
    antibiotico BOOLEAN DEFAULT FALSE,
    fecha_caducidad DATE,
    seccion_id INT,
    status BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (seccion_id) REFERENCES secciones(id)
);

-- =================================================================
-- TABLA DE CLIENTES
-- =================================================================
CREATE TABLE clientes (
    id INT PRIMARY KEY AUTO_INCREMENT,
    nombre VARCHAR(150) NOT NULL,
    rfc_nit VARCHAR(20),
    direccion TEXT,
    telefono VARCHAR(15),
    email VARCHAR(100),
    status BOOLEAN DEFAULT TRUE
);

-- =================================================================
-- TABLA DE MÉTODOS DE PAGO
-- =================================================================
CREATE TABLE metodos_pago (
    id INT PRIMARY KEY AUTO_INCREMENT,
    nombre VARCHAR(50) NOT NULL,
    status BOOLEAN DEFAULT TRUE
);

-- =================================================================
-- TABLA DE VENTAS (CABECERA)
-- =================================================================
CREATE TABLE ventas (
    id INT PRIMARY KEY AUTO_INCREMENT,
    folio VARCHAR(20) UNIQUE,
    usuario_id INT NOT NULL,
    cliente_id INT DEFAULT 1,
    metodo_pago_id INT NOT NULL,
    total DECIMAL(10,2) NOT NULL,
    pago_recibido DECIMAL(10,2) NOT NULL,
    cambio_entregado DECIMAL(10,2) NOT NULL,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    status BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    FOREIGN KEY (cliente_id) REFERENCES clientes(id),
    FOREIGN KEY (metodo_pago_id) REFERENCES metodos_pago(id)
);

-- =================================================================
-- TABLA DE DETALLE DE VENTAS
-- =================================================================
CREATE TABLE detalle_ventas (
    id INT PRIMARY KEY AUTO_INCREMENT,
    venta_id INT NOT NULL,
    producto_id INT,
    cantidad INT NOT NULL,
    precio_unitario DECIMAL(10,2) NOT NULL,
    precio_costo_momento DECIMAL(10,2) NOT NULL,
    subtotal DECIMAL(10,2) NOT NULL,
    status BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (venta_id) REFERENCES ventas(id),
    FOREIGN KEY (producto_id) REFERENCES productos(id)
);

-- =================================================================
-- TABLA DE CORTES DE CAJA
-- =================================================================
CREATE TABLE cortes_caja (
    id INT PRIMARY KEY AUTO_INCREMENT,
    usuario_id INT NOT NULL,
    fecha_apertura DATETIME DEFAULT CURRENT_TIMESTAMP,
    monto_inicial DECIMAL(10,2) NOT NULL,
    cerrado BOOLEAN DEFAULT FALSE,
    fecha_cierre DATETIME,
    monto_final DECIMAL(10,2),
    status BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

-- =================================================================
-- TABLA DE AUDITORÍA DE CORTES (NUEVA)
-- =================================================================
CREATE TABLE auditoria_cortes (
    id INT PRIMARY KEY AUTO_INCREMENT,
    corte_id INT NOT NULL,
    usuario_id INT NOT NULL,
    fecha_apertura DATETIME,
    fecha_cierre DATETIME,
    monto_inicial DECIMAL(10,2),
    monto_final DECIMAL(10,2),
    ventas_efectivo DECIMAL(10,2),
    ventas_tarjeta DECIMAL(10,2),
    ventas_transferencia DECIMAL(10,2),
    total_ventas DECIMAL(10,2),
    FOREIGN KEY (corte_id) REFERENCES cortes_caja(id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

-- =================================================================
-- TABLA DE SERVICIOS
-- =================================================================
CREATE TABLE servicios (
    id INT PRIMARY KEY AUTO_INCREMENT,
    nombre VARCHAR(100) NOT NULL,
    precio DECIMAL(10,2) NOT NULL,
    status BOOLEAN DEFAULT TRUE
);

-- =================================================================
-- TABLA DE CONSULTAS
-- =================================================================
CREATE TABLE consultas (
    id INT PRIMARY KEY AUTO_INCREMENT,
    nombre VARCHAR(100) NOT NULL,
    precio DECIMAL(10,2) NOT NULL,
    status BOOLEAN DEFAULT TRUE
);

-- =================================================================
-- INSERCIÓN DE DATOS INICIALES
-- =================================================================

-- Insertar roles
INSERT INTO roles (id, nombre) VALUES 
(1, 'Administrador'),
(2, 'Farmacéutico');

-- Usuario administrador (cambia la contraseña al entrar: Usuarios → editar)
INSERT INTO usuarios (nombre, username, password, rol) VALUES
('Administrador Principal', 'admin', '131004131004', 1);

-- Insertar secciones
INSERT INTO secciones (nombre) VALUES 
('Medicamentos'),
('Dermocosmética'),
('Cuidado Personal'),
('Nutrición'),
('Maternidad'),
('Antibióticos'),
('Analgésicos'),
('Vitaminas');

-- Insertar métodos de pago
INSERT INTO metodos_pago (nombre) VALUES 
('Efectivo'),
('Tarjeta de Crédito'),
('Tarjeta de Débito'),
('Transferencia');

-- Insertar cliente genérico
INSERT INTO clientes (nombre, rfc_nit) VALUES 
('Público General', 'XAXX010101000');

-- 3 productos de prueba para el punto de venta (puedes editarlos o eliminarlos)
INSERT INTO productos (nombre, codigo_barras, lote, stock_actual, stock_minimo, precio_costo, precio_publico, antibiotico, fecha_caducidad, seccion_id) VALUES
('PRUEBA Paracetamol 500mg (Caja 20)', '0000000000001', 'PRUEBA-01', 50, 5, 15.00, 35.50, 0, '2028-12-31', 7),
('PRUEBA Amoxicilina 500mg (Caja 12)', '0000000000002', 'PRUEBA-02', 30, 5, 40.00, 99.90, 1, '2028-12-31', 6),
('PRUEBA Vitamina C 1g (Tubo 10)', '0000000000003', 'PRUEBA-03', 40, 5, 25.00, 59.00, 0, '2028-12-31', 8);

-- Insertar algunos servicios
INSERT INTO servicios (nombre, precio) VALUES 
('Aplicación de inyección', 50.00),
('Toma de presión arterial', 30.00),
('Toma de glucosa', 25.00),
('Curaciones menores', 80.00);

-- Insertar algunas consultas
INSERT INTO consultas (nombre, precio) VALUES 
('Consulta general', 200.00),
('Consulta especializada', 350.00);

-- =================================================================
-- CREACIÓN DE ÍNDICES PARA OPTIMIZACIÓN
-- =================================================================
CREATE INDEX idx_productos_codigo ON productos(codigo_barras);
CREATE INDEX idx_productos_nombre ON productos(nombre);
CREATE INDEX idx_ventas_fecha ON ventas(fecha);
CREATE INDEX idx_ventas_usuario ON ventas(usuario_id);
CREATE INDEX idx_ventas_folio ON ventas(folio);
CREATE INDEX idx_detalle_venta_id ON detalle_ventas(venta_id);
CREATE INDEX idx_cortes_usuario ON cortes_caja(usuario_id);
CREATE INDEX idx_cortes_fecha ON cortes_caja(fecha_apertura);

-- =================================================================
-- VISTAS ÚTILES
-- =================================================================
CREATE VIEW vista_ventas_detalladas AS
SELECT 
    v.id as venta_id,
    v.folio,
    v.fecha,
    u.nombre as vendedor,
    c.nombre as cliente,
    mp.nombre as metodo_pago,
    v.total,
    v.pago_recibido,
    v.cambio_entregado,
    GROUP_CONCAT(CONCAT(p.nombre, ' (', dv.cantidad, ' x $', dv.precio_unitario, ')') SEPARATOR ', ') as productos
FROM ventas v
JOIN usuarios u ON v.usuario_id = u.id
LEFT JOIN clientes c ON v.cliente_id = c.id
JOIN metodos_pago mp ON v.metodo_pago_id = mp.id
JOIN detalle_ventas dv ON v.id = dv.venta_id
LEFT JOIN productos p ON dv.producto_id = p.id
WHERE v.status = 1
GROUP BY v.id;

CREATE VIEW vista_antibioticos_vendidos AS
SELECT 
    v.fecha,
    v.folio,
    u.nombre as vendedor,
    p.nombre as producto,
    p.lote,
    dv.cantidad,
    dv.precio_unitario as precio_venta,
    (dv.cantidad * dv.precio_unitario) as subtotal,
    (dv.cantidad * (dv.precio_unitario - dv.precio_costo_momento)) as utilidad
FROM detalle_ventas dv
JOIN productos p ON dv.producto_id = p.id
JOIN ventas v ON dv.venta_id = v.id
JOIN usuarios u ON v.usuario_id = u.id
WHERE p.antibiotico = 1 AND v.status = 1;

-- =================================================================
-- PROCEDIMIENTOS ALMACENADOS
-- =================================================================
DELIMITER //

CREATE PROCEDURE sp_generar_corte(IN p_usuario_id INT)
BEGIN
    DECLARE v_monto_inicial DECIMAL(10,2);
    DECLARE v_total_ventas DECIMAL(10,2);
    DECLARE v_monto_final DECIMAL(10,2);
    DECLARE v_corte_id INT;
    
    -- Obtener el corte abierto
    SELECT id, monto_inicial INTO v_corte_id, v_monto_inicial
    FROM cortes_caja 
    WHERE usuario_id = p_usuario_id AND cerrado = 0
    LIMIT 1;
    
    IF v_corte_id IS NOT NULL THEN
        -- Calcular ventas durante el corte
        SELECT IFNULL(SUM(total), 0) INTO v_total_ventas
        FROM ventas 
        WHERE usuario_id = p_usuario_id 
        AND fecha >= (SELECT fecha_apertura FROM cortes_caja WHERE id = v_corte_id)
        AND status = 1;
        
        -- Calcular monto final
        SET v_monto_final = v_monto_inicial + v_total_ventas;
        
        -- Actualizar corte
        UPDATE cortes_caja 
        SET cerrado = 1, fecha_cierre = NOW(), monto_final = v_monto_final
        WHERE id = v_corte_id;
        
        -- Insertar en auditoría
        INSERT INTO auditoria_cortes (corte_id, usuario_id, fecha_apertura, fecha_cierre, monto_inicial, monto_final, total_ventas)
        VALUES (v_corte_id, p_usuario_id, 
                (SELECT fecha_apertura FROM cortes_caja WHERE id = v_corte_id),
                NOW(), v_monto_inicial, v_monto_final, v_total_ventas);
    END IF;
END //

DELIMITER ;



-- Verificar la estructura actual de la tabla

-- Si necesitas agregar la columna numero_ventas
ALTER TABLE auditoria_cortes ADD COLUMN numero_ventas INT DEFAULT 0 AFTER total_ventas;

-- O si prefieres recrear la tabla completa (haz backup primero)
/*
DROP TABLE IF EXISTS auditoria_cortes;

CREATE TABLE auditoria_cortes (
    id INT PRIMARY KEY AUTO_INCREMENT,
    corte_id INT NOT NULL,
    usuario_id INT NOT NULL,
    fecha_apertura DATETIME NOT NULL,
    fecha_cierre DATETIME NOT NULL,
    monto_inicial DECIMAL(10,2) NOT NULL,
    monto_final DECIMAL(10,2) NOT NULL,
    ventas_efectivo DECIMAL(10,2) DEFAULT 0,
    ventas_tarjeta DECIMAL(10,2) DEFAULT 0,
    ventas_transferencia DECIMAL(10,2) DEFAULT 0,
    total_ventas DECIMAL(10,2) DEFAULT 0,
    numero_ventas INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (corte_id) REFERENCES cortes_caja(id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);
*/
-- =================================================================
-- FIN DEL SCRIPT
-- =================================================================