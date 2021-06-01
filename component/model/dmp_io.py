from sepal_ui import model
from traitlets import Any

class DmpModel(model.Model):
        
    # inputs 
    file = Any(None).tag(sync=True)
    event = Any(None).tag(sync=True)
    username = Any(None).tag(sync=True)
    password = Any(None).tag(sync=True)