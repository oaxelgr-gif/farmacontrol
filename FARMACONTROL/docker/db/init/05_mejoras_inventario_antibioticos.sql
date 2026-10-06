-- =================================================================
-- FarmaControl · Mejoras: anaqueles editables, datos de antibióticos,
-- registro de recetas de antibióticos (control sanitario), perfil de
-- receta (WhatsApp, logos) y catálogo de diagnósticos frecuentes.
-- Es seguro ejecutarlo más de una vez.
--   docker compose exec -T db sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" medicalife' < BD/05_mejoras_inventario_antibioticos.sql
-- =================================================================
USE medicalife;
SET NAMES utf8mb4;

DROP PROCEDURE IF EXISTS fc_add_col;
DELIMITER $$
CREATE PROCEDURE fc_add_col(IN tabla VARCHAR(64), IN columna VARCHAR(64), IN definicion VARCHAR(255))
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = tabla AND COLUMN_NAME = columna) THEN
        SET @sql = CONCAT('ALTER TABLE `', tabla, '` ADD COLUMN `', columna, '` ', definicion);
        PREPARE st FROM @sql; EXECUTE st; DEALLOCATE PREPARE st;
    END IF;
END$$
DELIMITER ;

-- Anaqueles (tabla secciones): ahora con descripción editable
CALL fc_add_col('secciones', 'descripcion', 'VARCHAR(255) NULL AFTER nombre');

-- Productos: compuesto (sustancia activa) y tipo de antibiótico
CALL fc_add_col('productos', 'sustancia_activa', 'VARCHAR(150) NULL AFTER nombre');
CALL fc_add_col('productos', 'tipo_antibiotico', 'VARCHAR(60) NULL AFTER antibiotico');

-- Perfil médico: datos del formato de receta
CALL fc_add_col('perfil_medico', 'whatsapp', 'VARCHAR(30) NULL AFTER telefono');
CALL fc_add_col('perfil_medico', 'logo_izq', 'VARCHAR(255) NULL');
CALL fc_add_col('perfil_medico', 'logo_der', 'VARCHAR(255) NULL');

DROP PROCEDURE IF EXISTS fc_add_col;

-- Diagnósticos que el médico usa (se aprenden solos al guardar consultas)
CREATE TABLE IF NOT EXISTS diagnosticos_frecuentes (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    descripcion     VARCHAR(200) NOT NULL,
    cie10           VARCHAR(10),
    usos            INT DEFAULT 1,
    ultimo_uso      DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_diag_desc (descripcion)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Registro de la receta presentada al vender antibióticos (uno por venta)
CREATE TABLE IF NOT EXISTS antibioticos_recetas (
    id                  INT PRIMARY KEY AUTO_INCREMENT,
    venta_id            INT NOT NULL,
    paciente_id         INT NULL,                 -- paciente interno de la clínica (si existe)
    paciente_nombre     VARCHAR(150) NOT NULL,
    medico_nombre       VARCHAR(150) NOT NULL,
    medico_cedula       VARCHAR(30) NOT NULL,
    medico_domicilio    VARCHAR(255),
    institucion         VARCHAR(150),             -- institución que expidió la receta
    receta_folio        VARCHAR(40),
    receta_fecha        DATE,
    receta_clinica_id   INT NULL,                 -- receta emitida en el consultorio
    vale_salida         VARCHAR(40),
    requiere_receta     BOOLEAN DEFAULT TRUE,
    destino_receta      VARCHAR(15) DEFAULT 'retenida',  -- retenida, sellada
    observaciones       VARCHAR(255),
    usuario_id          INT NOT NULL,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (venta_id) REFERENCES ventas(id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    INDEX idx_abr_venta (venta_id),
    INDEX idx_abr_fecha (created_at),
    INDEX idx_abr_cedula (medico_cedula)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Antibióticos dispensados en esa venta (compuesto, tipo, lote, cantidad)
CREATE TABLE IF NOT EXISTS antibioticos_dispensacion (
    id                  INT PRIMARY KEY AUTO_INCREMENT,
    registro_id         INT NOT NULL,
    venta_id            INT NOT NULL,
    producto_id         INT NOT NULL,
    producto_nombre     VARCHAR(200) NOT NULL,
    compuesto           VARCHAR(150),
    tipo_antibiotico    VARCHAR(60),
    lote                VARCHAR(50),
    fecha_caducidad     DATE,
    cantidad            INT NOT NULL,
    FOREIGN KEY (registro_id) REFERENCES antibioticos_recetas(id),
    FOREIGN KEY (venta_id) REFERENCES ventas(id),
    FOREIGN KEY (producto_id) REFERENCES productos(id),
    INDEX idx_abd_venta (venta_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Clasificación inicial de antibióticos existentes por nombre (solo los que no tienen tipo)
UPDATE productos SET tipo_antibiotico = CASE
    WHEN LOWER(nombre) REGEXP 'amoxi|ampici|penici|dicloxa|benzatin' THEN 'Penicilinas'
    WHEN LOWER(nombre) REGEXP 'cef|cefa' THEN 'Cefalosporinas'
    WHEN LOWER(nombre) REGEXP 'azitro|claritro|eritro' THEN 'Macrólidos'
    WHEN LOWER(nombre) REGEXP 'floxac' THEN 'Quinolonas'
    WHEN LOWER(nombre) REGEXP 'doxici|tetraci|minoci' THEN 'Tetraciclinas'
    WHEN LOWER(nombre) REGEXP 'sulfa|trimetop' THEN 'Sulfonamidas'
    WHEN LOWER(nombre) REGEXP 'genta|amika|neomi|estrepto' THEN 'Aminoglucósidos'
    WHEN LOWER(nombre) REGEXP 'clinda|linco' THEN 'Lincosamidas'
    WHEN LOWER(nombre) REGEXP 'metronid|tinidaz' THEN 'Nitroimidazoles'
    WHEN LOWER(nombre) REGEXP 'nitrofur' THEN 'Nitrofuranos'
    ELSE tipo_antibiotico END
WHERE antibiotico = 1 AND tipo_antibiotico IS NULL;
