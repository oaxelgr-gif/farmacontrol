-- =================================================================
-- FarmaControl · inicialización del contenedor MySQL (imagen farmacontrol-db)
-- Se ejecuta automáticamente SOLO la primera vez (volumen vacío).
-- Basado en BD/FARMACONTROL.sql
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

-- Insertar 10 usuarios
INSERT INTO usuarios (nombre, username, password, rol) VALUES 
('Administrador Principal', 'admin', '131004131004', 1),
('Carlos Mendoza', 'carlos', '12345', 2),
('Ana García', 'ana', '12345', 2),
('Luis Rodríguez', 'luis', '12345', 2),
('María López', 'maria', '12345', 2),
('Pedro Sánchez', 'pedro', '12345', 2),
('Laura Martínez', 'laura', '12345', 2),
('Jorge Fernández', 'jorge', '12345', 2),
('Sofía Ramírez', 'sofia', '12345', 2),
('Miguel Torres', 'miguel', '12345', 2);

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

-- Insertar 50 productos de ejemplo (extensible a 1000)
INSERT INTO productos (nombre, codigo_barras, lote, stock_actual, stock_minimo, precio_costo, precio_publico, antibiotico, fecha_caducidad, seccion_id) VALUES
('Paracetamol 500mg (Caja 20)', '7501001234567', 'LOTE-2024-001', 150, 20, 15.00, 35.50, 0, '2026-10-30', 1),
('Amoxicilina 500mg', '7501001234568', 'LOTE-2024-002', 80, 15, 40.00, 99.90, 1, '2025-05-15', 6),
('Ibuprofeno 400mg', '7501001234569', 'LOTE-2024-003', 8, 10, 80.00, 189.90, 0, '2027-01-20', 7),
('Vitamina D3 1000 UI', '7501001234570', 'LOTE-2024-004', 50, 5, 120.00, 290.00, 0, NULL, 8),
('Cefalexina 250mg', '7501001234571', 'LOTE-2024-005', 12, 12, 75.00, 175.50, 1, '2025-03-01', 6),
('A-Agua Termal Avene 150Ml', '3282770930597', 'LOTE-2024-006', 10, 5, 125.00, 250.00, 0, NULL, 2),
('A-Kerat 30 Crema 100 Ml', '3282776390517', 'LOTE-2024-007', 10, 5, 192.50, 385.00, 0, NULL, 2),
('Bloqueador Solar FPS 50+', '3282779275699', 'LOTE-2024-008', 10, 5, 240.00, 480.00, 0, NULL, 2),
('Cicalfate Crema 40Ml', '3282776088209', 'LOTE-2024-009', 10, 5, 163.00, 326.00, 0, NULL, 2),
('YODOPOVIDONA BUCOFARINGEO', '7501250882024', 'LOTE-2024-010', 10, 5, 38.00, 76.00, 0, '2026-08-15', 1),
('Aspirina 500mg', '7501001234572', 'LOTE-2024-011', 200, 30, 8.00, 18.50, 0, '2027-03-20', 7),
('Omeprazol 20mg', '7501001234573', 'LOTE-2024-012', 120, 20, 45.00, 95.00, 0, '2026-11-30', 1),
('Losartan 50mg', '7501001234574', 'LOTE-2024-013', 90, 15, 65.00, 130.00, 0, '2027-02-15', 1),
('Metformina 850mg', '7501001234575', 'LOTE-2024-014', 150, 25, 28.00, 65.00, 0, '2026-09-10', 1),
('Atorvastatina 20mg', '7501001234576', 'LOTE-2024-015', 85, 15, 95.00, 195.00, 0, '2027-01-05', 1),
('Azitromicina 500mg', '7501001234577', 'LOTE-2024-016', 45, 10, 110.00, 230.00, 1, '2025-07-22', 6),
('Claritromicina 500mg', '7501001234578', 'LOTE-2024-017', 30, 8, 125.00, 260.00, 1, '2025-08-30', 6),
('Ciprofloxacino 500mg', '7501001234579', 'LOTE-2024-018', 25, 5, 140.00, 290.00, 1, '2025-06-18', 6),
('Levofloxacino 500mg', '7501001234580', 'LOTE-2024-019', 20, 5, 155.00, 320.00, 1, '2025-05-12', 6),
('Vitamina C 1000mg', '7501001234581', 'LOTE-2024-020', 180, 30, 25.00, 55.00, 0, '2027-04-10', 8),
('Vitamina B12 1000mcg', '7501001234582', 'LOTE-2024-021', 95, 15, 85.00, 175.00, 0, '2027-02-28', 8),
('Multivitamínico Complejo B', '7501001234583', 'LOTE-2024-022', 110, 20, 150.00, 310.00, 0, '2027-03-15', 8),
('Hierro + Ácido Fólico', '7501001234584', 'LOTE-2024-023', 75, 10, 95.00, 195.00, 0, '2026-12-20', 8),
('Calcio + Vitamina D', '7501001234585', 'LOTE-2024-024', 130, 25, 120.00, 245.00, 0, '2027-05-30', 8),
('Crema Hidratante Nivea', '7501001234586', 'LOTE-2024-025', 200, 40, 45.00, 95.00, 0, NULL, 3),
('Shampoo Anticaspa Head&Shoulders', '7501001234587', 'LOTE-2024-026', 150, 30, 65.00, 135.00, 0, NULL, 3),
('Jabón Líquido Dove', '7501001234588', 'LOTE-2024-027', 180, 35, 28.00, 65.00, 0, NULL, 3),
('Desodorante Rexona', '7501001234589', 'LOTE-2024-028', 220, 45, 35.00, 75.00, 0, NULL, 3),
('Pasta Dental Colgate', '7501001234590', 'LOTE-2024-029', 250, 50, 18.00, 38.00, 0, NULL, 3),
('Enjuague Bucal Listerine', '7501001234591', 'LOTE-2024-030', 120, 25, 85.00, 170.00, 0, '2026-10-15', 3),
('Pañales Talla G Huggies', '7501001234592', 'LOTE-2024-031', 80, 15, 350.00, 650.00, 0, NULL, 5),
('Leche en Polvo NAN 1', '7501001234593', 'LOTE-2024-032', 60, 10, 420.00, 780.00, 0, '2025-12-31', 5),
('Toallitas Húmedas Pampers', '7501001234594', 'LOTE-2024-033', 140, 30, 95.00, 190.00, 0, NULL, 5),
('Crema para Pañal Desitin', '7501001234595', 'LOTE-2024-034', 90, 20, 125.00, 250.00, 0, '2026-08-20', 5),
('Termómetro Digital Braun', '7501001234596', 'LOTE-2024-035', 40, 5, 280.00, 520.00, 0, NULL, 3),
('Cubrebocas N95 3M', '7501001234597', 'LOTE-2024-036', 500, 100, 25.00, 50.00, 0, NULL, 3),
('Alcohol en Gel 1L', '7501001234598', 'LOTE-2024-037', 150, 30, 85.00, 170.00, 0, '2026-06-30', 3),
('Gasas Estériles 10x10', '7501001234599', 'LOTE-2024-038', 200, 40, 45.00, 95.00, 0, '2027-01-31', 3),
('Venda Elástica 10cm', '7501001234600', 'LOTE-2024-039', 180, 35, 28.00, 65.00, 0, NULL, 3),
('Tiras Reactivas Glucosa', '7501001234601', 'LOTE-2024-040', 50, 10, 350.00, 680.00, 0, '2025-11-30', 3),
('Jeringa 3ml BD', '7501001234602', 'LOTE-2024-041', 300, 60, 8.00, 18.00, 0, NULL, 3),
('Guantes Latex Talla M', '7501001234603', 'LOTE-2024-042', 400, 80, 15.00, 35.00, 0, NULL, 3),
('Curitas Nexcare', '7501001234604', 'LOTE-2024-043', 250, 50, 25.00, 55.00, 0, NULL, 3),
('Inhalador Salbutamol', '7501001234605', 'LOTE-2024-044', 60, 12, 180.00, 360.00, 0, '2026-04-15', 1),
('Insulina Humulina N', '7501001234606', 'LOTE-2024-045', 40, 8, 450.00, 850.00, 0, '2025-09-30', 1),
('Tiras Reactivas Colesterol', '7501001234607', 'LOTE-2024-046', 30, 5, 550.00, 1050.00, 0, '2025-12-15', 3),
('Monitor Presión Arterial', '7501001234608', 'LOTE-2024-047', 25, 5, 850.00, 1600.00, 0, NULL, 3),
('Glucómetro Accu-Chek', '7501001234609', 'LOTE-2024-048', 35, 7, 650.00, 1250.00, 0, NULL, 3),
('Oxímetro de Pulso', '7501001234610', 'LOTE-2024-049', 20, 4, 750.00, 1450.00, 0, NULL, 3),
('Nebulizador Omron', '7501001234611', 'LOTE-2024-050', 15, 3, 1200.00, 2300.00, 0, NULL, 3);

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

-- Insertar algunos cortes de caja de ejemplo
INSERT INTO cortes_caja (usuario_id, monto_inicial, cerrado, fecha_apertura, fecha_cierre, monto_final) VALUES
(2, 5000.00, TRUE, '2024-01-15 08:00:00', '2024-01-15 20:00:00', 18500.00),
(3, 3000.00, TRUE, '2024-01-15 08:00:00', '2024-01-15 20:00:00', 12500.00),
(2, 5000.00, FALSE, NOW(), NULL, NULL);

-- Insertar auditoría de cortes de ejemplo
INSERT INTO auditoria_cortes (corte_id, usuario_id, fecha_apertura, fecha_cierre, monto_inicial, monto_final, ventas_efectivo, ventas_tarjeta, ventas_transferencia, total_ventas) VALUES
(1, 2, '2024-01-15 08:00:00', '2024-01-15 20:00:00', 5000.00, 18500.00, 12000.00, 1500.00, 0.00, 13500.00),
(2, 3, '2024-01-15 08:00:00', '2024-01-15 20:00:00', 3000.00, 12500.00, 8500.00, 1000.00, 0.00, 9500.00);

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