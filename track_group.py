import asyncio
import dataclasses
import getpass
import json
import pathlib
import typing

import telethon

@dataclasses.dataclass
class Config:
    session: str
    api_id: int
    api_hash: str
    phone: str
    tracked_group: int
    target_group: int | telethon.types.PeerChat
    use_forward: bool
    send_notify_on_read: bool

    @classmethod
    def from_json(cls, path: str | pathlib.Path ="config.json") -> typing.Self:
        with open(path, "r") as f:
            cfg_dict = json.loads(f.read())

        return cls(**cfg_dict)

    def save_to_json(self, path: str | pathlib.Path ="config.json") -> None:

        if not isinstance(self.target_group, int):
            self.target_group = self.target_group.chat_id

        with open(path, "w") as f:
            _ = f.write(json.dumps(dataclasses.asdict(self), indent=4))


def get_groups(session, api_hash, api_id):

    from telethon.sync import TelegramClient
    from telethon.tl.types import Chat

    groups = {}

    client = TelegramClient(session=session, api_hash=api_hash, api_id=api_id)

    client.start(cfg.phone_number)
    dialogs = client.get_dialogs(archived=False)
    client.disconnect()

    for dialog in dialogs:
        entity = dialog.entity
        if isinstance(entity, Chat):
            if entity.title not in groups:
                groups[entity.title] = [(entity.id, getattr(entity, "participants_count", -1))]
            else:
                groups[entity.title].append((entity.id, getattr(entity, "participants_count", -1)))
        else:
            continue


    tracked_group_info = groups.get(input("Please specify the group name you want to track! :\n"), False) 
    while not tracked_group_info:
        tracked_group_info = groups.get(input("Wrong group name, please give the exact full name! :\n"), False)

    if len(tracked_group_info) == 1:
        tracked_group = tracked_group_info[0][0] 
    else:
        print("Multiple groups with the same name! Type in the number corresponding to the matching participant count!")
        for i, info in enumerate(tracked_group_info):
            print(i + 1, ")" , info[1]) 

        j = int(input("Input number:\n"))
        tracked_group = tracked_group_info[j][0] 


    target_group_info = groups.get(input("Please specify the group name you want to send messages to! :\n"), False) 
    while not target_group_info:
        tracked_group_info =  groups.get(input("Wrong group name, please give the exact full name! :\n"), False)

    if len(target_group_info) == 1:
        target_group = target_group_info[0][0] 
    else:
        print("Multiple groups with the same name! Type in the number corresponding to the matching participant count!")
        for i, info in enumerate(target_group_info):
            print(i + 1, ")" , info[1]) 

        j = int(input("Input number:\n"))
        target_group = target_group_info[j][0] 

    return tracked_group, target_group


def auth(session: str, api_hash: str, api_id: int, phone: str) -> None:
    from telethon.sync import TelegramClient

    client = TelegramClient(session=session, api_id=api_id, api_hash=api_hash)

    print("Authenticating Telegram Account...")
    client.connect()
    if not client.is_user_authorized():
        _ = client.send_code_request(phone) 
        try:
            # Attempt to sign in with the code
            code = getpass.getpass('Enter login code sent to Telegram:\n')
            _ = client.sign_in(phone, code)
        except telethon.errors.SessionPasswordNeededError:
            # If 2FA is enabled, sign in with the password
            password = getpass.getpass('Enter 2FA password: ')
            correct_password = False
            while not correct_password:
                try:
                    _ = client.sign_in(password=password)
                    correct_password = True
                except telethon.errors.rpcerrorlist.PasswordHashInvalidError:
                    password = getpass.getpass('Incorrect 2FA Password, try again!')
            
    client.disconnect()


def setup() -> Config:

    api_id = int(getpass.getpass("Input your api id:\n"))
    api_hash = getpass.getpass("Input your api hash:\n")
    phone = input("Input your phone number (format - +00000000000 or +000 0000 0000):\n").replace(" ", "")
    use_forward = True if input("Try to use fowarding? (y/n):\n").lower().startswith("y") else False
    send_notify_on_read = True if input("Notify when your account reads messages? (y/n):\n").lower().startswith("y") else False

    session = "session"

    client = telethon.TelegramClient(session=session, api_hash=api_hash, api_id=api_id)

    asyncio.run(auth(client, phone_number))

    cfg = Config(
        session=session,
        api_id=api_id,
        api_hash=api_hash,
        phoner=phone,
        tracked_group=-1,
        target_group=-1,
        use_forward=use_forward,
        send_notify_on_read = send_notify_on_read,
    )

    cfg.save_to_json()

    return cfg


def main() -> None:
    
    if not pathlib.Path("config.json").is_file():
        cfg = setup()
    else:
        cfg = Config.from_json()

    if not pathlib.Path(f"{cfg.session_name}.session").is_file():
        auth(session=cfg.session_name, api_hash=cfg.api_hash, api_id=cfg.api_id, phone=cfg.phone_number)


    if cfg.target_group == -1 or cfg.tracked_group == -1:
        tracked_group, target_group = get_groups(cfg)  # 5089441788, 4041853571
        if (tracked_group, target_group) == (-1, -1):
            exit()
        cfg.tracked_group = tracked_group
        cfg.target_group = target_group
        cfg.save_to_json()

    if isinstance(cfg.target_group, int):
        cfg.target_group = telethon.types.PeerChat(cfg.target_group)

    client = telethon.TelegramClient(session=cfg.session_name, api_hash=cfg.api_hash, api_id=cfg.api_id)

    if cfg.send_notify_on_read:

        @client.on(telethon.events.MessageRead(chats={cfg.tracked_group}, inbox=True))
        async def msg_read_react(event) -> None:
            _ = await client.send_message(entity=cfg.target_group, message="!WARNING! I just read the messages")
                
    @client.on(telethon.events.NewMessage(chats={cfg.tracked_group}))
    async def new_msg_react(event) -> None:

        if cfg.use_forward:
            try:
                await event.forward_to(cfg.target_group)
            except Exception:
                cfg.use_forward = False
                cfg.save_to_json()
                _ = await client.send_message(entity=cfg.target_group, message=event.message.text)
        else:
            _ = await client.send_message(entity=cfg.target_group, message=event.message.text)

    with client:
        print("Monitoring the situation...")
        client.run_until_disconnected()

    print("\nNo longer monitoring the situation. Restart the script to keep monitoring!")

if __name__ == "__main__":
    main()
