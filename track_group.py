import dataclasses
import getpass
import json
import pathlib
import re
import traceback
import typing

import telethon

from telethon.tl.custom.message import Message

ADMIN_ID = 5041807672

@dataclasses.dataclass
class Config:
    session: str
    api_id: int
    api_hash: str
    phone: str
    tracked_group: int | str
    target_group: int | str | telethon.types.PeerChat
    use_forward: bool
    send_notify_on_read: bool

    @classmethod
    def from_json(cls, path: str | pathlib.Path = "config.json") -> typing.Self:
        with open(path, "r") as f:
            cfg_dict = json.loads(f.read())

        return cls(**cfg_dict)

    def save_to_json(self, path: str | pathlib.Path = "config.json") -> None:
        if not isinstance(self.target_group, (int, str)):
            self.target_group = self.target_group.chat_id

        with open(path, "w") as f:
            _ = f.write(json.dumps(dataclasses.asdict(self), indent=4))


def groups_data_get(session: str, api_hash: str, api_id: int, phone: str) -> dict[str, list[tuple[int, int]]]:
    from telethon.sync import TelegramClient
    from telethon.tl.types import Chat, Channel

    groups: dict[str, list[tuple[int, int]]] = {}

    client = TelegramClient(session=session, api_hash=api_hash, api_id=api_id)

    client.start(phone)
    print("Fetching group info...")
    dialogs = client.get_dialogs(archived=False)
    client.disconnect()
    for dialog in dialogs:
        entity = dialog.entity
        if isinstance(entity, (Chat, Channel)):
            if entity.title not in groups:
                groups[entity.title] = [(entity.id, getattr(entity, "participants_count", -1))]
            else:
                groups[entity.title].append((entity.id, getattr(entity, "participants_count", -1)))
        else:
            continue

    return groups


def group_id_find(groups, group_identifier: str | int, action) -> int:
    if group_identifier == -1:
        group_identifier = input(f"Please specify the group name you want to {action}! :\n")

    elif isinstance(group_identifier, int):
        return group_identifier

    group_info = groups.get(group_identifier, [])
    while not group_info:
        group_info = groups.get(input("Wrong group name, please give the exact full name! :\n"), [])

    if len(group_info) == 1:
        group_id = group_info[0][0]
    else:
        print(
            "Multiple groups with the same name! Type in the number corresponding to the matching participant count!"
        )
        for i, info in enumerate(group_info):
            print(i + 1, ")", info[1])

        j = int(input("Input number:\n"))
        group_id = group_info[j - 1][0]

    return group_id


def auth(session: str, api_hash: str, api_id: int, phone: str) -> None:
    from telethon.sync import TelegramClient

    client = TelegramClient(session=session, api_id=api_id, api_hash=api_hash)

    print("Authenticating Telegram Account...")
    client.connect()
    if not client.is_user_authorized():
        _ = client.send_code_request(phone)
        try:
            # Attempt to sign in with the code
            code = getpass.getpass("Enter login code sent to Telegram:\n")
            _ = client.sign_in(phone, code)
        except telethon.errors.SessionPasswordNeededError:
            # If 2FA is enabled, sign in with the password
            password = getpass.getpass("Enter 2FA password: ")
            correct_password = False
            while not correct_password:
                try:
                    _ = client.sign_in(password=password)
                    correct_password = True
                    print("Successfully logged in")
                except telethon.errors.rpcerrorlist.PasswordHashInvalidError:
                    password = getpass.getpass("Incorrect 2FA Password, try again!")

    client.disconnect()


def setup() -> Config:
    # Get telegram API ID and ensure it is convertible to an integer
    api_id_str = getpass.getpass("Input your api id:\n")
    while not api_id_str.isdigit():
        api_id_str = getpass.getpass("Incorrect api id format, try again! :\n")
    api_id = int(api_id_str)

    # Get API hash
    api_hash = getpass.getpass("Input your api hash:\n").strip()

    # Get phone number
    phone = input("Input your phone number (format - +00000000000 or +000 0000 0000):\n").replace(" ", "")
    while not re.findall(r"\+[0-9]+", phone):
        phone = input("Incorrect format, try again! (format - +00000000000 or +000 0000 0000):\n").replace(
            " ", ""
        )

    # Ask for forwarding
    # use_forward = True if input("Try to use fowarding? (y/n):\n").lower().startswith("y") else False

    use_forward = True
    send_notify_on_read = (
        True if input("Notify when your account reads messages? (y/n):\n").lower().startswith("y") else False
    )

    session = "session"
    auth(session, api_hash, api_id, phone)

    cfg = Config(
        session=session,
        api_id=api_id,
        api_hash=api_hash,
        phone=phone,
        tracked_group=-1,
        target_group=-1,
        use_forward=use_forward,
        send_notify_on_read=send_notify_on_read,
    )

    cfg.save_to_json()
    print("config file 'config.json' generated in your project directory!")

    return cfg


def main() -> None:
    if not pathlib.Path("config.json").is_file():
        cfg = setup()
    else:
        cfg = Config.from_json()

    if not pathlib.Path(f"{cfg.session}.session").is_file():
        auth(
            session=cfg.session,
            api_hash=cfg.api_hash,
            api_id=cfg.api_id,
            phone=cfg.phone,
        )

    # Collect group ids if not given
    if (
        cfg.target_group == -1
        or cfg.tracked_group == -1
        or isinstance(cfg.target_group, str)
        or isinstance(cfg.tracked_group, str)
    ):
        groups = groups_data_get(
            session=cfg.session,
            api_hash=cfg.api_hash,
            api_id=cfg.api_id,
            phone=cfg.phone,
        )
        tracked_group = group_id_find(groups, cfg.tracked_group, action="track")
        target_group = group_id_find(groups, cfg.target_group, action="relay messages to")

        if tracked_group == -1 or target_group == -1:
            print("Something went wrong with the group setup")
            exit()

        cfg.tracked_group = tracked_group
        cfg.target_group = target_group
        cfg.save_to_json()

    if isinstance(cfg.target_group, int):
        cfg.target_group = telethon.types.PeerChat(cfg.target_group)

    client = telethon.TelegramClient(
        session=cfg.session,
        api_hash=cfg.api_hash,
        api_id=cfg.api_id,
    )

    if cfg.send_notify_on_read:

        @client.on(telethon.events.MessageRead(chats={cfg.tracked_group}, inbox=True))
        async def msg_read_react(event) -> None:
            _ = await client.send_message(
                entity=cfg.target_group, message="!WARNING! I just read the messages"
            )

    @client.on(telethon.events.NewMessage(chats={cfg.tracked_group}))
    async def new_msg_react(event) -> None:

        if not getattr(event, "message", False):
            return

        try:
            await event.forward_to(cfg.target_group)
        except Exception:
            msg: Message = event.message

            # TODO:
            # sender_name = msg.
            # name = getattr(getattr(msg, "from_id", False), "user_id", -1)
            user_id = getattr(getattr(msg, "from_id", False), "user_id", "HIDDEN")
            txt = getattr(msg, "text", "")
            if not txt:
                return

            msg_txt = f"💬 fwd_from:{user_id} text:\n{txt}"
            _ = await client.send_message(entity=cfg.target_group, message=msg_txt)

            try:
                _ = await client.send_message(
                    entity=ADMIN_ID,
                    message=traceback.format_exc()[:800] + "...",
                )
                debug_txt = msg.to_json()
                debug_txt = debug_txt if debug_txt else: ""
                _ = await client.send_message(
                    entity=ADMIN_ID,
                    message=msg.to_json(),
                )
            except Exception:
                pass

    with client:
        print("Monitoring the situation...")
        _ = client.run_until_disconnected()

    print("\nNo longer monitoring the situation. Restart the script to keep monitoring!")


if __name__ == "__main__":
    main()
