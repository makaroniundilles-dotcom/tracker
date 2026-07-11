import dataclasses
import getpass
import json
import pathlib
import typing
import argparse

# TODO: improve tracebacks and logs
# TODO: simplify the deployment process so that it is easy to migrate platform

import telethon
from telethon.tl.custom.message import Message


RICKBOT_ID = 6126376117


@dataclasses.dataclass
class Config:
    session: str
    api_id: int
    api_hash: str
    phone: str
    tracked_group: int
    target_group: int

    @classmethod
    def from_json(cls, path: str | pathlib.Path = "config.json") -> typing.Self:
        with open(path, "r") as f:
            cfg_dict = json.loads(f.read())

        return cls(**cfg_dict)

    def save_to_json(self, path: str | pathlib.Path = "config.json") -> None:
        with open(path, "w") as f:
            _ = f.write(json.dumps(dataclasses.asdict(self), indent=4))



def args_parse():
    parser = argparse.ArgumentParser(
        description="Telegram tracker script"
    )

    parser.add_argument(
        "-g",
        "--get-groups",
        action="store_true",
        help="Fetch groups, otherwise track groups using the provided config file",
    )

    return parser.parse_args()


def groups_data_get() -> None:
    from telethon.sync import TelegramClient
    from telethon.tl.types import Channel, Chat

    cfg = Config.from_json()
    print(cfg)

    if not pathlib.Path(f"{cfg.session}.session").is_file():
        auth(session=cfg.session, api_hash=cfg.api_hash, api_id=cfg.api_id, phone=cfg.phone)

    with TelegramClient(session=cfg.session, api_hash=cfg.api_hash, api_id=cfg.api_id) as client:
        print("Fetching group info...")
        dialogs = client.get_dialogs(archived=False)

    groups_data = []
    for dialog in dialogs:
        entity = dialog.entity

        if isinstance(entity, (Channel, Chat)):
            group_info = {
                "id": entity.id,
                "name": entity.title,
                "type": "channel" if isinstance(entity, Channel) else "group",
                "is_private": getattr(entity, "access_hash", None) is not None,
                "participant_count": getattr(entity, "participants_count", "N/A"),
            }

            # Additional info for channels
            if isinstance(entity, Channel):
                group_info["is_broadcast"] = entity.broadcast
                group_info["is_megagroup"] = entity.megagroup
                group_info["username"] = getattr(entity, "username", None)

            groups_data.append(group_info)

    # Save to JSON file
    with open("telegram_groups.json", "w", encoding="utf-8") as f:
        json.dump(groups_data, f, indent=2, ensure_ascii=False)

    print(f"\nSuccessfully saved {len(groups_data)} groups to 'telegram_groups.json'")
    print(f"\nAccess using command - 'less telegram_groups.json'")


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


def get_target(session: str, api_hash: str, api_id: int, target_group: int):
    from telethon.sync import TelegramClient

    with TelegramClient(session=session, api_id=api_id, api_hash=api_hash) as client:
        target = client.get_input_entity(telethon.types.PeerChannel(target_group))

    return target


def runner() -> None:
    cfg = Config.from_json()
    if not pathlib.Path(f"{cfg.session}.session").is_file():
        auth(session=cfg.session, api_hash=cfg.api_hash, api_id=cfg.api_id, phone=cfg.phone)

    client = telethon.TelegramClient(session=cfg.session, api_hash=cfg.api_hash, api_id=cfg.api_id)
    TARGET = get_target(session=cfg.session, api_hash=cfg.api_hash, api_id=cfg.api_id, target_group=cfg.target_group)

    @client.on(telethon.events.NewMessage(chats={cfg.tracked_group}))
    async def new_msg_react(event) -> None:
        if not getattr(event, "message", False):
            return
        try:
            await event.forward_to(TARGET)
        except Exception:
            msg: Message = event.message
            user_id = getattr(getattr(msg, "from_id", False), "user_id", "HIDDEN")
            txt = getattr(msg, "text", "")
            if not txt:
                return
            if user_id == RICKBOT_ID:
                user_id = "RickBot"
            msg_txt = f"💬 fwd_from:{user_id} text:\n{txt}"
            _ = await client.send_message(entity=TARGET, message=msg_txt)

    with client:
        print("Monitoring the situation...")
        _ = client.run_until_disconnected()

    print("\nNo longer monitoring the situation. Restart the script to keep monitoring!")


def main():

    args = args_parse()

    if not args.get_groups:
        runner()
    else:
        groups_data_get()


if __name__ == "__main__":
    main()
