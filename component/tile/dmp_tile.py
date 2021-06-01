from sepal_ui import sepalwidgets as sw 
import ipyvuetify as v
from sepal_ui.scripts import utils as su

from component import parameter as pm
from component.scripts import * 

class DmpTile(sw.Tile):
    
    def __init__(self, model):
        
        # gather the io as class attribute 
        self.model = model
        
        # create the widgets 
        self.aoi = sw.Markdown(pm.aoi)
        self.file_selector = sw.FileInput(label='Search File')
        
        self.date = sw.Markdown(pm.date)
        self.date_picker = sw.DatePicker(label='Disaster event date')
        
        self.scihub = sw.Markdown(pm.scihub)
        self.username = v.TextField(label = "Copernicus Scihub Username",v_model = None)
        self.password = sw.PasswordField(label = "Copernicus Scihub Password")
        
        self.process = sw.Markdown(pm.process)
        
        # bind them with the output 
        self.model \
            .bind(self.file_selector, 'file') \
            .bind(self.date_picker, 'event') \
            .bind(self.username, 'username') \
            .bind(self.password, 'password')
        
        # construct the tile 
        super().__init__(
            id_ = "process_widget",
            title = "Set input parameters",
            inputs = [
                self.aoi, self.file_selector, 
                self.date, self.date_picker, 
                self.scihub, self.username, self.password,
                self.process
            ],
            output = sw.Alert(),
            btn = sw.Btn("Process")
        )
        
        # link the click to an event 
        self.btn.on_event('click', self._on_click)
    
    @su.loading_button(debug=False)
    def _on_click(self, widget, data, event):
        
        ## check input file
        if not self.output.check_input(self.model.file, 'no aoi file selected'): return 
        if not self.output.check_input(self.model.event, 'no event date selected'): return 
        if not self.output.check_input(self.model.username, 'no username'): return 
        if not self.output.check_input(self.model.password, 'no password'): return 
        
        check_computer_size(self.output)
        create_dmp(self.model, self.output)

        self.output.add_live_msg('Computation complete', 'success')
         
        return
        