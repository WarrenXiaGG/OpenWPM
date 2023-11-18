import argparse
import random
import time
from pathlib import Path
from typing import Literal

from CrUx import CrUXData

from custom_command import LinkCountingCommand, SignupCommand
from openwpm.command_sequence import CommandSequence
from openwpm.commands.browser_commands import GetCommand
from openwpm.config import BrowserParams, ManagerParams
from openwpm.storage.sql_provider import SQLiteStorageProvider
from openwpm.task_manager import TaskManager

EMAILS = [
            "veerliudmila@gmail.com",
            "h53w66ht9@mozmail.com",
            "ohmyducks@duck.com"
]

def emailProducerProducer(email):
    return lambda url, site_title: email

parser = argparse.ArgumentParser()
parser.add_argument("--crux", action="store", default=None)
parser.add_argument("--headless", action="store_true", default=False)
parser.add_argument("--ignore-until", action="store", default=None)

args = parser.parse_args()

sites = iter([
    "https://www.nothingunknown.com/looking-for-more"
])


if args.crux is not None:
    # Load the latest crux list.
    print("Loading Crux List")
    sites = CrUXData("202310.csv.gz", rank_filter=1000, partition=args.crux, ignoreUntil=args.ignore_until)


display_mode: Literal["native", "headless", "xvfb"] = "native"
if args.headless:
    display_mode = "headless"

# Loads the default ManagerParams
# and NUM_BROWSERS copies of the default BrowserParams
NUM_BROWSERS = 2
manager_params = ManagerParams(num_browsers=NUM_BROWSERS)
browser_params = [BrowserParams(display_mode=display_mode) for _ in range(NUM_BROWSERS)]

# Update browser configuration (use this for per-browser settings)
for browser_param in browser_params:
    # Record HTTP Requests and Responses
    browser_param.http_instrument = False
    # Record cookie changes
    browser_param.cookie_instrument = False
    # Record Navigations
    browser_param.navigation_instrument = False
    # Record JS Web API calls
    browser_param.js_instrument = False
    # Record the callstack of all WebRequests made
    # browser_param.callstack_instrument = True
    # Record DNS resolution
    browser_param.dns_instrument = False
    # Set this value as appropriate for the size of your temp directory
    # if you are running out of space
    browser_param.maximum_profile_size = 1000 * (10**20)  # 1 GB = 1000 * 2^20 Bytes
    browser_param.tmp_profile_dir = Path("/mnt/cs356email/tmp-03")

# Update TaskManager configuration (use this for crawl-wide settings)
manager_params.data_directory = Path("./datadir/")
manager_params.log_path = Path("./datadir/openwpm.log")

# memory_watchdog and process_watchdog are useful for large scale cloud crawls.
# Please refer to docs/Configuration.md#platform-configuration-options for more information
# manager_params.memory_watchdog = True
# manager_params.process_watchdog = True


# Commands time out by default after 60 seconds
with TaskManager(
    manager_params,
    browser_params,
    SQLiteStorageProvider(Path("./datadir/crawl-data.sqlite")),
    None,
) as manager:
    # Visits the sites
    for index, site in enumerate(sites):
        def callback(success: bool, val: str = site) -> None:
            print(
                f"CommandSequence for {val} ran {'successfully' if success else 'unsuccessfully'}"
            )

        # generate a new random seed for each site
        seed = time.time()

        for email in EMAILS:
            # Parallelize sites over all number of browsers set above.
            command_sequence = CommandSequence(
                site,
                site_rank=index,
                callback=callback,
                reset=True
            )

            # Start by visiting the page
            command_sequence.append_command(GetCommand(url=site, sleep=3), timeout=60)
            # Have a look at custom_command.py to see how to implement your own command
            command_sequence.append_command(LinkCountingCommand())
            command_sequence.append_command(SignupCommand(emailProducerProducer(email),2,180,debug = True))

            # Run commands across all browsers (simple parallelization)
            random.seed(seed)
            manager.execute_command_sequence(command_sequence)
