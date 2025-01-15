import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError,Page
import json
import os

# 使用更真实的请求头
headers = {
    'Accept': '*/*',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    'X-Requested-With': 'XMLHttpRequest'
}

# 进度文件路径
progress_file = 'download_progress.json'

def load_progress():
    """加载进度信息"""
    if os.path.exists(progress_file):
        with open(progress_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        # 如果不存在，则初始化进度信息
        return {'last_page': 1, 'last_item_index': 0}

def save_progress(page_num, item_index=0):
    """保存当前下载进度"""
    progress = {'last_page': page_num, 'last_item_index': item_index}
    
    with open(progress_file, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=4)

def hover_and_wait_for_video_to_load(page, region_element):
    """
    对指定的 js-fast-video-custom-region 元素进行悬停，并等待对应的 video.h5-fast-video 加载完成并变得可见。
    
    :param page: Playwright page object.
    :param region_element: 目标区域元素。
    """
    try:
        # 模拟鼠标悬停在该区域上
        region_element.hover()

        # 等待对应的 video.h5-fast-video 出现并加载完成
        video_element = region_element.query_selector('video.h5-fast-video')
        if not video_element:
            raise ValueError("Video element not found within the region.")

        # 确认视频 src 属性已加载且不是隐藏状态
        page.wait_for_function(
            'el => el.src !== "" && getComputedStyle(el).display !== "none" && getComputedStyle(el).visibility !== "hidden"',
            arg=video_element,
            timeout=60000
        )

        print("Video loaded and is visible.")
    except PlaywrightTimeoutError:
        print("Failed to load or make the video visible within the timeout period.")
    except Exception as e:
        pass

def scroll_down(page: Page, scroll_amount=400, wait_time=1):
    """
    慢速滚动页面，每次滚动指定的距离。
    
    :param page: Playwright page object.
    :param scroll_amount: 每次滚动的距离（像素）。
    :param wait_time: 每次滚动后等待的时间（秒）。
    """
    last_height = page.evaluate("document.body.scrollHeight")

    while True:
        current_scroll_y = page.evaluate("window.scrollY")
        new_scroll_y = current_scroll_y + scroll_amount
        
        # Scroll down by the specified amount
        page.evaluate(f"window.scrollTo(0, {new_scroll_y});")
        
        # Wait to load page content after each scroll
        time.sleep(wait_time)  # 调整为每次滚动后的短暂停顿
        
        # Calculate new scroll height and compare with last scroll height
        new_height = page.evaluate("document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

def download_pages(page_count, download_func=None):
    """
    下载指定数量的页面。
    
    :param page_count: 要下载的页面数量
    :param download_func: 可选的回调函数，用于处理每个item的下载逻辑
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # 设置为有头模式以观察行为
        context = browser.new_context(
            user_agent=headers['User-Agent'],
            viewport={'width': 1920, 'height': 1080},
            bypass_csp=True,
            java_script_enabled=True,
            locale='zh-CN',
            timezone_id='Asia/Shanghai',
        )

        for i in range(page_count):
            url = f'https://www.aigei.com/s?type=video&q=%E7%89%B9%E6%95%88&page={i + 1}'

            try:
                page = context.new_page()
                print(f"Navigating to {url}")
                response = page.goto(url, wait_until="networkidle", timeout=30000)

                if not response or response.status != 200:
                    print(f"Failed to load page {i + 1}, status code: {response.status if response else 'None'}")
                    continue

                # 等待页面加载完成，确保所有JavaScript执行完毕
                page.wait_for_load_state('domcontentloaded')

                # 慢速滚动到页面底部以加载所有内容
                scroll_down(page)

                # 获取所有 div.js-fast-video-custom-region 元素
                region_elements = page.query_selector_all('div.js-fast-video-custom-region')
                items = page.query_selector_all('ul.unit-content-main')
                if not region_elements:
                    print("No region elements found.")
                    continue

                print(f"Found {len(region_elements)} region elements.")

                # 对每个区域元素进行悬停并等待视频加载
                for index, item in enumerate(items, start=1):
                    region_element=item.query_selector('div.js-fast-video-custom-region')
                    print(f"Hovering over region element {index}...")
                    hover_and_wait_for_video_to_load(page, region_element)

                    # 继续处理页面内容...
                    title_element = item.query_selector('b.trans-title')
                    video_element = item.query_selector('video.h5-fast-video')

                    if title_element and video_element:
                        title = title_element.text_content().strip()
                        download_link = video_element.get_attribute('src')

                        print(f"Page {i + 1}, Item {index} Title: {title}")
                        print(f"Page {i + 1}, Item {index} Download Link: {download_link}")

                        if download_func:
                            download_func(title, download_link)

                # 保存进度
                save_progress(i + 1)

            except PlaywrightTimeoutError as e:
                print(f"Timeout error on page {i + 1}: {e}")
                break
            except Exception as e:
                print(f"Error processing page {i + 1}: {e}")
                break

        browser.close()

def example_download(title, link):
    print(f"正在下载: {title} from {link}")  # 在这里实现实际的下载逻辑

if __name__ == "__main__":
    download_pages(1, download_func=example_download)