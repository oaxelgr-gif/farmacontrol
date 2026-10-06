-- =================================================================
-- FarmaControl · 2 pacientes de prueba ("fantasma") para el módulo clínico.
-- Puedes darlos de baja desde Clínica → Pacientes cuando ya no los necesites.
-- =================================================================
USE medicalife;
SET NAMES utf8mb4;

INSERT INTO pacientes (expediente, nombre, apellido_paterno, apellido_materno, fecha_nacimiento, sexo,
                       tipo_sangre, telefono, ciudad, notas, created_by)
VALUES
('P000001', 'PACIENTE', 'PRUEBA', 'UNO', '1980-01-15', 'M', 'O+', '0000000001', 'Querétaro',
 'Paciente de prueba para verificar el sistema. Dar de baja al terminar.', 1),
('P000002', 'PACIENTE', 'PRUEBA', 'DOS', '1992-06-20', 'F', 'A+', '0000000002', 'Querétaro',
 'Paciente de prueba para verificar el sistema. Dar de baja al terminar.', 1);

INSERT INTO paciente_alergias (paciente_id, alergeno, tipo, reaccion, severidad)
SELECT id, 'Penicilina (prueba)', 'medicamento', 'Alergia ficticia para probar avisos', 'moderada'
FROM pacientes WHERE expediente = 'P000002';
