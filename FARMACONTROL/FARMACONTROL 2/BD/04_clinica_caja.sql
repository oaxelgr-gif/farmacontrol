-- =================================================================
-- FarmaControl · Módulo clínico ↔ caja
-- Enlaza consultas (honorarios) y recetas (surtido) con las ventas.
-- Solo es necesario si ya habías ejecutado 02_modulo_clinico.sql antes
-- de esta versión. Es seguro ejecutarlo más de una vez.
--   mysql -u root -p medicalife < BD/04_clinica_caja.sql
-- =================================================================
USE medicalife;

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

CALL fc_add_col('consultas_medicas', 'venta_id', 'INT NULL AFTER costo');
CALL fc_add_col('recetas', 'venta_id', 'INT NULL AFTER proxima_cita');
CALL fc_add_col('recetas', 'surtida_at', 'DATETIME NULL AFTER venta_id');
DROP PROCEDURE IF EXISTS fc_add_col;
