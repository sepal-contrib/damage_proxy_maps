from sepal_ui import sepalwidgets as sw
import ipyvuetify as v
from sepal_ui.scripts import utils as su

from component import parameter as pm
from component.scripts import *


class DmpTile(sw.Tile):
    def __init__(self, model, aoi_model):

        # gather the io as class attribute
        self.aoi_model = aoi_model
        self.model = model

        # create widgets
        self.date_picker_start = sw.DatePicker(label="Start of event")
        self.date_picker_end = sw.DatePicker(label="End of event")
        self.username = v.TextField(label="Copernicus Scihub Username", v_model=None)
        self.password = sw.PasswordField(label="Copernicus Scihub Password")

        # bind them with the output
        self.model.bind(self.date_picker_start, "event_start").bind(self.date_picker_end, "event_end").bind(self.username, "username").bind(
            self.password, "password"
        )

        # construct the tile
        super().__init__(
            id_="process_widget",
            title="Set input parameters",
            inputs=[self.date_picker_start, self.date_picker_end, self.username, self.password],
            alert=sw.Alert(),
            btn=sw.Btn("Process"),
        )

        # link the click to an event
        self.btn.on_event("click", self._on_click)

    @su.loading_button(debug=False)
    def _on_click(self, widget, data, event):

        ## check input file
        if not self.alert.check_input(self.model.event_start, "no start date selected"):
            return
        if not self.alert.check_input(self.model.event_end, "no end date selected"):
            return
        if not self.alert.check_input(self.model.username, "no username"):
            return
        if not self.alert.check_input(self.model.password, "no password"):
            return

        # check_computer_size()
        create_dmp(self.aoi_model, self.model, self.alert)

        self.alert.add_live_msg("Computation complete", "success")

        return
