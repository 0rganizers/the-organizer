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
    - [x] specify server settings with `/ctfnote_update_auth`
    - [x] create a ctfnote pad for a `/chall`
    - [x] pin ctfnote link to the channel
    - [x] `/ctfnote_assign_player` assigns a player to be the challenge leader and annotates it in ctfnote. 
        - [x] If the player has not registered, it will be autoregistered
    - [ ] `/flag` should mark it as flagged on ctfnote
    - [ ] support for more than one concurrent ctf
    - [ ] better authentication - the ctfnote auth only is for the ctfnote stuff, but the underlying hedgedoc markdown can be accessed directly by the pad urls. They are hard to guess, but still...


Currently in development by:
- Robin Jadoul
- Cyanpencil
- Lucid

