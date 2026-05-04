import binascii
import http.cookiejar
import re
import urllib.request
import xml.etree.ElementTree as ET
import logging

from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("CiscoScraper")


class Scraper:
    def __init__(self, url, username, password):
        self.base_url = url.rstrip("/")
        self.username = username
        self.password = password
        self.domain = self.base_url.split("://")[1].split("/")[0]

        # Initialize session components
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar)
        )
        self.opener.addheaders = [
            (
                "User-Agent",
                "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0",
            ),
            ("Accept", "*/*"),
            ("Connection", "keep-alive"),
        ]
        logger.debug(f"Scraper initialized for {self.base_url}")

    def __enter__(self):
        self._login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            logger.error(f"Execution failed: {exc_val}")
        self._logout()

    def _add_cookie(self, name, value):
        cookie = http.cookiejar.Cookie(
            version=0,
            name=name,
            value=value,
            port=None,
            port_specified=False,
            domain=self.domain,
            domain_specified=True,
            domain_initial_dot=False,
            path="/",
            path_specified=True,
            secure=False,
            expires=None,
            discard=False,
            comment=None,
            comment_url=None,
            rest={},
        )
        self.cookie_jar.set_cookie(cookie)

    def _fetch_rsa_key(self):
        logger.info("Fetching RSA public key from device...")
        url = f"{self.base_url}/config/device/wcd?{{EncryptionSetting}}"
        req = urllib.request.Request(
            url, headers={"Referer": f"{self.base_url}/config/log_off_page.htm"}
        )
        try:
            with self.opener.open(req, timeout=10) as resp:
                data = resp.read().decode("utf-8")

            match = re.search(r"<rsaPublicKey>(.*?)</rsaPublicKey>", data, re.DOTALL)
            if not match:
                logger.error("Failed to find <rsaPublicKey> in device response.")
                raise Exception("RSA public key not found")

            logger.debug("RSA public key successfully imported.")
            return RSA.import_key(match.group(1).strip())
        except Exception as e:
            logger.error(f"Error during RSA key fetch: {e}")
            raise

    def _encrypt_credentials(self, rsa_key):
        logger.debug("Encrypting credentials with RSA key...")
        plain = f"user={self.username}&password={self.password}&ssd=true&"
        cipher = PKCS1_v1_5.new(rsa_key)
        encrypted = cipher.encrypt(plain.encode("utf-8"))
        return binascii.hexlify(encrypted).decode("ascii")

    def _login(self):
        logger.info(f"Attempting login to {self.domain} as '{self.username}'")

        # Pre-login cookies
        self._add_cookie("activeLangId", "English")
        self._add_cookie("isStackableDevice", "false")

        rsa_key = self._fetch_rsa_key()
        cred_hex = self._encrypt_credentials(rsa_key)

        login_url = f"{self.base_url}/config/System.xml?action=login&cred={cred_hex}"
        req = urllib.request.Request(
            login_url, headers={"Referer": f"{self.base_url}/config/log_off_page.htm"}
        )

        try:
            with self.opener.open(req, timeout=10) as resp:
                resp_text = resp.read().decode("utf-8")
                status = self._parse_status_code(resp_text)

                # Extract sessionID from custom header
                session_id = None
                for header, value in resp.headers.items():
                    if header.lower() == "sessionid":
                        session_id = value.split(";")[0].strip()
                        break

                if not session_id or not status:
                    logger.error(f"Login failed. Device returned status: {status}")
                    raise Exception(f"Login failed: {resp_text}")

                # Post-login cookies
                self._add_cookie("sessionID", session_id)
                self._add_cookie("userStatus", "ok")
                self._add_cookie("usernme", self.username)
                self._add_cookie("firstWelcomeBanner", "false")
                logger.info("Successfully logged in and session ID captured.")
        except Exception as e:
            logger.error(f"Network error during login: {e}")
            raise

    def _logout(self):
        logger.info("Logging out...")
        logout_url = f"{self.base_url}/config/log_off_page.htm"
        headers = {
            "Referer": f"{self.base_url}/home.htm",
            "Connection": "keep-alive",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
        }
        req = urllib.request.Request(
            logout_url, data=b"", headers=headers, method="POST"
        )
        try:
            with self.opener.open(req, timeout=10) as resp:
                logger.info("Logout command sent successfully.")
        except Exception as e:
            logger.warning(
                f"Logout request failed (session may have already timed out): {e}"
            )

    def get_led_status(self) -> bool:
        """Returns True if LEDs are ON, False if MASKED/OFF."""
        logger.info("Checking current LED status...")
        url = f"{self.base_url}/GW/wcd?{{file=/GW/Bridging/PortManagement/GreenEthernet_Props_master.xml}}{{GreenEthGlobalSetting}}{{EEEGlobalSetting}}"

        try:
            req = urllib.request.Request(url)
            with self.opener.open(req, timeout=10) as resp:
                data = resp.read().decode("utf-8")

            tree = ET.fromstring(data)
            led_state_element = tree.find(
                ".//DeviceConfiguration/GreenEthGlobalSetting/maskLedState"
            )

            if led_state_element is not None:
                is_on = led_state_element.text == "0"
                logger.info(
                    f"LED Status is currently: {'ON' if is_on else 'OFF (Masked)'}"
                )
                return is_on

            logger.warning("Could not find LED state element in XML response.")
            return False
        except Exception as e:
            logger.error(f"Failed to retrieve LED status: {e}")
            return False

    def _parse_status_code(self, data: str):
        try:
            tree = ET.fromstring(data)
            status = tree.find(".//ActionStatus/statusCode")
            return status is not None and status.text == "0"
        except ET.ParseError:
            logger.error("Failed to parse XML response from device.")
            return False

    def run(self, state_on: bool):
        """Sets the LED state."""
        action_label = "ON" if state_on else "OFF"
        logger.info(f"Requesting to turn LEDs {action_label}...")

        root = ET.Element("DeviceConfiguration")
        green_eth = ET.SubElement(root, "GreenEthGlobalSetting", action="set")
        led_state = ET.SubElement(green_eth, "maskLedState")
        led_state.text = "0" if state_on else "1"

        payload = ET.tostring(
            root, encoding="utf-8", method="xml", xml_declaration=True
        )

        headers = {
            "Content-Type": "data:text/xml;charset=utf-8",
            "Referer": f"{self.base_url}/home.htm",
        }

        try:
            url = f"{self.base_url}/GW/wcd"
            req = urllib.request.Request(
                url, data=payload, method="POST", headers=headers
            )

            with self.opener.open(req, timeout=10) as resp:
                data = resp.read().decode("utf-8")
                success = self._parse_status_code(data)

                if success:
                    logger.info(f"Successfully changed LED state to {action_label}.")
                else:
                    logger.warning(
                        f"Device returned a non-zero status code during LED change: {data}"
                    )
                return success
        except Exception as e:
            logger.error(f"Failed to change LED state: {e}")
            return False
