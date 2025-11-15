import argparse
import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

# 命令行参数解析
parser = argparse.ArgumentParser(description="Scrape Deakin University experts data.")
parser.add_argument('--port', type=str, default='9222', required=True, help="The port number for Chrome debugger.")
args = parser.parse_args()

# Chrome 设置
chrome_options = Options()
chrome_options.debugger_address = "127.0.0.1:" + args.port
driver = webdriver.Chrome(options=chrome_options)

final_data = []
base_url = 'https://experts.deakin.edu.au/search?by=text&type=user'

try:
    # 首次加载页面以获取总页数
    driver.get(base_url)
    print("Loading initial page to determine total pages...")
    time.sleep(5)  # 等待动态内容加载

    # 获取总页数 (倒数第二个li标签中的按钮文本)
    total_xpath = '//*[@id="app"]/div/main/div/div[2]/div[3]/div[3]/div[1]/div[2]/nav/ul/li[8]/button'
    try:
        total_element = driver.find_element(By.XPATH, total_xpath)
        total_pages = int(total_element.text)
        print(f"Total pages detected: {total_pages}")
    except (NoSuchElementException, ValueError) as e:
        print(f"Warning: Could not detect total pages: {e}. Defaulting to 1 page.")
        total_pages = 1

    # 遍历所有页面
    for current_page in range(1, total_pages + 1):
        print(f"\n=== Processing Page {current_page}/{total_pages} ===")
        
        # 重新加载基础页面并导航到当前页 (保持原始脚本的稳定模式)
        driver.get(base_url)
        time.sleep(5)
        
        # 定位并操作分页选择器
        try:
            select_element = driver.find_element(By.CSS_SELECTOR, "select[aria-label='Pagination']")
            driver.execute_script("arguments[0].style.display = 'block';", select_element)  # 强制显示隐藏元素
            select = Select(select_element)
            select.select_by_value(str(current_page))
            time.sleep(3)  # 等待页面内容更新
        except Exception as e:
            print(f"Error navigating to page {current_page}: {e}")
            continue

        # 提取当前页面的教师链接
        teacher_link_xpath = r'//*[@id="app"]/div/main/div/div[2]/div[3]/div[3]/div[2]/div[*]/div[2]/div/a'
        list_items0 = driver.find_elements(By.XPATH, teacher_link_xpath)
        teacher_list = [item.get_attribute('href') for item in list_items0]
        print(f"Found {len(teacher_list)} teacher(s) on this page.")

        # 遍历教师个人页面获取详细信息
        for href in teacher_list:
            all_data = {}
            print(f"  Scraping: {href}")

            try:
                driver.get(href)
                time.sleep(2)
                all_data['website'] = driver.current_url
            except Exception as e:
                print(f"    Failed to load profile: {e}")
                continue

            try:
                title = driver.find_element(By.XPATH, r'//*[@id="app"]/div/main/div/div[2]/div[1]/div[2]/div[1]/div[2]/p')
                all_data['title'] = title.text
            except:
                pass
            
            try:
                full_name = driver.find_element(By.XPATH, r'//*[@id="app"]/div/main/div/div[2]/div[1]/div[2]/div[1]/div[2]/h1')
                all_data['full name'] = full_name.text
            except:
                continue  # 没有全名则跳过该记录

            try:
                position = driver.find_element(By.XPATH, r'//*[@id="app"]/div/main/div/div[2]/div[1]/div[2]/div[1]/div[2]/div/p[1]')
                all_data['position'] = [position.text]
            except:
                pass

            try:
                org_unit = driver.find_element(By.XPATH, r'//*[@id="app"]/div/main/div/div[2]/div[1]/div[2]/div[1]/div[2]/div/p[2]')
                all_data['org unit'] = org_unit.text
            except:
                pass

            all_info = '' 
            try:
                research = driver.find_element(By.XPATH, r'//*[@id="app"]/div/main/div/div[2]/div[2]/div[2]/div/div/div[2]/div | //*[@id="app"]/div/main/div/div[2]/div[2]/div[2]/div/div[1]/div[2]/div')
                text_list0 = [p.text for p in research.find_elements(By.XPATH, './/p')]
                all_info += '\n'.join(text_list0)
            except:
                pass

            try:
                research = driver.find_element(By.XPATH, r'//*[@id="app"]/div/main/div/div[2]/div[2]/div[2]/div/div[1]/div[2]/div')
                all_info += research.text
            except:
                pass
            
            all_data['brief introduction'] = all_info

            try:
                button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, r'button[data-qa="contactModalButton"]')))
                button.click()
                email = driver.find_element(By.XPATH, r'//*[@id="portalTarget"]/div[2]/div/div[2]/div/div/div/div/ul/li[1]/span/a | //*[@id="portalTarget"]/div[2]/div/div[2]/div/div/div/div/ul/li/span/a')
                all_data['email'] = email.get_attribute('href')
            except:
                pass
            
            # 仅当成功获取到全名时才保存数据
            if all_data.get('full name'):
                final_data.append(all_data)
                print(f"    -> Success: {all_data['full name']}")
            else:
                print(f"    -> Skipped: No full name found")

            time.sleep(2)  # 请求间隔

finally:
    # 保存所有数据到JSON文件
    if final_data:
        filename = 'Deakin University_all_pages.json'
        with open(filename, 'w', encoding='utf-8') as json_file:
            json.dump(final_data, json_file, ensure_ascii=False, indent=4)
        print(f"\n{'='*50}\nScraping complete! Data saved to '{filename}'.\nTotal records: {len(final_data)}")
    else:
        print("\nNo data was collected.")
    
    driver.quit()