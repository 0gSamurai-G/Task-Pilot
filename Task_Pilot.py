import discord
from discord import app_commands
from discord.ext import commands
import datetime
import asyncio
import os # You need to import os

# --- Configuration (EDIT THESE) ---

# 1. TOKEN: Use an environment variable or a secure file. Replaced the public one.
ALLOWED_SERVERS = {1439561356960464979}
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
# 2. ROLE RESTRICTION: Define the names of the roles allowed to use MODERATION commands.
# Only users with one of these roles can use commands like !kick, !ban, !purge, !timeout.
MODERATION_ROLES = ["Admin", "Moderator"] 

# --- Bot Setup and Intents ---

# Intents are correctly defined.
intents = discord.Intents.default()
# Required for moderation/member lookup:
intents.members = True 
# Required for command processing:
intents.message_content = True 
# Set the command prefix
bot = commands.Bot(command_prefix='!', intents=intents)

# --- Custom Role Checker Function ---

def is_moderator():
    """Custom check function to see if the user has any role listed in MODERATION_ROLES.
    This variant is used for legacy `commands` checks. Kept for compatibility but not
    used on the new slash commands.
    """
    async def predicate(ctx):
        if not ctx.guild:
            return False
        role_names = [role.name for role in ctx.author.roles]
        if any(role_name in role_names for role_name in MODERATION_ROLES):
            return True
        raise commands.CheckFailure(f"You must have one of the following roles to use this command: {', '.join(MODERATION_ROLES)}")

    return commands.check(predicate)


def is_moderator_app():
    """App command (slash) check to ensure the invoking user has one of MODERATION_ROLES."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            raise app_commands.CheckFailure("This command must be used in a server/guild context.")
        role_names = [role.name for role in interaction.user.roles]
        if any(role_name in role_names for role_name in MODERATION_ROLES):
            return True
        raise app_commands.CheckFailure(f"You must have one of the following roles to use this command: {', '.join(MODERATION_ROLES)}")

    return app_commands.check(predicate)

# --- Events ---

@bot.event
async def on_ready():
    """Confirms the bot is running and connected to Discord."""
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')

    unauthorized_guilds = []
    for guild in bot.guilds:
        if guild.id not in ALLOWED_SERVERS:
            unauthorized_guilds.append(guild.name)
            await guild.leave()
            
    if unauthorized_guilds:
        print(f"🚫 CLEANUP: Left the following unauthorized guilds on startup: {', '.join(unauthorized_guilds)}")

    await bot.change_presence(activity=discord.Game(name="Ready for instructions"))
    try:
        await bot.tree.sync()
        print("🔁 App commands synced to Discord.")
    except Exception as e:
        print(f"⚠️ Failed to sync app commands: {e}")


@bot.event
async def on_guild_join(guild):
    """3. 🛡️ CHECK ON NEW INVITE"""
    if guild.id not in ALLOWED_SERVERS:
        print(f"❌ UNAUTHORIZED JOIN: Leaving Guild '{guild.name}' (ID: {guild.id})")
        # Optional: Add a polite message here before leaving
        await guild.leave()
    else:
        print(f"✅ ALLOWED JOIN: Staying in Guild '{guild.name}' (ID: {guild.id})")


@bot.event
async def on_command_error(ctx, error):
    """Handles all command errors, including custom role check failures."""
    if isinstance(error, commands.CheckFailure):
        # Handle the custom role restriction error
        await ctx.send(f"❌ **Permission Denied:** {error}", ephemeral=True)
    elif isinstance(error, commands.MissingPermissions):
        # Handle standard Discord permission errors (e.g., bot needs Manage Messages)
        missing = [perm.replace('_', ' ').title() for perm in error.missing_permissions]
        await ctx.send(f"❌ **Discord Permission Check Failed:** You are missing the required server permissions: {', '.join(missing)}.", ephemeral=True)
    elif isinstance(error, commands.BotMissingPermissions):
        # Handle cases where the bot itself lacks permissions
        missing = [perm.replace('_', ' ').title() for perm in error.missing_permissions]
        await ctx.send(f"❌ **Bot Error:** I am missing the required permissions to do that: {', '.join(missing)}.", ephemeral=True)
    # Allows other errors to be handled by their specific handlers if defined
    # or prints them to the console if no specific handler exists
    else:
        # Prevents error handlers from running twice
        if hasattr(ctx.command, 'on_error'):
            return
        # print(f"Ignoring exception in command {ctx.command}:", file=sys.stderr)
        # traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
        # Uncomment the line below for general error debugging if needed
        # await ctx.send(f"An unexpected error occurred: {type(error).__name__}", ephemeral=True)
        pass 

# --- Moderation Commands ---

@bot.tree.command(name='purge', description='Deletes a specified number of messages in the channel.')
@is_moderator_app()
async def purge(interaction: discord.Interaction, amount: int):
    # Permission check for the invoker
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("❌ You are missing the Manage Messages permission.", ephemeral=True)
        return

    if amount < 1:
        await interaction.response.send_message("Please specify a positive number of messages to delete.", ephemeral=True)
        return

    if amount > 100:
        await interaction.response.send_message("Cannot purge more than 100 messages at once.", ephemeral=True)
        return

    try:
        await interaction.response.defer(thinking=True)
        deleted = await interaction.channel.purge(limit=amount)
        confirmation = await interaction.followup.send(f'🧹 Successfully deleted **{len(deleted)}** messages.')
        await asyncio.sleep(5)
        try:
            await confirmation.delete()
        except Exception:
            pass
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to manage messages here (Manage Messages).", ephemeral=True)
    except discord.HTTPException as e:
        if getattr(e, 'status', None) == 400:
            await interaction.response.send_message("❌ Cannot bulk delete messages older than 14 days. Please choose a smaller range.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ An error occurred during purge: HTTP {getattr(e, 'status', 'unknown')}", ephemeral=True)


# --- KICK, BAN, TIMEOUT, UNTIMEOUT ---
# All moderation commands now use the @is_moderator() decorator
# along with the standard permission check.

@bot.tree.command(name='kick', description='Kicks a member from the server.')
@is_moderator_app()
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    if not interaction.user.guild_permissions.kick_members:
        await interaction.response.send_message("❌ You are missing the Kick Members permission.", ephemeral=True)
        return

    if member == interaction.user:
        await interaction.response.send_message("❌ You cannot kick yourself!", ephemeral=True)
        return
    if member == bot.user:
        await interaction.response.send_message("❌ I cannot kick myself!", ephemeral=True)
        return

    if reason is None:
        reason = "No reason provided."

    if interaction.user.top_role <= member.top_role:
        await interaction.response.send_message(f"❌ You cannot kick **{member.display_name}** because their role is higher than or equal to yours.", ephemeral=True)
        return

    await member.kick(reason=reason)
    await interaction.response.send_message(f'👢 Kicked **{member.display_name}** (ID: {member.id}). Reason: *{reason}*')


@bot.tree.command(name='ban', description='Bans a member from the server.')
@is_moderator_app()
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    if not interaction.user.guild_permissions.ban_members:
        await interaction.response.send_message("❌ You are missing the Ban Members permission.", ephemeral=True)
        return

    if member == interaction.user:
        await interaction.response.send_message("❌ You cannot ban yourself!", ephemeral=True)
        return
    if member == bot.user:
        await interaction.response.send_message("❌ I cannot ban myself!", ephemeral=True)
        return

    if reason is None:
        reason = "No reason provided."

    if interaction.user.top_role <= member.top_role:
        await interaction.response.send_message(f"❌ You cannot ban **{member.display_name}** because their role is higher than or equal to yours.", ephemeral=True)
        return

    await member.ban(reason=reason)
    await interaction.response.send_message(f'🔨 Banned **{member.display_name}** (ID: {member.id}). Reason: *{reason}*')


@bot.tree.command(name='unban', description='Unbans a user by ID or username.')
@is_moderator_app()
async def unban(interaction: discord.Interaction, user_input: str):
    """
    Unbans a user primarily by User ID, or attempts to find them by username/global name.
    Requires 'Ban Members' permission and MODERATION_ROLES.
    """
    
    # 1. Get the list of banned users (GuildBan objects)
    try:
        banned_users = await interaction.guild.bans()
    except discord.Forbidden:
        await interaction.response.send_message("❌ I am missing the **Ban Members** permission to view the ban list.", ephemeral=True)
        return

    target_user = None

    # --- Attempt 1: Match by User ID (Most Reliable) ---
    # Check if the input is a number (a User ID)
    if user_input.isdigit():
        try:
            user_id = int(user_input)
            # Find the ban entry corresponding to the ID
            ban_entry = discord.utils.get(banned_users, user__id=user_id)
            if ban_entry:
                target_user = ban_entry.user
        except ValueError:
            # Should not happen if isdigit() is true, but good safeguard
            pass 

    # --- Attempt 2: Match by Name (Fallback) ---
    if target_user is None:
        # Search for the user by name (case-insensitive)
        user_input_lower = user_input.lower()
        for ban_entry in banned_users:
            user = ban_entry.user
            # Check username or global display name (covers current Discord naming)
            if user.name.lower() == user_input_lower or (user.global_name and user.global_name.lower() == user_input_lower):
                target_user = user
                break
                
    # --- Execute Unban ---
    if target_user:
        await interaction.guild.unban(target_user)
        await interaction.response.send_message(f'🔓 Unbanned **{target_user.display_name}** (ID: {target_user.id}). Welcome back!')
    else:
        await interaction.response.send_message(f'❌ Could not find a banned user matching "{user_input}" in the ban list. Please ensure you are using the correct **User ID**.', ephemeral=True)



@bot.tree.command(name='timeout', description='Puts a member in timeout for a specified duration.')
@is_moderator_app()
async def timeout(interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "No reason provided"):
    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("❌ You are missing the Moderate Members permission.", ephemeral=True)
        return

    if interaction.user.top_role <= member.top_role and interaction.guild.owner != interaction.user:
        await interaction.response.send_message(f"❌ You cannot timeout **{member.display_name}** because their role is higher than or equal to yours.", ephemeral=True)
        return

    try:
        unit = duration[-1].lower()
        time_value = int(duration[:-1])
    except ValueError:
        await interaction.response.send_message("Invalid duration format. Use formats like `1h`, `30m`, or `7d`.", ephemeral=True)
        return

    if unit == 's':
        delta = datetime.timedelta(seconds=time_value)
    elif unit == 'm':
        delta = datetime.timedelta(minutes=time_value)
    elif unit == 'h':
        delta = datetime.timedelta(hours=time_value)
    elif unit == 'd':
        delta = datetime.timedelta(days=time_value)
    else:
        await interaction.response.send_message("Invalid duration unit. Use `s`, `m`, `h`, or `d`.", ephemeral=True)
        return

    if delta > datetime.timedelta(days=28):
        await interaction.response.send_message("Cannot timeout for more than 28 days.", ephemeral=True)
        return

    timeout_until = discord.utils.utcnow() + delta
    await member.timeout(timeout_until, reason=reason)
    await interaction.response.send_message(f'🔇 Timed out **{member.display_name}** until {discord.utils.format_dt(timeout_until, "f")}. Reason: *{reason}*')


@bot.tree.command(name='untimeout', description='Removes the timeout from a member.')
@is_moderator_app()
async def untimeout(interaction: discord.Interaction, member: discord.Member, reason: str = "Timeout removed by moderator"):
    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("❌ You are missing the Moderate Members permission.", ephemeral=True)
        return

    if not member.timed_out:
        await interaction.response.send_message(f"**{member.display_name}** is not currently in timeout.", ephemeral=True)
        return

    if interaction.user.top_role <= member.top_role and interaction.guild.owner != interaction.user:
        await interaction.response.send_message(f"❌ You cannot untimeout **{member.display_name}** because their role is higher than or equal to yours.", ephemeral=True)
        return

    await member.edit(timed_out_until=None, reason=reason)
    await interaction.response.send_message(f'🔊 Removed timeout from **{member.display_name}**.')

@bot.tree.command(name='lock', description='Locks the current channel by denying @everyone permission to send messages.')
@is_moderator_app()
async def lock(interaction: discord.Interaction, channel: discord.TextChannel = None):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("❌ You are missing the Manage Channels permission.", ephemeral=True)
        return

    channel = channel or interaction.channel
    overwrite = channel.overwrites_for(interaction.guild.default_role)

    if overwrite.send_messages is False:
        await interaction.response.send_message(f"🔒 **{channel.mention}** is already locked.")
        return

    overwrite.send_messages = False
    await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite, reason=f"Channel locked by {interaction.user.name}")
    await interaction.response.send_message(f"🔒 Channel **{channel.mention}** has been locked.")

@bot.tree.command(name='unlock', description='Unlocks the current channel by allowing @everyone to send messages.')
@is_moderator_app()
async def unlock(interaction: discord.Interaction, channel: discord.TextChannel = None):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("❌ You are missing the Manage Channels permission.", ephemeral=True)
        return

    channel = channel or interaction.channel
    overwrite = channel.overwrites_for(interaction.guild.default_role)

    if overwrite.send_messages is None or overwrite.send_messages is True:
        await interaction.response.send_message(f"🔓 **{channel.mention}** is already unlocked (or permissions are default).")
        return

    overwrite.send_messages = None
    await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite, reason=f"Channel unlocked by {interaction.user.name}")
    await interaction.response.send_message(f"🔓 Channel **{channel.mention}** has been unlocked.")




@bot.tree.command(name='whois', description='Displays detailed information about a member.')
async def whois(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user

    embed = discord.Embed(
        title=f"👤 User Info: {member.display_name}",
        color=member.color if member.color != discord.Color.default() else discord.Color.blue(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )

    embed.add_field(name="ID", value=member.id, inline=True)
    embed.add_field(name="Account Created", value=discord.utils.format_dt(member.created_at, "R"), inline=True)
    embed.add_field(name="Joined Server", value=discord.utils.format_dt(member.joined_at, "R"), inline=True)

    roles = [role.mention for role in member.roles if role.name != "@everyone"]
    roles_value = ", ".join(roles) if roles else "No extra roles"
    embed.add_field(name=f"Roles ({len(roles)})", value=roles_value, inline=False)

    status_emoji = {
        discord.Status.online: "🟢 Online",
        discord.Status.idle: "🌙 Idle",
        discord.Status.dnd: "🔴 Do Not Disturb",
        discord.Status.offline: "⚪ Offline"
    }.get(member.status, "⚫ Unknown")
    embed.add_field(name="Status", value=status_emoji, inline=True)

    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)



@bot.tree.command(name='serverinfo', description='Displays statistics about the current server.')
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild

    embed = discord.Embed(
        title=f"🏛️ Server Info: {guild.name}",
        color=discord.Color.gold(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )

    embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="Server ID", value=guild.id, inline=True)
    embed.add_field(name="Creation Date", value=discord.utils.format_dt(guild.created_at, "R"), inline=True)

    bot_count = len([member for member in guild.members if member.bot])
    member_count = guild.member_count
    embed.add_field(name="Member Count", value=f"Total: **{member_count}**\nHumans: {member_count - bot_count}\nBots: {bot_count}", inline=True)

    text_channels = len(guild.text_channels)
    voice_channels = len(guild.voice_channels)
    embed.add_field(name="Channels", value=f"Text: {text_channels}\nVoice: {voice_channels}\nCategories: {len(guild.categories)}", inline=True)

    embed.add_field(name="Roles", value=len(guild.roles), inline=True)
    embed.add_field(name="Boost Level", value=f"Level {guild.premium_tier} ({guild.premium_subscription_count} boosts)", inline=True)

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)




@bot.tree.command(name='targetpurge', description='Deletes the specified number of messages from a specific member.')
@is_moderator_app()
async def targetpurge(interaction: discord.Interaction, member: discord.Member, amount: int):
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("❌ You are missing the Manage Messages permission.", ephemeral=True)
        return

    if amount < 1:
        await interaction.response.send_message("Please specify a positive number of messages to delete.", ephemeral=True)
        return

    if amount > 100:
        await interaction.response.send_message("Cannot delete more than 100 messages at once due to Discord's API limits.", ephemeral=True)
        return

    try:
        await interaction.response.defer(thinking=True)
        messages = []
        async for message in interaction.channel.history(limit=500):
            if len(messages) == amount:
                break
            if message.author == member:
                messages.append(message)

        if not messages:
            await interaction.followup.send(f'Could not find **{amount}** recent messages from **{member.display_name}** within the last 500 messages.', ephemeral=True)
            return

        await interaction.channel.delete_messages(messages)
        deleted_count = len(messages)
        confirmation = await interaction.followup.send(f'🧹 Successfully deleted **{deleted_count}** recent messages from **{member.display_name}**.')
        await asyncio.sleep(5)
        try:
            await confirmation.delete()
        except Exception:
            pass

    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to manage messages here (Manage Messages).", ephemeral=True)
    except discord.HTTPException as e:
        if getattr(e, 'status', None) == 400:
            await interaction.response.send_message("❌ Cannot delete messages older than 14 days. Please try a lower amount.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ An error occurred during purge: HTTP {getattr(e, 'status', 'unknown')}", ephemeral=True)





# The custom error handler handles all missing permissions/roles now, so the specific
# error handlers (like @kick.error) are less necessary but can be kept if desired.

# --- Run the Bot ---
if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        print("❌ FATAL ERROR: DISCORD_BOT_TOKEN environment variable is not set. Exiting.")
    else:
        bot.run(DISCORD_BOT_TOKEN)