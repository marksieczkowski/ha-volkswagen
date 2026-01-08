from __future__ import annotations
from typing import TYPE_CHECKING

import json
import os
import tempfile
import logging

# https://github.com/tillsteinbach/CarConnectivity
from carconnectivity import carconnectivity

if TYPE_CHECKING:
    from typing import List, Optional

    from carconnectivity.garage import Garage


LOG_LEVELS: List[str] = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
DEFAULT_LOG_LEVEL = "ERROR"
CONFIG_FILE = "carconnectivity.json"
LOG: logging.Logger = logging.getLogger("carconnectivity-example")


def main() -> None:
    """ Simple example showing how to retrieve all vehicles from the account """

    tokenstore_file: str = os.path.join(tempfile.gettempdir(), 'tokenstore')

    log_level: int = LOG_LEVELS.index(DEFAULT_LOG_LEVEL)

    logging.basicConfig(level=LOG_LEVELS[log_level], format='%(asctime)s:%(levelname)s:%(message)s', datefmt='%Y-%m-%dT%H:%M:%S%z')

    print('#  read CarConnectivity configuration')
    with open(CONFIG_FILE, 'r', encoding='utf-8') as config_file:
        config_dict = json.load(config_file)
        print('#  Login')
        car_connectivity = carconnectivity.CarConnectivity(config=config_dict, tokenstore_file=tokenstore_file)
        print('#  fetch data')
        car_connectivity.fetch_all()
        print('#  getData')
        garage: Optional[Garage] = car_connectivity.get_garage()
        if garage is not None:
            print('#  list all vehicles')
            for vehicle in garage.list_vehicles():
                print(f'#  {vehicle}')
        print('#  Shutdown')
        car_connectivity.shutdown()

    print('#  done')


if __name__ == '__main__':
    main()