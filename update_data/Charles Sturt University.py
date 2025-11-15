from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
import time
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
import json
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import random
import argparse
import re
import os
from supabase import create_client, Client

# Supabase configuration - Get from environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Please set SUPABASE_URL and SUPABASE_KEY environment variables")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 创建一个解析器
parser = argparse.ArgumentParser(description="Process some integers.")
parser.add_argument('--port', type=str, required=True, help="The port of the remote debugging Chrome instance.")
args = parser.parse_args()

options = webdriver.ChromeOptions()
chrome_options = Options()
chrome_options.debugger_address = "127.0.0.1:" + args.port

driver = webdriver.Chrome(options=chrome_options)
final_data = []

driver.get('https://www.csu.edu.au/research/gulbali/find-experts')
print(driver.title)
time.sleep(5)

teacher_list = []

hrefs = driver.find_elements(By.XPATH, r'//div/div[*]/div/div/div[2]/h2/a')
for href in hrefs:
    teacher_list.append(href.get_attribute('href'))

for href in teacher_list:
    all_data = {}
    
    try:
        driver.get(href)
        time.sleep(3)
        print(driver.current_url)
        all_data['website'] = driver.current_url
    except:
        continue

    try:
        name_element = driver.find_element(By.XPATH, r'//*[@id="research_staff_profile"]/section[1]/h2 | //*[@id="content-banner-4201251"]/div[2]/h2')
        pattern = re.compile(r'^((?:Honorary Associate )?Professor|(?:Associate )?Professor|Dr\.|Mr|Ms|Mrs|Doctor|A/Prof|AsPr)\s+(.+)$')
        match = pattern.match(name_element.text)
        if match:
            all_data['full name'] = match.group(2).strip()
            all_data['title'] = match.group(1).strip()
        else:
            all_data['full name'] = name_element.text.strip()
            all_data['title'] = None
    except:
        pass

    try:
        position = driver.find_element(By.XPATH, r'//*[@id="research_staff_profile"]/section[1]/h3 | //*[@id="content-banner-4201251"]/div[2]/h3')
        all_data['position'] = [position.text]
    except:
        pass

    try:
        org_unit = driver.find_element(By.XPATH, r'//*[@id="research_staff_profile"]/section[1]/p')
        all_data['org unit'] = org_unit.text
    except:
        pass

    try:
        email = driver.find_element(By.XPATH, r'//*[@id="research_staff_profile"]/section[1]/div[1]/div[2]/ul/li[2]/a | //*[@id="staff-bio-contact"]/div[1]/ul/li[span[text()="Email"]]/a')
        all_data['email'] = email.text
    except:
        pass

    try:
        all_info = ''
        research = driver.find_element(By.XPATH, r'//*[@id="staff-bio-contact"]/div[*]')
        text_list0 = [p.text for p in research.find_elements(By.XPATH, './/p')]
        all_info += '\n'.join(text_list0)
        all_data['brief introduction'] = all_info
    except:
        pass

    # Set default values for fields not being scraped
    all_data['telephone'] = None
    all_data['orcid'] = None

    try:
        # Upsert data into Supabase (insert or update if website exists)
        response = supabase.table("original_charles_sturt_university").upsert(
            all_data,
            on_conflict='website'  # Specify the unique column for conflict resolution
        ).execute()
        
        if response.data:
            print(f"Successfully saved: {all_data.get('full name', 'Unknown')}")
        elif response.error:
            print(f"Error saving data: {response.error}")
            
    except Exception as e:
        print(f"Supabase error: {str(e)}")
        continue

    print(all_data)
    final_data.append(all_data)
    time.sleep(3)

driver.quit()