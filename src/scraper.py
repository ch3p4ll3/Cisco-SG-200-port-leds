import binascii
import http.cookiejar
import re
import urllib.request
import xml.etree.ElementTree as ET

from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA


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

    def __enter__(self):
        self._login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # TODO: Add logout logic here if the Cisco API supports it
        pass

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
        url = f"{self.base_url}/config/device/wcd?{{EncryptionSetting}}"
        req = urllib.request.Request(
            url, headers={"Referer": f"{self.base_url}/config/log_off_page.htm"}
        )
        with self.opener.open(req, timeout=10) as resp:
            data = resp.read().decode("utf-8")

        match = re.search(r"<rsaPublicKey>(.*?)</rsaPublicKey>", data, re.DOTALL)
        if not match:
            raise Exception("RSA public key not found")
        return RSA.import_key(match.group(1).strip())

    def _encrypt_credentials(self, rsa_key):
        plain = f"user={self.username}&password={self.password}&ssd=true&"
        cipher = PKCS1_v1_5.new(rsa_key)
        encrypted = cipher.encrypt(plain.encode("utf-8"))
        return binascii.hexlify(encrypted).decode("ascii")

    def _login(self):
        # Pre-login cookies
        self._add_cookie("activeLangId", "English")
        self._add_cookie("isStackableDevice", "false")

        rsa_key = self._fetch_rsa_key()
        cred_hex = self._encrypt_credentials(rsa_key)

        login_url = f"{self.base_url}/config/System.xml?action=login&cred={cred_hex}"
        req = urllib.request.Request(
            login_url, headers={"Referer": f"{self.base_url}/config/log_off_page.htm"}
        )

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
                raise Exception(f"Login failed: {resp_text}")

            # Post-login cookies
            self._add_cookie("sessionID", session_id)
            self._add_cookie("userStatus", "ok")
            self._add_cookie("usernme", self.username)
            self._add_cookie("firstWelcomeBanner", "false")

    def get_led_status(self) -> bool:
        """Returns True if LEDs are ON, False if MASKED/OFF."""
        url = f"{self.base_url}/GW/wcd?{{file=/GW/Bridging/PortManagement/GreenEthernet_Props_master.xml}}{{GreenEthGlobalSetting}}{{EEEGlobalSetting}}"
        req = urllib.request.Request(url)
        with self.opener.open(req, timeout=10) as resp:
            data = resp.read().decode("utf-8")

        tree = ET.fromstring(data)
        led_state_element = tree.find(
            ".//DeviceConfiguration/GreenEthGlobalSetting/maskLedState"
        )

        if led_state_element is not None:
            # maskLedState '0' means LEDs are showing (ON)
            # maskLedState '1' means LEDs are masked (OFF)
            return led_state_element.text == "0"
        return False

    def _parse_status_code(self, data: str):
        tree = ET.fromstring(data)
        status = tree.find(".//ActionStatus/statusCode")

        if status is not None and status.text == "0":
            return True
        return False

    def run(self, state_on: bool):
        """Sets the LED state."""
        root = ET.Element("DeviceConfiguration")
        green_eth = ET.SubElement(root, "GreenEthGlobalSetting", action="set")
        led_state = ET.SubElement(green_eth, "maskLedState")

        # Logic: To turn ON, mask must be 0. To turn OFF, mask must be 1.
        led_state.text = "0" if state_on else "1"

        payload = ET.tostring(
            root, encoding="utf-8", method="xml", xml_declaration=True
        )

        headers = {
            "Content-Type": "data:text/xml;charset=utf-8",
            "Referer": f"{self.base_url}/home.htm",
        }

        url = f"{self.base_url}/GW/wcd"
        req = urllib.request.Request(url, data=payload, method="POST", headers=headers)

        with self.opener.open(req, timeout=10) as resp:
            data = resp.read().decode("utf-8")
            return self._parse_status_code(data)

        return False
