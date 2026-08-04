import aiohttp
import asyncio
import re
from datetime import datetime

# ================= 配置区域 =================
SOURCE_URLS = [
    "https://ghproxy.net/https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
    "https://ghproxy.net/https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/countries/cn.m3u",
    "https://ghproxy.net/https://raw.githubusercontent.com/yuanzl77/IPTV/main/live.m3u",
]

# 输出文件名
OUTPUT_FILE = "result.m3u"

# 并发限制 (数字越小越稳，但越慢；建议 20-50)
CONCURRENCY = 30
# ==========================================

async def check_url(session, url):
    """异步检测单个链接是否有效"""
    try:
        # 使用 GET 请求并只下载头部，模拟真实播放
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                # 检查内容类型，确保是视频流 (ts, m3u8, mp4 等)
                content_type = response.headers.get('Content-Type', '')
                if any(x in content_type for x in ['video', 'audio', 'mpeg', 'octet-stream', 'm3u8']):
                    return url
            return None
    except Exception:
        return None

async def main():
    valid_links = []
    all_urls = []
    
    print("🔍 开始提取直播源...")
    
    # 1. 提取所有链接
    async with aiohttp.ClientSession() as session:
        for source_url in SOURCE_URLS:
            try:
                async with session.get(source_url) as resp:
                    text = await resp.text()
                    # 简单的正则提取 http/https 链接
                    urls = re.findall(r'https?://[^\s"\'<>]+', text)
                    all_urls.extend(urls)
            except Exception as e:
                print(f"❌ 下载源失败 {source_url}: {e}")

    # 去重
    all_urls = list(set(all_urls))
    print(f"📦 共提取到 {len(all_urls)} 个链接，开始检测连通性...")
    
    if not all_urls:
        print("未找到任何链接，请检查源地址。")
        return

    # 2. 分批检测
    semaphore = asyncio.Semaphore(CONCURRENCY)
    
    async def bounded_check(url):
        async with semaphore:
            result = await check_url(session, url)
            if result:
                valid_links.append(result)
                print(f"✅ 有效: {result.split('/')[-1]}") # 只显示文件名，避免刷屏
            else:
                print(f"⏳ 检测中... 当前有效: {len(valid_links)}")
            return result

    # 重新创建 session 用于检测
    connector = aiohttp.TCPConnector(limit=CONCURRENCY, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        # 使用 gather 并发执行，但受 semaphore 限制
        tasks = [bounded_check(url) for url in all_urls]
        await asyncio.gather(*tasks)

    # 3. 保存结果
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for link in valid_links:
            # 尝试从链接中提取频道名，如果提取不到就用链接本身
            name = link.split('/')[-1].split('.')[0] 
            f.write(f'#EXTINF:-1,{name}\n{link}\n')

    print(f"\n🎉 检测完成！")
    print(f"📊 有效链接：{len(valid_links)} 个")
    print(f"💾 结果已保存到桌面: {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
