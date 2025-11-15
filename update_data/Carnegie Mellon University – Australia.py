import os
import time
import argparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from supabase import create_client, Client

# ==================== 配置 ====================
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://your-project.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "your-anon-key")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==================== 参数解析 ====================
parser = argparse.ArgumentParser(description="CMU 教师信息爬虫")
parser.add_argument('--port', type=str, default='9222', required=True, help="Chrome 远程调试端口")
args = parser.parse_args()

# ==================== 初始化浏览器 ====================
chrome_options = Options()
chrome_options.debugger_address = f"127.0.0.1:{args.port}"
driver = webdriver.Chrome(options=chrome_options)
wait = WebDriverWait(driver, 15)

# ==================== 主逻辑 ====================
def main():
    try:
        print("正在访问 CMU 教师页面...")
        driver.get('https://www.heinz.cmu.edu/faculty-research/profiles/')
        
        # 等待页面主要元素加载
        wait.until(EC.presence_of_element_located((By.ID, "main")))
        time.sleep(2)  # 额外等待确保内容渲染
        
        teacher_links = collect_teacher_links()
        print(f"\n{'='*50}")
        print(f"✓ 共收集到 {len(teacher_links)} 个教师链接")
        
        if not teacher_links:
            print("⚠ 警告：未收集到任何链接，请检查XPath和页面结构！")
            return
        
        # 处理每个教师
        for index, link in enumerate(teacher_links, 1):
            print(f"\n[{index}/{len(teacher_links)}] 处理: {link}")
            process_teacher_profile(link)
            time.sleep(3)
            
    finally:
        print("\n爬虫执行完毕，关闭浏览器...")
        driver.quit()

def find_next_page_button():
    """查找下一页按钮，返回按钮元素或None"""
    xpath_candidates = [
        # 策略1: nav下的直接子元素（双下划线class）- 最可能成功
        "//nav[contains(@class, 'pagination__inner-container')]/a[contains(@class, 'pagination__next-link')]",
        # 策略2: nav/div下的a标签（用户提供的结构）
        "//nav[contains(@class, 'pagination__inner-container')]/div/a[contains(@class, 'pagination__next-link')]",
        # 策略3: li内的a标签
        "//nav//li[last()]/a[contains(@class, 'pagination__next-link') or contains(@aria-label, 'Next')]",
        # 策略4: 通用的下一页链接
        "//a[@aria-label='Next page' or @aria-label='next page']",
        # 策略5: 包含pageIndex的href
        "//a[contains(@href, 'pageIndex=') and (contains(@class, 'next') or contains(@aria-label, 'Next'))]",
    ]
    
    for xpath in xpath_candidates:
        try:
            button = driver.find_element(By.XPATH, xpath)
            print(f"  └─ 成功找到按钮，使用XPath: {xpath}")
            return button
        except NoSuchElementException:
            continue
    
    return None

def collect_teacher_links():
    """从所有分页页面收集教师链接"""
    links = []
    current_page = 1
    
    while True:
        print(f"\n{'='*50}")
        print(f"正在收集第 {current_page} 页的教师链接...")
        print(f"当前URL: {driver.current_url}")
        
        # 先滚动到页面中部，确保内容区域加载
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 3);")
        time.sleep(2)
        
        # 提取当前页面的教师链接
        page_links = extract_links_from_page_debug()
        
        if not page_links:
            print("  ⚠  本页未找到任何教师链接！")
        else:
            links.extend(page_links)
            print(f"  ✓ 本页找到 {len(page_links)} 个链接，总计 {len(links)} 个")
        
        # 查找下一页按钮
        next_button = find_next_page_button()
        
        if not next_button:
            print("  └─ ⚠ 未找到下一页按钮，停止爬取")
            print("\n--- 分页区域源码 ---")
            try:
                pagination_html = driver.find_element(By.CLASS_NAME, "pagination__inner-container").get_attribute('outerHTML')
                print(pagination_html[:500])
            except:
                print("无法找到分页区域")
            print("--- 结束 ---\n")
            break
        
        # 检查按钮状态
        button_class = next_button.get_attribute("class") or ""
        aria_disabled = next_button.get_attribute("aria-disabled") or "false"
        
        print(f"  └─ 按钮状态 - class: {button_class}, aria-disabled: {aria_disabled}")
        
        if "disabled" in button_class or aria_disabled == "true":
            print("  └─ 已到达最后一页（按钮已禁用）")
            break
        
        # 点击按钮
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
        time.sleep(1)
        
        print(f"  └─ 点击下一页按钮，加载第 {current_page + 1} 页...")
        next_button.click()
        
        # 等待页面加载
        time.sleep(3)
        current_page += 1
    
    return links

def extract_links_from_page_debug():
    """从当前页面提取教师链接（带调试）"""
    # 正确的XPath - 移除[*]并简化
    primary_xpath = '//*[@id="main"]/div/section[4]/ol/li/article/div/p[2]/a'
    
    print(f"  └─ 尝试主要XPath: {primary_xpath}")
    
    try:
        # 等待元素出现
        wait.until(EC.presence_of_all_elements_located((By.XPATH, primary_xpath)))
        elements = driver.find_elements(By.XPATH, primary_xpath)
        
        if elements:
            links = [elem.get_attribute('href') for elem in elements if elem.get_attribute('href')]
            print(f"  ✓ 成功提取 {len(links)} 个链接")
            return links
        else:
            print("  └─ 主要XPath未找到元素，尝试备选方案...")
            
    except TimeoutException:
        print("  └─ 等待元素超时，尝试备选方案...")
    
    # 备选XPath列表
    alternative_xpaths = [
        '//*[@id="main"]//section//ol/li/article/div/p[2]/a',
        '//article//div/p[2]/a[contains(@href, "/people/")]',
        '//a[contains(@href, "/people/") and contains(@href, "cmu.edu")]',
    ]
    
    for xpath in alternative_xpaths:
        print(f"  └─ 尝试备选XPath: {xpath}")
        try:
            elements = driver.find_elements(By.XPATH, xpath)
            if elements:
                links = [elem.get_attribute('href') for elem in elements if elem.get_attribute('href')]
                print(f"  ✓ 备选XPath成功: {len(links)} 个链接")
                return links
        except:
            continue
    
    return []

def process_teacher_profile(url: str):
    """处理单个教师页面并保存到 Supabase"""
    try:
        driver.get(url)
        time.sleep(3)
        
        # 提取信息
        data = {}
        
        # 姓名（必需字段）
        try:
            data['full name'] = driver.find_element(By.XPATH, '//*[@id="main"]/div/section[2]/div/h1').text
        except:
            print("  ✗ 无法提取姓名，跳过此页面")
            return
        
        # 职位
        try:
            data['position'] = driver.find_element(By.XPATH, '//*[@id="main"]/div/section[2]/div/h2').text
        except:
            data['position'] = None
        
        # 电话
        try:
            data['telephone'] = driver.find_element(By.XPATH, '//span[@class="vcard__telephone"]/a').text
        except:
            data['telephone'] = None
        
        # 邮箱
        try:
            data['email'] = driver.find_element(By.XPATH, '//span[@class="vcard__email"]/a').text
        except:
            data['email'] = None
        
        # 简介（合并多个可能区域）
        intro_parts = []
        for xpath in [
            '//*[@id="main"]/div/section[2]/div[@class="user-markup"]',
            '//*[@id="rmjs-1"]/div[@class="user-markup"]'
        ]:
            try:
                section = driver.find_element(By.XPATH, xpath)
                elements = section.find_elements(By.XPATH, './/p | ./ul/li')
                texts = [e.get_attribute('innerText').strip() for e in elements if e.get_attribute('innerText').strip()]
                if texts:
                    intro_parts.append('\n'.join(texts))
            except:
                continue
        
        data['brief introduction'] = '\n\n'.join(intro_parts) if intro_parts else None
        
        # 其他字段
        data['title'] = None
        data['org unit'] = None
        data['orcid'] = None
        
        # 保存到 Supabase（修复唯一约束冲突）
        try:
            # 清理 URL 并指定冲突解决列
            data['website'] = url.strip()
            
            response = supabase.table('original_carnegie_mellon_university_australia')\
                .upsert(data, on_conflict='website').execute()
            
            if response.data:
                print(f"  ✓ 数据已保存 (ID: {response.data[0]['id']})")
            else:
                print(f"  ⚠ 保存成功但无返回数据")
        except Exception as e:
            print(f"  ✗ Supabase 保存失败: {e}")
            debug_data = {k: (v[:50] + '...' if v and isinstance(v, str) and len(v) > 50 else v) for k, v in data.items()}
            print(f"    数据摘要: {debug_data}")
            
    except Exception as e:
        print(f"  ✗ 无法处理该页面: {e}")
        return

if __name__ == "__main__":
    main()