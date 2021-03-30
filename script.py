#!/apollo/sbin/envroot $ENVROOT/bin/python

import logging
import os
import subprocess

from amzlogging import init, setup_logfile

# Initializing flag as True
# If True, loop can continue it's iterations
iterable = True

# Logging configuration at the top of main
appname = "HostHealthRetriever"

# Check if ENVROOT is set by #!
# This allows script to run even without Apollo environment setup
if "ENVROOT" in os.environ:
    log_dir = os.environ["ENVROOT"] + "/var/output/logs/"
else:
    log_dir = "/tmp/logs/"
os.makedirs(log_dir, exist_ok=True)

# Init logging configuration
init(appname=appname, loglevel=logging.INFO, info_to_milestone=False)
setup_logfile(filename=log_dir + "host_health_retriever_application.log")


# Updates interval duration
def update_interval(pressure):
    if pressure > 0.9:
        interval = 2
    else:
        interval = 5
    return interval


# Helper function which makes the sar call
def sar_call(interval):
    # Use sar in sysstat to generate CPU stats every 1 second for the given interval
    sar_command = ["sar", "-u", "1", str(interval)]

    # Run the sar_command
    call = subprocess.run(
        sar_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True
    )

    return call.stdout


# Helper function which makes the awk call
def awk_call(sar_output):
    # Command to parse the sar output and extract the average value of Idle time
    awk_command = ["awk", "-v", "OFS='\\t'", '{if($1== "Average:") print $8}']

    # Run the awk_command
    call = subprocess.run(
        awk_command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
        input=sar_output,
    )

    return call.stdout


# Retrieves average CPU Idle time in the last interval
def get_pressure(interval):
    # Call sar helper method
    sar_output = sar_call(interval)

    # Call awk helper method
    awk_output = awk_call(sar_output)

    # Set pressure value in the range [0,1]
    pressure = (100.0 - float(awk_output)) / 100.0

    return round(pressure, 2)


# Helper function to set iterable=True so that the execution of the loop starts
def enable_execution():
    global iterable
    iterable = True
    logging.info("iterable flag set to True, execution will continue.")
    return


# Helper function to set iterable=False so that the execution of the loop stops
# Used to terminate the application
def disable_execution():
    global iterable
    iterable = False
    logging.info("iterable flag set to False, execution will stop.")
    return


# Helper function to get global variable iterable
def get_iterable():
    return iterable


def main():
    """
    Define the function local to main() to reduce it's visibilty outside of main() and
    thus no need for type checking "pressure" parameter
    """
    # Updates the file at /tmp/injected_resource with the latest pressure value
    # Envoy expects atomical updates to the file via sym links
    def inject_pressure(pressure):
        with open("/tmp/injected_resource_target1", "w") as f:
            subprocess.run(["echo", str(pressure)], stdout=f, check=True, stderr=subprocess.PIPE)

        subprocess.run(
            ["ln", "-s", "/tmp/injected_resource_target1", "/tmp/injected_resource_new"],
            check=True,
            stderr=subprocess.PIPE,
        )

        subprocess.run(
            ["sudo", "mv", "-fT", "/tmp/injected_resource_new", "/tmp/injected_resource"],
            check=True,
            stderr=subprocess.PIPE,
        )

    logging.info("Initiating health checking.")

    # Run the loop till get_iterable() returns True
    while get_iterable():
        # Set initial interval duration to be 5 seconds
        interval = 5

        try:
            # Get pressure value
            pressure = get_pressure(interval)

            # Update the interval duration based on pressure
            interval = update_interval(pressure)

            # Update the injected_resource file
            inject_pressure(pressure)

            logging.info(
                "Updated pressure: " + str(pressure) + ", Upcoming interval: " + str(interval) + "s"
            )
        # Handle exceptions raised by function calls above
        except subprocess.CalledProcessError as e:
            logging.debug(e)
            logging.debug(e.stderr)
            logging.info("Exception occurred, running next iteration.")
        except Exception as e:
            logging.debug(e)
            logging.info("Exception occurred, running next iteration.")
    return True


if __name__ == "__main__":
    enable_execution()
    main()
