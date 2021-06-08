import ipyvuetify as v 
from sepal_ui import sepalwidgets as sw
from ipywidgets import jslink

class PasswordField(v.Layout, sw.SepalWidget):
    
    EYE_ICONS = ['mdi-eye', 'mdi-eye-off']
    TYPES = ['password', 'text']
    
    def __init__(self, label = "password", **kwargs):
    
        # set visibility status 
        self.password_viz = False
        
        # create the eye icon 
        self.eye = v.Icon(class_ = 'ml-1', children=[self.EYE_ICONS[0]])
        
        # create the widget 
        self.text_field = v.TextField(
            v_model = None, 
            type = self.TYPES[0], 
            label=label
        )
    
        # create the textfield 
        super().__init__(
            Row = True,
            children = [self.text_field, self.eye],
            v_model = None,
            **kwargs
        )
    
        # link the icon to the display behaviour 
        self.eye.on_event('click', self._toggle_viz)
        
    def _toggle_viz(self, widget, event, data):
        
        viz = not self.password_viz
        
        # change password viz 
        self.password_viz = viz 
        self.eye.children = [self.EYE_ICONS[viz]]
        self.text_field.type = self.TYPES[viz]
        
        return
    
    