# -*- coding: utf-8 -*-
"""
Package defining a report for GW2 inventory changes.

Main features :
    - Compare 2 inventories
    - Build detailed list of changes for each item : id, name, icon, count, price

The data fetched from GW2 API will be saved in local files for reuse and for display.

@author: Krashnark
"""
import threading
import urllib.request

from gw2_tracker import gw2_api


class _Report:
    """The report gather the information to show to the user after the data comparison :
    - total earnings (liquid gold & aquisition value)
    - Detail of items :
        - Item picture (save it in a file)
        - Item id (for debug)
        - Item name
        - Item count
        - Aquisition price (how much it costs to get the resource)
        - Liquid gold value (how much gold we get by selling the ressource)

        The 2 pricings are expressed for the whole item stock, not a single unit
    """

    def __init__(self):
        self.totalLiquidGoldValue = 0
        self.totalAquisitionValue = 0

        self.itemsDetail = []

    def compare_inventories(self, old_inventory, new_inventory):
        """Create dictionnary indicating the differences between reference and new inventories

        Arguments : old and new inventories (Inventory objects)
        Output : fill self.itemsDetail with item id and count information.

        This function only process basic data (id & count). Remaining data will
        be fetched later (simultanously). Previous content of self.itemsDetail
        is discarded.
        """
        # temporary dictionnary to compute differences
        comparison = (
            new_inventory.items.copy()
        )  # Comparison now holds the newly acquired item (whatever the count)
        print("comparison.keys() : ")
        print(comparison.keys())
        print("end of comparison.keys()")

        for k, v in old_inventory.items.items():
            if (
                k in comparison.keys()
            ):  # item exist in both inventories (whatever the count)
                print(
                    f"For id = {k}, comparison[k] = {comparison[k]}, old_inventory.items[k] = {old_inventory.items[k]} :"
                )
                comparison[k] -= old_inventory.items[k]
                print(
                    f"    item in both inventories => comparison[k] = {comparison[k]}"
                )
            else:  # item exist only in old inventory => it has been removed.
                print(
                    f"For id = {k}, old_inventory.items[k] = {old_inventory.items[k]} :"
                )
                comparison[k] = -old_inventory.items[k]
                print(
                    f"    item only in old inventory => comparison[k] = {comparison[k]}"
                )

            if comparison[k] == 0:  # Remove item if count = 0
                del comparison[k]

        # Save comparison result in self.itemsDetail
        self.itemsDetail = []
        for k, v in comparison.items():
            self.itemsDetail.append({"id": k, "count": v})

        if self.itemsDetail == []:
            print("Comparison done : no difference found.")
        else:
            print(
                f"Comparison done : found {len(comparison)} item count change : {comparison}"
            )

            if len(self.itemsDetail) > 50:
                import json

                with open("debug/old_inventory_according_to_comparison.txt", "w") as f:
                    json.dump(old_inventory.items, f, indent=3, ensure_ascii=False)
                with open("debug/new_inventory_according_to_comparison.txt", "w") as f:
                    json.dump(new_inventory.items, f, indent=3, ensure_ascii=False)
                with open("debug/comparison_result.txt", "w") as f:
                    json.dump(comparison, f, indent=3, ensure_ascii=False)

                raise ValueError(
                    "La comparaison a encore merdé (plus de 50 différences)..."
                )

    def _get_trading_post_prices(self, item_id, ptr_lock, ptr_prices_table):
        """Internal function. For a given item id, get the lowest sell offer & highest buy offer

        Arguments :
            - item id for which to get the price
            - ptr_lock : lock object to allow several thread to fill ptr_prices_table
            - ptr_prices_table : a variable to fill with the result

        Output : add an entry in ptr_prices_table (via a lock)

        Note :
            - If no sell offer, the function will raise an error. I am not sure
            how to handle this kind of situation when initially creating the
            tool : item too expensive (jckpot ?) or just no one bother to sell it ?
            - If no buy offer, buy offer price set to 0.
        """
        url = "https://api.guildwars2.com/v2/commerce/listings/" + str(item_id)
        priceResponse = gw2_api.GW2_API_handler(url)

        if priceResponse == "":  # No answer from API => Set output as ""
            with ptr_lock:
                ptr_prices_table[item_id] = ""
        else:
            if priceResponse["sells"] == []:
                raise ValueError(
                    f"No sell offer for item {item_id}. Contacter Guigui: ça l intéresse !"
                )
            else:
                lowestSellOffer = priceResponse["sells"][0]["unit_price"]

            if priceResponse["buys"] == []:
                highestBuyOffer = 0
            else:
                highestBuyOffer = priceResponse["buys"][0]["unit_price"]

            with ptr_lock:
                ptr_prices_table[item_id] = {
                    "sell": lowestSellOffer,
                    "buy": highestBuyOffer,
                }

    def _get_item_properties(self, item_id, ptr_lock, ptr_item_properties_table):
        """Internal function. For a given item id, get item properties via GW2 API

        Arguments :
            - item id for which to get the properties
            - ptr_lock : lock object to allow several thread to fill ptr_prices_table
            - ptr_item_properties_table : a variable to fill with the result

        Output : add an entry in ptr_item_properties_table (via a lock)
        """
        url = "https://api.guildwars2.com/v2/items?id=" + str(item_id) + "&lang=fr"
        propertyResponse = gw2_api.GW2_API_handler(url)

        with ptr_lock:
            ptr_item_properties_table[item_id] = propertyResponse

    def get_item_details(self):
        """Complete the comparison data. For each item, this function will fetch/compute :
        - Item name
        - Item icon (url & picture data)
        - Aquisition price (how much it costs to get the resource)
        - Liquid gold value (how much gold we get by selling the ressource)

        This function also fills :
            - self.totalLiquidGoldValue
            - self.totalAquisitionValue

        The 2 pricings are expressed for the whole item stock, not a single unit

        Input : self.itemsDetail with basic data (id & count)
        Output : list of dicts (keys: id, count, name, icon url, aquisition price,
                 liquid gold value, comment)
        """
        # Check that the function was called at appropriate moment.
        # if self.itemsDetail == []:
        #    raise ValueError ("self.itemsDetail is still empty. Please fill it first with items id & count.")

        # Reset total gold values & detailed item list
        self.totalLiquidGoldValue = 0
        self.totalAquisitionValue = 0

        lock = (
            threading.Lock()
        )  # to make sure that no thread collides when saving results.

        threads = []

        print("Starting to compute the report...")

        # Fetch all data simultaneously !
        propertyResponse = dict()
        tpPrices = (
            dict()
        )  # trading post prices. Key = item id, value = lowest sell offer & highest buy offer
        for i in range(0, len(self.itemsDetail)):
            # Get trading post prices for each item
            threads.append(
                threading.Thread(
                    target=self._get_trading_post_prices,
                    args=(self.itemsDetail[i]["id"], lock, tpPrices),
                )
            )
            # Get property data for each item (especially name & NPC price)
            threads.append(
                threading.Thread(
                    target=self._get_item_properties,
                    args=(self.itemsDetail[i]["id"], lock, propertyResponse),
                )
            )

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        print(f"propertyResponse = {propertyResponse}")

        for i in range(0, len(self.itemsDetail)):
            # Reset additional data in self.itemsDetail, keep only id & count
            if "name" in self.itemsDetail[i].keys():
                self.itemsDetail[i] = {
                    "id": self.itemsDetail[i]["id"],
                    "count": self.itemsDetail[i]["count"],
                }
            # Initialize comment field
            self.itemsDetail[i]["comment"] = ""

            if (
                propertyResponse[self.itemsDetail[i]["id"]] == ""
            ):  # Unable to get properties (example : Augmentation au niveau 80 object : id = 78599)
                debug_id = self.itemsDetail[i]["id"]
                print(
                    f"Could not retrieve properties for item {debug_id} => Skipping value computation for this item."
                )
                self.itemsDetail[i]["name"] = "UNKOWN"
                self.itemsDetail[i]["aquisition price"] = 0
                self.itemsDetail[i]["liquid gold value"] = 0
                self.itemsDetail[i]["comment"] = (
                    self.itemsDetail[i]["comment"] + "Unkown item. "
                )
            else:
                self.itemsDetail[i]["name"] = propertyResponse[
                    self.itemsDetail[i]["id"]
                ]["name"]
                urllib.request.urlretrieve(
                    propertyResponse[self.itemsDetail[i]["id"]]["icon"],
                    "Download/" + str(self.itemsDetail[i]["id"]) + ".png",
                )

                # NoSell : item is not sellable to NPC => Price = 0
                if "NoSell" in propertyResponse[self.itemsDetail[i]["id"]]["flags"]:
                    npcPrice = 0
                    self.itemsDetail[i]["comment"] = (
                        self.itemsDetail[i]["comment"] + "Item not sellable to NPC. "
                    )
                else:
                    npcPrice = propertyResponse[self.itemsDetail[i]["id"]][
                        "vendor_value"
                    ]

                # Compute aquisition price
                if (
                    tpPrices[self.itemsDetail[i]["id"]] == ""
                ):  # Item is not sold on trading post
                    self.itemsDetail[i]["aquisition price"] = 0
                    self.itemsDetail[i]["liquid gold value"] = npcPrice
                    self.itemsDetail[i]["comment"] = (
                        self.itemsDetail[i]["comment"]
                        + "Item not sold on trading post. "
                    )
                else:
                    self.itemsDetail[i]["aquisition price"] = tpPrices[
                        self.itemsDetail[i]["id"]
                    ]["sell"]

                    if tpPrices[self.itemsDetail[i]["id"]]["buy"] == []:
                        self.itemsDetail[i]["liquid gold value"] = npcPrice
                        self.itemsDetail[i]["comment"] = (
                            self.itemsDetail[i]["comment"]
                            + "No buyer on trading post. "
                        )
                    else:
                        self.itemsDetail[i]["liquid gold value"] = max(
                            npcPrice,
                            round(0.85 * tpPrices[self.itemsDetail[i]["id"]]["sell"]),
                        )

                    if npcPrice >= 0.85 * tpPrices[self.itemsDetail[i]["id"]]["sell"]:
                        self.itemsDetail[i]["comment"] = (
                            self.itemsDetail[i]["comment"]
                            + "TP price low : sell to NPC instead. "
                        )

                # Prices are for entire item stock => multiply unit price by item count
                self.itemsDetail[i]["aquisition price"] *= self.itemsDetail[i]["count"]
                self.itemsDetail[i]["liquid gold value"] *= self.itemsDetail[i]["count"]

            # Finally, sum the prices to get the total
            self.totalAquisitionValue += self.itemsDetail[i]["aquisition price"]
            self.totalLiquidGoldValue += self.itemsDetail[i]["liquid gold value"]

        print("Report computed")


# Main for debug and testing
if __name__ == "__main__":
    dict1 = {"28445": 3, "12452": 1}
    dict2 = {"28445": 10, "12452": 2}

    # Test compare_inventories
    class inv:
        def __init__(self):
            self.items = dict()

    inv1 = inv()
    inv1.items = dict1
    inv2 = inv()
    inv2.items = dict2

    r = Report()
    r.compare_inventories(inv1, inv2)

    # test get_item_details
    r.itemsDetail = [{"id": 28445, "count": 3}, {"id": 12452, "count": 2}]
    r.get_item_details()
