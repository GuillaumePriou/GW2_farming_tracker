import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

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
    item["id"] = 12134
    print("Download/" + str(item["id"]) + ".png")
    image = Image.open("Download/" + str(item["id"]) + ".png")
    photoImage = ImageTk.PhotoImage(image)
    iconLabel = ttk.Label(root, image=photoImage)
    iconLabel.image = photoImage
    iconLabel.pack()
    root.mainloop()
