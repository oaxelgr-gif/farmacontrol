"""
Punto de entrada de FarmaControl.

Toda la lógica vive ahora en el paquete `farmacontrol/` (un blueprint por
apartado). Este archivo solo crea la aplicación para que sigas ejecutando:

    python app.py
"""
from farmacontrol import create_app

app = create_app()

if __name__ == "__main__":
    app.run(
        host=app.config["HOST"],
        port=app.config["PORT"],
        debug=app.config["DEBUG"],
    )
