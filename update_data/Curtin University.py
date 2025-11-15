from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
import time
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
import json
import argparse
import re
import os
import sys
from supabase import create_client, Client

# 创建一个解析器 - 只保留端口参数
parser = argparse.ArgumentParser(description="Curtin University staff profile scraper")
parser.add_argument('--port', type=str, default='9222', required=True, help="The Chrome debugger port number.")
parser.add_argument('--supabase_url', type=str, help="Supabase项目URL（可选，优先使用环境变量SUPABASE_URL）")
parser.add_argument('--supabase_key', type=str, help="Supabase API密钥（可选，优先使用环境变量SUPABASE_KEY）")

args = parser.parse_args()

# --- Supabase Setup ---
# 从环境变量获取 Supabase URL 和 Key
supabase_url: str = args.supabase_url or os.getenv("SUPABASE_URL")
supabase_key: str = args.supabase_key or os.getenv("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    raise ValueError("请设置环境变量 SUPABASE_URL 和 SUPABASE_KEY")

# 初始化 Supabase 客户端
supabase: Client = create_client(supabase_url, supabase_key)
TABLE_NAME = "original_charles_darwin_university_cdu" # 您提供的表名


options = webdriver.ChromeOptions()
chrome_options = Options()
chrome_options.debugger_address = "127.0.0.1:" + args.port
driver = webdriver.Chrome(options=chrome_options)

# ==================== 自动检测总页数 ====================
print("=" * 60)
print("PHASE 1: 自动检测总页数")
print("=" * 60)

# 加载第一页来检测总结果数
initial_url = 'https://search.curtin.edu.au/results/people?start_rank=0&type=staff&q=all%2520Profile&collection=curtin-university&form=simple2&clive=curtin-staff-profiles'
print("加载第1页以检测总结果数...")
driver.get(initial_url)
time.sleep(3)

total_pages = 0

try:
    # 读取包含总结果信息的按钮
    results_button = driver.find_element(By.XPATH, '//*[@id="root"]/main/div/div[3]/div/div/div/nav/div/button[3]')
    button_text = results_button.text.strip()
    
    print(f"按钮文本: '{button_text}'")
    
    # 提取所有数字
    numbers = re.findall(r'\d+', button_text)
    
    if numbers:
        # 最大的数字是总结果数
        total_pages = max(map(int, numbers))

        print(f"✓ 计算出 {total_pages} 个总页数")
    else:
        print(f"⚠ 在按钮文本中未找到数字")
        driver.quit()
        sys.exit(1)
        
except Exception as e:
    print(f"⚠ 读取分页按钮失败: {e}")
    driver.quit()
    sys.exit(1)

print(f"✓ 将处理第 1 页至第 {total_pages} 页")
print("=" * 60)
# ==================== 结束自动检测 ====================

final_data = []

# 从第1页开始处理所有页面（range是左闭右开）
for num in range(1, total_pages + 1):  # 必须从1开始，因为公式是 (num-1)*10+1
    current_start_rank = (num - 1) * 10 + 1
    print(f"\n{'='*50}")
    print(f"处理第 {num}/{total_pages} 页 (start_rank={current_start_rank})")
    print(f"{'='*50}")
    
    driver.get(f'https://search.curtin.edu.au/results/people?start_rank=0&type=staff&q=all%2520Profile&collection=curtin-university&form=simple2&clive=curtin-staff-profiles')
    print(f"页面标题: {driver.title}")
    time.sleep(3)
                                                   
    try:                                    
        list_items0 = driver.find_elements(By.XPATH, r'//*[@id="root"]/main/div/div[3]/div/div/div/a[*]')
        teacher_list = [item.get_attribute('href') for item in list_items0]
        print(f"本页找到 {len(teacher_list)} 个教师档案")
    except Exception as e:
        print(f"⚠ 查找档案链接失败: {e}")
        continue

    for href in teacher_list:
        all_data = {}
        
        try:
            driver.get(href)
            time.sleep(3)
            print(f"正在处理: {driver.current_url}")
            all_data['website'] = driver.current_url
        except:
            continue
        
        try:                                            
            name = driver.find_element(By.XPATH, r'//*[@id="public-staff-profile"]/section/h2')
            pattern = re.compile(r'^((?:Honorary Associate )?Professor|(?:Associate )?Professor|Dr|Mr|Ms|Mrs|Miss|A/Prof|AsPr)\s+(.+)$')
            m = pattern.match(name.text)
            all_data['full name'] = m.group(2)
            all_data['title'] = m.group(1)
        except:
            continue
        
        try:                                            
            position = driver.find_element(By.XPATH, r'//*[@id="public-staff-profile"]/section/section[1]/dl/dt[contains(text(), "Position")]/following-sibling::dd[1]')
            all_data['position'] = [position.text]
        except:
            pass

        try:                                            
            org_unit = driver.find_element(By.XPATH, r'//*[@id="public-staff-profile"]/section/section[1]/dl/dt[contains(text(), "School")]/following-sibling::dd[1]')
            all_data['org unit'] = org_unit.text
        except:
            pass
        
        try:                                        
            orcid = driver.find_element(By.XPATH, r'//*[@id="public-staff-profile"]/section/section[1]/dl/dt[contains(text(), "ORCID")]/following-sibling::dd[1]')
            all_data['orcid'] = orcid.text
        except:
            pass

        try:                                        
            google_scholar = driver.find_element(By.XPATH, r'//*[@id="public-staff-profile"]/section/section[1]/dl/dt[contains(text(), "google")]/following-sibling::dd[1]')
            all_data['google scholar'] = google_scholar.text
        except:
            pass

        try:                                        
            telephone = driver.find_element(By.XPATH, r'//*[@id="public-staff-profile"]/section/section[1]/dl/dt[contains(text(), "Telephone")]/following-sibling::dd[1]')
            all_data['telephone'] = '+61 ' + telephone.text
        except:
            pass

        try:                                        
            email = driver.find_element(By.XPATH, r'//*[@id="public-staff-profile"]/section/section[1]/dl/dt[contains(text(), "Email")]/following-sibling::dd[1]')
            all_data['email'] = email.text
        except:
            pass

        all_info = '' 
        try:                                           
            research = driver.find_element(By.XPATH, r'/h2[contains(text(), "Brief Summary")]/following-sibling::div')
            text_list0 = [p.get_attribute('innerText') for p in research.find_elements(By.XPATH, './/p | ./ul/li')]
            all_info += '\n'.join(text_list0)
        except Exception as e:
            pass

        try:                                           
            research = driver.find_element(By.XPATH, r'//h2[contains(text(), "Overview")]/following-sibling::div')
            text_list0 = [p.get_attribute('innerText') for p in research.find_elements(By.XPATH, './/p | ./ul/li')]
            all_info += '\n'.join(text_list0)
        except Exception as e:
            pass

        if all_info != '':
            all_data['brief introduction'] = all_info
        
        # 数据存入Supabase
        try:
            response = supabase.table('original_curtin_university').upsert(
                all_data,  # 数据字典
                on_conflict='website'  # 冲突检测列
            ).execute()
            
            if response.data:
                print(f"  ✓ 成功保存/更新数据")
                
            else:
                print(f"  ✗ 保存失败: {response}")
                
        except Exception as e:
            print(f"  ✗ Supabase操作失败: {e}")
        
        time.sleep(3)


# 关闭浏览器
driver.quit()
