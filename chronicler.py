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
CONFIG.setdefault('subs', {})

NON_TEXT = re.compile(r'^[^\w(\'"]')
SENTENCE_END = re.compile(r'.*[.…!?]+$')

class Chronicler(Client):
    input_channel: TextChannel
    output_channel: TextChannel

    async def on_ready(self):
        await self.update_status()

        self.input_channel = self.get_channel(int(CONFIG['channel']['input']))
        self.output_channel = self.get_channel(int(CONFIG['channel']['output']))

        print(f'\nMonitoring {self.input_channel} as {self.user}')
    
    async def save_config(self):
        with open('config.toml', 'w') as f:
            toml.dump(CONFIG, f)
    
    async def update_status(self):
        N = CONFIG['state']['sentence_count']
        if N > 0:
            sentence = 'sentences' if N > 1 else 'sentence'
            status = f'{N} {sentence} chronicled so far'
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
    
    async def assemble_sentence(self):
        words = []
        async for m in self.input_channel.history(limit=200):
            if (dtl := CONFIG['state']['last_message_dt']) and m.created_at <= dtl:
                break
            if m.author == self.user:
                continue
            if m.type != MessageType.default:
                continue
            words.append(CONFIG['subs'].pop(str(m.id), m.clean_content))

        async for m in self.input_channel.history(limit=1):
            timestamp = m.created_at

        await self.output_channel.send(' '.join(words[::-1]))

        CONFIG['state']['last_message_dt'] = timestamp
        CONFIG['state']['sentence_count'] += 1

        await self.save_config()

        await self.update_status()


    async def on_message(self, msg: Message):
        if msg.author == self.user:
            return
        if msg.channel != self.input_channel:
            return

        content = msg.clean_content.strip()

        async for m in self.input_channel.history(limit=2):
            last_msg = m

        if msg.author == last_msg.author and msg.id != last_msg.id:
            return await self.error(msg, 'WAIT_TURN')
        if len(msg.attachments) or len(msg.embeds):
            return await self.error(msg, 'TEXT_ONLY')
        if len(content.split()) > 1:
            return await self.error(msg, 'ONE_WORD')
        if NON_TEXT.match(content):
            return await self.error(msg, 'TEXT_ONLY')

        # TODO: word blocklist, maybe..?

        if SENTENCE_END.match(content):
            return await self.assemble_sentence()

    async def on_message_edit(self, before: Message, after: Message):
        """
        Check message edits. This allows for:
        - posting a sentence, if the final word suddenly gained a fullstop etc;
        - keeping an old version of a word, iff it became malformed
        - deleting the above kept substitution if the message is now fine
        """
        if before.author == self.user:
            return
        if before.channel != self.input_channel:
            return

        if (dtl := CONFIG['state']['last_message_dt']) and before.created_at <= dtl:
            return
        
        became_malformed = False

        is_most_recent = after.id == self.input_channel.last_message_id
        was_end = bool(SENTENCE_END.match(before.clean_content))
        now_end = bool(SENTENCE_END.match(after.clean_content))

        if NON_TEXT.match(after.clean_content) or len(after.clean_content.split()) > 1:
            became_malformed = True
        elif is_most_recent:
            if not was_end and now_end:
                # Final message was changed to be the end..!
                return await self.assemble_sentence()
        elif now_end:
            became_malformed = True
        
        if became_malformed:
            CONFIG['subs'][str(before.id)] = before.clean_content
            await self.save_config()
        elif str(before.id) in CONFIG['subs']:
            del CONFIG['subs'][str(before.id)]
            await self.save_config()

intents = Intents.default()
intents.message_content = True

client = Chronicler(intents=intents)
client.run(CLIENT_KEY)
