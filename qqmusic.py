from fastmcp import FastMCP
import httpx
import logging

logger = logging.getLogger('QQMusic')

mcp = FastMCP("QQMusic")

@mcp.tool()
async def search_music(song_name: str) -> dict:
    """搜索QQ音乐。当用户要求播放歌曲、搜索音乐时使用此工具。参数 song_name 是歌曲名称或歌手名。"""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"https://api.xingzhige.com/API/QQmusicVIP/?name={song_name}&type=json", timeout=10.0)
            data = resp.json()
            if data.get("code") == 200 and data.get("data"):
                songs = data["data"][:5]
                return {"content": "\n".join([f"{i+1}. {s['name']} - {s['singer']}" for i,s in enumerate(songs)])}
            return {"content": "未找到音乐"}
        except Exception as e:
            return {"content": f"搜索出错: {str(e)}"}

@mcp.tool()
async def get_weather(city: str) -> dict:
    """查询城市天气。当用户询问天气、气温时使用此工具。参数 city 是城市名称。"""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"https://api.xingzhige.com/API/tianqiV3/?city={city}", timeout=10.0)
            data = resp.json()
            if data:
                return {"content": f"{city}: {data.get('weather','')} {data.get('temperature','')}"}
            return {"content": "未找到天气"}
        except Exception as e:
            return {"content": f"查询出错: {str(e)}"}

@mcp.tool()
async def web_search(keywords: str) -> dict:
    """联网搜索。当用户要求搜索新闻、查资料时使用此工具。参数 keywords 是搜索关键词。"""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"https://html.duckduckgo.com/html/?q={keywords}", timeout=10.0)
            import re
            results = []
            for m in re.finditer(r'<a class="result__a" href="([^"]+)"[^>]*>([^<]+)</a>', resp.text):
                if len(results) >= 5: break
                results.append(m.group(2).strip() + " - " + m.group(1))
            return {"content": "\n".join(results) or "无结果"}
        except Exception as e:
            return {"content": f"搜索出错: {str(e)}"}

if __name__ == "__main__":
    mcp.run(transport="stdio")