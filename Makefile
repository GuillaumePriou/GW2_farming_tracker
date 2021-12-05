.PHONY: format lint test build

FMT_HEAD = "\033[1m%s\033[0m:\n"
FMT_CMD = "  \033[36;1m%-10s\033[0m : %s\n"

SRC_DIR = gw2_tracker
TESTS_DIR = tests
DIST_DIR = dist
NAME = gw2-tracker-$(VERSION)

VERSION = $(shell python -c 'import gw2_tracker; print(gw2_tracker.__version__)')

help:
	@printf $(FMT_HEAD) "Available commands:"
	@printf $(FMT_CMD) "format" "use black and isort to reformat code and tests"
	@printf $(FMT_CMD) "lint" "run linting utilities"
	@printf $(FMT_CMD) "test" "run tests with pytest"
	@printf $(FMT_CMD) "build" "bundle the application using pyinstaller"
	@printf "\n"
	@printf "Note: commands should be run in a virtual environment with development\ndependencies installed (usually with poetry).\n"

format:
	isort $(SRC_DIR) $(TESTS_DIR)
	black $(SRC_DIR) $(TESTS_DIR)

lint:
	flake8 $(SRC_DIR) $(TESTS_DIR)

test:
	pytest

build: lint test
	rm -f "$(DIST_DIR)/$(NAME).zip"
	pyinstaller \
		--clean --onedir -y \
		--distpath $(DIST_DIR) \
		--add-data "$(SRC_DIR)/assets/*:gw2_tracker/assets" \
		--name "$(NAME)" \
		gw2_tracker_launcher.py
	zip -r "$(DIST_DIR)/$(NAME).zip" "$(DIST_DIR)/$(NAME)"