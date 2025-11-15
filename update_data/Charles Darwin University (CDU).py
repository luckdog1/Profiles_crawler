import os
import re
import time
import argparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from supabase import create_client, Client

# --- Argument Parsing ---
parser = argparse.ArgumentParser(description="CQU Expert Scraper with Supabase integration.")
parser.add_argument('--port', type=str, required=True, help="The port of the remote debugging Chrome instance.")
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

# --- Selenium WebDriver Setup ---
chrome_options = Options()
chrome_options.debugger_address = f"127.0.0.1:{args.port}"
# chrome_options.page_load_strategy = 'eager' # 可选：如果页面加载慢，可以尝试这个

try:
    driver = webdriver.Chrome(options=chrome_options)
except Exception as e:
    print(f"连接到 Chrome 实例失败: {e}")
    print("请确保 Chrome 已以远程调试模式启动，例如: chrome.exe --remote-debugging-port=9222")
    exit()

# --- Main Scraping Logic ---
driver.get(r'https://www.cqu.edu.au/research/current-research/find-an-expert')
time.sleep(5) # 等待初始页面加载

# 点击 "Show More" 按钮以加载更多专家

# 初始化 total 为 None，后续动态读取
total = None
try:
    # 定位分页信息的 <p> 元素
    pagination_element = driver.find_element(By.XPATH, '//p[@class="funnelback-search_pagination_Go9_d"]')
    # 提取所有文本子节点
    text_nodes = pagination_element.find_elements(By.XPATH, './text()')
    # 总数是第4个文本节点（索引从0开始，所以是 [3]）
    if len(text_nodes) >= 4:
        total_text = text_nodes[3].get_attribute('textContent')  # 获取 "521"
        total = int(total_text.strip())  # 转换为整数
        print(f"动态读取的总数 total: {total}")
    else:
        print("分页文本节点不足，无法获取总数")
except Exception as e:
    print(f"读取总数失败: {e}")
    total = 512  # 降级方案：使用默认值

# 如果动态读取失败，使用默认值
if total is None:
    total = 512
    print("使用默认总数 total: 512")

current, total = 0, total  # 更新循环中的 total 值

while current < total: # 根据实际情况调整这个循环条件
    try:
        showing_element = driver.find_element(By.XPATH, r'//*[@id="skip-to-content"]/div/div/div/div/p')
        # 从 "Showing 1 to 20 of 512" 这样的文本中提取数字
        current, total_ = map(int, re.findall(r'\d+', showing_element.text))
        print(f"当前已加载: {current} / {total_}")

        # 定位并点击 "Show More" 按钮
        wait = WebDriverWait(driver, 10)
        btn = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[@aria-label="Show More"]')))
        
        driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", btn)
        time.sleep(1)
        btn.click()
        time.sleep(3) # 等待新内容加载

    except (NoSuchElementException, TimeoutException) as e:
        print(f"找不到 'Show More' 按钮或页面加载超时，可能已加载全部内容。错误: {e}")
        break
    except Exception as e:
        print(f"发生未知错误: {e}")
        break

# 获取所有专家页面的链接
print("正在收集所有专家链接...")
list_items0 = driver.find_elements(By.XPATH, r'//*[@id="skip-to-content"]/div/div/div/a[*]')
teacher_list = [item.get_attribute('href') for item in list_items0 if item.get_attribute('href')]
print(f"共找到 {len(teacher_list)} 个专家链接。")

# 遍历每个专家页面并抓取数据
for i, href in enumerate(teacher_list):
    print(f"\n--- 正在处理第 {i+1}/{len(teacher_list)} 位专家: {href} ---")
    all_data = {}

    try:
        driver.get(href)
        time.sleep(2) # 等待个人资料页面加载
        all_data['website'] = driver.current_url
    except Exception as e:
        print(f"无法访问页面 {href}: {e}")
        continue

    try:
        name_element = driver.find_element(By.XPATH, r'//*[@id="profile"]/div/div/div/div[2]/h4/b')
        # 使用正则表达式分离头衔和姓名
        pattern = re.compile(r'^((?:Honorary Associate )?Professor|(?:Associate )?Professor|Dr\.|Mr|Ms|Mrs|Doctor|A/Prof|AsPr)\s+(.+)$')
        match = pattern.match(name_element.text)
        if match:
            all_data['full name'] = match.group(2).strip()
            all_data['title'] = match.group(1).strip()
        else:
            all_data['full name'] = name_element.text.strip()
            all_data['title'] = None
    except Exception as e:
        print(f"提取姓名/头衔失败: {e}")
        all_data['full name'] = None
        all_data['title'] = None

    try:
        # 修复：直接获取组织单位元素的文本
        org_unit_element = driver.find_element(By.XPATH, r'//*[@id="profile"]/div/div/div/div[2]/div[1]/div[3]')
        all_data['org_unit'] = org_unit_element.text.strip()
    except Exception as e:
        print(f"提取 'org_unit' 失败: {e}")
        all_data['org_unit'] = None

    try:
        email_element = driver.find_element(By.XPATH, r'//*[@id="profile"]/div/div/div/div[2]/div[1]/div[2]/a')
        all_data['email'] = email_element.text.strip()
    except Exception as e:
        print(f"提取 'email' 失败: {e}")
        all_data['email'] = None

    try:
        telephone_element = driver.find_element(By.XPATH, r'//*[@id="profile"]/div/div/div/div[2]/div[1]/div[6]')
        all_data['telephone'] = telephone_element.text.strip()
    except Exception as e:
        print(f"提取 'telephone' 失败: {e}")
        all_data['telephone'] = None

    try:
        orcid_element = driver.find_element(By.XPATH, r'//*[@id="profile"]/div/div/div/div[2]/div[1]/div[4]/a')
        all_data['orcid'] = orcid_element.text.strip()
    except Exception as e:
        print(f"提取 'orcid' 失败: {e}")
        all_data['orcid'] = None

    all_info = ''
    try:
        research_element = driver.find_element(By.XPATH, r'//*[@id="about"]/div')
        # 获取所有段落和列表项的文本
        text_list = [p.get_attribute('innerText') for p in research_element.find_elements(By.XPATH, './/p | ./ul/li')]
        all_info = '\n'.join(filter(None, text_list)).strip()
    except Exception as e:
        print(f"提取 'brief introduction' 失败: {e}")

    if all_info:
        all_data['brief introduction'] = all_info
    else:
        all_data['brief introduction'] = None

    print(f"抓取到的数据: {all_data}")

    # --- 将数据插入 Supabase ---
    try:
        # 映射字段名以匹配数据库列
        data_to_insert = {
            "website": all_data.get('website'),
            "title": all_data.get('title'),
            "full name": all_data.get('full name'),
            # 注意：您的表中有 'position' 列，但脚本中没有抓取此项。
            # 如果需要，请添加抓取逻辑。
            "position": None, 
            "org unit": all_data.get('org_unit'), # 映射 'org_unit' 到 "org unit"
            "email": all_data.get('email'),
            "telephone": all_data.get('telephone'),
            "orcid": all_data.get('orcid'),
            "brief introduction": all_data.get('brief introduction'),
        }
        
        # 执行插入操作
        response = supabase.table(TABLE_NAME).insert(data_to_insert).execute()
        
        if response.data:
            print(f"成功插入数据: {all_data.get('full name')}")
        else:
            # 这通常不会发生，因为错误会作为异常抛出
            print(f"插入数据时发生未知错误: {response}")

    except Exception as e:
        # 捕获可能的错误，例如唯一性约束冲突
        print(f"插入数据到 Supabase 失败: {e}")
        print("可能是重复数据或其他数据库错误。")

    
    # 否则，可以适当缩短，例如 time.sleep(2) 或 time.sleep(5)。
    time.sleep(3)

print("\n所有专家数据处理完毕。")
