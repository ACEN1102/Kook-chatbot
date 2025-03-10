import aiohttp
from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, KOOK_API_URL, BOT_TOKEN
import json

# 初始化DeepSeek客户端
deepseek_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

KOOK_BOT_TOKEN = BOT_TOKEN

# 定义工具元数据
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_game_list",
            "description": "获取当前支持的游戏列表。",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_guild_user_list",
            "description": "服务器现在有哪些用户(哪些人)。",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_game_activity",
            "description": "查询用户正在玩的游戏。",
            "parameters": {
                "type": "object",
                "properties": {
                },
                "required": ["user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_guild_id_by_name",
            "description": "根据服务器名称获取服务器 ID。",
            "parameters": {
                "type": "object",
                "properties": {
                    }
                },
                "required": ["guild_name"]
            }
        }
]

async def call_deepseek_api(user_message):
    """调用DeepSeek API，支持Function Calling"""
    try:
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个助手，可以调用工具帮助用户查询游戏、音乐等信息。"},
                {"role": "user", "content": user_message},
            ],
            tools=TOOLS,  # 传递工具元数据
            tool_choice="auto"  # 让模型自行决定是否调用工具
        )
        return response.choices[0].message
    except Exception as e:
        print(f"DeepSeek API调用失败: {e}")
        return None

async def get_game_list():
    """获取游戏列表"""
    url = f"{KOOK_API_URL}/game"
    headers = {"Authorization": f"Bot {KOOK_BOT_TOKEN}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("data", {}).get("items", [])
            else:
                print(f"获取游戏列表失败: {response.status}")
                return []

async def get_guild_user_list(guild_id):
    """获取服务器中的用户列表"""
    url = f"{KOOK_API_URL}/guild/user-list"
    headers = {"Authorization": f"Bot {KOOK_BOT_TOKEN}"}
    params = {"guild_id": guild_id}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            # 打印调试信息
            print(f"请求 URL: {url}")
            print(f"请求参数: {params}")
            print(f"响应状态码: {response.status}")

            if response.status == 200:
                data = await response.json()
                print(f"API 返回数据: {data}")  # 打印原始返回数据

                # 确保返回数据格式正确
                if "data" in data and "items" in data["data"]:
                    return data["data"]["items"]
                else:
                    print("API 返回数据格式不匹配")
                    return []
            else:
                print(f"获取服务器用户列表失败: {response.status}")
                return []

async def get_user_game_activity(user_id):
    """查询用户正在玩的游戏"""
    url = f"{KOOK_API_URL}/game/activity"
    headers = {"Authorization": f"Bot {KOOK_BOT_TOKEN}"}
    params = {"user_id": user_id}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("data", {}).get("games", [])
            else:
                print(f"查询用户游戏活动失败: {response.status}")
                return []

async def get_guild_list():
    """获取机器人加入的服务器列表"""
    url = f"{KOOK_API_URL}/guild/list"
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    params = {"page": 1, "page_size": 50}  # 获取第一页，每页 50 条数据

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("code") == 0:
                    return data.get("data", {}).get("items", [])
                else:
                    print(f"获取服务器列表失败: {data.get('message')}")
                    return []
            else:
                print(f"获取服务器列表失败: {response.status}")
                return []

async def get_guild_id_by_name(guild_name):
    """根据服务器名称获取服务器 ID"""
    guild_list = await get_guild_list()
    for guild in guild_list:
        if guild.get("name") == guild_name:
            return guild.get("id")
    return None

# async def get_guild_view(guild_id):
#     """获取服务器详情"""
#     url = f"{KOOK_API_URL}/guild/view"
#     headers = {"Authorization": f"Bot {BOT_TOKEN}"}
#     params = {"guild_id": guild_id}
#
#     async with aiohttp.ClientSession() as session:
#         async with session.get(url, headers=headers, params=params) as response:
#             if response.status == 200:
#                 data = await response.json()
#                 if data.get("code") == 0:
#                     return data.get("data", {})
#                 else:
#                     print(f"获取服务器详情失败: {data.get('message')}")
#                     return {}
#             else:
#                 print(f"获取服务器详情失败: {response.status}")
#                 return {}


async def handle_user_query(user_message, event_data):
    """处理用户查询，支持Function Calling"""
    # 调用DeepSeek API
    response = await call_deepseek_api(user_message)
    if not response:
        return "抱歉，我暂时无法回答这个问题。"

    # 检查是否需要调用工具
    if response.tool_calls:
        tool_call = response.tool_calls[0]
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)

        # 执行工具
        if tool_name == "get_game_list":
            result = await get_game_list()
            if result:
                game_names = [game["name"] for game in result]
                return f"当前游戏列表如下：\n" + "\n".join(game_names)
            else:
                return "获取游戏列表失败，请稍后再试。"
        elif tool_name == "get_guild_user_list":
            # 从 event_data 的 extra 中获取 guild_id
            guild_id = event_data.get("extra", {}).get("guild_id")
            if not guild_id:
                return "要查询服务器中的用户列表，我需要知道服务器的名称或ID。请提供服务器的名称或ID。"

            result = await get_guild_user_list(guild_id)
            if result:
                user_names = [user["username"] for user in result]
                return f"服务器中的用户列表如下：\n" + "\n".join(user_names)
            else:
                return "获取服务器用户列表失败，请稍后再试。"
        elif tool_name == "get_user_game_activity":
            # 直接从事件数据中获取 user_id
            user_id = event_data.get("author_id")
            if not user_id:
                return "未找到用户 ID，请确保消息来自有效用户。"

            result = await get_user_game_activity(user_id)
            if result:
                game_names = [game["name"] for game in result]
                return f"用户正在玩的游戏如下：\n" + "\n".join(game_names)
            else:
                return "查询用户游戏活动失败，请稍后再试。"
        elif tool_name == "get_guild_list":
            result = await get_guild_list()
            if result:
                guild_names = [guild["name"] for guild in result]
                return f"机器人加入的服务器列表如下：\n" + "\n".join(guild_names)
            else:
                return "获取服务器列表失败，请稍后再试。"
        elif tool_name == "get_guild_id_by_name":
            guild_name = tool_args.get("guild_name")
            guild_id = await get_guild_id_by_name(guild_name)
            if guild_id:
                return f"服务器 '{guild_name}' 的 ID 是: {guild_id}"
            else:
                return f"未找到服务器 '{guild_name}'"
        else:
            return "未知工具调用。"

    # 如果不需要调用工具，直接返回模型回复
    return response.content
