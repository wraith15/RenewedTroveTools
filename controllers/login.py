from models.interface import Controller
from flet import (
    Divider,
    Card,
    Text,
    TextStyle,
    Column,
    Row,
    Chip,
    Icon,
    TextField,
    Container,
)
from models.interface import RTTImage
from utils.kiwiapi import API_URL, API_ENABLED, API_DISABLED_REASON
from utils.locale import loc
from flet_core import padding, MainAxisAlignment


class LoginController(Controller):
    def setup_controls(self):
        api_disabled = not API_ENABLED
        self.token_input = TextField(
            data="input",
            label=loc("Insert pass key here"),
            text_align="center",
            password=True,
            can_reveal_password=True,
            helper_style=TextStyle(color="red"),
            on_change=self.execute_login,
            content_padding=10,
            autofocus=True,
            disabled=api_disabled,
            helper_text=API_DISABLED_REASON if api_disabled else None,
        )
        discord_login = Chip(
            leading=Icon("discord"),
            label=Text("Discord"),
            on_click=self.execute_login_discord,
            disabled=api_disabled,
        )
        trovesaurus_login = Chip(
            leading=RTTImage(
                src="https://trovesaurus.com/images/logos/Sage_64.png?1",
                width=24,
            ),
            label=Text("Trovesaurus"),
            on_click=self.execute_login_trovesaurus,
            disabled=api_disabled,
        )
        self.main = Card(
            Container(
                Column(
                    controls=[
                        Text(
                            value=loc("Login"), size=40, width=460, text_align="center"
                        ),
                        self.token_input,
                        Text(
                            loc("👇Get pass key from👇"), width=460, text_align="center"
                        ),
                        Text(
                            API_DISABLED_REASON,
                            width=460,
                            text_align="center",
                            visible=api_disabled,
                            color="yellow",
                        ),
                        Row(
                            controls=[discord_login, trovesaurus_login],
                            width=400,
                            alignment=MainAxisAlignment.SPACE_EVENLY,
                        ),
                        Divider(),
                        Chip(
                            label=Text(loc("Go back")),
                            on_click=self.cancel_login,
                            width=460,
                        ),
                    ],
                    horizontal_alignment="center",
                ),
                padding=padding.all(20),
            ),
            width=500,
        )

    def setup_events(self):
        pass

    async def execute_login(self, e):
        if not API_ENABLED:
            self.token_input.helper_text = API_DISABLED_REASON
            return await self.token_input.update_async()
        if self.token_input.value.strip():
            self.page.user_data = await self.page.RTT.login(
                self.token_input.value.strip()
            )
            if self.page.user_data is None:
                self.token_input.helper_text = loc("Invalid pass key")
                return await self.token_input.update_async()
            else:
                await self.page.RTT.setup_appbar()
                await self.page.go_async("/")
        else:
            return

    async def execute_login_discord(self, e):
        if not API_ENABLED:
            await self.page.snack_bar.show(API_DISABLED_REASON, color="yellow")
            return
        await self.page.launch_url_async(f"{API_URL}/user/discord/login")

    async def execute_login_trovesaurus(self, e):
        if not API_ENABLED:
            await self.page.snack_bar.show(API_DISABLED_REASON, color="yellow")
            return
        await self.page.launch_url_async("https://trovesaurus.com/profile")

    async def cancel_login(self, e):
        await self.page.go_async("/")
