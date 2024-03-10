import time
from selenium import webdriver
from bs4 import BeautifulSoup
import re
from selenium.webdriver.chrome.options import Options

chrome_options = Options()
chrome_options.add_argument("--headless")  # Запуск в headless режиме

def get_last_lines(file_path, num_lines):
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
        return [line.strip() for line in lines[-num_lines:]] if lines else []

def get_lines_with_tokens(file_path, tokens):
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
        return [line.strip() for line in lines if tokens in line] if lines else []
    
bebra_code = 0

def scrape_page():
    global bebra_code
    driver = webdriver.Chrome()
    driver.get("https://www.btctool.pro/hot-mint")

    last_refresh_time = time.time()
    refresh_interval = 300  # 5 минут в секундах

    while True:
        try:
            current_time = time.time()
            if current_time - last_refresh_time >= refresh_interval:
                driver.refresh()
                last_refresh_time = current_time
                print("страница update")

            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            items = soup.find_all('div', class_='rank-item item-wrap')

            for item in items:
                tokens = item.find('div', class_='item tokens').text
                protocol = item.find('div', class_='item protocol contentColor').text
                times = item.find('div', class_='item times contentColor').text

                wallets = item.find('div', class_='item wallets contentColor').text
                supply = item.find('div', class_='item supply contentColor').text

                supply_text_cleaned = re.sub(r'\D', '', supply)  # Keep only numbers
                number_text_cleaned = re.sub(r'\D', '', times)  # Keep only numbers
                if number_text_cleaned.isdigit():
                    number = int(number_text_cleaned)
                    data = f"{tokens} | {protocol} | {number} | {wallets} | {supply_text_cleaned}"

                    existing_tokens = [line.split(' | ')[0] for line in get_last_lines('times.txt', 5000)]
                    existing_tokens_above_2000 = [line.split(' | ')[0] for line in get_last_lines('times.txt', 5000) if int(line.split(' | ')[2]) >= 2000]
                    if number >= 500 and number < 2000:
                        if tokens not in existing_tokens:
                            data_to_write = True
                        else:
                            data_to_write = False
                    elif number > 2000:
                        if tokens not in existing_tokens_above_2000:
                            data_to_write = True
                        else:
                            data_to_write = False
                    else:
                        data_to_write = False

                    if data_to_write:
                        with open('times.txt', 'a', encoding='utf-8') as file:
                            print(f"записано {data}")
                            file.write(f"{data}\n")
        except Exception as e:
            print(f"An error occurred: {e}")
            driver.refresh()  # Refresh the webpage in case of an error

        time.sleep(3)  # Wait for 3 seconds before the next page request

if __name__ == '__main__':
    scrape_page()