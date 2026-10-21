"""Clean embeds and interactive leaderboards for Red-DiscordBot."""

import asyncio
import math
import time

import discord
from redbot.core import Config, checks, commands
from redbot.core.bot import Red


BLUE = discord.Color.from_rgb(44, 151, 255)
GREEN = discord.Color.from_rgb(46, 204, 113)
GOLD = discord.Color.from_rgb(241, 196, 15)
RED = discord.Color.from_rgb(231, 76, 60)
PAGE_SIZE = 10


def make_embed(title, description, guild, color=BLUE, member=None):
    embed = discord.Embed(
        title=title, description=description, color=color,
        timestamp=discord.utils.utcnow(),
    )
    embed.set_footer(text=f"{guild.name} • Vouch Tracker")
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    if member:
        embed.set_thumbnail(url=member.display_avatar.url)
    return embed


class LeaderboardView(discord.ui.View):
    """Pages are controlled by the person who invoked the command."""

    def __init__(self, author_id, guild, entries):
        super().__init__(timeout=120)
        self.author_id = author_id
        self.guild = guild
        self.entries = entries
        self.page = 0
        self.pages = max(1, math.ceil(len(entries) / PAGE_SIZE))
        self.message = None
        self.update_buttons()

    def update_buttons(self):
        self.previous.disabled = self.page == 0
        self.next_page.disabled = self.page >= self.pages - 1

    def render(self):
        embed = make_embed("🏆 Vouch Leaderboard", "Top-rated members in this server.", self.guild, GOLD)
        start = self.page * PAGE_SIZE
        visible = self.entries[start:start + PAGE_SIZE]
        if not visible:
            embed.description = "No vouches recorded yet. Members will appear here once they receive vouches."
        else:
            rows = []
            for rank, (member, count) in enumerate(visible, start=start + 1):
                medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"`#{rank:02d}`")
                rows.append(f"{medal} **{member.mention}**\nㅤㅤ`{count:,}` vouches")
            embed.description = "\n\n".join(rows)
        embed.add_field(name="Ranked Members", value=f"{len(self.entries):,}")
        embed.add_field(name="Total Vouches", value=f"{sum(count for _, count in self.entries):,}")
        embed.set_footer(text=f"{self.guild.name} • Page {self.page + 1}/{self.pages} • Vouch Tracker")
        return embed

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the person who opened this leaderboard can turn pages.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Previous", emoji="◀️", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = max(0, self.page - 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.render(), view=self)

    @discord.ui.button(label="Next", emoji="▶️", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = min(self.pages - 1, self.page + 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.render(), view=self)

    async def on_timeout(self):
        for button in self.children:
            button.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class Vouches(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        # Original identifier and configuration keys preserve existing data.
        self.config = Config.get_conf(self, identifier=1234567890)
        self.config.register_guild(tracked_roles=[], vouch_channel_id=None)
        self.config.register_member(vouch_count=0)
        self.leaderboard_cooldown = {}
        self._count_lock = asyncio.Lock()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.author.bot:
            return
        settings = await self.config.guild(message.guild).all()
        if message.channel.id != settings["vouch_channel_id"]:
            return
        role_ids = set(settings["tracked_roles"])
        recipients = {
            member.id: member for member in message.mentions
            if member.id != message.author.id
            and not member.bot
            and any(role.id in role_ids for role in member.roles)
        }
        if not recipients:
            return
        recorded = []
        async with self._count_lock:
            for member in recipients.values():
                count = max(0, await self.config.member(member).vouch_count()) + 1
                await self.config.member(member).vouch_count.set(count)
                recorded.append((member, count))
        embed = make_embed(
            "✅ Vouch Recorded",
            f"New vouch from {message.author.mention}.", message.guild, GREEN,
        )
        for member, count in recorded[:10]:
            embed.add_field(name=member.display_name[:256], value=f"{member.mention} • **{count:,}** total", inline=False)
        if len(recorded) > 10:
            embed.add_field(name="Additional Members", value=f"{len(recorded) - 10} more received a vouch.", inline=False)
        try:
            await message.channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            pass

    @commands.hybrid_command(name="vouches", description="Check user vouches")
    @commands.guild_only()
    async def vouches_command(self, ctx: commands.Context, user: discord.Member):
        count = max(0, await self.config.member(user).vouch_count())
        embed = make_embed("⭐ Member Reputation", f"Reputation for {user.mention}", ctx.guild, member=user)
        embed.add_field(name="Total Vouches", value=f"**{count:,}**")
        await ctx.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    @commands.hybrid_command(name="addvouch", description="Add user vouches")
    @commands.guild_only()
    @checks.admin_or_permissions(administrator=True)
    async def addvouch_command(self, ctx: commands.Context, user: discord.Member, number: int):
        if number <= 0:
            await ctx.send(embed=make_embed("Invalid Amount", "Enter a positive number.", ctx.guild, RED))
            return
        async with self._count_lock:
            count = max(0, await self.config.member(user).vouch_count()) + number
            await self.config.member(user).vouch_count.set(count)
        embed = make_embed("✅ Vouches Added", f"Updated {user.mention}", ctx.guild, GREEN, user)
        embed.add_field(name="Added", value=f"+{number:,}")
        embed.add_field(name="New Total", value=f"**{count:,}**")
        await ctx.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    @commands.hybrid_command(name="removevouch", description="Remove user vouches")
    @commands.guild_only()
    @checks.admin_or_permissions(administrator=True)
    async def removevouch_command(self, ctx: commands.Context, user: discord.Member, number: int):
        if number <= 0:
            await ctx.send(embed=make_embed("Invalid Amount", "Enter a positive number.", ctx.guild, RED))
            return
        async with self._count_lock:
            old = max(0, await self.config.member(user).vouch_count())
            count = max(0, old - number)
            await self.config.member(user).vouch_count.set(count)
        embed = make_embed("➖ Vouches Removed", f"Updated {user.mention}", ctx.guild, GOLD, user)
        embed.add_field(name="Removed", value=f"-{old - count:,}")
        embed.add_field(name="New Total", value=f"**{count:,}**")
        await ctx.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    @commands.hybrid_command(name="vouchleaderboard", description="Show the vouch leaderboard")
    @commands.guild_only()
    async def vouchleaderboard_command(self, ctx: commands.Context):
        if not ctx.author.guild_permissions.administrator:
            now = time.monotonic()
            deadline = self.leaderboard_cooldown.get(ctx.guild.id, 0)
            if now < deadline:
                await ctx.send(embed=make_embed(
                    "⏳ Cooldown", f"Try again in **{math.ceil(deadline - now)} seconds**.", ctx.guild, GOLD
                ))
                return
            self.leaderboard_cooldown[ctx.guild.id] = now + 30
        entries = []
        for member in ctx.guild.members:
            count = await self.config.member(member).vouch_count()
            if count > 0:
                entries.append((member, count))
        entries.sort(key=lambda item: (-item[1], item[0].id))
        view = LeaderboardView(ctx.author.id, ctx.guild, entries)
        view.message = await ctx.send(
            embed=view.render(), view=view, allowed_mentions=discord.AllowedMentions.none()
        )

    @commands.hybrid_command(name="setvouchchannel", description="Set vouch channel")
    @commands.guild_only()
    @checks.admin_or_permissions(administrator=True)
    async def setvouchchannel_command(self, ctx: commands.Context, channel: discord.TextChannel):
        await self.config.guild(ctx.guild).vouch_channel_id.set(channel.id)
        await ctx.send(embed=make_embed(
            "✅ Vouch Channel Updated", f"Now tracking vouches in {channel.mention}.", ctx.guild, GREEN
        ))

    @commands.hybrid_command(name="setvouchroles", description="Set roles for vouches")
    @commands.guild_only()
    @checks.admin_or_permissions(administrator=True)
    async def setvouchroles_command(
        self, ctx: commands.Context, role1: discord.Role, role2: discord.Role = None,
        role3: discord.Role = None, role4: discord.Role = None, role5: discord.Role = None,
    ):
        roles = list({r.id: r for r in (role1, role2, role3, role4, role5) if r}.values())
        await self.config.guild(ctx.guild).tracked_roles.set([role.id for role in roles])
        embed = make_embed("✅ Tracked Roles Updated", "Members with these roles can receive vouches.", ctx.guild, GREEN)
        embed.add_field(name="Eligible Roles", value="\n".join(role.mention for role in roles), inline=False)
        await ctx.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())


async def setup(bot: Red):
    await bot.add_cog(Vouches(bot))
