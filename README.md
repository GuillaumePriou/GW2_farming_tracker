# GW2 tracker tool
A small software to precisely evaluate how many gold pieces a user is making during a play session.

This app aims at fixing a limitation of the GW2Efficiency website for computing
your gains over a play session (or more). The way GW2Efficiency works, it
computes the value of your account before and after, and outputs the difference.
This is problematic if you have a lot of item which price fluctuates a lot, say
*Mystical Coins*. The change in price before and after your play session will
be present in the GW2Efficiency difference, and may completely swallow other
sources, for instance what you earned during your play.

Our software compute a difference of *inventory*, that is it figures out which
items, resources etc. have changed during you play session. Then it computes
the total prices of items that actually changed, ignoring items you have neither
gained nor consumed. This avoids the above problem and reports the actual
amount you earned.

# Installation

## Bundled version
1. Download the zip file of the latest version, corresponding to your plateform,
   from the [release page](https://github.com/GuillaumePriou/GW2_farming_tracker/releases)
2. Unzip the compressed folder wherever you'd like to install GW2 tracker
3. Start the executable to run the tool. The executable is named the same as the
   zip file (without the `.zip`), e.g. `gw2_tracker-v0.1.0-linux`

## Development version
GW2 tracker is developped using python 3.10 and uses poetry for dependency
management. You'll need to install python 3.10 or higher first, and poetry.
We advise using a virtual environment, which poetry will do by default.

1. Clone this repository locally
2. Activate your virtual environment if necessary
3. Run `poetry run poetry install` to install the tools and its
   dependencies in the virtual environment
4. Run `poetry run gw2_tracker` to run GW2 tracke from the environment


# Usage

The text with a white background at the top of the UI displays useful messages
on the state of the tool.

1. Enter an API key for your account inside the field. Make sure the key has
   the permissions to access your wallets, inventory and characters. Click on
   the `Use key` button to validate your key.
2. Before starting your play session, click `Get start snapshot` to record the
   content of your account prior to play. The content is saved on disc, so you
   can compute the gains accross multiple play sessions.
3. After your play session, click on `Compute gains` to retrieve a new snapshot
   and compute the difference. The content and value of the difference is
   displayed in the central area.
