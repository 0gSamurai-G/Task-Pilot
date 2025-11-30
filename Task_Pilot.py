import discord
from discord.ext import commands
import datetime
import asyncio
import os

# --- Configuration (EDIT THESE) ---
ALLOWED_SERVERS = {1439561356960464979}
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
MODERATION_ROLES = ["Admin", "Moderator"] 

# --- Bot Setup and Intents ---
intents = discord.Intents.default()
intents.members = True 
intents.message_content = True 

bot = commands.Bot(command_prefix='!', intents=intents)

# --- Custom Role Checker for Slash Commands ---
def is_moderator():
    async def predicate(interaction: discord.Interaction):
        if not interaction.guild:
            return False
        
        role_names = [role.name for role in interaction.user.roles]
        if any(role_name in role_names for role_name in MODERATION_ROLES):
            return True
        
        raise discord.ApplicationCommandError(f"You must have one of the following roles: {', '.join(MODERATION_ROLES)}")
    return predicate

# --- Events ---
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')

    unauthorized_guilds = []
    for guild in bot.guilds:
        if guild.id not in ALLOWED_SERVERS:
            unauthorized_guilds.append(guild.name)
            await guild.leave()
            
    if unauthorized_guilds:
        print(f"🚫 CLEANUP: Left unauthorized guilds: {', '.join(unauthorized_guilds)}")

    await bot.change_presence(activity=discord.Game(name="Ready for instructions"))
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")

@bot.event
async def on_guild_join(guild):
    if guild.id not in ALLOWED_SERVERS:
        print(f"❌ UNAUTHORIZED JOIN: Leaving Guild '{guild.name}' (ID: {guild.id})")
        await guild.leave()
    else:
        print(f"✅ ALLOWED JOIN: Staying in Guild '{guild.name}' (ID: {guild.id})")

# --- Slash Command Error Handler ---
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.AppCommandError):
    if isinstance(error, discord.ApplicationCommandError):
        await interaction.response.send_message(f"❌ **Permission Denied:** {error}", ephemeral=True)
    elif isinstance(error, discord.MissingPermissions):
        missing = [perm.replace('_', ' ').title() for perm in error.missing_permissions]
        await interaction.response.send_message(f"❌ You are missing permissions: {', '.join(missing)}.", ephemeral=True)
    elif isinstance(error, discord.BotMissingPermissions):
        missing = [perm.replace('_', ' ').title() for perm in error.missing_permissions]
        await interaction.response.send_message(f"❌ **Bot Error:** I need permissions: {', '.join(missing)}.", ephemeral=True)
    else:
        await interaction.response.send_message(f"An unexpected error occurred: {str(error)}", ephemeral=True)

# --- MODERATION SLASH COMMANDS ---

@bot.tree.command(name="purge", description="Deletes a specified number of messages in the channel")
@discord.app_commands.describe(amount="Number of messages to delete (1-100)")
@discord.app_commands.check(is_moderator)
@discord.app_commands.checks.has_permissions(manage_messages=True)
async def slash_purge(interaction: discord.Interaction, amount: int):
    if amount < 1:
        await interaction.response.send_message("Please specify a positive number.", ephemeral=True)
        return
        
    if amount > 100:
        await interaction.response.send_message("Cannot purge more than 100 messages.", ephemeral=True)
        return

    try:
        deleted = await interaction.channel.purge(limit=amount + 1)
        confirmation = await interaction.response.send_message(f'🧹 Deleted **{len(deleted) - 1}** messages.', ephemeral=True)
        await asyncio.sleep(5)
        try:
            await confirmation.delete()
        except:
            pass
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have Manage Messages permission.", ephemeral=True)
    except discord.HTTPException as e:
        if e.status == 400:
            await interaction.response.send_message("❌ Cannot delete messages older than 14 days.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Purge error: HTTP {e.status}", ephemeral=True)

@bot.tree.command(name="kick", description="Kicks a member from the server")
@discord.app_commands.describe(member="Member to kick", reason="Reason for kick (optional)")
@discord.app_commands.check(is_moderator)
@discord.app_commands.checks.has_permissions(kick_members=True)
async def slash_kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if member == interaction.user:
        await interaction.response.send_message("❌ You cannot kick yourself!", ephemeral=True)
        return
    if member == interaction.client.user:
        await interaction.response.send_message("❌ I cannot kick myself!", ephemeral=True)
        return
        
    if interaction.user.top_role <= member.top_role and interaction.guild.owner != interaction.user:
        await interaction.response.send_message(f"❌ Cannot kick **{member.display_name}** - role hierarchy.", ephemeral=True)
        return

    await member.kick(reason=reason)
    await interaction.response.send_message(f'👢 Kicked **{member.display_name}** (ID: {member.id})\nReason: *{reason}*')

@bot.tree.command(name="ban", description="Bans a member from the server")
@discord.app_commands.describe(member="Member to ban", reason="Reason for ban (optional)")
@discord.app_commands.check(is_moderator)
@discord.app_commands.checks.has_permissions(ban_members=True)
async def slash_ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if member == interaction.user:
        await interaction.response.send_message("❌ You cannot ban yourself!", ephemeral=True)
        return
    if member == interaction.client.user:
        await interaction.response.send_message("❌ I cannot ban myself!", ephemeral=True)
        return
        
    if interaction.user.top_role <= member.top_role and interaction.guild.owner != interaction.user:
        await interaction.response.send_message(f"❌ Cannot ban **{member.display_name}** - role hierarchy.", ephemeral=True)
        return

    await member.ban(reason=reason)
    await interaction.response.send_message(f'🔨 Banned **{member.display_name}** (ID: {member.id})\nReason: *{reason}*')

@bot.tree.command(name="unban", description="Unbans a user by ID or username")
@discord.app_commands.describe(user_input="User ID or username of banned user")
@discord.app_commands.check(is_moderator)
@discord.app_commands.checks.has_permissions(ban_members=True)
async def slash_unban(interaction: discord.Interaction, user_input: str):
    try:
        banned_users = await interaction.guild.bans()
    except discord.Forbidden:
        await interaction.response.send_message("❌ Missing Ban Members permission.", ephemeral=True)
        return

    target_user = None

    if user_input.isdigit():
        user_id = int(user_input)
        ban_entry = discord.utils.get(banned_users, user__id=user_id)
        if ban_entry:
            target_user = ban_entry.user

    if target_user is None:
        user_input_lower = user_input.lower()
        for ban_entry in banned_users:
            user = ban_entry.user
            if (user.name.lower() == user_input_lower or 
                (user.global_name and user.global_name.lower() == user_input_lower)):
                target_user = user
                break
                
    if target_user:
        await interaction.guild.unban(target_user)
        await interaction.response.send_message(f'🔓 Unbanned **{target_user.display_name}** (ID: {target_user.id})')
    else:
        await interaction.response.send_message(f'❌ No banned user found matching "{user_input}". Use User ID.', ephemeral=True)

@bot.tree.command(name="timeout", description="Puts a member in timeout")
@discord.app_commands.describe(member="Member to timeout", duration="Duration (1h, 30m, 7d)", reason="Reason (optional)")
@discord.app_commands.check(is_moderator)
@discord.app_commands.checks.has_permissions(moderate_members=True)
async def slash_timeout(interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "No reason provided"):
    if interaction.user.top_role <= member.top_role and interaction.guild.owner != interaction.user:
        await interaction.response.send_message(f"❌ Cannot timeout **{member.display_name}** - role hierarchy.", ephemeral=True)
        return

    try:
        unit = duration[-1].lower()
        time_value = int(duration[:-1])
    except ValueError:
        await interaction.response.send_message("Invalid format. Use: 1h, 30m, 7d", ephemeral=True)
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
        await interaction.response.send_message("Invalid unit. Use: s, m, h, d", ephemeral=True)
        return

    if delta > datetime.timedelta(days=28):
        await interaction.response.send_message("Cannot timeout > 28 days.", ephemeral=True)
        return

    timeout_until = discord.utils.utcnow() + delta
    await member.timeout(timeout_until, reason=reason)
    await interaction.response.send_message(f'🔇 Timed out **{member.display_name}** until {discord.utils.format_dt(timeout_until, "f")}\nReason: *{reason}*')

@bot.tree.command(name="untimeout", description="Removes timeout from a member")
@discord.app_commands.describe(member="Member to remove timeout from", reason="Reason (optional)")
@discord.app_commands.check(is_moderator)
@discord.app_commands.checks.has_permissions(moderate_members=True)
async def slash_untimeout(interaction: discord.Interaction, member: discord.Member, reason: str = "Timeout removed"):
    if not member.timed_out:
        await interaction.response.send_message(f"**{member.display_name}** is not timed out.", ephemeral=True)
        return
        
    if interaction.user.top_role <= member.top_role and interaction.guild.owner != interaction.user:
        await interaction.response.send_message(f"❌ Cannot untimeout **{member.display_name}** - role hierarchy.", ephemeral=True)
        return

    await member.edit(timed_out_until=None, reason=reason)
    await interaction.response.send_message(f'🔊 Removed timeout from **{member.display_name}**.')

@bot.tree.command(name="lock", description="Locks current channel")
@discord.app_commands.describe(channel="Channel to lock (optional)")
@discord.app_commands.check(is_moderator)
@discord.app_commands.checks.has_permissions(manage_channels=True)
async def slash_lock(interaction: discord.Interaction, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    overwrite = channel.overwrites_for(interaction.guild.default_role)
    
    if overwrite.send_messages is False:
        await interaction.response.send_message(f"🔒 **{channel.mention}** is already locked.", ephemeral=True)
        return
        
    overwrite.send_messages = False
    await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite, 
                                reason=f"Locked by {interaction.user.name}")
    await interaction.response.send_message(f"🔒 **{channel.mention}** locked.")

@bot.tree.command(name="unlock", description="Unlocks current channel")
@discord.app_commands.describe(channel="Channel to unlock (optional)")
@discord.app_commands.check(is_moderator)
@discord.app_commands.checks.has_permissions(manage_channels=True)
async def slash_unlock(interaction: discord.Interaction, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    overwrite = channel.overwrites_for(interaction.guild.default_role)
    
    if overwrite.send_messages is None or overwrite.send_messages is True:
        await interaction.response.send_message(f"🔓 **{channel.mention}** is already unlocked.", ephemeral=True)
        return

    overwrite.send_messages = None
    await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite, 
                                reason=f"Unlocked by {interaction.user.name}")
    await interaction.response.send_message(f"🔓 **{channel.mention}** unlocked.")

@bot.tree.command(name="whois", description="Shows user information")
@discord.app_commands.describe(member="Member (optional, defaults to you)")
async def slash_whois(interaction: discord.Interaction, member: discord.Member = None):
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
    embed.set_footer(text=f"Requested by {interaction.user.display_name}", 
                    icon_url=interaction.user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="Shows server statistics")
async def slash_serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    
    embed = discord.Embed(
        title=f"🏛️ Server Info: {guild.name}",
        color=discord.Color.gold(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )

    embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "None", inline=True)
    embed.add_field(name="Server ID", value=guild.id, inline=True)
    embed.add_field(name="Created", value=discord.utils.format_dt(guild.created_at, "R"), inline=True)
    
    bot_count = len([m for m in guild.members if m.bot])
    member_count = guild.member_count
    embed.add_field(name="Members", value=f"**{member_count}** total\nHumans: {member_count-bot_count}\nBots: {bot_count}", inline=True)

    text_channels = len(guild.text_channels)
    voice_channels = len(guild.voice_channels)
    embed.add_field(name="Channels", value=f"Text: {text_channels}\nVoice: {voice_channels}\nCategories: {len(guild.categories)}", inline=True)
    
    embed.add_field(name="Roles", value=len(guild.roles), inline=True)
    embed.add_field(name="Boosts", value=f"Level {guild.premium_tier} ({guild.premium_subscription_count or 0} boosts)", inline=True)

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
        
    embed.set_footer(text=f"Requested by {interaction.user.display_name}", 
                    icon_url=interaction.user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="targetpurge", description="Deletes messages from specific member")
@discord.app_commands.describe(member="Target member", amount="Number of messages (1-100)")
@discord.app_commands.check(is_moderator)
@discord.app_commands.checks.has_permissions(manage_messages=True)
async def slash_targetpurge(interaction: discord.Interaction, member: discord.Member, amount: int):
    if amount < 1:
        await interaction.response.send_message("Specify positive number.", ephemeral=True)
        return
    
    if amount > 100:
        await interaction.response.send_message("Max 100 messages due to API limits.", ephemeral=True)
        return

    messages = []
    async for message in interaction.channel.history(limit=500):
        if len(messages) == amount:
            break
        if message.author == member and not message.author.bot:
            messages.append(message)

    if len(messages) == 0:
        await interaction.response.send_message(f'No recent messages from **{member.display_name}** found.', ephemeral=True)
        return
            
    messages.append(interaction.message) if hasattr(interaction, 'message') and interaction.message else None
    deleted_count = len(messages) - 1 if len(messages) > len(messages)-1 else len(messages)
    
    try:
        await interaction.channel.delete_messages(messages)
        await interaction.response.send_message(f'🧹 Deleted **{min(deleted_count, amount)}** messages from **{member.display_name}**.', ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Missing Manage Messages permission.", ephemeral=True)
    except discord.HTTPException as e:
        if e.status == 400:
            await interaction.response.send_message("❌ Messages older than 14 days cannot be deleted.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Error: HTTP {e.status}", ephemeral=True)

# --- Run the Bot ---
if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        print("❌ FATAL ERROR: DISCORD_BOT_TOKEN not set. Exiting.")
    else:
        bot.run(DISCORD_BOT_TOKEN)
