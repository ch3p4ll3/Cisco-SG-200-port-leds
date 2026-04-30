import json
from logging import getLogger
from os import getenv
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

from src.logger import configure_logger
from src.scraper import Scraper

load_dotenv()

base_path = Path(__file__).parent
configure_logger(base_path)
logger = getLogger(__file__)

# MQTT Configuration
DISCOVERY_PREFIX = "homeassistant"
COMPONENT = "switch"
OBJECT_ID = "cisco_sg200_leds"
TOPIC_BASE = f"{DISCOVERY_PREFIX}/{COMPONENT}/{OBJECT_ID}"
COMMAND_TOPIC = f"{TOPIC_BASE}/set"
STATE_TOPIC = f"{TOPIC_BASE}/state"
AVAILABILITY_TOPIC = f"{TOPIC_BASE}/availability"

led_status = False


def run_scraper(state_on: bool):
    """Executes the Selenium script to toggle LEDs."""
    logger.info("Setting Cisco LEDs to: %s", "ON" if state_on else "OFF")
    try:
        with Scraper(
            getenv("SWITCH_URL"),
            getenv("SWITCH_USERNAME"),
            getenv("SWITCH_PASSWORD"),
        ) as sc:
            sc.run(state_on)
        return True
    except Exception as e:
        logger.exception("Scraper execution failed", exc_info=True)
        return False


def get_led_status():
    """Executes the Selenium script to toggle LEDs."""
    logger.info("Getting Cisco LEDs status")
    try:
        status = False

        with Scraper(
            getenv("SWITCH_URL"),
            getenv("SWITCH_USERNAME"),
            getenv("SWITCH_PASSWORD"),
        ) as sc:
            status = sc.get_led_status()
        return status
    except Exception as e:
        logger.exception("Scraper execution failed", exc_info=True)
        return False


def on_connect(client, userdata, flags, rc):
    """Callback for when the client connects to the broker."""
    global led_status

    if rc == 0:
        logger.info("Connected to MQTT Broker!")
        # Re-subscribe on connect (good practice for reconnections)
        client.subscribe(COMMAND_TOPIC)
        # Register the switch
        setup_ha_discovery(client)

        led_status = get_led_status()
        client.publish(STATE_TOPIC, "ON" if led_status else "OFF", retain=True)
        client.publish(AVAILABILITY_TOPIC, "online", retain=True)
    else:
        logger.error("Connection failed with code %d", rc)


def on_message(client, userdata, msg):
    """Handles incoming ON/OFF toggle from Home Assistant UI."""
    global led_status

    payload = msg.payload.decode().upper()
    logger.info("Toggle received: %s", payload)

    target_state = payload == "ON"

    if target_state == led_status:
        logger.debug("Leds already %s", "ON" if led_status else "OFF")
        client.publish(STATE_TOPIC, payload, retain=True)
        return

    success = run_scraper(target_state)

    if success:
        # Inform HA that the command was successful
        led_status = target_state
        client.publish(STATE_TOPIC, payload, retain=True)
    else:
        # If it fails, report the opposite to 'snap' the toggle back in the UI
        revert_state = "OFF" if target_state else "ON"
        client.publish(STATE_TOPIC, revert_state, retain=True)


def setup_ha_discovery(client):
    """Registers a single toggle switch in Home Assistant."""
    config_payload = {
        "name": "Cisco Switch LEDs",
        "unique_id": "cisco_sg200_led_toggle",
        "command_topic": COMMAND_TOPIC,
        "state_topic": STATE_TOPIC,
        "availability_topic": AVAILABILITY_TOPIC,
        "payload_on": "ON",
        "payload_off": "OFF",
        "state_on": "ON",
        "state_off": "OFF",
        "device": {"identifiers": ["cisco_sg200_01"], "name": "Cisco Network Switch"},
    }
    client.publish(f"{TOPIC_BASE}/config", json.dumps(config_payload), retain=True)


def main():
    client = mqtt.Client()
    client.username_pw_set(getenv("MQTT_USER"), getenv("MQTT_PASSWORD"))

    client.on_connect = on_connect
    client.on_message = on_message

    # Enable a Will message: if the script crashes, HA shows the switch as 'Unavailable'
    client.will_set(AVAILABILITY_TOPIC, "offline", retain=True)

    client.connect(getenv("MQTT_BROKER"), int(getenv("MQTT_PORT", 1883)))

    try:
        client.loop_forever()
    except KeyboardInterrupt:
        client.publish(AVAILABILITY_TOPIC, "offline", retain=True)
        logger.info("Service stopped.")


if __name__ == "__main__":
    main()
