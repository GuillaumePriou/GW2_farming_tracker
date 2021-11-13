# -*- coding: utf-8 -*-
"""
View layer of GW2 tool to evaluate gold earnings.

@author: Krashnark
"""
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

""" Gold widget to display properly any gold value
"""
class GoldWidget(ttk.Frame) :
    def __init__(self, parent, currency_value = 0):
        super().__init__(parent)
        
        self.gold = int(currency_value / 10000)
        self.silver = int(currency_value / 100) - self.gold * 100
        self.copper = currency_value - self.gold * 10000 - self.silver * 100
        
        
        # Gold number & logo
        self.goldLabelNumber = ttk.Label(self, text=self.gold)
        self.goldLabelNumber.pack(side="left")
        
        self.goldLogo = tk.PhotoImage(file ="Assets/Gold_coin_20px.png")
        self.goldLogoLabel = ttk.Label(self,image = self.goldLogo)
        self.goldLogoLabel.pack(side="left")
    
        # Silver number & logo
        self.silverLabelNumber = ttk.Label(self, text=self.silver)
        self.silverLabelNumber.pack(side="left")
        
        self.silverLogo = tk.PhotoImage(file ="Assets/Silver_coin_20px.png")
        self.silverLogoLabel = ttk.Label(self,image = self.silverLogo)
        self.silverLogoLabel.pack(side="left")
    
        # Copper number & logo
        self.copperLabelNumber = ttk.Label(self, text=self.copper)
        self.copperLabelNumber.pack(side="left")
        
        self.copperLogo = tk.PhotoImage(file ="Assets/Copper_coin_20px.png")
        self.copperLogoLabel = ttk.Label(self,image = self.copperLogo)
        self.copperLogoLabel.pack(side="left")
        
    """ Update the value displayed by the widget.
        Input : the new value to display
    """
    def setValue(self, new_value) :
        self.gold = int(new_value / 10000)
        self.silver = int(new_value / 100) - self.gold * 100
        self.copper = new_value - self.gold * 10000 - self.silver * 100
        
        self.goldLabelNumber.config(text = self.gold)
        self.silverLabelNumber.config(text = self.silver)
        self.copperLabelNumber.config(text = self.copper)
        

""" A dedicated frame to display the details of item gained during a play session.
    Information to be displayed in a table-like form :
        - Item icon
        - Item id (for debug)
        - Item name
        - Item count
        - Aquisition price
        - Liquid gold value
        
    Input : list of items (dict)
"""
class DetailsReportDisplay(ttk.Frame):
    def __init__ (self, parent, items_list = []):
        super().__init__(parent)
        
        # Legends for the details
        self.itemIdLegend1 = ttk.Label(self, text = "ID objet")
        self.itemIdLegend1.grid(row=0, column=1)
        
        self.itemIdLegend2 = ttk.Label(self, text = "Nom objet")
        self.itemIdLegend2.grid(row=0, column=2)
                               
        self.itemIdLegend3 = ttk.Label(self, text = "Nombre objets")
        self.itemIdLegend3.grid(row=0, column=3)
                               
        self.itemIdLegend4 = ttk.Label(self, text = "Or liquide")
        self.itemIdLegend4.grid(row=0, column=4)
                               
        self.itemIdLegend5 = ttk.Label(self, text = "Cout aquisition")
        self.itemIdLegend5.grid(row=0, column=5)
        
        self.iconLabelList = list()
                    
        if items_list == []:
            print("View : detail display report received an empty list of items.")
            self.noItemLabel = ttk.Label(self, text = "Aucun changement d'inventaire.")
            self.noItemLabel.grid(row=1, column=0)
        else:
            rowNb = 0
            print(f'item list to display : {items_list}')
            for item in items_list :
                rowNb += 1
                
                idem_id = item['id']
                print(f'Create a row of labels for item {idem_id}')
                
                # Display item icon (loaded from a file)
                try:
                    picture_path = "Download/" + str(item['id']) + ".png"
                    self.iconLabelList.append(self.build_image_label(self, picture_path))
                    self.iconLabelList[rowNb-1].grid(row=rowNb, column=0)
                except ValueError as error:
                    self.iconLabel = ttk.Label(self, text="Image non trouvée")
                    print(error)
                    self.iconLabel.grid(row=rowNb, column=0)
    
                
                # Display item id
                idLabel = ttk.Label(self, text=item['id'])
                idLabel.grid(row=rowNb, column=1)
                
                # Display item name
                nameLabel = ttk.Label(self, text=item['name'])
                nameLabel.grid(row=rowNb, column=2)
                
                # Display item count
                countLabel = ttk.Label(self, text=item['count'])
                countLabel.grid(row=rowNb, column=3)
                
                # Display item liquid gold value
                liquidGoldLabel = GoldWidget(self, item['liquid gold value'])
                liquidGoldLabel.grid(row=rowNb, column=4)
                
                # Display item aquisition price
                aquisitionPriceLabel = GoldWidget(self, item['aquisition price'])
                aquisitionPriceLabel.grid(row=rowNb, column=5)
    
    def build_image_label(self, parent, picture_path):
        print(f'try to open {picture_path}')
        image = Image.open(picture_path)
        photoImage = ImageTk.PhotoImage(image)
        iconLabel = ttk.Label(parent, image=photoImage)
        iconLabel.image = photoImage
        return iconLabel
        
        

""" A dedicated frame to display the item gained during a play session.
    Information to be displayed :
        At the top : 
        - total gold value earned (aquisition & liquid)
        - Time
        
        In a table-like form :
        - Item icon
        - Item id (for debug)
        - Item name
        - Item count
        - Aquisition price
        - Liquid gold value
"""
class FullReportDisplay(ttk.Frame):
    def __init__ (self, parent, report_to_display = None):
        super().__init__(parent)
        #self.farmTimeLabel = ttk.Label(text='Durée : à calculer')
        #self.farmTimeLabel.grid(row=0, column=0)
        
        # Total aquisition price display
        self.totalAcquisitionvalueLabel = ttk.Label(self, text='Prix à l\'achat')
        self.totalAcquisitionvalueLabel.grid(row=0, column=0)
        
        if report_to_display == None :
            self.totalAquisitionGoldwidget = GoldWidget(self, 0)
        else:
            self.totalAquisitionGoldwidget = GoldWidget(self, report_to_display.totalAquisitionValue)
        self.totalAquisitionGoldwidget.grid(row=0, column=1)
        
        
        # Total liquid gold price display
        self.totalLiquidGoldValueLabel = ttk.Label(self, text='Prix liquid gold')
        self.totalLiquidGoldValueLabel.grid(row=0, column=2)
        
        if report_to_display == None :
            self.totalLiquidGoldGoldwidget = GoldWidget(self, 0)
        else:
            self.totalLiquidGoldGoldwidget = GoldWidget(self, report_to_display.totalLiquidGoldValue)
        self.totalLiquidGoldGoldwidget.grid(row=0, column=3)
        
        if report_to_display == None :
            self.details = DetailsReportDisplay(self, [])
        else:
            self.details = DetailsReportDisplay(self, report_to_display.itemsDetail)
        self.details.grid(row=1, column=0, columnspan=3)
        
        #print(f'report_to_display.totalAquisitionValue = {report_to_display.totalAquisitionValue}')
        #print(f'report_to_display.totalLiquidGoldValue = {report_to_display.totalLiquidGoldValue}')
        #print(f'report_to_display.itemsDetail = {report_to_display.itemsDetail}')
    
    def update_detail_display(self, new_report):
        # re-init with new value
        self.details.destroy()
        self.details = DetailsReportDisplay(self, new_report.itemsDetail)
        self.details.grid(row=1, column=0, columnspan=3)
        
            
            
            
        
        

class View(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        
        # Define a big important message to help user to use the this application
        self.bigImportantMessageLabel = ttk.Label(self, 
                                                  text='Bienvenue. saissisez une clé API Guild Wars 2 valide.', 
                                                  font='bold')
        self.bigImportantMessageLabel.grid(row=0, column=0, columnspan=2)
        
        # Entry widget where the user paste his API key
        self.keyInput = ttk.Entry(self, width=80)
        self.keyInput.grid(row=2, column=0)
        
        self.okButton = ttk.Button(self, text="Utiliser cette clé !",
                             command=self.save_key)
        self.okButton.grid(row=2, column=2)
        
        # Buttons to get inventories and calculate differences
        
        self.startButton = ttk.Button(self, text="Commencer",
                             command=self.set_reference)
        self.startButton.grid(row=4, column=0)
        
        self.stopButton = ttk.Button(self, text="Calculer les gains",
                             command=self.compute_gains)
        self.stopButton.grid(row=4, column=1)
        
        self.fullReportDisplay = FullReportDisplay(self)
        self.fullReportDisplay.grid(row=5, column=0, columnspan=3)
        
        


    def set_controller(self, controller):
        self.controller = controller
        
    def refresh_api_key_entry_content(self, value_from_model):
        self.keyInput.insert(0, value_from_model)
    
    # Some functions to update message of big important message label
    def show_action_in_progress(self, msg): # Does 
        print("yellow !!")
        self.bigImportantMessageLabel.config(text= msg)
        self.bigImportantMessageLabel['foreground'] = 'yellow'
        
    def show_success(self, msg):
        self.bigImportantMessageLabel['text'] = msg
        self.bigImportantMessageLabel['foreground'] = 'green'
        
    def show_error(self, msg):
        self.bigImportantMessageLabel['text'] = msg
        self.bigImportantMessageLabel['foreground'] = 'red'

    # API key input management
    def save_key(self):
        print("Cliqué sur le bouton save api key")
        self.show_action_in_progress('Vérification de la clé...')
        if self.controller:
            self.controller.save_api_key(self.keyInput.get())
    
    # Reference  inventory fetch management
    def set_reference(self):
        self.controller.set_reference_inventory()
    
    # Compute gains management
    def compute_gains(self):
        print("View : begin compute gains")
        self.controller.compute_gains()
        print("View : end compute gains")
        #self.report = ReportDisplay(self.controller.compute_gains())
        #self.report.grid(row=5, column=0, columnspan=5)
    
    def display_report(self, report):
        print("View : begin report display")
        self.fullReportDisplay.update_detail_display(report)
        print("View : end report display")


# for testing debug only
import Model as m
        
# Main for debug
if __name__ == "__main__":
    root = tk.Tk()
    """
    w = GoldWidget(root)
    w.pack()
    w.setValue(45678)
    """
    """
    report = m.Report()
    report.totalLiquidGoldValue = 654321
    report.totalAquisitionValue = 123456
    
    item_1 = dict()
    item_1['name'] = "item 1"
    item_1['id'] = "1"
    item_1['count'] = "11"
    item_1['icon url'] = "aze"
    item_1["aquisition price"] = 111
    item_1['liquid gold value'] = 11111
    item_1['comment'] = "Common item 1. "
    
    item_2 = dict()    
    item_2['name'] = "item 2"
    item_2['id'] = "2"
    item_2['count'] = "22"
    item_2['icon url'] = "aze"
    item_2["aquisition price"] = 222
    item_2['liquid gold value'] = 22222
    item_2['comment'] = "Common item 2. "
    
    report.DetailedItemsList = [item_1,item_2]
        
    a = FullReportDisplay(root, report) 
    a.grid()
    """
    item = dict()
    item['id'] = 12134
    print("Download/" + str(item['id']) + ".png")
    image = Image.open("Download/" + str(item['id']) + ".png")
    photoImage = ImageTk.PhotoImage(image)
    iconLabel = ttk.Label(root, image=photoImage)
    iconLabel.image = photoImage
    iconLabel.pack()
    root.mainloop()