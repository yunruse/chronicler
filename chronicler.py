from asyncio import sleep
from pathlib import Path
import re

from discord import Client, TextChannel, Message
from discord import CustomActivity, MessageType, Intents

import toml
import emoji

FP_BLOCKED_WORDS = Path('banned_words.txt')
if FP_BLOCKED_WORDS.is_file():
    BLOCKED_WORDS = set(FP_BLOCKED_WORDS.read_text().strip().splitlines())
else:
    BLOCKED_WORDS = set()

CLIENT_KEY = Path('discord.keys').read_text().strip()

with open('config.toml') as f:
    CONFIG = toml.load(f)

CONFIG.setdefault('state', {})
CONFIG['state'].setdefault('sentence_count', 0)
CONFIG['state'].setdefault('last_message_dt', None)
CONFIG.setdefault('subs', {})

NON_TEXT = re.compile(r'^[^\w(\'"]')
SENTENCE_END = re.compile(r'(.*)[.…!?]+$')

def has_emoji(string: str):
    DISCORD_EMOJI = re.compile(r'<a?:[a-zA-Z0-9_]+?:\d+>')
    return any(emoji.analyze(string)) or any(DISCORD_EMOJI.findall(string))

def is_multiple_words(string: str):
    if len(string.split()) > 1:
        return True
    if '\u2800' in string:
        # Braille pattern blank
        return True
    return False

def is_blocked(word: str):
    # remove punctuation; set lowercase
    word_p = SENTENCE_END.sub('\\1', word.lower())
    print('Scanning:', word_p, word_p in BLOCKED_WORDS)
    return word_p in BLOCKED_WORDS

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

    async def assemble_sentence(self, sentence_end_id: int):
        sentence_end_seen = False
        words = []
        async for m in self.input_channel.history(limit=200):
            if (dtl := CONFIG['state']['last_message_dt']) and m.created_at <= dtl:
                break
            if m.author.bot:
                continue
            if m.type != MessageType.default:
                continue
            if m.id == sentence_end_id:
                sentence_end_seen = True

            content = m.clean_content.strip()
            if is_blocked(content):
                continue
            if len(words):
                if SENTENCE_END.match(content) or is_multiple_words(content):
                    # Timestamp is a bit outdated somehow!
                    break
            words.append(CONFIG['subs'].pop(str(m.id), content))
        
        if not sentence_end_seen:
            return

        async for m in self.input_channel.history(limit=1):
            timestamp = m.created_at

        await self.output_channel.send(' '.join(words[::-1]))

        CONFIG['state']['last_message_dt'] = timestamp
        CONFIG['state']['sentence_count'] += 1

        await self.save_config()

        await self.update_status()


    async def on_message(self, msg: Message):
        if msg.author.bot:
            return
        if msg.channel != self.input_channel:
            return

        content = msg.clean_content.strip()

        async for m in self.input_channel.history(limit=2):
            # TODO: This doesn't account for if the user spams
            last_msg = m

        if is_blocked(content):
            return

        if msg.author == last_msg.author and msg.id != last_msg.id:
            return await self.error(msg, 'WAIT_TURN')
        if msg.attachments or msg.embeds or msg.stickers or has_emoji(content):
            return await self.error(msg, 'TEXT_ONLY')
        if is_multiple_words(content):
            return await self.error(msg, 'ONE_WORD')
        if len(content) > CONFIG['error']['MAX_CHAR_LENGTH']:
            return await self.error(msg, 'ONE_WORD')
        if NON_TEXT.match(content):
            return await self.error(msg, 'TEXT_ONLY')

        if SENTENCE_END.match(content):
            return await self.assemble_sentence(msg.id)

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

        def malformed(x: str):
            return (
                len(x) > CONFIG['error']['MAX_CHAR_LENGTH'] or 
                NON_TEXT.match(after.clean_content) or
                is_multiple_words(after.clean_content))

        if malformed(after.clean_content):
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

if __name__ == '__main__':
    intents = Intents.default()
    intents.message_content = True

    client = Chronicler(intents=intents)
    client.run(CLIENT_KEY)
