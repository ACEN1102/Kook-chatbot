import asyncio
import json
import websockets
import aiohttp
import zlib

from config import GATEWAY_URL, BOT_TOKEN, BOT_USER_ID, KOOK_API_URL
from llm_service import handle_user_query  # 引入llm_service中的函数

session_id = None
last_sn = 0  # 记录最后处理的消息sn

async def get_gateway_url():
    """获取WebSocket网关地址"""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            GATEWAY_URL,
            headers={"Authorization": f"Bot {BOT_TOKEN}"},
            params={"compress": 1}  # 启用压缩
        ) as response:
            gateway_data = await response.json()
            if gateway_data["code"] != 0:
                raise Exception(f"获取网关地址失败: {gateway_data['message']}")
            return gateway_data['data']['url']

async def connect_to_gateway():
    """连接WebSocket网关"""
    global session_id, last_sn

    retry_count = 0
    max_retries = 3
    retry_delay = 5  # 重试延迟（秒）

    while retry_count < max_retries:
        try:
            # 获取WebSocket网关地址
            websocket_url = await get_gateway_url()
            print(f"WebSocket URL: {websocket_url}")

            # 如果存在session_id和last_sn，尝试恢复会话
            if session_id and last_sn > 0:
                websocket_url += f"&resume=1&sn={last_sn}&session_id={session_id}"

            # 连接WebSocket
            async with websockets.connect(websocket_url, open_timeout=10) as ws:
                print("WebSocket连接成功")

                # 发送身份验证
                auth_payload = {
                    "s": 2,  # Identify信令
                    "d": {
                        "token": BOT_TOKEN,
                        "intents": 513,  # 订阅消息事件
                        "shard": [0, 1]
                    }
                }
                await ws.send(json.dumps(auth_payload))

                # 心跳循环
                async def heartbeat(interval):
                    while True:
                        await asyncio.sleep(interval / 1000)
                        await ws.send(json.dumps({"s": 2, "sn": last_sn}))  # 心跳PING

                # 接收消息
                async for message in ws:
                    try:
                        # 解压数据（如果启用压缩）
                        decompressed_data = zlib.decompress(message).decode('utf-8')
                        data = json.loads(decompressed_data)
                    except zlib.error:
                        # 如果数据未压缩，直接解析
                        data = json.loads(message)

                    # 处理信令
                    if data['s'] == 1:  # HELLO信令
                        if data['d']['code'] == 0:
                            session_id = data['d']['session_id']
                            print(f"HELLO成功，session_id: {session_id}")
                            asyncio.create_task(heartbeat(30000))  # 启动心跳
                        else:
                            print(f"HELLO失败，错误码: {data['d']['code']}")
                            await handle_reconnect()
                    elif data['s'] == 0:  # EVENT信令
                        await handle_event(data)
                    elif data['s'] == 3:  # PONG信令
                        print("收到PONG")
                    elif data['s'] == 5:  # RECONNECT信令
                        print("收到RECONNECT，重新连接...")
                        await handle_reconnect()
                    elif data['s'] == 6:  # RESUME ACK信令
                        print("RESUME成功")
                break  # 连接成功，退出重试循环
        except (TimeoutError, ConnectionError) as e:
            retry_count += 1
            print(f"连接失败，重试 {retry_count}/{max_retries}: {e}")
            if retry_count < max_retries:
                await asyncio.sleep(retry_delay)
            else:
                raise Exception("连接失败，已达到最大重试次数")

async def handle_event(data):
    """处理事件消息"""
    global last_sn

    # 更新last_sn
    if 'sn' in data:
        last_sn = data['sn']

    # 解析事件数据
    event_data = data['d']
    print(f"收到事件: {event_data}")
    channel_type = event_data.get('channel_type')
    event_type = event_data.get('type')
    target_id = event_data.get('target_id')
    author_id = event_data.get('author_id')
    content = event_data.get('content')
    msg_id = event_data.get('msg_id')
    msg_timestamp = event_data.get('msg_timestamp')
    extra = event_data.get('extra', {})

    # 处理不同类型的事件
    if event_type == 255:  # 系统消息
        await handle_system_message(extra)
    else:  # 非系统消息（如文字消息、图片消息等）
        await handle_user_message(event_data)

async def handle_system_message(extra):
    """处理系统消息"""
    extra_type = extra.get('type')
    body = extra.get('body', {})

    if extra_type == "joined_channel":  # 用户加入语音频道
        print(f"用户 {body['user_id']} 加入语音频道 {body['channel_id']} (时间: {body['joined_at']})")
    elif extra_type == "exited_channel":  # 用户退出语音频道
        print(f"用户 {body['user_id']} 退出语音频道 {body['channel_id']} (时间: {body['exited_at']})")
    elif extra_type == "user_updated":  # 用户信息更新
        print(f"用户 {body['user_id']} 更新了信息: 用户名={body['username']}, 头像={body['avatar']}")
    elif extra_type == "self_joined_guild":  # 自己新加入服务器
        print(f"自己加入了服务器: {body['guild_id']}, state={body['state']}")
    elif extra_type == "self_exited_guild":  # 自己退出服务器
        print(f"自己退出了服务器: {body['guild_id']}")
    elif extra_type == "message_btn_click":  # Card 消息中的 Button 点击事件
        print(f"用户 {body['user_id']} 点击了消息 {body['msg_id']} 的按钮, value={body['value']}")
    else:
        print(f"收到未知系统消息类型: {extra_type}, 数据: {extra}")

async def handle_user_message(event_data):
    """处理用户消息（非系统消息）"""
    channel_type = event_data.get('channel_type')
    event_type = event_data.get('type')
    target_id = event_data.get('target_id')
    author_id = event_data.get('author_id')
    content = event_data.get('content')
    msg_id = event_data.get('msg_id')
    extra = event_data.get('extra', {})

    # 根据消息类型处理
    if event_type == 1:  # 文字消息
        print(f"收到文字消息: {content} (频道: {target_id}, 发送者: {author_id})")
        if f"(met){BOT_USER_ID}(met)" in content:  # 判断是否@了机器人
            user_message = content.replace(f"(met){BOT_USER_ID}(met)", "").strip()
            reply = await handle_user_query(user_message,event_data)  # 传递 event_data
            await send_message(target_id, f"(met){author_id}(met) {reply}")  # @用户并回复
    elif event_type == 2:  # 图片消息
        print(f"收到图片消息: {content} (频道: {target_id}, 发送者: {author_id})")
    elif event_type == 3:  # 视频消息
        print(f"收到视频消息: {content} (频道: {target_id}, 发送者: {author_id})")
    elif event_type == 4:  # 文件消息
        print(f"收到文件消息: {content} (频道: {target_id}, 发送者: {author_id})")
    elif event_type == 8:  # 音频消息
        print(f"收到音频消息: {content} (频道: {target_id}, 发送者: {author_id})")
    elif event_type == 9:  # KMarkdown 消息
        print(f"收到KMarkdown消息: {content} (频道: {target_id}, 发送者: {author_id})")
        if f"(met){BOT_USER_ID}(met)" in content:  # 判断是否@了机器人
            user_message = content.replace(f"(met){BOT_USER_ID}(met)", "").strip()
            reply = await handle_user_query(user_message, event_data)  # 传递 event_data
            await send_message(target_id, f"(met){author_id}(met) {reply}")  # @用户并回复
    elif event_type == 10:  # Card 消息
        print(f"收到Card消息: {content} (频道: {target_id}, 发送者: {author_id})")
    else:
        print(f"收到未知消息类型: {event_type}, 数据: {event_data}")

async def send_message(channel_id, text):
    """发送消息"""
    async with aiohttp.ClientSession() as session:
        await session.post(
            "https://www.kookapp.cn/api/v3/message/create",
            headers={"Authorization": f"Bot {BOT_TOKEN}"},
            json={"channel_id": channel_id, "content": text}
        )

async def handle_reconnect():
    """处理重连"""
    global session_id, last_sn
    session_id = None
    last_sn = 0
    await connect_to_gateway()

if __name__ == "__main__":
    asyncio.run(connect_to_gateway())