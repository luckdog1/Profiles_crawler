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
from selenium.webdriver.support.ui import Select
import re
import argparse
import os
from supabase import create_client, Client



# 创建一个解析器
parser = argparse.ArgumentParser(description="Australian Catholic University (Brisbane campus)")

# 添加命令行参数
parser.add_argument('--start', type=int, default=0, help="起始页码（从0开始）")
parser.add_argument('--end', type=int, default=999, help="最大页码（安全限制）")
parser.add_argument('--port', type=str, default=None,  # 添加 default=None
                    help="Chrome调试端口")
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
# 根据是否提供端口选择浏览器启动方式
# if args.port:
#     # 使用现有浏览器（需要提前启动 chrome --remote-debugging-port=端口）
#     print(f"连接到已打开的Chrome浏览器（端口: {args.port}）")
#     chrome_options = Options()
#     chrome_options.debugger_address = f"127.0.0.1:{args.port}"
#     driver = webdriver.Chrome(options=chrome_options)
# else:
#     # 启动新浏览器
#     print("启动新的Chrome浏览器实例")
#     chrome_options = Options()
#     # 可选：添加无头模式或其他配置
#     # chrome_options.add_argument('--headless')
#     # chrome_options.add_argument('--no-sandbox')
#     driver = webdriver.Chrome(options=chrome_options)
options = webdriver.ChromeOptions()
chrome_options = Options()
chrome_options.debugger_address = "127.0.0.1:" + args.port

driver = webdriver.Chrome(options=chrome_options)


# 初始化页码计数器
current_page = args.start
total_processed = 0

while current_page < args.end:
    # 构建当前页的URL
    url = f'https://www.acu.edu.au/searchresearchers?searchStudioQuery=&facets=fq%3Dresearcherfilter_s%3A%22Researcher%22&page=researcher&isGrid=false&orderBy=&start={current_page * 10}&facetFilters=1&model=Default'
    print(f"\n=== 处理第 {current_page} 页 ===")
    print(f"URL: {url}")
    driver.get(url)
    time.sleep(5)

    try:
        # 等待并点击"Allow all cookies"按钮
        allow_all_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll"]'))
        )
        allow_all_button.click()
        print("已点击'Allow all cookies'按钮")
        time.sleep(3)  # 等待弹窗消失
    except Exception as e:
        print(f"未找到cookie按钮或点击失败: {e}")
        
    # 检查页面是否没有结果
    try:
        no_results = driver.find_element(By.XPATH, r'//*[@id="searchstax-search-results"]//div[contains(text(), "No results found")]')
        if no_results.is_displayed():
            print("未找到结果，停止...")
            break
    except NoSuchElementException:
        pass
    
    # 获取研究人员链接
    list_items0 = driver.find_elements(By.XPATH, r'//*[@id="searchstax-search-results"]/div[*]/div/div/div/div[1]/a')

    teacher_list = []
    for list0 in list_items0: 
        href = list0.get_attribute('href')
        if href:
            teacher_list.append(href)

    if not teacher_list:
        print("本页未找到研究人员链接，停止...")
        break

    # 处理每个研究人员
    for href in teacher_list:
        all_data = {}
        
        try:
            driver.get(href)
            time.sleep(3)
            all_data['website'] = driver.current_url
            print(f"\n  处理: {driver.current_url}")
        except:
            print(f"  加载失败，跳过: {href}")
            continue

        # 提取姓名
        try:                                                   
            name = driver.find_element(By.XPATH, r'/html/body/div[1]/div[4]/div/section/h2 | /html/body/div[1]/div[4]/div/section/h3 | /html/body/div[1]/div[4]/div/section/div/div[1]/h3')
            print(f"  姓名: {name.text}")
        except:
            print("  提取姓名失败，跳过...")
            continue
        
        # 解析姓名和职称
        try:
            pattern = re.compile(r'^((?:Honorary Associate )?Professor|(?:Associate )?Professor|Dr|Mr|Ms|Mrs|A/Prof)\s+(.+)$')
            m = pattern.match(name.text)
            if m:
                all_data['title'] = m.group(1)
                all_data['full name'] = m.group(2)
            else:
                all_data['full name'] = name.text
        except:
            all_data['full name'] = name.text

        # 提取其他信息
        # 提取职位和单位信息
        try:
            position_unit = driver.find_element(By.XPATH, r'/html/body/div[1]/div[4]/div/section/h3 | /html/body/div[1]/div[4]/div/section//em')
            html_content = position_unit.get_attribute('innerHTML')
            
            parts = [p.strip().strip('"') for p in html_content.split('<br>') if p.strip()]
            
            if len(parts) >= 2:
                all_data['position'] = [parts[0]]
                all_data['org unit'] = parts[1]
                print(f"  职位: {parts[0]}")
                print(f"  单位: {parts[1]}")
            elif len(parts) == 1:
                # 假设第一个文本是职位
                all_data['org unit'] = parts[0]
                print(f"  单位: {parts[0]}")
                
        except NoSuchElementException:
            print("  未找到职位/单位信息")

        try:                                   
            telephone = driver.find_element(By.XPATH, r'/html/body/div[1]/div[4]/div/section//p[contains(.,"Phone")]')
            all_data['telephone'] = telephone.text
        except:
            pass

        try:                                                 
            email = driver.find_element(By.XPATH, r'/html/body/div[1]/div[4]/div/section//p[contains(.,"Email:")]')
            all_data['email'] = email.text
        except:
            pass

        try:                                          
            orcid = driver.find_element(By.XPATH, r'/html/body/div[1]/div[4]/div/section//p[contains(.,"ORCID ID:")]')
            all_data['orcid'] = orcid.text
        except:
            pass

        # 提取简介
        try:                               
            info_list = driver.find_elements(By.XPATH, r'/html/body/div[1]/div[4]/div/section/p[*] | /html/body/div[1]/div[4]/div/section/p | /html/body/div[1]/div[4]/div/section/h4')
            all_info = ''
            i = 0
            while(i < len(info_list)):
                while i < len(info_list) and len(info_list[i].find_elements(By.XPATH, r'./strong')) == 1:
                    i += 1
                while i < len(info_list) and info_list[i].tag_name != 'h4':
                    all_info += info_list[i].text + ' '
                    i += 1
                break
            if all_info.strip():
                all_data['brief introduction'] = all_info.strip()  # 修改字段名以匹配表结构
        except:
            pass

        # 数据存入Supabase
        try:
            # 使用upsert操作：如果website存在则更新，否则插入
            # 指定冲突处理列：website
            response = supabase.table('original_australian_catholic_university_brisbane_campus').upsert(
                all_data,  # 数据字典
                on_conflict='website'  # 冲突检测列
            ).execute()
            
            if response.data:
                print(f"  ✓ 成功保存/更新数据")
                total_processed += 1
            else:
                print(f"  ✗ 保存失败: {response}")
                
        except Exception as e:
            print(f"  ✗ Supabase操作失败: {e}")
        
        time.sleep(3)
    
    # 检查下一页按钮是否禁用
    try:
        disabled_next_button = driver.find_element(By.CSS_SELECTOR, 'a[aria-label="Next"][disabled="disabled"]')
        print(f"\n=== 下一页按钮已禁用（灰色），在第 {current_page} 页停止 ===")
        break
    except NoSuchElementException:
        print(f"  下一页按钮可用，继续到第 {current_page + 1} 页")
        current_page += 1
        continue

print(f"\n=== 完成 ===")
print(f"处理页数: {current_page - args.start + 1}")
print(f"总共处理研究人员: {total_processed}")

# 关闭浏览器
driver.quit()