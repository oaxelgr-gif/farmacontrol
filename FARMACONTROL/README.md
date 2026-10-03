# FarmaControl 2.0

Sistema de punto de venta, inventario, caja y reportes para **MEDICALIFE**.
Versión reestructurada: backend modular (un blueprint por apartado) e interfaz
nueva estilo *Liquid Glass* con modo claro/oscuro.

## Ejecutar con Docker (recomendado)

Requiere **Docker Desktop**. No necesitas instalar MySQL ni Python.

```bash
cd FARMACONTROL
cp .env.example .env          # cambia las claves
docker compose up -d --build  # o: make up
```

| Servicio | Imagen | URL |
|---|---|---|
| Sistema (Flask) | `farmacontrol-web` | http://localhost:5010 |
| API (FastAPI) | `farmacontrol-api` | http://localhost:8000/docs |
| MySQL 8 | `farmacontrol-db` | `localhost:3307` (usuario `farmacontrol`) |

- La primera vez, MySQL crea la base `medicalife` con los datos de `docker/db/init/` (tarda ~30 s).
- Los datos viven en el volumen `farmacontrol_db_data`; sobreviven a `docker compose down`.
- `make logs` ver registros · `make backup` respaldo SQL · `make reset-db` borra y recrea la base.
- Para usar tus datos actuales: `mysqldump -u root -p medicalife > docker/db/init/01_esquema_y_datos.sql`
  **antes** del primer `docker compose up` (o tras `make reset-db`).

### Cómo se comunican

```
Navegador ──► web (Flask :5010) ──► api (FastAPI :8000) ──► db (MySQL :3306)
                    └──────────────── reportes/inventario ───────┘
```

- El punto de venta (búsqueda, catálogos, clientes, cobro) pasa por la **API**.
  Flask se autentica con `X-Internal-Token` + `X-User-Id`; si la API no responde,
  la venta se procesa con la lógica local para no detener la caja.
- Clientes externos (apps, integraciones) usan JWT: `POST /v1/auth/token` y luego
  `Authorization: Bearer <token>`. Todo documentado en `/docs`.

### Endpoints principales de la API

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Estado de API y BD |
| POST | `/v1/auth/token` | Login (JWT) |
| GET | `/v1/productos/buscar?q=` | Código exacto o por nombre |
| GET/POST/PATCH/DELETE | `/v1/productos` | Inventario (admin para escribir) |
| GET | `/v1/catalogo/{productos,procedimientos,consultas}` | Artículos vendibles |
| GET/POST | `/v1/clientes` | Clientes |
| POST | `/v1/ventas` | Cobrar (transacción, precios del servidor) |
| GET | `/v1/ventas`, `/v1/ventas/{id}` | Historial y detalle |
| GET/POST | `/v1/caja`, `/v1/caja/abrir`, `/v1/caja/cerrar` | Corte de caja |
| GET | `/v1/reportes/resumen-dia` | KPIs (admin) |

## Ejecutar sin Docker

```bash
pip install -r requirements.txt
cp .env.example .env        # opcional: ajusta BD y clave secreta
python app.py               # http://localhost:5010
```

Necesitas MySQL encendido en tu equipo. Sin `.env` se usan los valores de la versión anterior
(BD `medicalife`, usuario `root`, puerto 5010). Si ves *Can't connect to MySQL server*, MySQL está apagado.

## Estructura

```
docker-compose.yml          → orquesta las 3 imágenes (db, api, web)
docker/db/                  → imagen MySQL: configuración + scripts de inicialización
docker/web/                 → imagen Flask: Dockerfile + Gunicorn
api/                        → imagen FastAPI: app/ (routers, services, schemas) + Dockerfile
app.py                      → punto de entrada (python app.py)
config.py                   → configuración (lee .env)
farmacontrol/
├── __init__.py             → create_app(): registra blueprints, errores, contexto
├── db.py                   → conexión por petición + fetch_all/fetch_one/execute/transaction
├── models.py               → Usuario y roles (1 Admin, 2 Farmacéutico)
├── navigation.py           → menú lateral por rol (editar aquí para cambiar el menú)
├── blueprints/
│   ├── auth/               → /login, /logout, /
│   ├── dashboard/          → /inicio (admin), /inicio_farmacia
│   ├── inventario/         → /inventario, /producto/...
│   ├── usuarios/           → /usuarios, /usuario/...
│   ├── caja/               → /corte_caja, /abrir_caja, /cerrar_caja
│   ├── cortes/             → historial, detalle, impresión, auditoría y CSV de cortes
│   ├── ventas/             → punto de venta, tickets, detalle y reimpresión
│   ├── api/                → /api/... (búsqueda, clientes, cobro)
│   ├── reportes/           → los 8 reportes + panel
│   ├── servicios/          → servicios y consultas
│   ├── clinica/            → /clinica: pacientes, expediente, consultas, recetas, estudios, agenda
│   └── sistema/            → /test_db
├── services/               → lógica de negocio (ventas, cortes, caducidad, catálogos)
└── utils/                  → decoradores, contraseñas, fechas y filtros de plantilla
templates/                  → una carpeta por apartado + layouts/ y partials/
static/css/glass.css        → sistema de diseño (tokens, vidrio, componentes)
static/js/app.js, pos.js    → utilidades de UI y punto de venta
```

Todas las URLs anteriores se conservan. En plantillas, los `url_for` ahora llevan
el prefijo del blueprint, p. ej. `url_for('inventario.listar_productos')`.

## Mejoras principales

**Backend**
- `app.py` de 2,750 líneas dividido en 11 blueprints + capa de servicios.
- Ventas en una sola transacción real (antes `autocommit` impedía el rollback).
- Precios, total y cambio se calculan en el servidor; ya no se confía en el navegador.
- Servicios/consultas se guardan con `producto_id = NULL` (antes se registraban como si fueran un producto con el mismo id, alterando reportes).
- Bloqueo de stock (`FOR UPDATE`) y validación de caducidad al cobrar.
- Contraseñas con hash; las cuentas existentes se migran solas al iniciar sesión.
- `/gestion/guardar` ahora exige rol de administrador; tabla en lista blanca.
- Métodos de pago clasificados por nombre (en la BD el id 3 es *Débito*, no *Transferencia*).
- Reporte financiero: corregido el ingreso que se multiplicaba por cada renglón de la venta.
- Corregidas plantillas que fallaban: reimpresión de cortes y de tickets, tickets de corte (`now()`, campos faltantes, `ventas_otros`).
- Folios con milisegundos para evitar duplicados; páginas de error 404/500; cabeceras de seguridad.

**Interfaz**
- Diseño *Liquid Glass*: superficies translúcidas con desenfoque, reflejos y fondo animado.
- Modo oscuro (botón de luna) que se recuerda por navegador.
- Barra lateral única por rol; en celular se vuelve barra inferior.
- Punto de venta: búsqueda con filtro en vivo, cantidades editables, botones de billetes rápidos y cálculo de cambio, métodos de pago tomados de la BD, aviso de antibióticos.
- Panel con gráfica semanal, cobros por método y más vendidos; mensajes como notificaciones flotantes; confirmaciones con ventana propia.

## Módulo clínico (Consultorio) — `/clinica`

Solo para administrador (médico). Menú lateral → **Clínica**.

- **Pacientes**: alta/edición con expediente `P000001`, contacto, tipo de sangre, aseguradora, contacto de emergencia.
- **Expediente** por paciente: línea de tiempo, consultas y número de visitas, padecimientos (CIE-10, activos/resueltos),
  alergias (se alertan en consulta y receta), antecedentes, tratamiento actual, estudios con resultados y archivos, recetas, citas, signos vitales.
- **Consulta** (nota médica `C000001`): motivo, signos vitales con IMC/T.A. automáticos, exploración, diagnósticos CIE-10
  (opción de agregarlos al expediente), plan, receta (medicamentos ligados al inventario), estudios y próxima cita — todo en una sola transacción.
- **Recetas** `R000001` imprimibles en **media carta** (o carta con original + copia). Machote: `templates/clinica/receta_imprimir.html`;
  datos del médico (cédula, especialidad, consultorio) en **Clínica → Perfil médico**.
- **Estudios** (laboratorio, imagen, gabinete…) pendientes / con resultado; **Agenda** de citas.

### Caja, farmacia, PDF y reportes

- **Cobrar consulta**: en la nota médica → *Cobrar en caja*, o en la consulta nueva → *Guardar y cobrar en caja*.
  El punto de venta abre con los honorarios (precio tomado de la consulta) y los medicamentos de la receta que están en inventario.
  La venta queda a nombre del paciente (se crea/enlaza su cliente) y la consulta se marca **Pagada**; no se puede cobrar dos veces.
- **Surtir receta**: en el POS botón **Receta (F6)** con el folio (`R000123` o `123`), o desde *Recetas → Surtir*.
  Funciona también para el farmacéutico. La receta queda **Surtida** con la fecha y el folio de la venta.
- **Expediente PDF**: en el expediente → *Expediente PDF* → *Imprimir / Guardar PDF* (hoja carta).
- **Reportes** (`/clinica/reportes`): consultas, pacientes nuevos, honorarios cobrados y por cobrar, diagnósticos
  y medicamentos más frecuentes, pacientes frecuentes, edad/sexo, agenda y exportación CSV.
- **API** (`/docs` → *Clínica*): pacientes, ficha, consultas, recetas (por id o folio), estudios y citas (solo admin).
  `POST /v1/ventas` acepta artículos `tipo: "honorario"` y `receta_id` / `paciente_id`.

### Instalar en una base existente

```bash
mysql -u root -p medicalife < BD/02_modulo_clinico.sql          # tablas del módulo
mysql -u root -p medicalife < BD/03_clinica_datos_demo.sql      # opcional: 3 pacientes de ejemplo
mysql -u root -p medicalife < BD/04_clinica_caja.sql            # enlace consulta/receta ↔ venta (si ya tenías el módulo)
```

Con Docker, los scripts nuevos solo corren en un volumen nuevo. Si ya tenías la BD levantada:
`docker compose exec -T db mysql -uroot -p"$MYSQL_ROOT_PASSWORD" medicalife < BD/02_modulo_clinico.sql`
(o `make reset-db`, que borra los datos). Los archivos adjuntos se guardan en `instance/uploads` (volumen `farmacontrol_uploads`).

## Respaldo

La versión anterior quedó en `_respaldo_v1/` (app.py, models.py, plantillas y CSS originales).
