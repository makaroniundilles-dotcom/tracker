import dataclasses
import getpass
import json
import pathlib
import typing

# TODO: improve tracebacks and logs
# TODO: improve adding more groups
# TODO: get targets to improve forwarding speeds

import telethon
from telethon.tl.custom.message import Message

ADMIN_ID = 1301596502
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


def groups_data_get(session: str, api_hash: str, api_id: int, phone: str) -> dict[str, list[tuple[int, int]]]:

    from telethon.sync import TelegramClient
    from telethon.tl.types import Channel, Chat

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
                groups[entity.title] = [
                    (entity.id, getattr(entity, "participants_count", -1))
                ]
            else:
                groups[entity.title].append(
                    (entity.id, getattr(entity, "participants_count", -1))
                )
        else:
            continue

    return groups


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

    client = TelegramClient(session=session, api_id=api_id, api_hash=api_hash)

    client.connect()

    target = client.get_input_entity(telethon.types.PeerChannel(cfg.target_group))

    client.disconnect()

    return target


def main() -> None:

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


if __name__ == "__main__":
    main()
