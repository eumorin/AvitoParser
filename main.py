from config import url, host, user, password, db_name, google_code, mails
from selenium.webdriver.common.by import By
from selenium import webdriver
from selenium_stealth import stealth
import psycopg2
import time
import smtplib
from email.mime.text import MIMEText
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait

def new_ad(message):
    sender = "egorumorin182002@gmail.com"
    password = google_code

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()

    try:
        server.login(sender, password)
        msg = MIMEText(message)
        msg["Subject"] = "OMNIPORT GmbH: Новый товар на Авито"
        for mail in mails:
            server.sendmail(sender, mail, msg.as_string())

        print("The message was sent successfully")
    except Exception as ex:
        print(f"{ex}\nCheck your login or password again")

def get_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("start-maximized")

    options.add_argument("--headless") #Optional

    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    driver = webdriver.Chrome(options=options)

    stealth(driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
            )

    return driver

def page_has_loaded(driver):
    page_state = driver.execute_script('return document.readyState;')
    return page_state == 'complete'

# TODO: StaleElementReferenceException returns sometimes. Need to fix that
def parse_data(driver) -> dict:
    driver.get(url)
    wait = WebDriverWait(driver, 20)
    try:
        wait.until(page_has_loaded)
    except TimeoutException:
        print("Page has not been loaded")
        return "Failed"
    blocks = driver.find_elements(By.CSS_SELECTOR, '[class*="body-root"]')
    data = []
    for block in blocks:
        name = block.find_element(By.CSS_SELECTOR, '[class*="body-titleRow"] h3').text
        price = block.find_element(By.CSS_SELECTOR, '[class*="price-price"] meta[itemprop="price"]').get_attribute('content')
        product_url = block.find_element(By.CSS_SELECTOR, '[class*="body-titleRow"] a').get_attribute("href")
        data.append([name, price, product_url])
    return data


def db_check2(data):
    try:
        data_dict = {link: [name, price] for name, price, link in data}

        parsed_links = set(data_dict.keys())
        connection = psycopg2.connect(
            host=host,
            user=user,
            password=password,
            database=db_name
        )
        connection.autocommit = True

        with connection.cursor() as cursor:
            cursor.execute("""CREATE TABLE IF NOT EXISTS vehicles(
                                Id SERIAL PRIMARY KEY,
                                Name varchar(100) NOT NULL,
                                Price integer,
                                AvitoLink varchar(150));""")

        with connection.cursor() as cursor:
            cursor.execute("SELECT avitolink FROM vehicles;")
            existing_links = cursor.fetchall()
            existing_links = {k[0] for k in existing_links}
            old_links = existing_links - parsed_links
            for link in old_links:
                cursor.execute(f"DELETE FROM vehicles WHERE avitolink = %s;", (link, ))

            new_links = parsed_links - existing_links
            for link in new_links:
                name, price = data_dict[link]
                cursor.execute(f"INSERT INTO vehicles (Name, Price, AvitoLink) VALUES (%s, %s, %s);", (name, price, link))
            return [i for i in data if i[2] in new_links]
    except Exception as ex:
        print("[INFO] Error while working with PostgreSQL", ex)
    finally:
        if connection:
            connection.close()
            print("[INFO] PostgreSQL connection closed")

def main():
    while True:
        driver = get_driver()
        data = parse_data(driver)
        time.sleep(5)
        driver.quit()
        if data == "Failed":
            continue
        message = ""
        new_products = db_check2(data)
        print(new_products)
        if new_products:
            for data in new_products:
               message += f"В нашем профиле появилось новое объявление: {data[0]} стоимостью {data[1]} рублей\n{data[2]}\n\n"
            new_ad(message=message)
        time.sleep(600)

if __name__ == '__main__':
    main()
