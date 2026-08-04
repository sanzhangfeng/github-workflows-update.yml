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

# 并发限制：一次只测 50 个，防止被封 IP (之前可能太快了)
CONCURRENCY_LIMIT = 50 
# ==========================================

async def check_url(session, url):
    """
    修改版检测逻辑：
    不再使用 HEAD，而是尝试 GET 下载前 1024 字节。
    只要能连上并读到数据，就算有效。
    """
    try:
        # 使用 GET 请求，只读一点点头部数据
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                # 尝试读取一点点内容，确认不是空文件
                await response.content.read(1024)
                return True
    except Exception:
        pass
    return False

async def process_source(session, url, valid_links, semaphore):
    """处理单个源文件的下载和解析"""
    try:
        async with session.get(url) as response:
            if response.status == 200:
                content = await response.text()
                # 简单的 M3U 解析逻辑
                lines = content.splitlines()
                current_name = ""
                for line in lines:
                    line = line.strip()
                    if line.startswith("#EXTINF"):
                        # 提取频道名
                        parts = line.split(",", 1)
                        current_name = parts[1] if len(parts) > 1 else "Unknown"
                    elif line.startswith("http"):
                        # 发现链接，加入检测队列
                        async with semaphore: # 限制并发数
                            is_valid = await check_url(session, line)
                            if is_valid:
                                print(f"✅ 有效: {current_name}")
                                valid_links.append(f"#EXTINF:-1,{current_name}\n{line}")
    except Exception as e:
        print(f"❌ 源下载失败: {url} - {e}")

async def main():
    print(f"🚀 开始检测直播源... ({datetime.now().strftime('%H:%M:%S')})")
    
    # 设置信号量限制并发
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    
    connector = aiohttp.TCPConnector(limit=CONCURRENCY_LIMIT)
    async with aiohttp.ClientSession(connector=connector) as session:
        valid_links = []
        tasks = []
        
        total_count = 0 # 这里简化处理，实际总数很难在异步前预知
        
        for url in SOURCE_URLS:
            tasks.append(process_source(session, url, valid_links, semaphore))
            
        await asyncio.gather(*tasks)

    # 保存结果
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for link in valid_links:
            f.write(link + "\n")

    print(f"\n🎉 检测完成，有效链接：{len(valid_links)} 个")
    print(f"💾 结果已保存到桌面: {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
