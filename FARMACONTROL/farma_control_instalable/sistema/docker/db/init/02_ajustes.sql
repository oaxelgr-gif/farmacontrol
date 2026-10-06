-- Ajustes posteriores al esquema base (se ejecuta una sola vez, al crear el volumen)
USE medicalife;

-- Índices útiles para reportes y cortes
CREATE INDEX idx_ventas_status_fecha ON ventas(status, fecha);
CREATE INDEX idx_detalle_producto ON detalle_ventas(producto_id);
CREATE INDEX idx_productos_caducidad ON productos(status, fecha_caducidad);
