# -*- coding: utf-8 -*-
"""
Model layer of GW2 tool to evaluate gold earnings.

Main features :
    - set API key (Model.apiKey)
    - get inventory and define it as reference
    - get inventory and compare it to the reference
    - generates full report for user

@author: Krashnark
"""

import json
import os.path

import Inventory as i
import Report as r
import APIKey as k

class Model:
    def __init__(self, api_key = ""):
        
        """ Model initialization.
        
        self.applicationState possible values :
            - "0 - started"
            - "1 - got api key"
            - "2 - got start inventory"
            - "3 - got end inventory"
            - "4 - got full report"
        """
        self.applicationState = "0 - started"
        self.apiKey = k.APIKey() # Declare API key, try to load a previously saved API key        
        self.referenceInventory = i.Inventory()
        self.newInventory = i.Inventory()        
        self.report = r.Report()
        
        
        if self.apiKey.keyValue != '':
            self.applicationState = "1 - got api key"            
        
        if self.applicationState == "1 - got api key" :
            # Try to load saved reference inventory
            if os.path.isfile("Application_data/start_inventory.txt") : 
                self.referenceInventory.load_from_file("Application_data/start_inventory.txt", self.apiKey.keyValue)
                self.applicationState = "2 - got start inventory"
            else:
                print ("Could not find saved and valid reference inventory.")
        
        """ This loading do not make sense without loading the full report
        if self.applicationState == "2 - got start inventory" :
            # try to load target inventory
            try:
                self.referenceInventory.load_from_file("Application_data/end_inventory.txt", self.apiKey)
                self.applicationState = "3 - got end inventory"
            except ValueError as error :
                print ("Could not find saved and valid reference inventory.")
                print (error)
        """
        
        # Maybe will implement load function for report.
        # Maybe...
        
    def set_new_key (self, new_key):
        """ User set a new key. Let's validate it and save it.
        """
        try:
            self.apiKey.keyValue = new_key
            self.applicationState = "1 - got api key"
        except :
            pass
        
    def set_reference_inventory(self) :
        """ Get full inventory of an account and put it in reference inventory
        """
        if self.applicationState == "0 - started" :
                raise ValueError("Key was not yet defined !")
                
        self.referenceInventory.get_full_inventory(self.apiKey.keyValue)
        
        self.referenceInventory.save_to_file("Application_data/start_inventory.txt", self.apiKey.keyValue)
        
        self.applicationState = "2 - got start inventory"
        
        """with open("debug/reference_inventory.txt", 'w') as f:
            json.dump(self.referenceInventory.items, f, indent=3, ensure_ascii=False)
        """
        
    
    def get_inventory_and_compare_it(self) :
        """ Get full inventory of an account and put it in new/updated inventory.
        Then compare reference inventory with new inventory and build the report.
        """
        if self.applicationState in ("0 - started","1 - got api key") :
            raise ValueError("Missing key or reference inventory !")
        self.newInventory.get_full_inventory(self.apiKey.keyValue)
        
        self.referenceInventory.save_to_file("Application_data/end_inventory.txt", self.apiKey.keyValue)
        self.applicationState = "3 - got end inventory"
        self.report.compare_inventories(self.referenceInventory, 
                                        self.newInventory)
        
        print(f'function get inventory & compare it : report content after comparison :')
        print(f'   self.report.itemsDetail : {self.report.itemsDetail}' )
        
        self.report.get_item_details()
        
        print(f'function get inventory & compare it : report content after getting details :')
        print(f'   self.report.itemsDetail : {self.report.itemsDetail}' )
        
        self.applicationState = "4 - got full report"
        
        """with open("debug/new_inventory.txt", 'w') as f:
            json.dump(self.newInventory.items, f, indent=3, ensure_ascii=False)
        """    
        
        
# Main for debug
if __name__ == "__main__":
    #m = Model()
    #m.set_reference_inventory()
    
    #print ("self._unaggregatedItemResults")
    #print(m._unaggregatedItemResults)
    
    #print ("reference inventory : ")
    #print(m.referenceInventory)
    
    comparisonExample =  {
                            '78758' : 38, # Ordres codés : non vendable, lié au compte
                            '49424' : 24, # infusion +1 : TP only
                            '49428' : 5,  # Infusion +5 : TP only
                            '19697' : 234, # Minrai de cuivre, vendable TP & NPC
                         }
    r = Report()
    #r.compute(comparisonExample)
    
    print(f'r.totalAquisitionValue : {r.totalAquisitionValue}')
    print(f'r.totalLiquidGoldValueto : {r.totalLiquidGoldValue}') 
    print(f'r.DetailedItemsList : {r.DetailedItemsList}') 
    
    