# -*- coding: utf-8 -*-
"""
Simple package containing just a function to call the GW2 API.

That is all. Dependency : requests library.

@author: Krashnark
"""
import requests

def GW2_API_handler (url, api_key =""):
    """ A function to manage calls to GW2 API.
    Inputs: 
        - URL
        - API key (optional, default = "")
    Output if successful : dict containing response content (response.json())
    Output if failure : empty string
    """
    headers = {'Authorization': 'Bearer {}'.format(api_key)}
    response = requests.get(url, headers=headers, timeout=15)
    
    if response.status_code == 200:
        return response.json()
    else:
        return ''
        #raise ValueError(f'Invalid request at {url} for key {api_key} : {response.status_code}')
        
# Main for debug and testing
if __name__ == "__main__":
    url = "https://api.guildwars2.com/v2/items/12452"
    response = GW2_API_handler(url)
    print(response)
    