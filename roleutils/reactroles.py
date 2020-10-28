import logging
from typing import List, Union

import discord
from redbot.core import commands
from redbot.core.commands import IDConverter
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import pagify
from redbot.core.utils.menus import menu, close_menu, DEFAULT_CONTROLS

from .abc import MixinMeta
from .converters import StrictRole, RealEmojiConverter
from .utils import my_role_heirarchy

log = logging.getLogger("red.phenom4n4n.roleutils.reactroles")


class ReactRoles(MixinMeta):
    """
    Reaction Roles.
    """

    def __init__(self, *_args):
        super().__init__(*_args)
        self.cache["reactroles"] = {"channel_cache": set(), "message_cache": set()}

    async def initialize(self):
        log.debug("ReactRole Initialize")
        await self._update_cache()
        await super().initialize()

    async def _update_cache(self):
        all_guilds = await self.config.all_guilds()
        all_guildmessage = await self.config.custom("GuildMessage").all()
        self.cache["reactroles"]["message_cache"].update(
            msg_id for guild_data in all_guildmessage.values() for msg_id in guild_data.keys()
        )
        self.cache["reactroles"]["channel_cache"].update(
            chnl_id
            for guild_data in all_guilds.values()
            for chnl_id in guild_data["reactroles"]["channels"]
            if guild_data["reactroles"]["enabled"]
        )

    def _edit_cache(self, message: discord.Message, remove=False):
        if not remove:
            self.cache["reactroles"]["message_cache"].add(message.id)
            self.cache["reactroles"]["channel_cache"].add(message.channel.id)
        else:
            self.cache["reactroles"]["message_cache"].remove(message.id)
            self.cache["reactroles"]["channel_cache"].remove(message.channel.id)

    async def bulk_delete_set_roles(
        self, guild: discord.Guild, message_id: IDConverter, emoji_ids: List[int]
    ):
        ...  # TODO delete rr's on guildmessage from given emoji id

    @commands.is_owner()
    @commands.group(aliases=["rr"])
    async def reactrole(self, ctx: commands.Context):
        """Reaction Role management."""

    @commands.admin_or_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @reactrole.command(name="add")
    async def reactrole_add(
        self,
        ctx: commands.Context,
        message: discord.Message,
        emoji: RealEmojiConverter,
        role: StrictRole,
    ):
        """Add a reaction role to a message."""
        async with self.config.custom("GuildMessage", ctx.guild.id, message.id).reactroles() as r:
            r["react_to_roleid"][emoji if isinstance(emoji, str) else str(emoji.id)] = role.id
            r["channel"] = message.channel.id
            r["rules"] = None
        if str(emoji) not in [str(emoji) for emoji in message.reactions]:
            await message.add_reaction(emoji)
        await ctx.send(f"{emoji} has been binded to {role} on {message.jump_url}")

        # Add this message and channel to tracked cache
        self._edit_cache(message)

    @commands.admin_or_permissions(manage_roles=True)
    @reactrole.group(name="delete", aliases=["remove"], invoke_without_command=True)
    async def reactrole_delete(
        self,
        ctx: commands.Context,
        message_id: Union[discord.Message, IDConverter],
    ):
        """Delete an entire reaction role for a message."""

    @reactrole_delete.command(name="bind")
    async def delete_bind(
        self,
        ctx: commands.Context,
        message_id: Union[discord.Message, IDConverter],
        emoji: Union[RealEmojiConverter, IDConverter],
    ):
        """Delete an emoji-role bind for a reaction role."""
        message_id = message_id.id if isinstance(message_id, discord.Message) else message_id
        async with self.config.custom("GuildMessage", ctx.guild.id, message_id).reactroles() as r:
            try:
                del r["react_to_roleid"][emoji if isinstance(emoji, str) else str(emoji.id)]
            except KeyError:
                return await ctx.send("That wasn't a valid emoji for that message.")
        await ctx.send(f"That emoji role bind was deleted.")
        await self._update_cache()

    @commands.admin_or_permissions(manage_roles=True)
    @reactrole.command(name="list")
    async def react_list(self, ctx: commands.Context):
        """View the reaction roles on this server."""
        data = (await self.config.custom("GuildMessage").all()).get(str(ctx.guild.id))
        if not data:
            return await ctx.send("There are no reaction roles set up here!")

        react_roles = []
        for index, message_data in enumerate(data.items(), start=1):
            message_id = message_data[0]
            data = message_data[1]["reactroles"]
            link = f"https://discord.com/channels/{ctx.guild.id}/{data['channel']}/{message_id}"
            reactions = [f"[Reaction Role #{index}]({link})"]
            for emoji, role in data["react_to_roleid"].items():
                role = ctx.guild.get_role(role)
                if role:
                    try:
                        emoji = int(emoji)
                    except ValueError:
                        pass
                    else:
                        emoji = self.bot.get_emoji(emoji) or emoji
                    reactions.append(f"{emoji}: {role.mention}")
                else:
                    ...  # TODO make this remove the set rr if role is not found
            if len(reactions) > 1:
                react_roles.append("\n".join(reactions))
        if not react_roles:
            return await ctx.send("There are no reaction roles set up here!")

        color = await ctx.embed_color()
        description = "\n\n".join(react_roles)
        if len(description) > 2048:
            embeds = []
            pages = list(pagify(description, delims=["\n\n"], page_length=2048))
            for index, page in enumerate(pages, start=1):
                e = discord.Embed(
                    color=color,
                    description=page,
                )
                e.set_author(name="Reaction Roles", icon_url=ctx.guild.icon_url)
                e.set_footer(text=f"{index}/{len(pages)}")
                embeds.append(e)
            await menu(ctx, embeds, DEFAULT_CONTROLS)
        else:
            e = discord.Embed(
                color=color,
                description=description,
            )
            e.set_author(name="Reaction Roles", icon_url=ctx.guild.icon_url)
            emoji = self.bot.get_emoji(729917314769748019) or "❌"
            await menu(ctx, [e], {emoji: close_menu})

    @commands.is_owner()
    @reactrole.command(hidden=True)
    async def clear(self, ctx: commands.Context):
        """Clear all ReactRole data."""
        await self.config.custom("GuildMessage").clear()
        await ctx.tick()

    @commands.Cog.listener("on_raw_reaction_add")
    @commands.Cog.listener("on_raw_reaction_remove")
    async def on_raw_reaction_add_or_remove(self, payload: discord.RawReactionActionEvent):
        log.debug("Begin reaction listener")
        if payload.guild_id is None:
            log.debug("Not functioning in a guild")
            return

        # TODO add in listeners
        if (
            str(payload.channel_id) not in self.cache["reactroles"]["channel_cache"]
            or str(payload.message_id) not in self.cache["reactroles"]["message_cache"]
        ):
            log.debug("Not cached")
            return
        guild = self.bot.get_guild(payload.guild_id)
        if payload.event_type == "REACTION_ADD":
            member = payload.member
        else:
            member = guild.get_member(payload.user_id)

        if member is None or member.bot:
            log.debug("Failed to get member or member is a bot")
            return
        if not guild.me.guild_permissions.manage_roles:
            log.debug("No permissions to manage roles")
            return

        reacts = await self.config.custom(
            "GuildMessage", guild.id, payload.message_id
        ).reactroles.all()
        emoji_id = (
            str(payload.emoji) if payload.emoji.is_unicode_emoji() else str(payload.emoji.id)
        )
        role = guild.get_role(
            reacts["react_to_roleid"].get(emoji_id)
        )  # TODO make this remove the set rr if role is not found
        if not role or not my_role_heirarchy(guild, role):
            log.debug("Failed to get role, or role outranks me")
            return

        if payload.event_type == "REACTION_ADD":
            if role not in member.roles:
                await member.add_roles(role, reason="Reaction role")
        else:
            if role in member.roles:
                await member.remove_roles(role, reason="Reaction role")

    # TODO
    # add raw_message_delete listener to automatically delete messages
    # that have reaction roles assigned from config

    # @commands.Cog.listener()
    # async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
    #     if payload.guild_id is None:
    #         return
    #     # TODO add channel caching here and in listeners
    #     if str(payload.message_id) not in self.cache["reactroles"]["message_cache"]:
    #         return
    #     guild = self.bot.get_guild(payload.guild_id)
    #     if not guild.me.guild_permissions.manage_roles:
    #         return
    #     member = guild.get_member(payload.user_id)
    #     if member.bot:
    #         return
    #
    #     guildmessage = await self.config.custom("GuildMessage", guild.id, payload.message_id).all()
    #     reacts = guildmessage["reactroles"]
    #     emoji_id = (
    #         str(payload.emoji) if payload.emoji.is_unicode_emoji() else str(payload.emoji.id)
    #     )
    #     role = guild.get_role(
    #         reacts["react_to_roleid"].get(emoji_id)
    #     )  # TODO make this remove the set rr if role is not found
    #     if role and my_role_heirarchy(guild, role) and role in member.roles:
    #         await member.remove_roles(role, reason="Reaction role")
