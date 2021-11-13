# -*- coding: utf-8 -*-
"""
Simple package for defining an API key behavior

Main features :
    - Check API key validity (including permissions)
    - Save/load API key from a file

@author: Krashnark
"""
import os

import GW2_API_handler as gw2h

class APIKey:
    def __init__(self):    
        """ Initialize Key object.
        
        The function automatically tries to load a key from a file.
        """
        # To avoid copy-pasta : store key location in this variable.
        self.keyLocation = 'Application_data/API_key.txt'
        
        # Create parent folder if it does not already exist
        if not os.path.exists('Application_data'):
            os.makedirs('Application_data')
            
        # try to load a previously saved key
        if os.path.isfile(self.keyLocation):
            with open(self.keyLocation, 'r') as f:
                try: 
                    self.keyValue = f.read()
                    print("Loaded saved key.")
                except ValueError as error:
                    print("Found saved key but is was not valid.")
                    print(error)
                    self.__keyValue = ''
                    
        else:
            print ("No saved key found.")
            self.__keyValue = ''
    
    @property
    def keyValue(self):
        """ Model.keyValue getter """
        return self.__keyValue
    
   
    @keyValue.setter
    def keyValue(self, new_value):  
        """ Model.keyValue setter
            
            Check that the API key given in argument possesses all the authorizations
            needed for this tool.
            
            Authorizations needed : 
                - wallet
                - inventories
                - characters (to get list of characters, which allows to fetch single
                  character inventory)
        """       
        result = gw2h.GW2_API_handler("https://api.guildwars2.com/v2/tokeninfo", new_value)
      
        if result == "" :
            raise ValueError(f'Unable to check permissions for key {new_value} ! Check that the key is valid !')
        
        if 'wallet' not in result['permissions'] :
            print("Missing wallet permission")
            raise ValueError(f'Key {self.keyValue} is missing wallet permission !')
        elif 'inventories' not in result['permissions'] :
            print("Missing inventories permission")
            raise ValueError(f'Key {self.keyValue} is missing inventories permission !')
        elif 'characters' not in result['permissions'] :
            print("Missing characters permission")
            raise ValueError(f'Key {self.keyValue} is missing characters permission !')
        
        print("Valid key with appropriate permissions : OK.")
        self.__keyValue = new_value
        
        with open(self.keyLocation, 'w') as f:
                    f.write(new_value)


# Main for debug and testing
if __name__ == "__main__":
    k = APIKey()
    
    #k.keyValue = 'fake'