-- =================================================================
-- FarmaControl · Datos de ejemplo del módulo clínico (opcional)
-- Docker: se carga al crear la base. Local: BD/03_clinica_datos_demo.sql
-- Puedes borrarlos desde la interfaz (dar de baja pacientes).
-- =================================================================
USE medicalife;
SET NAMES utf8mb4;

INSERT INTO perfil_medico (usuario_id, nombre_mostrar, especialidad, cedula_profesional, cedula_especialidad,
                           institucion, telefono, email, direccion, horario, leyenda_receta)
VALUES (1, 'Dr. Administrador Principal', 'Medicina General', '12345678', NULL,
        'Universidad Nacional Autónoma de México', '(55) 1234-5678', 'consultorio@medicalife.mx',
        'Av. Salud 123, Col. Centro, C.P. 06000, Ciudad de México', 'Lun a Sáb 9:00 – 20:00',
        'Esta receta tiene vigencia de 30 días. No se surten antibióticos sin receta.')
ON DUPLICATE KEY UPDATE nombre_mostrar = nombre_mostrar;

INSERT INTO pacientes (expediente, nombre, apellido_paterno, apellido_materno, fecha_nacimiento, sexo, curp,
                       tipo_sangre, estado_civil, ocupacion, escolaridad, telefono, email, direccion, ciudad,
                       codigo_postal, contacto_nombre, contacto_parentesco, contacto_telefono, created_by)
VALUES
('P000001', 'María Elena', 'Hernández', 'Ruiz', '1968-04-12', 'F', 'HERM680412MDFRZR01', 'O+', 'Casada',
 'Comerciante', 'Secundaria', '5512345601', 'maria.hdz@correo.com', 'Calle Pino 45', 'Ciudad de México', '06700',
 'José Hernández', 'Esposo', '5512345602', 1),
('P000002', 'Jorge Luis', 'Martínez', 'Gómez', '1985-09-30', 'M', 'MAGJ850930HDFRMR02', 'A+', 'Soltero',
 'Ingeniero', 'Licenciatura', '5523456701', 'jorge.mtz@correo.com', 'Av. Reforma 210, Int. 4', 'Ciudad de México', '06600',
 'Laura Gómez', 'Madre', '5523456702', 1),
('P000003', 'Sofía', 'López', 'Castro', '2016-02-18', 'F', 'LOCS160218MDFPSF03', 'B+', 'Soltera',
 'Estudiante', 'Primaria', '5534567801', NULL, 'Calle Olivo 9', 'Ciudad de México', '07300',
 'Andrea Castro', 'Madre', '5534567801', 1);

SET @p1 = (SELECT id FROM pacientes WHERE expediente = 'P000001');
SET @p2 = (SELECT id FROM pacientes WHERE expediente = 'P000002');
SET @p3 = (SELECT id FROM pacientes WHERE expediente = 'P000003');

INSERT INTO paciente_antecedentes (paciente_id, heredofamiliares, personales_patologicos, personales_no_patologicos,
    quirurgicos, gineco_obstetricos, tabaquismo, alcoholismo, actividad_fisica, alimentacion, inmunizaciones)
VALUES
(@p1, 'Madre con diabetes tipo 2 e hipertensión. Padre finado por infarto agudo al miocardio a los 66 años.',
 'Diabetes mellitus tipo 2 (2015). Hipertensión arterial sistémica (2018).', 'Casa propia con todos los servicios.',
 'Colecistectomía laparoscópica (2010).', 'G3 P3 A0. Menopausia a los 50 años.', 'Negado', 'Ocasional',
 'Caminata 20 min, 3 veces por semana', 'Alta en carbohidratos', 'Esquema completo. Influenza 2025.'),
(@p2, 'Padre con hipertensión.', 'Asma intermitente en la infancia. Rinitis alérgica.', 'Vive en departamento.',
 'Negados', NULL, '5 cigarrillos/día por 8 años', 'Social, fines de semana', 'Gimnasio 2 veces por semana',
 'Comida fuera de casa frecuente', 'Esquema completo. COVID-19 refuerzo 2024.'),
(@p3, 'Abuela materna con asma.', 'Bronquiolitis a los 8 meses.', 'Asiste a primaria, convive con mascota (perro).',
 'Negados', NULL, 'No aplica', 'No aplica', 'Natación 1 vez por semana', 'Balanceada', 'Cartilla completa para la edad.');

INSERT INTO paciente_alergias (paciente_id, alergeno, tipo, reaccion, severidad) VALUES
(@p1, 'Penicilina', 'medicamento', 'Urticaria generalizada y edema palpebral', 'grave'),
(@p2, 'Ácaros del polvo', 'ambiental', 'Rinorrea y estornudos', 'leve'),
(@p3, 'Ibuprofeno', 'medicamento', 'Broncoespasmo leve', 'moderada');

INSERT INTO paciente_padecimientos (paciente_id, nombre, cie10, tipo, estado, fecha_diagnostico, notas) VALUES
(@p1, 'Diabetes mellitus tipo 2', 'E11', 'cronico', 'activo', '2015-06-01', 'Meta HbA1c < 7%.'),
(@p1, 'Hipertensión arterial sistémica', 'I10', 'cronico', 'controlado', '2018-03-15', 'Meta TA < 130/80.'),
(@p2, 'Rinitis alérgica', 'J30.4', 'cronico', 'controlado', '2010-01-01', NULL),
(@p2, 'Faringoamigdalitis aguda', 'J03.9', 'agudo', 'resuelto', CURDATE() - INTERVAL 40 DAY, NULL),
(@p3, 'Asma leve intermitente', 'J45.2', 'cronico', 'activo', '2022-05-10', 'Crisis en temporada de frío.');

INSERT INTO paciente_medicamentos (paciente_id, medicamento, dosis, frecuencia, via, fecha_inicio, indicado_por) VALUES
(@p1, 'Metformina 850 mg', '1 tableta', 'Cada 12 horas', 'Oral', '2015-06-01', 'Médico tratante'),
(@p1, 'Losartán 50 mg', '1 tableta', 'Cada 24 horas', 'Oral', '2018-03-15', 'Médico tratante'),
(@p2, 'Loratadina 10 mg', '1 tableta', 'Cada 24 horas (por razón necesaria)', 'Oral', '2020-01-01', 'Médico tratante'),
(@p3, 'Salbutamol inhalador 100 mcg', '2 disparos', 'Por razón necesaria', 'Inhalada', '2022-05-10', 'Pediatra');

-- Consultas de seguimiento (María: control de diabetes con 3 visitas)
INSERT INTO consultas_medicas (folio, paciente_id, medico_id, fecha, tipo, motivo, padecimiento_actual, peso_kg, talla_cm,
    imc, temperatura, ta_sistolica, ta_diastolica, frecuencia_cardiaca, frecuencia_respiratoria, saturacion_o2,
    glucosa_capilar, exploracion_fisica, diagnostico, plan_tratamiento, indicaciones, pronostico, proxima_cita, costo)
VALUES
('C000001', @p1, 1, NOW() - INTERVAL 90 DAY, 'control', 'Control de diabetes e hipertensión',
 'Refiere poliuria ocasional. Apego irregular a dieta.', 78.5, 158, 31.44, 36.5, 142, 88, 80, 18, 97, 186,
 'Consciente, orientada, hidratada. Ruidos cardiacos rítmicos. Pulsos pedios presentes. Sin edema.',
 'DM2 descontrolada. HAS en descontrol.', 'Ajuste de dosis, solicitud de HbA1c y perfil de lípidos.',
 'Dieta de 1500 kcal, caminata 30 min diarios.', 'Bueno para la vida, reservado para la función', CURDATE() - INTERVAL 60 DAY, 350),
('C000002', @p1, 1, NOW() - INTERVAL 60 DAY, 'control', 'Revisión de resultados de laboratorio',
 'Trae resultados. Mejor apego a dieta.', 76.0, 158, 30.44, 36.4, 134, 84, 76, 17, 98, 142,
 'Sin cambios relevantes respecto a la consulta previa.', 'DM2 en mejoría. Dislipidemia mixta.',
 'Agregar atorvastatina. Continuar metformina.', 'Continuar dieta y ejercicio.', 'Bueno', CURDATE() - INTERVAL 15 DAY, 350),
('C000003', @p1, 1, NOW() - INTERVAL 15 DAY, 'control', 'Control mensual',
 'Asintomática. Glucosas en casa 110-140 mg/dL.', 74.2, 158, 29.72, 36.6, 128, 80, 74, 16, 98, 118,
 'Adecuado estado general. Pies sin lesiones.', 'DM2 controlada. HAS controlada.',
 'Continuar tratamiento actual.', 'Revisión de pies diaria. Control en 1 mes.', 'Bueno', CURDATE() + INTERVAL 15 DAY, 350),
('C000004', @p2, 1, NOW() - INTERVAL 40 DAY, 'primera_vez', 'Dolor de garganta y fiebre de 2 días',
 'Odinofagia intensa, fiebre de 38.5 °C, malestar general.', 82.0, 176, 26.47, 38.4, 118, 76, 96, 20, 97, NULL,
 'Hiperemia faríngea con exudado amigdalino bilateral. Adenopatías cervicales dolorosas.',
 'Faringoamigdalitis aguda bacteriana.', 'Antibiótico por 10 días, analgésico.', 'Reposo, líquidos abundantes.',
 'Bueno', NULL, 350),
('C000005', @p3, 1, NOW() - INTERVAL 7 DAY, 'urgencia', 'Tos y silbido en el pecho',
 'Tos seca nocturna de 3 días y sibilancias tras exposición al frío.', 28.0, 128, 17.09, 36.9, 100, 62, 104, 26, 95, NULL,
 'Sibilancias espiratorias bilaterales, sin tiraje.', 'Crisis asmática leve.',
 'Salbutamol inhalado, valoración en 7 días.', 'Evitar frío y polvo. Uso de cámara espaciadora.', 'Bueno', CURDATE() + INTERVAL 1 DAY, 400);

SET @c1 = (SELECT id FROM consultas_medicas WHERE folio = 'C000001');
SET @c2 = (SELECT id FROM consultas_medicas WHERE folio = 'C000002');
SET @c3 = (SELECT id FROM consultas_medicas WHERE folio = 'C000003');
SET @c4 = (SELECT id FROM consultas_medicas WHERE folio = 'C000004');
SET @c5 = (SELECT id FROM consultas_medicas WHERE folio = 'C000005');

INSERT INTO consulta_diagnosticos (consulta_id, descripcion, cie10, tipo) VALUES
(@c1, 'Diabetes mellitus tipo 2 sin complicaciones', 'E11.9', 'principal'),
(@c1, 'Hipertensión esencial (primaria)', 'I10', 'secundario'),
(@c2, 'Diabetes mellitus tipo 2 sin complicaciones', 'E11.9', 'principal'),
(@c2, 'Hiperlipidemia mixta', 'E78.2', 'secundario'),
(@c3, 'Diabetes mellitus tipo 2 sin complicaciones', 'E11.9', 'principal'),
(@c4, 'Amigdalitis aguda, no especificada', 'J03.9', 'principal'),
(@c5, 'Asma predominantemente alérgica', 'J45.0', 'principal');

INSERT INTO recetas (folio, paciente_id, consulta_id, medico_id, fecha, diagnostico, indicaciones_generales, proxima_cita) VALUES
('R000001', @p1, @c2, 1, NOW() - INTERVAL 60 DAY, 'DM2 / Dislipidemia mixta', 'Dieta baja en grasas y azúcares.', CURDATE() - INTERVAL 15 DAY),
('R000002', @p2, @c4, 1, NOW() - INTERVAL 40 DAY, 'Faringoamigdalitis aguda', 'Completar el antibiótico aunque mejoren los síntomas.', NULL),
('R000003', @p3, @c5, 1, NOW() - INTERVAL 7 DAY, 'Crisis asmática leve', 'Acudir a urgencias si hay dificultad para respirar.', CURDATE() + INTERVAL 1 DAY);

SET @r1 = (SELECT id FROM recetas WHERE folio = 'R000001');
SET @r2 = (SELECT id FROM recetas WHERE folio = 'R000002');
SET @r3 = (SELECT id FROM recetas WHERE folio = 'R000003');

INSERT INTO receta_medicamentos (receta_id, medicamento, presentacion, dosis, via, frecuencia, duracion, cantidad, indicaciones) VALUES
(@r1, 'Metformina 850 mg', 'Caja con 30 tabletas', '1 tableta', 'Oral', 'Cada 12 horas', '30 días', '2 cajas', 'Tomar con alimentos'),
(@r1, 'Atorvastatina 20 mg', 'Caja con 30 tabletas', '1 tableta', 'Oral', 'Cada 24 horas por la noche', '30 días', '1 caja', NULL),
(@r2, 'Claritromicina 500 mg', 'Caja con 14 tabletas', '1 tableta', 'Oral', 'Cada 12 horas', '10 días', '2 cajas', 'Alérgico a penicilina: no usar amoxicilina'),
(@r2, 'Paracetamol 500 mg', 'Caja con 20 tabletas', '1 tableta', 'Oral', 'Cada 8 horas', '5 días', '1 caja', 'Si hay fiebre o dolor'),
(@r3, 'Salbutamol 100 mcg', 'Inhalador 200 dosis', '2 disparos', 'Inhalada', 'Cada 6 horas', '7 días', '1 pieza', 'Usar con cámara espaciadora');

INSERT INTO estudios (paciente_id, consulta_id, tipo, nombre, fecha_solicitud, fecha_resultado, estado, laboratorio, resultado, interpretacion) VALUES
(@p1, @c1, 'laboratorio', 'Hemoglobina glucosilada (HbA1c)', CURDATE() - INTERVAL 90 DAY, CURDATE() - INTERVAL 75 DAY, 'resultado',
 'Laboratorio Central', 'HbA1c 8.4 %', 'Descontrol glucémico'),
(@p1, @c1, 'laboratorio', 'Perfil de lípidos', CURDATE() - INTERVAL 90 DAY, CURDATE() - INTERVAL 75 DAY, 'resultado',
 'Laboratorio Central', 'CT 238 mg/dL, TG 265 mg/dL, HDL 38 mg/dL, LDL 147 mg/dL', 'Dislipidemia mixta'),
(@p1, @c3, 'laboratorio', 'Hemoglobina glucosilada (HbA1c)', CURDATE() - INTERVAL 15 DAY, NULL, 'solicitado', NULL, NULL, NULL),
(@p1, @c3, 'gabinete', 'Electrocardiograma de 12 derivaciones', CURDATE() - INTERVAL 15 DAY, NULL, 'solicitado', NULL, NULL, NULL),
(@p3, @c5, 'imagen', 'Radiografía de tórax PA', CURDATE() - INTERVAL 7 DAY, CURDATE() - INTERVAL 6 DAY, 'resultado',
 'Imagenología del Valle', 'Hiperinsuflación leve, sin consolidaciones.', 'Compatible con crisis asmática');

INSERT INTO citas (paciente_id, medico_id, fecha_hora, motivo, estado) VALUES
(@p3, 1, TIMESTAMP(CURDATE() + INTERVAL 1 DAY, '10:00:00'), 'Revaloración de crisis asmática', 'confirmada'),
(@p1, 1, TIMESTAMP(CURDATE() + INTERVAL 15 DAY, '09:30:00'), 'Control mensual de diabetes', 'programada'),
(@p2, 1, TIMESTAMP(CURDATE(), '17:00:00'), 'Valoración de rinitis', 'programada');
