from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class Scraper:
    def __init__(self, url: str, username: str, password: str):
        options = Options()
        options.add_argument("--headless")

        self.driver = webdriver.Firefox(options=options)

        if url is None or username is None or password is None:
            raise ValueError("Values cannot be None")

        self.__url = url
        self.__username = username
        self.__password = password

        self.__skip_apply = False

    def __enter__(self):
        self.driver.get(self.__url)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__save_and_logout()
        self.driver.quit()

    def run(self, turn_on: bool):
        self.__fill_credentials()
        self.__wait_for_page_loading()
        self.__navigate_to_led_settings()

        self.__manage_leds(turn_on)

    def __fill_credentials(self):
        elem = self.driver.find_element(By.NAME, "userName")
        elem.clear()
        elem.send_keys(self.__username)
        elem.send_keys(Keys.TAB)

        elem = self.driver.find_element(By.ID, "password")
        elem.clear()
        elem.send_keys(self.__password)
        elem.send_keys(Keys.ENTER)

    def __wait_for_page_loading(self):
        try:
            WebDriverWait(self.driver, 100).until(
                EC.invisibility_of_element((By.ID, "dvProgBar"))
            )

            WebDriverWait(self.driver, 100).until(
                EC.invisibility_of_element((By.ID, "dvProgVeil"))
            )
        finally:
            pass
    
    def __navigate_to_led_settings(self):
        try:
            element = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//tr[5]/td/table/tbody/tr/td/img"))
            )

            WebDriverWait(self.driver, 100).until(
                EC.invisibility_of_element((By.ID, "dvProgVeil"))
            )

            element.click()


            element = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//tr[10]/td/a/img"))
            )
            element.click()

            element = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//a[@id='NAV_12']"))
            )
            element.click()
        finally:
            pass
    
    def __manage_leds(self, turn_on: bool):
        iframe = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//iframe[@id='mainFrame_gw']"))
        )

        # Switch to the iframe
        self.driver.switch_to.frame(iframe)

        checkbox = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, "//input[@id='chkLED']"))
        )

        if checkbox.is_selected() and not turn_on:
            print("LED is already ON. Turning it OFF.")
            checkbox.click()  # Uncheck the checkbox to turn the LED off
        elif not checkbox.is_selected() and turn_on:
            print("LED is already OFF. Turning it ON.")
            checkbox.click()  # Check the checkbox to turn the LED on
        else:
            self.__skip_apply = True
            print(f"LED is already {'ON' if turn_on else 'OFF'}. No action needed.")
    
    def __save_and_logout(self):
        if not self.__skip_apply:
            apply_button = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, "//a[@id='defaultButton']"))
            )

            apply_button.click()

            try:
                WebDriverWait(self.driver, 10).until(
                    EC.visibility_of_element_located((By.XPATH, "//div[@id='pageMessageLine0']"))
                )
            except:
                pass

        self.driver.switch_to.default_content()

        logout_button = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, "//a[@id='lnkLogout']"))
        )

        logout_button.click()

        try:
            WebDriverWait(self.driver, 10).until(
                EC.number_of_windows_to_be(2)  # Wait for exactly 2 windows
            )

            # Get the window handles (list of open windows/tabs)
            windows = self.driver.window_handles

            # Switch to the new window (the second window/tab opened)
            self.driver.switch_to.window(windows[1])


            confirm_logout = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, "//a[@id='btnOk']"))
            )

            confirm_logout.click()
        except:
            pass
