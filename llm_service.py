import aiohttp
from openai import OpenAI

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, SYSTEM_PROMPT ,KOOK_API_URL, BOT_TOKEN


# 初始化DeepSeek客户端
deepseek_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

KOOK_BOT_TOKEN = BOT_TOKEN

async def call_deepseek_api(user_message):
    """调用DeepSeek API获取回复"""
    try:
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            stream=False
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"DeepSeek API调用失败: {e}")
        return "抱歉，我暂时无法回答这个问题。"

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

async def add_game_activity(game_id):
    """添加游戏活动记录（开始玩游戏）"""
    url = f"{KOOK_API_URL}/game/activity"
    headers = {"Authorization": f"Bot {KOOK_BOT_TOKEN}"}
    payload = {"id": game_id, "data_type": 1}  # data_type=1 表示游戏
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            if response.status == 200:
                return True
            else:
                print(f"添加游戏活动记录失败: {response.status}")
                return False

async def delete_game_activity():
    """删除游戏活动记录（结束玩游戏）"""
    url = f"{KOOK_API_URL}/game/delete-activity"
    headers = {"Authorization": f"Bot {KOOK_BOT_TOKEN}"}
    payload = {"data_type": 1}  # data_type=1 表示游戏
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            if response.status == 200:
                return True
            else:
                print(f"删除游戏活动记录失败: {response.status}")
                return False

async def get_active_game_players():
    """查询当前正在玩游戏的用户"""
    # 假设KOOK API提供了查询当前活动状态的接口
    url = f"{KOOK_API_URL}/game/active-players"
    headers = {"Authorization": f"Bot {KOOK_BOT_TOKEN}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("data", {}).get("players", [])
            else:
                print(f"查询当前玩游戏用户失败: {response.status}")
                return []

async def handle_user_query(user_message):
    """处理用户查询"""
    # 调用DeepSeek API获取初始回复
    reply = await call_deepseek_api(user_message)

    # 判断是否需要调用工具
    if "游戏列表" in user_message:
        games = await get_game_list()
        if games:
            game_names = [game["name"] for game in games]
            reply = f"当前游戏列表如下：\n" + "\n".join(game_names)
        else:
            reply = "获取游戏列表失败，请稍后再试。"
    elif "开始玩游戏" in user_message:
        game_name = user_message.replace("开始玩游戏", "").strip()
        games = await get_game_list()
        target_game = next((game for game in games if game["name"] == game_name), None)
        if target_game:
            success = await add_game_activity(target_game["id"])
            reply = f"已开始玩 {game_name}。" if success else f"开始玩 {game_name} 失败。"
        else:
            reply = f"未找到游戏：{game_name}。"
    elif "结束玩游戏" in user_message:
        success = await delete_game_activity()
        reply = "已结束当前游戏。" if success else "结束游戏失败。"
    elif "是否有用户正在玩游戏" in user_message:
        active_players = await get_active_game_players()
        if active_players:
            player_names = [player["username"] for player in active_players]
            reply = f"当前正在玩游戏的用户有：\n" + "\n".join(player_names)
        else:
            reply = "当前没有用户正在玩游戏。"
    return reply