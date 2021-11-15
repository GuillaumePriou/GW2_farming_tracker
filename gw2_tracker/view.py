# -*- coding: utf-8 -*-
"""
View layer of GW2 tool to evaluate gold earnings.

@author: Krashnark
"""
import tkinter as tk
from importlib import abc, resources
from tkinter import ttk
from typing import ClassVar

from PIL import Image, ImageTk

ASSET_SOURCES = resources.files("gw2_tracker").joinpath("assets")

ASSETS = {
    k: ASSET_SOURCES.joinpath(f"{k}_coin_20px.png")
    for k in ("copper", "silver", "gold")
}


class CoinWidget(ttk.Frame):
    """Widget displaying a single coin"""

    IMAGE_CACHE: ClassVar[dict[abc.Traversable, tk.PhotoImage]] = {}

    label: ttk.Label
    logo: ttk.Label

    def __init__(self, parent, asset: abc.Traversable, amount: int = 0):
        """
        Parameters:
            parent: parent widget
            asset: asset to display after the amount
        """
        super().__init__(parent)

        if asset not in self.IMAGE_CACHE:
            self.IMAGE_CACHE[asset] = tk.PhotoImage(data=asset.read_bytes())

        self.label = ttk.Label(self, text="-")
        self.logo = ttk.Label(self, image=self.IMAGE_CACHE[asset])

        self.label.pack(side="left")
        self.logo.pack(side="left")

        self.amount = amount

    @property
    def amount(self) -> int:
        return self._amount

    @amount.setter
    def amount(self, value: int):
        self._amount = value
        self.label.config(text=self._amount)


class GoldWidget(ttk.Frame):
    copper: CoinWidget
    silver: CoinWidget
    gold: CoinWidget

    def __init__(self, parent, amount=0):
        super().__init__(parent)

        self.copper = CoinWidget(self, ASSETS["copper"])
        self.silver = CoinWidget(self, ASSETS["silver"])
        self.gold = CoinWidget(self, ASSETS["gold"])

        self.gold.pack(side="left")
        self.silver.pack(side="left")
        self.copper.pack(side="left")

        self.amount = amount

    @property
    def amount(self) -> int:
        return self._amount

    @amount.setter
    def amount(self, value: int):
        self._amount = value
        self.copper.amount = value % 100
        self.silver.amount = (value // 100) % 100
        self.gold.amount = value // 10000


class DetailsReportDisplay(ttk.Frame):
    """A dedicated frame to display the details of item gained during a play session.
    Information to be displayed in a table-like form :
        - Item icon
        - Item id (for debug)
        - Item name
        - Item count
        - Aquisition price
        - Liquid gold value

    Input : list of items (dict)
    """

    def __init__(self, parent, items_list=[]):
        super().__init__(parent)

        # Legends for the details
        self.itemIdLegend1 = ttk.Label(self, text="ID objet")
        self.itemIdLegend1.grid(row=0, column=1)

        self.itemIdLegend2 = ttk.Label(self, text="Nom objet")
        self.itemIdLegend2.grid(row=0, column=2)

        self.itemIdLegend3 = ttk.Label(self, text="Nombre objets")
        self.itemIdLegend3.grid(row=0, column=3)

        self.itemIdLegend4 = ttk.Label(self, text="Or liquide")
        self.itemIdLegend4.grid(row=0, column=4)

        self.itemIdLegend5 = ttk.Label(self, text="Cout aquisition")
        self.itemIdLegend5.grid(row=0, column=5)

        self.iconLabelList = list()

        if items_list == []:
            print("View : detail display report received an empty list of items.")
            self.noItemLabel = ttk.Label(self, text="Aucun changement d'inventaire.")
            self.noItemLabel.grid(row=1, column=0)
        else:
            rowNb = 0
            print(f"item list to display : {items_list}")
            for item in items_list:
                rowNb += 1

                idem_id = item["id"]
                print(f"Create a row of labels for item {idem_id}")

                # Display item icon (loaded from a file)
                try:
                    picture_path = "Download/" + str(item["id"]) + ".png"
                    self.iconLabelList.append(
                        self.build_image_label(self, picture_path)
                    )
                    self.iconLabelList[rowNb - 1].grid(row=rowNb, column=0)
                except ValueError as error:
                    self.iconLabel = ttk.Label(self, text="Image non trouvée")
                    print(error)
                    self.iconLabel.grid(row=rowNb, column=0)

                # Display item id
                idLabel = ttk.Label(self, text=item["id"])
                idLabel.grid(row=rowNb, column=1)

                # Display item name
                nameLabel = ttk.Label(self, text=item["name"])
                nameLabel.grid(row=rowNb, column=2)

                # Display item count
                countLabel = ttk.Label(self, text=item["count"])
                countLabel.grid(row=rowNb, column=3)

                # Display item liquid gold value
                liquidGoldLabel = GoldWidget(self, item["liquid gold value"])
                liquidGoldLabel.grid(row=rowNb, column=4)

                # Display item aquisition price
                aquisitionPriceLabel = GoldWidget(self, item["aquisition price"])
                aquisitionPriceLabel.grid(row=rowNb, column=5)

    def build_image_label(self, parent, picture_path):
        print(f"try to open {picture_path}")
        image = Image.open(picture_path)
        photoImage = ImageTk.PhotoImage(image)
        iconLabel = ttk.Label(parent, image=photoImage)
        iconLabel.image = photoImage
        return iconLabel


class FullReportDisplay(ttk.Frame):
    """A dedicated frame to display the item gained during a play session.
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

    def __init__(self, parent, report_to_display=None):
        super().__init__(parent)
        # self.farmTimeLabel = ttk.Label(text='Durée : à calculer')
        # self.farmTimeLabel.grid(row=0, column=0)

        # Total aquisition price display
        self.totalAcquisitionvalueLabel = ttk.Label(self, text="Prix à l'achat")
        self.totalAcquisitionvalueLabel.grid(row=0, column=0)

        if report_to_display == None:
            self.totalAquisitionGoldwidget = GoldWidget(self, 0)
        else:
            self.totalAquisitionGoldwidget = GoldWidget(
                self, report_to_display.totalAquisitionValue
            )
        self.totalAquisitionGoldwidget.grid(row=0, column=1)

        # Total liquid gold price display
        self.totalLiquidGoldValueLabel = ttk.Label(self, text="Prix liquid gold")
        self.totalLiquidGoldValueLabel.grid(row=0, column=2)

        if report_to_display == None:
            self.totalLiquidGoldGoldwidget = GoldWidget(self, 0)
        else:
            self.totalLiquidGoldGoldwidget = GoldWidget(
                self, report_to_display.totalLiquidGoldValue
            )
        self.totalLiquidGoldGoldwidget.grid(row=0, column=3)

        if report_to_display == None:
            self.details = DetailsReportDisplay(self, [])
        else:
            self.details = DetailsReportDisplay(self, report_to_display.itemsDetail)
        self.details.grid(row=1, column=0, columnspan=3)

        # print(f'report_to_display.totalAquisitionValue = {report_to_display.totalAquisitionValue}')
        # print(f'report_to_display.totalLiquidGoldValue = {report_to_display.totalLiquidGoldValue}')
        # print(f'report_to_display.itemsDetail = {report_to_display.itemsDetail}')

    def update_detail_display(self, new_report):
        # re-init with new value
        self.details.destroy()
        self.details = DetailsReportDisplay(self, new_report.itemsDetail)
        self.details.grid(row=1, column=0, columnspan=3)


class View(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        # Define a big important message to help user to use the this application
        self.bigImportantMessageLabel = ttk.Label(
            self, text="Hello this is dog.", font="bold"
        )
        self.bigImportantMessageLabel.grid(row=0, column=0, columnspan=2)

        # Entry widget where the user paste his API key
        self.keyInput = ttk.Entry(self, width=80)
        self.keyInput.grid(row=2, column=0)

        self.okButton = ttk.Button(
            self, text="Utiliser cette clé !", command=self.save_key
        )
        self.okButton.grid(row=2, column=2)

        # Buttons to get inventories and calculate differences

        self.startButton = ttk.Button(
            self, text="Commencer", command=self.set_reference
        )
        self.startButton.grid(row=4, column=0)

        self.stopButton = ttk.Button(
            self, text="Calculer les gains", command=self.compute_gains
        )
        self.stopButton.grid(row=4, column=1)

        self.fullReportDisplay = FullReportDisplay(self)
        self.fullReportDisplay.grid(row=5, column=0, columnspan=3)

    def set_controller(self, controller):
        self.controller = controller

    def refresh_api_key_entry_content(self, value_from_model):
        self.keyInput.insert(0, value_from_model)

    # Some functions to update message of big important message label
    def show_action_in_progress(self, msg):  # Does
        print("yellow !!")
        self.bigImportantMessageLabel.config(text=msg)
        self.bigImportantMessageLabel["foreground"] = "yellow"

    def show_success(self, msg):
        self.bigImportantMessageLabel["text"] = msg
        self.bigImportantMessageLabel["foreground"] = "green"

    def show_error(self, msg):
        self.bigImportantMessageLabel["text"] = msg
        self.bigImportantMessageLabel["foreground"] = "red"

    # API key input management
    def save_key(self):
        print("Cliqué sur le bouton save api key")
        self.show_action_in_progress("Vérification de la clé...")
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
        # self.report = ReportDisplay(self.controller.compute_gains())
        # self.report.grid(row=5, column=0, columnspan=5)

    def display_report(self, report):
        print("View : begin report display")
        self.fullReportDisplay.update_detail_display(report)
        print("View : end report display")
