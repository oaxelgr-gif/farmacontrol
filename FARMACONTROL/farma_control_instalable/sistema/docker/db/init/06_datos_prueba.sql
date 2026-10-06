-- FarmaControl · completa los datos del antibiótico de prueba (compuesto y tipo)
USE medicalife;
SET NAMES utf8mb4;
UPDATE productos SET sustancia_activa = 'Amoxicilina', tipo_antibiotico = 'Penicilinas'
WHERE codigo_barras = '0000000000002';
UPDATE productos SET sustancia_activa = 'Paracetamol' WHERE codigo_barras = '0000000000001';
UPDATE productos SET sustancia_activa = 'Ácido ascórbico' WHERE codigo_barras = '0000000000003';
