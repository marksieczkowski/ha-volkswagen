# HA-Volkswagen

A Home Assistant Integration for North America Volkswagen vehicles.  This integration was inspired by the [Volkswagen Connect](https://github.com/robinostlund/homeassistant-volkswagencarnet) (EU vehicles) and the [Fordpass](https://github.com/marq24/ha-fordpass) integrations.  I currently have an ID.4 so that is what I'm testing against.

This integration leverages the [CarConnectivity](https://github.com/tillsteinbach/CarConnectivity) and the [CarConnectivity-connector-volkswagen-na](https://github.com/zackcornelius/CarConnectivity-connector-volkswagen-na) projects to communicate with the VW API.

## Notes

I strongly recommend you create a second ID for your MyVW App, and use that ID for this integration.  So if VW gets upset about the API access and blocks the ID you won't lose access to your MyVW app.
