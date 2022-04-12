from sepal_ui import model
from traitlets import Any


class DmpModel(model.Model):

    # inputs
    event_start = Any(None).tag(sync=True)
    event_end = Any(None).tag(sync=True)
    username = Any(None).tag(sync=True)
    password = Any(None).tag(sync=True)
