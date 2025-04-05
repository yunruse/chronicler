# Chronicler

This is a tiny Discord bot intended to chronicle one-word-story channels.

Requires Python 3.9 and:

```sh
pip install discordpy emoji toml
```

# Setup
0. Optionally, create a `banned_words.txt` so that the bot does not repeat slurs etc. I source from [this source](https://github.com/Hesham-Elbadawi/list-of-banned-words/tree/master) personally.

1. Create a channel for users to type a word in, and a channel for the bot to assemble sentences in. They may be the same channel if you wish. I personally have a thread inside the channel where the bot posts.

2. [**Create a bot.**](https://discord.com/developers/applications) It'll need permissions to:
  - read messages and channel history,
  - manage messages (in the input thread),
  - send messages (in the input and output threads).
3. Put the bot's API key into `discord.keys` (no newline).
4. Copy `config.example.toml`, filling out [**the channel IDs**](https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID).
5. Run it!
