import asyncio
import discord
from quart import Quart, jsonify, request

from DiscordClient import client 
import config

app = Quart(__name__)

@app.route('/', methods=['GET'])
def index():
    return "test"

@app.route('/v1/discord/send', methods=['POST'])
async def send_message_discord():
    params = await request.get_json()
    result = ""
    print(params)
    if "message" in params and "channel_id" in params:
        channel_id: int = params["channel_id"]
        mention = ""
        if "mention" in params:
            mention = params["mention"]
        message = mention + params["message"]
        result = await client.send_message_by_channel_id(channel_id, message)

    return jsonify({"result": result})

@app.route('/v1/discord/sheldon/send', methods=['GET', 'POST'])
async def send_message_to_sheldon_channel():
    params = request.json if request.method == "POST" else request.args
    result = ""
    if "msg" in params:
        msg = params["msg"]
        result = await client.send_message("sheldon", msg)

    return jsonify({"result": result})

@app.before_serving
async def before_serving():
    loop = asyncio.get_event_loop()
    await client.login(config.DISCORD_TOKEN)
    loop.create_task(client.connect())

if __name__ == '__main__':
    app.config['JSON_AS_ASCII'] = False
    app.config['JSONIFY_MIMETYPE'] = "application/json;charset=utf-8"
    app.run(debug=True, port=config.APP_PORT)
