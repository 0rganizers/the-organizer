# The Organizer

This is the management bot for the discord server of the Organizers CTF team.

Some planned/wanted features include
- [X] Create a new channel for a challenge
    - [X] Make sure a new channel goes before solved challenges
- [X] Make a channel/challenge as solved
- [X] Prevent unauthorized use
- [ ] Create/remove challenge categories?
- [X] Archive all current "active" challenge channels
- [ ] Manage logins/passwords for contests
- [ ] Autocollect challenges from CTFd-hosted contests, collect descriptions and files, create channels
- [ ] Automatically submit a flag for CTFd contests with managed login
- [ ] Manage a calendar of upcoming contests to see who is interested in a particular CTF, and how much tryharding there will or should be
- [ ] Team- and individual-based opt-in and opt-out
- [ ] ctfnote integration
    - [x] specify server settings with `/ctfnote_update_auth`  (can be done by player)
    - [x] create a ctfnote pad for a `/chall` (can be done by player)
    - [x] pin ctfnote link to the channel
    - [x] `/ctfnote_assign_player` assigns a player to be the challenge leader and annotates it in ctfnote. (can be done by player)
        - [x] If the player has not registered, it will be autoregistered
    - [x] `/ctfnote_who_leads` (can be done by player)
    - [ ] `/flag` should mark it as flagged on ctfnote
    - [ ] support for more than one concurrent ctf
    - [ ] better authentication - the ctfnote auth only is for the ctfnote stuff, but the underlying hedgedoc markdown can be accessed directly by the pad urls. They are hard to guess, but still...


Currently in development by:
- Robin Jadoul
- Cyanpencil
- Lucid

## Setup

*Written for testing*

* create a discord [server for testing](https://discord.gg/CHAMHZfHFX). Also called a `guild` in discord speech.

  * create a role `CTF Player` or similar
  * enable in discord settings (Advanced) the developer mode so you can right-click things to get IDs.
  * right-click the server to get the server ID. E.g. `990596882034221096`
  * find the role IDs for player and admin in the settings

* Get yourself a bot token and client ID from the [discord developer console](https://discord.com/developers/applications)

  * see under "OAuth 2" the client ID and bot token

* Go to "OAuth2", "URL Generator"

  * select `applications.commands`

    > allows your app to use [commands](https://discord.com/developers/docs/interactions/application-commands) in a guild

    ([source](https://discord.com/developers/docs/topics/oauth2))

  * select `bot`

    > for oauth2 bots, this puts the bot in the user's selected guild by default

  * > not sure what you need from the bottom part. We just said "administrator" for testing :sweat_smile:

* copy the `config.sample.json`  to `config.json` and fill it in.

* build and run:

  ```
  docker build -t orgzbot .
  docker run --rm -it orgzbot:latest
  ```

* in the discord server, specify the ctfnote credentials with the `/ctfnote_update_auth` command.
