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
async def is_moderator(interaction: discord.Interaction):
    """Check if user has moderator role"""
    if not interaction.guild:
        return False
    
    role_names = [role.name for role in interaction.user.roles]
    return any(role_name in role_names for role_name in MODERATION_ROLES)

# --- Events ---
@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')

    # Leave unauthorized guilds
    unauthorized_guilds = []
    for guild in bot.guilds:
        if guild.id not in ALLOWED_SERVERS:
            unauthorized_guilds.append(guild.name)
            await guild.leave()
            
    if unauthorized_guilds:
        print(f"🚫 Left unauthorized guilds: {', '.join(unauthorized_guilds)}")

    await bot.change_presence(activity=discord.Game(name="Ready for instructions"))
    
    # Sync slash commands globally
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")

@bot.event
async def on_guild_join(guild):
    if guild.id not in ALLOWED_SERVERS:
        print(f"❌ UNAUTHORIZED JOIN: Leaving '{guild.name}' (ID: {guild.id})")
        await guild.leave()
    else:
        print(f"✅ ALLOWED JOIN: Staying in '{guild.name}' (ID: {guild.id})")

# --- Global Slash Command Error Handler ---
@bot.tree.error
async def on_tree_error(interaction: discord.Interaction, error: discord.AppCommandError):
    if interaction.response.is_done():
        return
    
    if isinstance(error, discord.AppCommandCheckFailure):
        await interaction.response.send_message("❌ **Permission Denied:** You need a Moderator role.", ephemeral=True)
    elif isinstance(error, discord.MissingPermissions):
        missing_perms = [perm.replace('_', ' ').replace('Guild', '').title() for perm in error.missing_permissions]
        await interaction.response.send_message(f"❌ Missing permissions: {', '.join(missing_perms)}", ephemeral=True)
    elif isinstance(error, discord.BotMissingPermissions):
        missing_perms = [perm.replace('_', ' ').replace('Guild', '').title() for perm in error.missing_permissions]
        await interaction.response.send_message(f"❌ **Bot Error:** I need: {', '.join(missing_perms)}", ephemeral=True)
    else:
        print(f"Unexpected slash command error: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ An unexpected error occurred.", ephemeral=True)

# --- MODERATION SLASH COMMANDS ---

@bot.tree.command(name="purge", description="🧹 Delete messages from channel")
@discord.app_commands.describe(amount="Number of messages to delete (1-100)")
@discord.app_commands.checks.has_permissions(manage_messages=True)
@discord.app_commands.check(is_moderator)
async def slash_purge(interaction: discord.Interaction, amount: int):
    if amount < 1 or amount > 100:
        await interaction.response.send_message("❌ Amount must be between 1-100.", ephemeral=True)
        return

    try:
        deleted = await interaction.channel.purge(limit=amount + 1)
        await interaction.response.send_message(
            f'🧹 Deleted **{len(deleted) - 1}** messages.', 
            ephemeral=True
        )
    except discord.Forbidden:
        await interaction.response.send_message("❌ I lack Manage Messages permission.", ephemeral=True)
    except discord.HTTPException as e:
        if "older than 14 days" in str(e).lower():
            await interaction.response.send_message("❌ Cannot delete messages older than 14 days.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Purge failed: {str(e)}", ephemeral=True)

@bot.tree.command(name="kick", description="👢 Kick a member from server")
@discord.app_commands.describe(member="Member to kick", reason="Reason (optional)")
@discord.app_commands.checks.has_permissions(kick_members=True)
@discord.app_commands.check(is_moderator)
async def slash_kick(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    if member == interaction.user:
        await interaction.response.send_message("❌ You cannot kick yourself!", ephemeral=True)
        return
    if member == interaction.client.user:
        await interaction.response.send_message("❌ I cannot kick myself!", ephemeral=True)
        return
    if interaction.user.top_role <= member.top_role and interaction.guild.owner_id != interaction.user.id:
        await interaction.response.send_message(f"❌ Cannot kick **{member.display_name}** - role hierarchy.", ephemeral=True)
        return

    reason = reason or "No reason provided"
    await member.kick(reason=reason)
    await interaction.response.send_message(f'👢 **{member.display_name}** (ID: {member.id}) kicked\n**Reason:** {reason}')

@bot.tree.command(name="ban", description="🔨 Ban a member from server")
@discord.app_commands.describe(member="Member to ban", reason="Reason (optional)")
@discord.app_commands.checks.has_permissions(ban_members=True)
@discord.app_commands.check(is_moderator)
async def slash_ban(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    if member == interaction.user:
        await interaction.response.send_message("❌ You cannot ban yourself!", ephemeral=True)
        return
    if member == interaction.client.user:
        await interaction.response.send_message("❌ I cannot ban myself!", ephemeral=True)
        return
    if interaction.user.top_role <= member.top_role and interaction.guild.owner_id != interaction.user.id:
        await interaction.response.send_message(f"❌ Cannot ban **{member.display_name}** - role hierarchy.", ephemeral=True)
        return

    reason = reason or "No reason provided"
    await member.ban(reason=reason)
    await interaction.response.send_message(f'🔨 **{member.display_name}** (ID: {member.id}) banned\n**Reason:** {reason}')

@bot.tree.command(name="unban", description="🔓 Unban a user by ID or name")
@discord.app_commands.describe(user_input="User ID or username")
@discord.app_commands.checks.has_permissions(ban_members=True)
@discord.app_commands.check(is_moderator)
async def slash_unban(interaction: discord.Interaction, user_input: str):
    try:
        banned_users = [entry async for entry in interaction.guild.bans()]
    except discord.Forbidden:
        await interaction.response.send_message("❌ I lack Ban Members permission.", ephemeral=True)
        return

    target_user = None
    if user_input.isdigit():
        user_id = int(user_input)
        target_user = discord.utils.find(lambda e: e.user.id == user_id, banned_users)
        if target_user:
            target_user = target_user.user

    if not target_user:
        user_input_lower = user_input.lower()
        for entry in banned_users:
            user = entry.user
            if (user.name.lower() == user_input_lower or 
                user.global_name and user.global_name.lower() == user_input_lower):
                target_user = user
                break

    if target_user:
        await interaction.guild.unban(target_user)
        await interaction.response.send_message(f'🔓 **{target_user.display_name}** (ID: {target_user.id}) unbanned!')
    else:
        await interaction.response.send_message(f'❌ No banned user found: "{user_input}"\n**Tip:** Use User ID for accuracy.', ephemeral=True)

@bot.tree.command(name="timeout", description="🔇 Timeout a member")
@discord.app_commands.describe(member="Member", duration="Duration (1s/1m/1h/7d)", reason="Reason")
@discord.app_commands.checks.has_permissions(moderate_members=True)
@discord.app_commands.check(is_moderator)
async def slash_timeout(interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "No reason"):
    if interaction.user.top_role <= member.top_role and interaction.guild.owner_id != interaction.user.id:
        await interaction.response.send_message(f"❌ Cannot timeout **{member.display_name}** - role hierarchy.", ephemeral=True)
        return

    try:
        unit = duration[-1].lower()
        time_value = int(duration[:-1])
    except ValueError:
        await interaction.response.send_message("❌ Invalid format! Use: `1s`, `30m`, `2h`, `7d`", ephemeral=True)
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
        await interaction.response.send_message("❌ Invalid unit! Use: `s`, `m`, `h`, `d`", ephemeral=True)
        return

    if delta > datetime.timedelta(days=28):
        await interaction.response.send_message("❌ Maximum 28 days timeout.", ephemeral=True)
        return

    timeout_until = discord.utils.utcnow() + delta
    await member.timeout(timeout_until, reason=reason)
    await interaction.response.send_message(
        f'🔇 **{member.display_name}** timed out until {discord.utils.format_dt(timeout_until, "f")}\n**Reason:** {reason}'
    )

@bot.tree.command(name="untimeout", description="🔊 Remove timeout from member")
@discord.app_commands.describe(member="Member", reason="Reason")
@discord.app_commands.checks.has_permissions(moderate_members=True)
@discord.app_commands.check(is_moderator)
async def slash_untimeout(interaction: discord.Interaction, member: discord.Member, reason: str = "Timeout removed"):
    if not member.timed_out:
        await interaction.response.send_message(f"❌ **{member.display_name}** is not timed out.", ephemeral=True)
        return
    if interaction.user.top_role <= member.top_role and interaction.guild.owner_id != interaction.user.id:
        await interaction.response.send_message(f"❌ Cannot untimeout **{member.display_name}** - role hierarchy.", ephemeral=True)
        return

    await member.timeout(None, reason=reason)
    await interaction.response.send_message(f'🔊 Timeout removed from **{member.display_name}**.')

@bot.tree.command(name="lock", description="🔒 Lock channel (deny @everyone send messages)")
@discord.app_commands.describe(channel="Channel (optional)")
@discord.app_commands.checks.has_permissions(manage_channels=True)
@discord.app_commands.check(is_moderator)
async def slash_lock(interaction: discord.Interaction, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    overwrite = channel.overwrites_for(interaction.guild.default_role)
    
    if overwrite.send_messages is False:
        await interaction.response.send_message(f"🔒 **{channel.mention}** is already locked.", ephemeral=True)
        return
        
    overwrite.send_messages = False
    await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite, 
                                reason=f"Locked by {interaction.user}")
    await interaction.response.send_message(f"🔒 **{channel.mention}** locked!")

@bot.tree.command(name="unlock", description="🔓 Unlock channel")
@discord.app_commands.describe(channel="Channel (optional)")
@discord.app_commands.checks.has_permissions(manage_channels=True)
@discord.app_commands.check(is_moderator)
async def slash_unlock(interaction: discord.Interaction, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    overwrite = channel.overwrites_for(interaction.guild.default_role)
    
    if overwrite.send_messages is None or overwrite.send_messages is True:
        await interaction.response.send_message(f"🔓 **{channel.mention}** is already unlocked.", ephemeral=True)
        return

    overwrite.send_messages = None
    await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite, 
                                reason=f"Unlocked by {interaction.user}")
    await interaction.response.send_message(f"🔓 **{channel.mention}** unlocked!")

@bot.tree.command(name="whois", description="👤 Get detailed user information")
@discord.app_commands.describe(member="Member (optional)")
async def slash_whois(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user 

    embed = discord.Embed(
        title=f"👤 {member.display_name}",
        color=member.color or discord.Color.blue(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    
    embed.add_field(name="🆔 ID", value=member.id, inline=True)
    embed.add_field(name="📅 Created", value=discord.utils.format_dt(member.created_at, "R"), inline=True)
    embed.add_field(name="📥 Joined", value=discord.utils.format_dt(member.joined_at, "R"), inline=True)

    roles = [role.mention for role in member.roles if role != interaction.guild.default_role]
    embed.add_field(
        name=f"🎭 Roles ({len(roles)})", 
        value=", ".join(roles) if roles else "No roles", 
        inline=False
    )

    status_map = {
        discord.Status.online: "🟢 Online",
        discord.Status.idle: "🌙 Idle", 
        discord.Status.dnd: "🔴 DND",
        discord.Status.offline: "⚪ Offline"
    }
    embed.add_field(name="📶 Status", value=status_map.get(member.status, "⚫ Unknown"), inline=True)

    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"Requested by {interaction.user.display_name}", 
                    icon_url=interaction.user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="🏛️ Server statistics")
async def slash_serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    
    embed = discord.Embed(
        title=f"🏛️ {guild.name}",
        color=discord.Color.gold(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )

    embed.add_field(name="👑 Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
    embed.add_field(name="🆔 ID", value=guild.id, inline=True)
    embed.add_field(name="📅 Created", value=discord.utils.format_dt(guild.created_at, "R"), inline=True)
    
    bots = sum(1 for m in guild.members if m.bot)
    humans = guild.member_count - bots
    embed.add_field(name="👥 Members", value=f"**{guild.member_count}** total\n🧑 {humans} humans\n🤖 {bots} bots", inline=True)

    text = len(guild.text_channels)
    voice = len(guild.voice_channels)
    cats = len(guild.categories)
    embed.add_field(name="📺 Channels", value=f"📝 {text}\n🔊 {voice}\n📁 {cats}", inline=True)
    
    embed.add_field(name="🏷️ Roles", value=len(guild.roles) - 1, inline=True)
    embed.add_field(name="⭐ Boosts", value=f"Tier {guild.premium_tier}\n({guild.premium_subscription_count or 0})", inline=True)

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
        
    embed.set_footer(text=f"Requested by {interaction.user.display_name}", 
                    icon_url=interaction.user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="targetpurge", description="🧹 Delete specific member's messages")
@discord.app_commands.describe(member="Target member", amount="Messages to delete (1-100)")
@discord.app_commands.checks.has_permissions(manage_messages=True)
@discord.app_commands.check(is_moderator)
async def slash_targetpurge(interaction: discord.Interaction, member: discord.Member, amount: int):
    if amount < 1 or amount > 100:
        await interaction.response.send_message("❌ Amount must be 1-100.", ephemeral=True)
        return

    messages = []
    async for message in interaction.channel.history(limit=500):
        if len(messages) >= amount:
            break
        if message.author == member:
            messages.append(message)

    if not messages:
        await interaction.response.send_message(f"❌ No recent messages from **{member.display_name}**.", ephemeral=True)
        return

    try:
        await interaction.channel.delete_messages(messages)
        await interaction.response.send_message(
            f'🧹 Deleted **{len(messages)}** messages from **{member.display_name}**.', 
            ephemeral=True
        )
    except discord.Forbidden:
        await interaction.response.send_message("❌ I lack Manage Messages permission.", ephemeral=True)
    except discord.HTTPException as e:
        if "older than 14 days" in str(e).lower():
            await interaction.response.send_message("❌ Some messages are older than 14 days.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Delete failed: {str(e)}", ephemeral=True)

# --- Run the Bot ---
if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        print("❌ ERROR: Set DISCORD_BOT_TOKEN environment variable!")
        exit(1)
    else:
        print("🚀 Starting bot...")
        bot.run(DISCORD_BOT_TOKEN)
