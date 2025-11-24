import discord
from discord.ext import commands
import datetime
import asyncio
import os # You need to import os

# --- Configuration (EDIT THESE) ---

# 1. TOKEN: Use an environment variable or a secure file. Replaced the public one.
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
# 2. ROLE RESTRICTION: Define the names of the roles allowed to use MODERATION commands.
# Only users with one of these roles can use commands like !kick, !ban, !purge, !timeout.
MODERATION_ROLES = ["Admin", "Moderator", "Helper"] 

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
    """Custom check function to see if the user has any role listed in MODERATION_ROLES."""
    async def predicate(ctx):
        # Check if the command is in a guild (server) context
        if not ctx.guild:
            return False
            
        # Check if the user has a role matching any name in MODERATION_ROLES
        role_names = [role.name for role in ctx.author.roles]
        
        # Check if any required role name is in the user's role list
        if any(role_name in role_names for role_name in MODERATION_ROLES):
            return True
        
        # If no matching role is found, raise the custom exception
        raise commands.CheckFailure(f"You must have one of the following roles to use this command: {', '.join(MODERATION_ROLES)}")
        
    return commands.check(predicate)

# --- Events ---

@bot.event
async def on_ready():
    """Confirms the bot is running and connected to Discord."""
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
    await bot.change_presence(activity=discord.Game(name="Moderating the Server"))

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

@bot.command(name='purge', help='Deletes a specified number of messages in the channel.')
# COMBINED CHECK: User must have a MODERATION_ROLE AND the Manage Messages permission.
@is_moderator()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    # ... (Command logic is largely unchanged, it was already correct) ...
    if amount < 1:
        await ctx.send("Please specify a positive number of messages to delete.", ephemeral=True)
        return
        
    if amount > 100:
        await ctx.send("Cannot purge more than 100 messages at once.", ephemeral=True)
        return

    # Delete the messages. +1 to include the command message itself.
    # ADDED ERROR HANDLING for messages too old for bulk delete (more than 14 days)
    try:
        deleted = await ctx.channel.purge(limit=amount + 1)
        confirmation = await ctx.send(f'🧹 Successfully deleted **{len(deleted) - 1}** messages.')
        await asyncio.sleep(5)
        await confirmation.delete()
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to manage messages here (Manage Messages).")
    except discord.HTTPException as e:
        if e.status == 400:
            await ctx.send("❌ Cannot bulk delete messages older than 14 days. Please choose a smaller range.")
        else:
            await ctx.send(f"❌ An error occurred during purge: HTTP {e.status}")


# --- KICK, BAN, TIMEOUT, UNTIMEOUT ---
# All moderation commands now use the @is_moderator() decorator
# along with the standard permission check.

@bot.command(name='kick', help='Kicks a member from the server.')
@is_moderator()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    # ADDED CHECK: Prevent mods from kicking themselves or the bot
    if member == ctx.author:
        await ctx.send("❌ You cannot kick yourself!", ephemeral=True)
        return
    if member == bot.user:
        await ctx.send("❌ I cannot kick myself!", ephemeral=True)
        return
        
    if reason is None:
        reason = "No reason provided."

    # ADDED CHECK: Prevent kicking members with higher/equal roles (hierarchy check)
    if ctx.author.top_role <= member.top_role:
        await ctx.send(f"❌ You cannot kick **{member.display_name}** because their role is higher than or equal to yours.", ephemeral=True)
        return

    await member.kick(reason=reason)
    await ctx.send(f'👢 Kicked **{member.display_name}** (ID: {member.id}). Reason: *{reason}*')


@bot.command(name='ban', help='Bans a member from the server.')
@is_moderator()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason=None):
    # ADDED CHECK: Prevent mods from banning themselves or the bot
    if member == ctx.author:
        await ctx.send("❌ You cannot ban yourself!", ephemeral=True)
        return
    if member == bot.user:
        await ctx.send("❌ I cannot ban myself!", ephemeral=True)
        return
        
    if reason is None:
        reason = "No reason provided."

    # ADDED CHECK: Prevent banning members with higher/equal roles (hierarchy check)
    if ctx.author.top_role <= member.top_role:
        await ctx.send(f"❌ You cannot ban **{member.display_name}** because their role is higher than or equal to yours.", ephemeral=True)
        return

    await member.ban(reason=reason)
    await ctx.send(f'🔨 Banned **{member.display_name}** (ID: {member.id}). Reason: *{reason}*')


@bot.command(name='unban', help='Unbans a user by ID or username.')
@is_moderator()
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, user_input):
    """
    Unbans a user primarily by User ID, or attempts to find them by username/global name.
    Requires 'Ban Members' permission and MODERATION_ROLES.
    """
    
    # 1. Get the list of banned users (GuildBan objects)
    try:
        banned_users = await ctx.guild.bans()
    except discord.Forbidden:
        await ctx.send("❌ I am missing the **Ban Members** permission to view the ban list.", ephemeral=True)
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
        await ctx.guild.unban(target_user)
        # Use target_user.display_name for the name shown on Discord
        await ctx.send(f'🔓 Unbanned **{target_user.display_name}** (ID: {target_user.id}). Welcome back!')
    else:
        await ctx.send(f'❌ Could not find a banned user matching "{user_input}" in the ban list. Please ensure you are using the correct **User ID**.', ephemeral=True)



@bot.command(name='timeout', help='Puts a member in timeout for a specified duration.')
@is_moderator()
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, duration: str, *, reason="No reason provided"):
    # ADDED CHECK: Prevent timing out members with higher/equal roles (hierarchy check)
    if ctx.author.top_role <= member.top_role and ctx.guild.owner != ctx.author:
        await ctx.send(f"❌ You cannot timeout **{member.display_name}** because their role is higher than or equal to yours.", ephemeral=True)
        return

    # ... (Duration parsing logic is largely unchanged, it was already correct) ...
    try:
        unit = duration[-1].lower()
        time_value = int(duration[:-1])
    except ValueError:
        await ctx.send("Invalid duration format. Use formats like `1h`, `30m`, or `7d`.", ephemeral=True)
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
        await ctx.send("Invalid duration unit. Use `s`, `m`, `h`, or `d`.", ephemeral=True)
        return

    if delta > datetime.timedelta(days=28):
        await ctx.send("Cannot timeout for more than 28 days.", ephemeral=True)
        return

    # Apply the timeout
    timeout_until = discord.utils.utcnow() + delta
    await member.timeout(timeout_until, reason=reason)
    await ctx.send(f'🔇 Timed out **{member.display_name}** until {discord.utils.format_dt(timeout_until, "f")}. Reason: *{reason}*')


@bot.command(name='untimeout', aliases=['remove_timeout'], help='Removes the timeout from a member.')
@is_moderator()
@commands.has_permissions(moderate_members=True)
async def untimeout(ctx, member: discord.Member, *, reason="Timeout removed by moderator"):
    # ... (Improved untimeout logic) ...
    if not member.timed_out:
        await ctx.send(f"**{member.display_name}** is not currently in timeout.", ephemeral=True)
        return
        
    # ADDED CHECK: Prevent un-timing out members with higher/equal roles
    if ctx.author.top_role <= member.top_role and ctx.guild.owner != ctx.author:
        await ctx.send(f"❌ You cannot untimeout **{member.display_name}** because their role is higher than or equal to yours.", ephemeral=True)
        return

    await member.edit(timed_out_until=None, reason=reason)
    await ctx.send(f'🔊 Removed timeout from **{member.display_name}**.')

@bot.command(name='lock', help='Locks the current channel by denying @everyone permission to send messages.')
@is_moderator()
@commands.has_permissions(manage_channels=True)
async def lock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    # Get the @everyone role for the guild
    overwrite = channel.overwrites_for(ctx.guild.default_role)
    
    if overwrite.send_messages is False:
        await ctx.send(f"🔒 **{channel.mention}** is already locked.")
        return
        
    overwrite.send_messages = False
    await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=f"Channel locked by {ctx.author.name}")
    await ctx.send(f"🔒 Channel **{channel.mention}** has been locked.")

@bot.command(name='unlock', help='Unlocks the current channel by allowing @everyone to send messages.')
@is_moderator()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    overwrite = channel.overwrites_for(ctx.guild.default_role)
    
    if overwrite.send_messages is None or overwrite.send_messages is True:
        await ctx.send(f"🔓 **{channel.mention}** is already unlocked (or permissions are default).")
        return

    overwrite.send_messages = None # Removing the explicit deny/allow makes it follow the default channel permissions
    await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=f"Channel unlocked by {ctx.author.name}")
    await ctx.send(f"🔓 Channel **{channel.mention}** has been unlocked.")




@bot.command(name='whois', aliases=['userinfo'], help='Displays detailed information about a member.')
async def whois(ctx, member: discord.Member = None):
    # If no member is specified, default to the command author
    member = member or ctx.author 

    embed = discord.Embed(
        title=f"👤 User Info: {member.display_name}",
        color=member.color if member.color != discord.Color.default() else discord.Color.blue(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )

    # General Information
    embed.add_field(name="ID", value=member.id, inline=True)
    embed.add_field(name="Account Created", value=discord.utils.format_dt(member.created_at, "R"), inline=True)
    embed.add_field(name="Joined Server", value=discord.utils.format_dt(member.joined_at, "R"), inline=True)

    # Roles
    # Get all roles except @everyone, sorted highest to lowest
    roles = [role.mention for role in member.roles if role.name != "@everyone"]
    roles_value = ", ".join(roles) if roles else "No extra roles"
    embed.add_field(name=f"Roles ({len(roles)})", value=roles_value, inline=False)

    # Status and Activity (Basic Check)
    status_emoji = {
        discord.Status.online: "🟢 Online",
        discord.Status.idle: "🌙 Idle",
        discord.Status.dnd: "🔴 Do Not Disturb",
        discord.Status.offline: "⚪ Offline"
    }.get(member.status, "⚫ Unknown")
    embed.add_field(name="Status", value=status_emoji, inline=True)

    # Avatar
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
    
    await ctx.send(embed=embed)



@bot.command(name='serverinfo', aliases=['guildinfo'], help='Displays statistics about the current server.')
async def serverinfo(ctx):
    guild = ctx.guild
    
    embed = discord.Embed(
        title=f"🏛️ Server Info: {guild.name}",
        color=discord.Color.gold(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )

    # Basic Info
    embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="Server ID", value=guild.id, inline=True)
    embed.add_field(name="Creation Date", value=discord.utils.format_dt(guild.created_at, "R"), inline=True)
    
    # Member Count
    bot_count = len([member for member in guild.members if member.bot])
    member_count = guild.member_count
    embed.add_field(name="Member Count", value=f"Total: **{member_count}**\nHumans: {member_count - bot_count}\nBots: {bot_count}", inline=True)

    # Channel Count
    text_channels = len(guild.text_channels)
    voice_channels = len(guild.voice_channels)
    embed.add_field(name="Channels", value=f"Text: {text_channels}\nVoice: {voice_channels}\nCategories: {len(guild.categories)}", inline=True)
    
    # Other Stats
    embed.add_field(name="Roles", value=len(guild.roles), inline=True)
    embed.add_field(name="Boost Level", value=f"Level {guild.premium_tier} ({guild.premium_subscription_count} boosts)", inline=True)

    # Server Icon
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
        
    embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
    
    await ctx.send(embed=embed)




@bot.command(name='targetpurge', help='Deletes the specified number of messages from a specific member.')
@is_moderator()
@commands.has_permissions(manage_messages=True)
async def targetpurge(ctx, member: discord.Member, amount: int):
    # Standard input validation
    if amount < 1:
        await ctx.send("Please specify a positive number of messages to delete.", ephemeral=True)
        return
    
    # Discord API limit is 100 messages at a time. This command searches deeper.
    if amount > 100:
        await ctx.send("Cannot delete more than 100 messages at once due to Discord's API limits.", ephemeral=True)
        return

    # Define a check function to filter messages by the target member
    def is_target_member(message):
        # We need to make sure the command message itself (from ctx.author) is not included
        # unless ctx.author happens to be the 'member' being purged, but it's cleaner
        # to focus only on the member check here.
        return message.author == member

    try:
        # We search a maximum number of messages (amount + 1 for the command message itself).
        # When using a 'check', the 'limit' specifies how many messages *must pass the check*.
        # However, since a member's messages are interspersed, we need to SEARCH deeper 
        # to FIND 'amount' messages.

        # The correct way to use 'purge' with a check is to use the `limit` as the 
        # maximum *messages to delete*. But since the deleted messages are interspersed
        # with others, we will use fetch to manually get the messages.

        # --- FIX: Use fetch and delete to ensure accurate count ---
        
        # 1. Fetch messages manually (search deep enough to find 'amount' messages)
        # 500 is a safe depth to search for 'amount' messages.
        messages = []
        async for message in ctx.channel.history(limit=500):
            if len(messages) == amount:
                break
            if message.author == member:
                messages.append(message)
                
        # 2. Add the command message itself to the delete list (to hide the mod action)
        messages.append(ctx.message)

        # 3. Use bulk delete on the found list
        deleted_count = len(messages) - 1 # Subtract the command message
        await ctx.channel.delete_messages(messages)
        # --- END FIX ---
        
        if deleted_count > 0:
            confirmation = await ctx.send(f'🧹 Successfully deleted **{deleted_count}** recent messages from **{member.display_name}**.')
        else:
            await ctx.send(f'Could not find **{amount}** recent messages from **{member.display_name}** within the last 500 messages.', ephemeral=True)
        
        await asyncio.sleep(5)
        await confirmation.delete()
        
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to manage messages here (Manage Messages).")
    except discord.HTTPException as e:
        if e.status == 400:
            await ctx.send("❌ Cannot delete messages older than 14 days. Please try a lower amount.")
        else:
            await ctx.send(f"❌ An error occurred during purge: HTTP {e.status}")





# The custom error handler handles all missing permissions/roles now, so the specific
# error handlers (like @kick.error) are less necessary but can be kept if desired.

# --- Run the Bot ---
if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        print("❌ FATAL ERROR: DISCORD_BOT_TOKEN environment variable is not set. Exiting.")
    else:
        bot.run(DISCORD_BOT_TOKEN)