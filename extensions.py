from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from flask_talisman import Talisman # REINTRODUCIAMO TALISMAN

db = SQLAlchemy()
csrf = CSRFProtect()
talisman = Talisman() # REINTRODUCIAMO L'ISTANZA