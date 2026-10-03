# ---------- Imagen: farmacontrol-db (MySQL 8 con esquema y datos iniciales) ----------
FROM mysql:8.0

ENV TZ=America/Mexico_City

# Configuración del servidor (utf8mb4, zona horaria)
COPY conf/farmacontrol.cnf /etc/mysql/conf.d/farmacontrol.cnf

# Scripts que se ejecutan al crear la base por primera vez
COPY init/ /docker-entrypoint-initdb.d/

EXPOSE 3306
