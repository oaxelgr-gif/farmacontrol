-- =================================================================
-- FarmaControl · MÓDULO CLÍNICO (expediente de pacientes)
-- Pacientes, antecedentes, alergias, padecimientos, medicamentos,
-- consultas (signos vitales, diagnósticos, notas), recetas, estudios,
-- citas y perfil del médico para las recetas.
--
-- Docker: se ejecuta solo al crear la base.
-- Instalación existente:  mysql -u root -p medicalife < BD/02_modulo_clinico.sql
-- Es seguro ejecutarlo más de una vez (IF NOT EXISTS).
-- =================================================================
USE medicalife;
SET NAMES utf8mb4;

-- -----------------------------------------------------------------
-- Perfil del médico (encabezado de recetas). Uno por usuario.
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS perfil_medico (
    usuario_id          INT PRIMARY KEY,
    nombre_mostrar      VARCHAR(150) NOT NULL,
    especialidad        VARCHAR(120),
    cedula_profesional  VARCHAR(30),
    cedula_especialidad VARCHAR(30),
    institucion         VARCHAR(150),
    telefono            VARCHAR(30),
    email               VARCHAR(120),
    direccion           VARCHAR(255),
    horario             VARCHAR(150),
    leyenda_receta      VARCHAR(255),
    updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------------
-- Pacientes
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pacientes (
    id                      INT PRIMARY KEY AUTO_INCREMENT,
    expediente              VARCHAR(20) UNIQUE,
    nombre                  VARCHAR(80)  NOT NULL,
    apellido_paterno        VARCHAR(80)  NOT NULL,
    apellido_materno        VARCHAR(80),
    fecha_nacimiento        DATE,
    sexo                    CHAR(1),                 -- F, M, O
    curp                    VARCHAR(18),
    tipo_sangre             VARCHAR(5),              -- O+, A-, ...
    estado_civil            VARCHAR(20),
    ocupacion               VARCHAR(100),
    escolaridad             VARCHAR(60),
    telefono                VARCHAR(20),
    telefono_alt            VARCHAR(20),
    email                   VARCHAR(120),
    direccion               VARCHAR(255),
    ciudad                  VARCHAR(80),
    codigo_postal           VARCHAR(10),
    contacto_nombre         VARCHAR(120),
    contacto_parentesco     VARCHAR(40),
    contacto_telefono       VARCHAR(20),
    aseguradora             VARCHAR(80),
    poliza                  VARCHAR(40),
    cliente_id              INT NULL,                -- enlace opcional con clientes del POS
    notas                   TEXT,
    status                  BOOLEAN DEFAULT TRUE,
    created_by              INT NULL,
    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at              DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (cliente_id) REFERENCES clientes(id),
    FOREIGN KEY (created_by) REFERENCES usuarios(id),
    INDEX idx_pac_nombre (apellido_paterno, nombre),
    INDEX idx_pac_curp (curp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Antecedentes (historia clínica) — 1 a 1 con paciente
CREATE TABLE IF NOT EXISTS paciente_antecedentes (
    paciente_id             INT PRIMARY KEY,
    heredofamiliares        TEXT,
    personales_patologicos  TEXT,
    personales_no_patologicos TEXT,
    quirurgicos             TEXT,
    traumaticos             TEXT,
    transfusionales         TEXT,
    gineco_obstetricos      TEXT,
    tabaquismo              VARCHAR(120),
    alcoholismo             VARCHAR(120),
    toxicomanias            VARCHAR(120),
    actividad_fisica        VARCHAR(120),
    alimentacion            VARCHAR(255),
    inmunizaciones          TEXT,
    updated_at              DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (paciente_id) REFERENCES pacientes(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS paciente_alergias (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    paciente_id     INT NOT NULL,
    alergeno        VARCHAR(120) NOT NULL,
    tipo            VARCHAR(20) DEFAULT 'medicamento',   -- medicamento, alimento, ambiental, otro
    reaccion        VARCHAR(255),
    severidad       VARCHAR(10) DEFAULT 'moderada',      -- leve, moderada, grave
    status          BOOLEAN DEFAULT TRUE,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paciente_id) REFERENCES pacientes(id),
    INDEX idx_alergia_pac (paciente_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Padecimientos / problemas de salud del paciente (lista de problemas)
CREATE TABLE IF NOT EXISTS paciente_padecimientos (
    id                  INT PRIMARY KEY AUTO_INCREMENT,
    paciente_id         INT NOT NULL,
    nombre              VARCHAR(200) NOT NULL,
    cie10               VARCHAR(10),
    tipo                VARCHAR(15) DEFAULT 'cronico',  -- cronico, agudo
    estado              VARCHAR(15) DEFAULT 'activo',   -- activo, controlado, resuelto
    fecha_diagnostico   DATE,
    notas               TEXT,
    status              BOOLEAN DEFAULT TRUE,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (paciente_id) REFERENCES pacientes(id),
    INDEX idx_padec_pac (paciente_id),
    INDEX idx_padec_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Medicamentos de uso actual / crónico
CREATE TABLE IF NOT EXISTS paciente_medicamentos (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    paciente_id     INT NOT NULL,
    medicamento     VARCHAR(150) NOT NULL,
    dosis           VARCHAR(80),
    frecuencia      VARCHAR(80),
    via             VARCHAR(40),
    fecha_inicio    DATE,
    fecha_fin       DATE,
    indicado_por    VARCHAR(120),
    activo          BOOLEAN DEFAULT TRUE,
    status          BOOLEAN DEFAULT TRUE,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paciente_id) REFERENCES pacientes(id),
    INDEX idx_med_pac (paciente_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------------
-- Consultas médicas
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS consultas_medicas (
    id                      INT PRIMARY KEY AUTO_INCREMENT,
    folio                   VARCHAR(20) UNIQUE,
    paciente_id             INT NOT NULL,
    medico_id               INT NOT NULL,
    fecha                   DATETIME DEFAULT CURRENT_TIMESTAMP,
    tipo                    VARCHAR(20) DEFAULT 'subsecuente', -- primera_vez, subsecuente, urgencia, control, seguimiento
    motivo                  VARCHAR(255) NOT NULL,
    padecimiento_actual     TEXT,
    interrogatorio          TEXT,
    -- signos vitales y somatometría
    peso_kg                 DECIMAL(5,2),
    talla_cm                DECIMAL(5,1),
    imc                     DECIMAL(5,2),
    temperatura             DECIMAL(4,1),
    ta_sistolica            SMALLINT,
    ta_diastolica           SMALLINT,
    frecuencia_cardiaca     SMALLINT,
    frecuencia_respiratoria SMALLINT,
    saturacion_o2           SMALLINT,
    glucosa_capilar         SMALLINT,
    perimetro_abdominal     DECIMAL(5,1),
    -- valoración
    exploracion_fisica      TEXT,
    resultados_previos      TEXT,
    diagnostico             TEXT,
    plan_tratamiento        TEXT,
    indicaciones            TEXT,
    pronostico              VARCHAR(120),
    proxima_cita            DATE,
    costo                   DECIMAL(10,2) DEFAULT 0,
    venta_id                INT NULL,                        -- cobro en caja (NULL = pendiente)
    estado                  VARCHAR(15) DEFAULT 'cerrada',   -- abierta, cerrada, cancelada
    status                  BOOLEAN DEFAULT TRUE,
    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paciente_id) REFERENCES pacientes(id),
    FOREIGN KEY (medico_id) REFERENCES usuarios(id),
    INDEX idx_cons_pac_fecha (paciente_id, fecha),
    INDEX idx_cons_fecha (fecha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS consulta_diagnosticos (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    consulta_id     INT NOT NULL,
    descripcion     VARCHAR(200) NOT NULL,
    cie10           VARCHAR(10),
    tipo            VARCHAR(15) DEFAULT 'principal',  -- principal, secundario, presuntivo
    padecimiento_id INT NULL,
    FOREIGN KEY (consulta_id) REFERENCES consultas_medicas(id),
    FOREIGN KEY (padecimiento_id) REFERENCES paciente_padecimientos(id),
    INDEX idx_diag_cons (consulta_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Notas de evolución / adendas (el expediente no se edita, se complementa)
CREATE TABLE IF NOT EXISTS consulta_notas (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    consulta_id     INT NOT NULL,
    usuario_id      INT NOT NULL,
    nota            TEXT NOT NULL,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (consulta_id) REFERENCES consultas_medicas(id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------------
-- Recetas
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS recetas (
    id                      INT PRIMARY KEY AUTO_INCREMENT,
    folio                   VARCHAR(20) UNIQUE,
    paciente_id             INT NOT NULL,
    consulta_id             INT NULL,
    medico_id               INT NOT NULL,
    fecha                   DATETIME DEFAULT CURRENT_TIMESTAMP,
    diagnostico             VARCHAR(255),
    indicaciones_generales  TEXT,
    proxima_cita            DATE,
    venta_id                INT NULL,                 -- surtida en farmacia
    surtida_at              DATETIME NULL,
    status                  BOOLEAN DEFAULT TRUE,
    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paciente_id) REFERENCES pacientes(id),
    FOREIGN KEY (consulta_id) REFERENCES consultas_medicas(id),
    FOREIGN KEY (medico_id) REFERENCES usuarios(id),
    INDEX idx_rec_pac (paciente_id, fecha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS receta_medicamentos (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    receta_id       INT NOT NULL,
    producto_id     INT NULL,                 -- enlace opcional al inventario
    medicamento     VARCHAR(150) NOT NULL,
    presentacion    VARCHAR(100),
    dosis           VARCHAR(80),
    via             VARCHAR(40),
    frecuencia      VARCHAR(80),
    duracion        VARCHAR(60),
    cantidad        VARCHAR(40),
    indicaciones    VARCHAR(255),
    FOREIGN KEY (receta_id) REFERENCES recetas(id),
    FOREIGN KEY (producto_id) REFERENCES productos(id),
    INDEX idx_recmed_receta (receta_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------------
-- Estudios (laboratorio, imagen, gabinete)
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS estudios (
    id                  INT PRIMARY KEY AUTO_INCREMENT,
    paciente_id         INT NOT NULL,
    consulta_id         INT NULL,
    tipo                VARCHAR(20) DEFAULT 'laboratorio',  -- laboratorio, imagen, gabinete, patologia, otro
    nombre              VARCHAR(150) NOT NULL,
    fecha_solicitud     DATE,
    fecha_resultado     DATE,
    estado              VARCHAR(15) DEFAULT 'solicitado',   -- solicitado, en_proceso, resultado, cancelado
    laboratorio         VARCHAR(120),
    resultado           TEXT,
    interpretacion      TEXT,
    archivo             VARCHAR(255),
    archivo_nombre      VARCHAR(255),
    status              BOOLEAN DEFAULT TRUE,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (paciente_id) REFERENCES pacientes(id),
    FOREIGN KEY (consulta_id) REFERENCES consultas_medicas(id),
    INDEX idx_est_pac (paciente_id),
    INDEX idx_est_estado (estado)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------------
-- Citas / agenda
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS citas (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    paciente_id     INT NOT NULL,
    medico_id       INT NULL,
    fecha_hora      DATETIME NOT NULL,
    duracion_min    SMALLINT DEFAULT 30,
    motivo          VARCHAR(200),
    estado          VARCHAR(15) DEFAULT 'programada',  -- programada, confirmada, atendida, cancelada, no_asistio
    consulta_id     INT NULL,
    notas           VARCHAR(255),
    status          BOOLEAN DEFAULT TRUE,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paciente_id) REFERENCES pacientes(id),
    FOREIGN KEY (medico_id) REFERENCES usuarios(id),
    FOREIGN KEY (consulta_id) REFERENCES consultas_medicas(id),
    INDEX idx_cita_fecha (fecha_hora)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
