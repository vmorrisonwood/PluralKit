import logging
import json
import os

import discord

logging.basicConfig(level=logging.DEBUG)
logging.getLogger("discord").setLevel(logging.INFO)
logging.getLogger("websockets").setLevel(logging.INFO)

logger = logging.getLogger("pluralkit.bot")
logger.setLevel(logging.DEBUG)

client = discord.Client()


@client.event
async def on_error(evt, *args, **kwargs):
    logger.exception(
        "Error while handling event {} with arguments {}:".format(evt, args))


@client.event
async def on_ready():
    # Print status info
    logger.info("Connected to Discord.")
    logger.info("Account: {}#{}".format(
        client.user.name, client.user.discriminator))
    logger.info("User ID: {}".format(client.user.id))


@client.event
async def on_message(message):
    # Ignore bot messages
    if message.author.bot:
        return

    # Split into args. shlex sucks so we don't bother with quotes
    args = message.content.split(" ")

    from pluralkit import proxy, utils
    
    command_items = utils.command_map.items()
    command_items = sorted(command_items, key=lambda x: len(x[0]), reverse=True)

    prefix = "pk;"
    for command, (func, _, _, _) in command_items:
        if message.content.startswith(prefix + command):
            args_str = message.content[len(prefix + command):].strip()
            args = args_str.split(" ")

            # Splitting on empty string yields one-element array, remove that
            if len(args) == 1 and not args[0]:
                args = []

            async with client.pool.acquire() as conn:
                await func(conn, message, args)
                return

    # Try doing proxy parsing
    async with client.pool.acquire() as conn:
        await proxy.handle_proxying(conn, message)

@client.event
async def on_socket_raw_receive(msg):
    # Since on_reaction_add is buggy (only works for messages the bot's already cached, ie. no old messages)
    # we parse socket data manually for the reaction add event
    if isinstance(msg, str):
        try:
            msg_data = json.loads(msg)
            if msg_data.get("t") == "MESSAGE_REACTION_ADD":
                evt_data = msg_data.get("d")
                if evt_data:
                    user_id = evt_data["user_id"]
                    message_id = evt_data["message_id"]
                    emoji = evt_data["emoji"]["name"]

                    async with client.pool.acquire() as conn:
                        from pluralkit import proxy
                        await proxy.handle_reaction(conn, user_id, message_id, emoji)
        except ValueError:
            pass

async def run():
    from pluralkit import db
    try:
        logger.info("Connecting to database...")
        pool = await db.connect()

        logger.info("Attempting to create tables...")
        async with pool.acquire() as conn:
            await db.create_tables(conn)

        logger.info("Connecting to InfluxDB...")

        client.pool = pool
        logger.info("Connecting to Discord...")
        await client.start(os.environ["TOKEN"])
    finally:
        logger.info("Logging out from Discord...")
        await client.logout()
