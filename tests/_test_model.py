# m = Model()
# m.set_reference_inventory()

# print ("self._unaggregatedItemResults")
# print(m._unaggregatedItemResults)

# print ("reference inventory : ")
# print(m.referenceInventory)

comparisonExample = {
    "78758": 38,  # Ordres codés : non vendable, lié au compte
    "49424": 24,  # infusion +1 : TP only
    "49428": 5,  # Infusion +5 : TP only
    "19697": 234,  # Minrai de cuivre, vendable TP & NPC
}
r = Report()
# r.compute(comparisonExample)

print(f"r.totalAquisitionValue : {r.totalAquisitionValue}")
print(f"r.totalLiquidGoldValueto : {r.totalLiquidGoldValue}")
print(f"r.DetailedItemsList : {r.DetailedItemsList}")
