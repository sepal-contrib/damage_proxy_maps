from sepal_ui import sepalwidgets as sw 
import ipyvuetify as v

from component import widget as cw
from component import parameter as pm
from component.scripts import * 

class DmpTile(sw.Tile):
    
    def __init__(self, dmp_io):
        
        # gather the io as class attribute 
        self.io = dmp_io
        
        # create the widgets 
        self.aoi = sw.Markdown(pm.aoi)
        self.file_selector = sw.FileInput(label='Search File')
        
        self.date = sw.Markdown(pm.date)
        self.date_picker = sw.DatePicker(label='Disaster event date')
        
        self.scihub = sw.Markdown(pm.scihub)
        self.username = v.TextField(
            label = "Copernicus Scihub Username",
            v_model = None
        )
        self.password = cw.PasswordField(label = "Copernicus Scihub Password")
        
        self.process = sw.Markdown(pm.process)
        
        # bind them with the output 
        self.output = sw.Alert() \
            .bind(self.file_selector, self.io, 'file') \
            .bind(self.date_picker, self.io, 'event') \
            .bind(self.username, self.io, 'username') \
            .bind(self.password.text_field, self.io, 'password', secret=True)
        
        self.btn = sw.Btn("Process")
        
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
            output = self.output,
            btn = self.btn
        )
        
        # link the click to an event 
        self.btn.on_event('click', self._on_click)
        
    def _on_click(self, widget, data, event):
        
        widget.toggle_loading()
        
        ## check input file
        if not self.output.check_input(self.io.file, 'no aoi file selected'): return widget.toggle_loading()
        if not self.output.check_input(self.io.event, 'no event date selected'): return widget.toggle_loading()
        if not self.output.check_input(self.io.username, 'no username'): return widget.toggle_loading()
        if not self.output.check_input(self.io.password, 'no password'): return widget.toggle_loading()
        
        try:
            check_computer_size(self.output)
            create_dmp(self.io, self.output)
        
            self.output.add_live_msg('Computation complete', 'success')
        
        except Exception as e: 
            self.output.add_live_msg(str(e), 'error')
            
        widget.toggle_loading()
        
        return
        