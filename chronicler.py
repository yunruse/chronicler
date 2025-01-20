from asyncio import sleep
from pathlib import Path
import re

from discord import Client, TextChannel, Message
from discord import CustomActivity, MessageType, Intents

import toml

CLIENT_KEY = Path('discord.keys').read_text().strip()

with open('config.toml') as f:
    CONFIG = toml.load(f)

CONFIG.setdefault('state', {})
CONFIG['state'].setdefault('sentence_count', 0)
CONFIG['state'].setdefault('last_message_dt', None)

class Chronicler(Client):
    input_channel: TextChannel
    output_channel: TextChannel

    async def on_ready(self):
        await self.update_status()

        self.input_channel = self.get_channel(int(CONFIG['channel']['input']))
        self.output_channel = self.get_channel(int(CONFIG['channel']['output']))

        print(f'\nMonitoring {self.input_channel} as {self.user}')
    
    async def update_status(self):
        N = CONFIG['state']['sentence_count']
        if N > 0:
            status = f'{N} sentences chronicled so far'
        else:
            status = 'Ready to chronicle!'

        await self.change_presence(activity=CustomActivity(name=status))

    async def error(self, msg: Message, key: str, delete: bool = True):
        "The message was erroneous! Respond and delete."
        reply = await msg.reply(CONFIG['error'].get(key, 'Unknown error!'))
        if delete:
            await msg.delete()
        await sleep(CONFIG['error']['DISPLAY_SECONDS'])
        await reply.delete()
    
    async def get_sentence(self):
        words = []
        async for m in self.input_channel.history(limit=200):
            if (dtl := CONFIG['state']['last_message_dt']) and m.created_at <= dtl:
                break
            if m.author == self.user:
                continue
            if m.type != MessageType.default:
                continue
            words.append(m.clean_content)

        async for m in self.input_channel.history(limit=1):
            timestamp = m.created_at
        return ' '.join(words[::-1]), timestamp

    async def assemble_sentence(self):
        sentence, timestamp = await self.get_sentence()
        print(sentence, timestamp)
        await self.output_channel.send(sentence)

        CONFIG['state']['last_message_dt'] = timestamp
        CONFIG['state']['sentence_count'] += 1
        with open('config.toml', 'w') as f:
            toml.dump(CONFIG, f)

        await self.update_status()


    async def on_message(self, msg: Message):
        if msg.author == self.user:
            return
        if msg.channel != self.input_channel:
            return

        content = msg.clean_content.strip()

        if msg.author == self.input_channel.last_message.author:
            return await self.error(msg, 'WAIT_TURN')
        if len(msg.attachments) or len(msg.embeds):
            return await self.error(msg, 'TEXT_ONLY')
        if len(content.split()) > 1:
            return await self.error(msg, 'ONE_WORD')
        
        if re.match(r'^[^\w(\'"]', content):
            return await self.error(msg, 'TEXT_ONLY')
        
        # TODO: word blocklist, maybe..?

        print(content)
        
        if re.match(r'.*[.…!?]+$', content):
            return await self.assemble_sentence()

intents = Intents.default()
intents.message_content = True

client = Chronicler(intents=intents)
client.run(CLIENT_KEY)
