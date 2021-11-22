.PHONY: reformat

reformat:
	isort gw2_tracker tests && black gw2_tracker tests