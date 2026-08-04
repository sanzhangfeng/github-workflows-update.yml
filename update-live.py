import aiohttp
import asyncio
import re
from datetime import datetime

# ================= 配置区域 =================
# 1. 这里填写你要检测的直播源地址列表 (已增加国内稳定源)
SOURCE_URLS = [
    "https://ghproxy.net/https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
    "https://ghproxy.net/https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/countries/cn.m3u",
    "https://ghproxy.net/https://raw.githubusercontent.com/yuanzl77/IPTV/main/live.m3u",
]

# 2. 超时设置 (秒)，如果网络慢可以适当调大
TIMEOUT = aiohttp.ClientTimeout(total=5)

# 3. 输出文件名
OUTPUT_FILE = "result.m3u"
# ==========================================

async def check_url(session, url):
    """异步检测单个链接是否有效"""
    try:
        async with session.head(url, timeout=TIMEOUT) as response:
            # 只要状态码是 200 或 301/302 重定向，通常都算有效
            if response.status in [200, 301, 302]:
                return url
    except Exception:
        pass
    
    # 如果 HEAD 请求失败，尝试 GET 请求（有些服务器禁止 HEAD）
    try:
        async with session.get(url, timeout=TIMEOUT) as response:
            if response.status == 200:
                return url
    except Exception:
        pass
        
    return None

async def main():
    print(f"🚀 开始检测直播源... ({datetime.now().strftime('%H:%M:%S')})")
    
    # 用于存储所有提取到的链接
    all_links = []
    
    # 1. 下载并提取链接
    connector = aiohttp.TCPConnector(ssl=False) # 忽略SSL证书错误，防止部分源报错
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for url in SOURCE_URLS:
            tasks.append(fetch_and_parse(session, url))
        
        results = await asyncio.gather(*tasks)
        for links in results:
            all_links.extend(links)
            
    # 去重
    unique_links = list(set(all_links))
    print(f"📡 共提取到 {len(unique_links)} 个链接，开始检测连通性...")
    
    # 2. 并发检测链接有效性
    valid_links = []
    # 限制并发数为 50，防止瞬间请求太多被封 IP
    semaphore = asyncio.Semaphore(50) 
    
    async def limited_check(url):
        async with semaphore:
            return await check_url(session, url)
            
    # 重新建立 session 用于检测
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [limited_check(url) for url in unique_links]
        results = await asyncio.gather(*tasks)
        
        for link in results:
            if link:
                valid_links.append(link)
                
    print(f"✅ 检测完成，有效链接：{len(valid_links)} 个")
    
    # 3. 保存结果
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for link in valid_links:
            # 简单的写入格式，你可以根据需要添加频道名
            f.write(f"#EXTINF:-1,Channel\n{link}\n")
            
    print(f"💾 结果已保存到桌面: {OUTPUT_FILE}")

async def fetch_and_parse(session, url):
    """下载 m3u 文件并提取 http/https 链接"""
    try:
        async with session.get(url) as response:
            if response.status == 200:
                text = await response.text()
                # 使用正则提取所有 http/https 开头的链接
                return re.findall(r'https?://[^\s"\'<>]+', text)
    except Exception as e:
        print(f"❌ 下载源失败: {url} - {e}")
    return []

if __name__ == "__main__":
    asyncio.run(main())
