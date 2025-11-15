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
import winsound
from supabase import create_client, Client
import os

# 创建一个解析器
parser = argparse.ArgumentParser(description="Australian National University (ANU)")

# 添加命令行参数
parser.add_argument('--start', type=int, default=0, help="起始页码（从0开始）")
parser.add_argument('--end', type=int, default=99999, help="最大页码（安全限制）")
parser.add_argument('--port', type=str, help="Chrome调试端口")
parser.add_argument('--supabase_url', type=str, help="Supabase项目URL（可选，优先使用环境变量SUPABASE_URL）")
parser.add_argument('--supabase_key', type=str, help="Supabase API密钥（可选，优先使用环境变量SUPABASE_KEY）")

# 解析命令行参数
args = parser.parse_args()

# Supabase配置
SUPABASE_URL = args.supabase_url or os.getenv("SUPABASE_URL")
SUPABASE_KEY = args.supabase_key or os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("请提供Supabase URL和Key（通过环境变量SUPABASE_URL/SUPABASE_KEY或命令行参数）")

# 初始化Supabase客户端
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ========== Chrome配置 ==========
options = webdriver.ChromeOptions()
chrome_options = Options()
chrome_options.debugger_address = "127.0.0.1:" + args.port

driver = webdriver.Chrome(options=chrome_options)

def isTruePerson():
    try:
        isTruePerson = driver.find_element(By.XPATH, r'/html/body/div[1]/div/h1')
        if isTruePerson.text == 'researchportalplus.anu.edu.au':
            winsound.Beep(1000, 1000)
            time.sleep(30)
    except:
        pass

def get_last_page_number():
    """获取最后一页的页码"""
    try:
         # 获取所有分页链接
        page_links = driver.find_elements(By.XPATH, '//*[@id="main-content"]/div/div[2]/nav/ul/li/a')
        
        max_page = 0
        for link in page_links:
            href = link.get_attribute('href')
            # 提取page=后面的数字
            match = re.search(r'page=(\d+)', href)
            if match:
                page_num = int(match.group(1))
                max_page = max(max_page, page_num)
        
        return max_page if max_page > 0 else None
       
    except:
        return None

def insert_to_supabase(data):
    """将数据插入到Supabase表中"""
    try:
        response = supabase.table("original_australian_national_university_anu").insert(data).execute()
        return response
    except Exception as e:
        print(f"Error inserting to Supabase: {e}")
        return None

# 获取起始页
current_page = args.start

# 首先访问起始页以获取总页数
driver.get(f'https://researchportalplus.anu.edu.au/en/persons/?page={current_page}')
isTruePerson()
time.sleep(3)

# 获取最后一页的页码
last_page = get_last_page_number()
if last_page:
    print(f"总页数: {last_page}")
else:
    print("无法获取总页数，使用默认值999")
    last_page = 999

# 从起始页到最后一页
for num in range(current_page, last_page + 1):
    driver.get(f'https://researchportalplus.anu.edu.au/en/persons/?page={num}')
    isTruePerson()
    print(f"第 {num} 页，标题: {driver.title}")
    time.sleep(3)

    try:
        list_items0 = driver.find_elements(By.XPATH, r'//*[@id="main-content"]/div/div[2]/ul/li[*]/div/div[1]/h3/a')
    except:
        print(f"第 {num} 页没有找到人员列表")
        continue
        
    teacher_list = []
    for num0, list0 in enumerate(list_items0): 
        href = list0.get_attribute('href')
        teacher_list.append(href)

    print(f"第 {num} 页找到 {len(teacher_list)} 个人员")

    for href in teacher_list:
        all_data = {}
        
        try:
            driver.get(href)
            isTruePerson()
            time.sleep(3)
            print(f"正在处理: {driver.current_url}")
            all_data['website'] = driver.current_url
        except:
            continue
        
        try:
            name = driver.find_element(By.XPATH, r'//*[@id="page-content"]/div[1]/section/div[1]/div/div/section[1]/div[2]/div[1]/h1')
            pattern = re.compile(r'^((?:Honorary Associate )?Professor|(?:Associate )?Professor|Dr|Mr|Ms|Mrs|A/Prof|AsPr)\s+(.+)$')
            m = pattern.match(name.text)
            if m:
                all_data['title'] = m.group(1)
                all_data['full name'] = m.group(2)
            else:
                all_data['full name'] = name.text
        except:
            print(f"无法获取姓名: {href}")
            continue
        
        try:
            position = driver.find_element(By.XPATH, r'//*[@id="page-content"]/div[1]/section/div[1]/div/div/section[1]/div[2]/div[1]/div[1]/p')
            all_data['position'] = position.text
        except:
            pass

        try:
            org_unit = driver.find_element(By.XPATH, r'//*[@id="page-content"]/div[1]/section/div[1]/div/div/section[1]/div[2]/div[1]/div[2]/ul/li/a/span')
            all_data['org unit'] = org_unit.text
        except:
            pass
        
        try:
            orcid = driver.find_element(By.XPATH, r'//*[@id="page-content"]/div[1]/section/div[1]/div/div/section[1]/div[2]/div[1]/div[3]/a[2]')
            all_data['orcid'] = orcid.text
        except:
            pass

        # 获取Google Scholar链接
        try:
            google_scholar_link = driver.find_element(By.XPATH, '//a[contains(@href, "scholar.google.com")]')
            all_data['google scholar'] = google_scholar_link.get_attribute('href')
            print(f"  Google Scholar: {all_data['google scholar']}")
        except:
            all_data['google scholar'] = None
            print("  未找到Google Scholar链接")

        try:                                        
            email = driver.find_element(By.XPATH, r'//*[@id="page-content"]/div[1]/section/div[1]/div/div/section[1]/div[2]/div[2]/ul/li[2]/span[2]/a | //*[@id="page-content"]/div[1]/section/div[1]/div/div/section[1]/div[2]/div[2]/ul/li/span[2]/a')
            # print(email.text)
            all_data['email'] = email.text
        except:
            pass
        
        all_info = '' 
        try:
            research = driver.find_element(By.XPATH, r'//*[@id="main-content"]/section[1]/div/div[2]/div[1]/div/div')
            text_list0 = [p.get_attribute('innerText') for p in research.find_elements(By.XPATH, './/p | ./ul/li')]
            all_info = '\n'.join(text_list0)
            if all_info:
                all_info += '\n'
                all_data['brief introduction'] = all_info
        except Exception as e:
            print(f"获取简介时出错: {e}")


        # 提取所有 li 标签中的 span 内容
        try:
            # 获取该 ul 下的所有 li 元素
            list_items = driver.find_elements(By.XPATH, '//*[@id="main-content"]/section[4]/div[1]/div/div[2]/ul/li')
            
            print(f"  找到 {len(list_items)} 个 li 元素")
            
            for index, li in enumerate(list_items, start=1):
                try:
                    # 在每个 li 内部查找 h3/a/span
                    span_element = li.find_element(By.XPATH, './div[1]/div[1]/h3/a/span')
                    text_content = span_element.text.strip()
                    
                    if text_content:
                        all_info += text_content + '\n'  # 追加到 all_info
                        print(f"  第 {index} 个 li: {text_content}")
                except:
                    # 如果某个 li 没有这个结构，跳过
                    continue
                    
        except Exception as e:
            print(f"  提取 li 列表内容失败: {e}")

        
        
        print(f"准备插入数据: {all_data.get('full name', 'Unknown')}")
        
        # 插入到Supabase
        result = insert_to_supabase(all_data)
        if result:
            print(f"成功插入: {all_data.get('full name', 'Unknown')}")
        else:
            print(f"插入失败: {all_data.get('full name', 'Unknown')}")
            
        time.sleep(random.uniform(2, 4))  # 随机延迟2-4秒


