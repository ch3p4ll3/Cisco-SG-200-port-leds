# Cisco SG-200-PORT-LEDS

This project automates the toggling of physical Port LEDs on Cisco SG-200 series switches using Selenium. It operates as a persistent MQTT bridge, allowing Home Assistant to control the switch via a single toggle entity.

## 1. Setup with `uv`

Ensure you have [uv](https://github.com/astral-sh/uv) installed.

```bash
# Install dependencies and create the virtual environment
uv sync
```

## 2. Configuration (`.env`)

Create a `.env` file in the root directory to store your credentials and broker information.

```ini
# Cisco Switch Credentials
SWITCH_URL=http://192.168.1.254
SWITCH_USERNAME=admin
SWITCH_PASSWORD=your_secure_password

# MQTT Broker Settings
MQTT_BROKER=192.168.1.50
MQTT_PORT=1883
MQTT_USER=mqtt_user
MQTT_PASSWORD=mqtt_password
```

## 3. Usage

The script is now designed to run as a persistent service that listens for MQTT messages from Home Assistant.

**Start the MQTT Bridge:**
```bash
uv run python3 -m src.main
```

**Manual Overrides (CLI):**
You can still trigger the scraper manually without the MQTT loop if needed:
```bash
uv run python3 -m src.main --active
uv run python3 -m src.main --no-active
```

---

## 4. Home Assistant Integration

This project uses **MQTT Discovery**. You do **not** need to manually add switches to `configuration.yaml`. 

1. Ensure the MQTT Integration is active in Home Assistant.
2. Run `uv run python3 -m src.main`.
3. The script will automatically publish a discovery payload.
4. A new entity named `switch.cisco_switch_leds` will appear in your Home Assistant dashboard automatically.

### How it Works
* **Discovery**: Upon startup, the script registers a single toggle switch with Home Assistant.
* **State Reporting**: The script publishes to the `state` topic to ensure the UI toggle matches the physical state of the switch LEDs, removing "Unknown" status.
* **Availability**: If the script stops running, the switch will automatically show as `unavailable` in HA via an MQTT "Last Will and Testament" message.

---

## 5. Docker Deployment

If running in Docker, ensure your container stays active to listen for MQTT commands:

```yaml
services:
  cisco-led-bridge:
    build: .
    volumes:
      - ./data:/usr/local/app/data
      - /etc/localtime:/etc/localtime:ro
    env_file: ".env"
    restart: unless-stopped
```