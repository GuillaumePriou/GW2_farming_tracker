# -*- coding: utf-8 -*-:
"""
View layer of GW2 tool to evaluate gold earnings.

@author: Krashnark
"""
class Controller():
    def __init__(self, model, view):
        self.model = model
        self.view = view
        
        if self.model.apiKey.keyValue != '':
            self.view.refresh_api_key_entry_content(self.model.apiKey.keyValue)
            self.view.show_success('Clé validée. Définissez l\'inventaire de départ (référence)')
    
    def save_api_key(self, api_key_input):
        try:
            #self.view.show_action_in_progress('Vérification de la clé...')
            self.model.set_new_key(api_key_input)
            self.view.show_success('Clé validée. Définissez l\'inventaire de départ (référence)')
        except ValueError as error:
            # show an error message
            self.view.show_error(error)
    
    def set_reference_inventory(self):
        try:
            #self.view.show_action_in_progress('Récupération de l\'inventaire via l\'API...')
            self.model.set_reference_inventory()
            self.view.show_success('Inventaire de départ défini. Jouez puis calculez vos gains.')
        except ValueError as error:
            self.view.show_error(error)
    
    def compute_gains(self):
        try :
            print("Controller : begin compute gains & begin get new inventory")
            #self.view.show_action_in_progress('Récupération de l\'inventaire via l\'API et calcul des changements...')
            self.model.get_inventory_and_compare_it()
            print("Controller : end get new inventory. Show success.")
            #self.model.report.compute()
            self.view.show_success('Comparaison achevée.')
            print("Controller : begin display report")
            self.view.display_report(self.model.report)
            print("Controller : end display report & end compute gains")
        except ValueError as error:
            self.view.show_error(error)
