"""Extensiones de Flask compartidas por toda la aplicación."""
from flask_login import LoginManager

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Inicia sesión para continuar."
login_manager.login_message_category = "warning"
