import configparser
from time import sleep
import valve.rcon
import discord
import subprocess
from subprocess import PIPE
import asyncio
import sqlite3
import sys
import random
import string
import re
from datetime import datetime, timedelta, timezone
import os

config = configparser.ConfigParser()
config.read("config.ini")
#shop db file path location
file_path_shop_db = config["SHOP"]["Database"]
#Discord channel for posting shop item list
shop_discord_channel_id = config["DISCORD"]["shopListChannelId"]
#Discord api key needed to run the bot
discord_api_key = config["DISCORD"]["APIKEY"]
timezone = int(config["TIME"]["Timezone"])


intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)

async def registrationWatcher():
    while True:
        shopCon = sqlite3.connect(file_path_shop_db)
        shopCur = shopCon.cursor()
        #find complete registrations
        shopCur.execute("SELECT * FROM registration_codes WHERE status = 1")
        completed = shopCur.fetchall()
        messageSent = 0
        if completed != None:
            for user in completed:
                if messageSent == 0:
                    discordID = user[0]
                    discordObjID = user[1]
                    code = user[2]
                    print(f"Discord ID for {code} has been set to {discordID}")
                    #print(f"Discord Object ID is {discordObjID}")
    
                    members = client.get_all_members()
                    for member in members:
                        if (discordID == str(member)) and (messageSent == 0):
                            await member.send("Registration Complete")
                            shopCur.execute("DELETE FROM registration_codes WHERE discordID = ?", (discordID, ))
                            shopCon.commit()
                            messageSent = 1
        shopCur.close()
        shopCon.close()
        await asyncio.sleep(5)  # task runs every 5 seconds

async def updateWalletforCurrentUsers():
    while True:
        shopcon = sqlite3.connect(file_path_shop_db)
        shopcur = shopcon.cursor()
        shopcur.execute("SELECT ID FROM servers WHERE Enabled ='True'")
        ServerIDs = shopcur.fetchall()
        if ServerIDs != None:
            p = subprocess.Popen(['python.exe', 'updateWalletforCurrentUsers.py'],shell=True)
        await asyncio.sleep(1800)  # task runs every 30 min

async def updateShopList():
    while True:
        print("Updating Shop")
        channel = client.get_channel(int(shop_discord_channel_id))
        await channel.purge()
        
        try:
            shopCon = sqlite3.connect(file_path_shop_db)
            shopCur = shopCon.cursor()
            shopCur.execute("SELECT DISTINCT(category) FROM shop_items WHERE enabled = 1 AND category != 'NULL' ORDER BY category ASC")
            categories = shopCur.fetchall()
            for category in categories:
                cat = category[0]
                embedvar = discord.Embed(title=cat)
                embedvar.set_footer(text="To buy an item go to purchasing and use !buy followed by the item ID. Example !buy 1 ")
                shopCur.execute(f"SELECT * FROM shop_items WHERE enabled = 1 AND category = '{cat}' ORDER BY id desc")
                shop_items = shopCur.fetchall()


                for row in shop_items:
                    itemid = row[0]
                    name = row[1]
                    price = row[2]
                    count = row[4]
                    description = row[8]
                    category = [9]
                    
                    embedvar.add_field(name="ID: {} \tName: {} x {}".format(itemid, count, name), value="Price: {} coins\nDescription: {}".format(price, description),inline=False)
                await channel.send(embed=embedvar)

        except Exception as e:
                print(f"Update Shop Error: {e}")
                pass
        shopCur.close()
        shopCon.close()
        
        
        await asyncio.sleep(600) #updates every 10 minutes

async def purchaseItem(senderID,userIN,channelID,author):
    sourcechannel = client.get_channel(channelID)
    outOfKarma = 0
    loadDate = (datetime.now()).strftime("%m-%d-%YT%H:%M:%S")
    try:
        shopCon = sqlite3.connect(file_path_shop_db)
        shopCur = shopCon.cursor()
        #Get the price of the item
        shopCur.execute(f"SELECT name, price, itemid, count, itemType, kitID, cooldown FROM shop_items WHERE id =? AND enabled =1", (userIN, ))
        itemDetails = shopCur.fetchone()
        if itemDetails == None:
            print("Item not found")
            msg = "Item not found"
        else:
            itemname = itemDetails[0]
            itemcount = itemDetails[3]
            itemid = itemDetails[2]
            itemprice = itemDetails[1]
            itemType = itemDetails[4]
            itemKitID = itemDetails[5]
            cooldown = int(itemDetails[6])
            #Assign an order number
            shopCur.execute("SELECT order_number FROM shop_log ORDER BY order_number DESC")
            orderNums = shopCur.fetchone()
            if orderNums != None:
                order_number = int(orderNums[0]) + 1
            else:
                order_number = 1

            #get the wallet value of the user
            shopCur.execute(f"SELECT walletBalance,conanplatformid FROM accounts WHERE discordid =?", (senderID, ))
            senderDetails = shopCur.fetchone()
            if senderDetails == None:
                msg = (f"Couldn't find any coin for {senderID}. Try !register first.")
            else:
                senderCoin = senderDetails[0]
                platformid = senderDetails[1]
                if int(senderCoin) >= int(itemprice):
                    print(f"{senderID} Has enough coin to purchase {itemname} for {itemprice}")
                    #check if cooldown for this item is up for the user
                    shopCur.execute("SELECT timestamp FROM shop_log WHERE item =? AND player=? ORDER BY ID Desc", (itemname, senderID))
                    lastPurchase = shopCur.fetchone()
                    if lastPurchase != None:
                        timestamp = datetime.strptime(lastPurchase[0], "%m-%d-%YT%H:%M:%S")
                        now = datetime.now()
                        coolDownExpires = timestamp + timedelta(minutes=cooldown)
                        if now > coolDownExpires:
                            print("Cool down is up. Purchase allowed")
                            coolDownOK = True
                        else:
                            coolDownOK = False
                            print(f"Cannot purchase again yet, Cooldown expires {coolDownExpires}")
                            timediff = coolDownExpires - timestamp
                            status = f"Cannot purchase again yet, Cooldown expires in {timediff}"
                            msg = status
                    else: 
                        coolDownOK = True

                    if coolDownOK:
                        #check if the user is online

                        #sync users
                        p = subprocess.call(['python.exe', "currentUserSync.py"], stdout=sys.stdout)
                        userFound = 0
                        rconSuccess = 0
                        user_server = ''
                        #look for user on servers
                        shopCur.execute("SELECT ID, ServerName FROM servers WHERE enabled ='True'")
                        enabledServers = shopCur.fetchall()
                        if enabledServers != None:
                            for enabledServer in enabledServers:
                                serverid = enabledServer[0]
                                serverName = enabledServer[1]
                                shopCur.execute(f"SELECT b.conid FROM {serverName}_historicalUsers a LEFT JOIN {serverName}_currentUsers b ON a.userid = b.userid WHERE b.platformid = ? LIMIT 1",(platformid,))
                                conid = shopCur.fetchone()
                            
                                if conid != None:
                                    userFound = 1
                                    user_server = serverName
                                    shopCur.execute("SELECT rcon_host, rcon_port, rcon_pass FROM servers WHERE ID =?", (serverid, ))
                                    rconInfo = shopCur.fetchone()
                                    if rconInfo != None:
                                        rcon_host = rconInfo[0]
                                        rcon_port = rconInfo[1]
                                        rcon_pass = rconInfo[2]

                        if userFound == 1:
                            #try delivery
                            if itemType == 'single':
                                print("item type is single, processing order")
                                attempts = 0
                                while rconSuccess == 0 and attempts <= 5:
                                    try:
                                        with valve.rcon.RCON((rcon_host, int(rcon_port)), rcon_pass) as rcon:
                                            response = rcon.execute(f"con {conid[0]} spawnitem {itemid} {itemcount}")
                                            rcon.close()
                                            status = "Success!"
                                        print(response.text)
                                        rconSuccess = 1
                                    except valve.rcon.RCONAuthenticationError:
                                        print("Authentication Error")
                                        status = "Could not authenticate RCON"
                                        rconSuccess = 0
                                        attempts = attempts + 1
                                        pass
                                    except ConnectionResetError:
                                        print("Could not connect to server. Retry later")
                                        status = "Could not connect to server, possibly out of karma"
                                        rconSuccess = 0
                                        attempts = attempts + 5
                                        outOfKarma = 1
                                        pass
                            elif itemType == 'kit':
                                print("item type is kit, processing order")
                                #get items in the kit
                                shopCur.execute("SELECT itemID, count, name FROM shop_kits WHERE kitID =?",(itemKitID, ))
                                items = shopCur.fetchall()
                                if items == None:
                                    print("No items associated with kit, order canceled")
                                    msg = "No items associated with kit, order canceled"
                                else:
                                    for item in items:
                                        #sync users
                                        p = subprocess.call(['python.exe', "currentUserSync.py"], stdout=sys.stdout)
                                        rconSuccess = 0
                                        #look for user on server
                                        shopCur.execute(f"SELECT b.conid FROM {user_server}_historicalUsers a LEFT JOIN {user_server}_currentUsers b ON a.userid = b.userid WHERE b.platformid = ? LIMIT 1",(platformid,))
                                        conid = shopCur.fetchone()
                                        userFound = 0
                                        if conid == None:
                                            msg = "Couldn't find user online. Please try again once you are in game"
                                            userFound = 0
                                            rconSuccess = 1
                                            status = "User disconnected on order processing"
                                        else:
                                            userFound = 1
                                        
                                        loopItemID = item[0]
                                        loopItemCount = item[1]
                                        loopItemName = item[2]
                                        attempts = 0
                                        while rconSuccess == 0 and attempts <= 5:
                                            try:
                                                with valve.rcon.RCON((rcon_host, int(rcon_port)), rcon_pass) as rcon:
                                                    response = rcon.execute(f"con {conid[0]} spawnitem {loopItemID} {loopItemCount}")
                                                    rcon.close()
                                                    status = "Success!"
                                                    shopCur.execute("INSERT INTO shop_log (order_number, item, count, price, player, server, status, timestamp) VALUES (?,?,?,?,?,?,?,?)", (order_number, loopItemName, loopItemCount, 'KitItem', senderID, user_server, status, loadDate))
                                                    shopCon.commit()
                                                print(response.text)
                                                rconSuccess = 1
                                            except valve.rcon.RCONAuthenticationError:
                                                print("Authentication Error")
                                                status = "Could not authenticate RCON"
                                                rconSuccess = 0
                                                attempts = attempts + 1
                                                pass
                                            except ConnectionResetError:
                                                print("Could not connect to server. Retry later")
                                                status = "Could not connect to server, possibly out of karma"
                                                rconSuccess = 0
                                                attempts = attempts + 5
                                                outOfKarma = 1
                                                pass
                            else:
                                print("couldn't identify item type. Canceling order")
                                msg = "Couldn't identify item type. Canceling order"


                        if rconSuccess == 1:
                            #log purchase
                            shopCur.execute("INSERT INTO shop_log (order_number, item, count, price, player, server, status, timestamp) VALUES (?,?,?,?,?,?,?,?)", (order_number, itemname, itemcount, itemprice, senderID, user_server, status, loadDate))
                            shopCon.commit()
                            #remove coin
                            newBalance = int(senderCoin) - int(itemprice)
                            shopCur.execute(f"UPDATE accounts SET walletBalance = ? WHERE discordid =?",(int(newBalance), senderID))
                            shopCon.commit()
                            msg = f"Purchase successful! {itemcount} x {itemname} has been delivered. Your new coin balance is {newBalance}."
                            
                        elif rconSuccess == 0:
                            #log purchase
                            shopCur.execute("INSERT INTO shop_log (order_number, item, count, price, player, server, status, timestamp) VALUES (?,?,?,?,?,?,?,?)", (order_number, itemname, itemcount, itemprice, senderID, user_server, status, loadDate))
                            shopCon.commit()
                            if outOfKarma == 0:
                                msg = f"Purchase Failed! Error: {status}"

                else:
                    msg = "Insufficient Balance"
        shopCur.close()
        shopCon.close()
    except Exception as e:
            print(f"Error on DB: {e}")
            msg = ("Couldn't connect to DB. Try again later")
            pass
    if outOfKarma == 1:
        msg = f"Purchase Failed! Error: {status}\nOUT OF KARMA!!! PAUSING BOT FOR 5 MIN!"
        await sourcechannel.send(msg)
        sleep(301)
        outOfKarma = 0
    else:    
        await sourcechannel.send(msg)

def clean_text(rgx_list, text):
    new_text = text
    for rgx_match in rgx_list:
        new_text = re.sub(rgx_match, '', new_text)
    return new_text

async def watchChat4Registration():
    #subprocess.Popen(['python.exe', "chatlogwatchdog.py"], stdout=sys.stdout)
    #get list of enabled and dedicated servers and start chat log for them
    shopcon = sqlite3.connect(file_path_shop_db)
    shopcur = shopcon.cursor()
    shopcur.execute("SELECT ID, servername FROM servers WHERE Enabled ='True' AND Dedicated ='True'")
    ServerIDs = shopcur.fetchall()
    if ServerIDs != None:
        for ServerID in ServerIDs:
            server = ServerID[0]
            serverName = ServerID[1]
            print(f"Starting chat log watcher for {serverName}")
            #subprocess.Popen(['python', 'chatLogWatchDog.py', '--server', f'{ServerID}'], stdout=PIPE, stderr=PIPE, shell=True)
            subprocess.Popen(['python.exe', 'chatlogwatchdog.py', '--server', f'{server}'], stdout=sys.stdout)
    shopcon.close()

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))
    await client.change_presence(activity=discord.Game(name="Conan Exiles"))
    client.loop.create_task(registrationWatcher())
    client.loop.create_task(watchChat4Registration())
    client.loop.create_task(updateWalletforCurrentUsers())
    client.loop.create_task(updateShopList())
    

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    
    if message.content == '!register':
        discordID = message.author.name + '#' + message.author.discriminator
        discordObjID = message.author.id
        print(discordID)
        print(discordObjID)
        shopCon = sqlite3.connect(file_path_shop_db)
        shopCur = shopCon.cursor()
        # Create registration code
        N = 6
        code = ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(N))
        print(f"Registration code created for {discordID} code: {code}")


        # insert code with associated discord ID
        try:
            shopCur.execute("INSERT INTO registration_codes (discordID, discordObjID, registrationCode) VALUES (?, ?, ?)",
                             (discordID, discordObjID, code))
            shopCon.commit()
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                print("found duplicate updating registration code")
                shopCur.execute("UPDATE registration_codes SET registrationcode = ? WHERE discordID = ?",
                                 (code, discordID))
                shopCon.commit()
            else:
                print(f"failed to insert {e}")
            pass
        shopCon.close()
        await message.author.send(f"Please enter '!register {code}' into conan in-game chat without the quotes. Recommend entering in /local or /clan")

    if message.content == '!coin':
            discordID = message.author.name + '#' + message.author.discriminator
            discordObjID = message.author.id
            print(discordID)
            print(discordObjID)

            shopCon = sqlite3.connect(file_path_shop_db)
            # Get shopCursor
            shopCur = shopCon.cursor()

            # get wallet balance
            shopCur.execute("SELECT walletBalance FROM accounts WHERE discordid = ?",(discordID, ))
            coin = shopCur.fetchone()
            
            if coin == None:
                msg = "Couldn't find an account associated with your discord ID. Please !register first."
            else:
                coin = coin[0] 
                msg = (f"You have {coin} Irrelevant Coin(s)")
            shopCon.close()
            await message.channel.send(msg)

    if message.content.startswith('!buy'):
        userIN = message.content[5:]
        senderID = message.author.name + "#" + message.author.discriminator
        channelID = message.channel.id
        author = message.author
        await purchaseItem(senderID,userIN,channelID,author)

    if message.content.startswith('!gift'):

        senderDiscordID = message.author.name + "#" + message.author.discriminator
        pattern = re.compile(r'(?: <\S*[0-9]*>)?', re.IGNORECASE)
        match = pattern.findall(message.content)
        gift = clean_text(match, message.content)
        gift = gift[6:]
        mentioned = message.mentions
        mentionedCount = len(mentioned)
        senderCoinNeeded = int(gift) * mentionedCount
        #get senders balance, make sure it's enough, then send gift
        if int(gift) <= 0:
            msg = "Cannot send null value gift."
        else:
            try:
                shopCon = sqlite3.connect(file_path_shop_db)

                shopCur = shopCon.cursor()
                shopCur.execute(f"SELECT walletBalance FROM accounts WHERE discordid =?", (senderDiscordID, ))
                senderCoin = shopCur.fetchone()
                if senderCoin == None:
                    #YOU AINT GOT A WALLET
                    msg = ("Wallet not found. Try !register first")
                else:
                    senderCoin = senderCoin[0]
                    if int(senderCoin) >= int(senderCoinNeeded):
                        #you have enough
                        for mentions in mentioned:
                            discordid = mentions.name + "#" + mentions.discriminator
                            print(f"{senderDiscordID} is gifting {gift} to {discordid}")
                            
                            #Get starting balance
                            shopCur.execute(f"SELECT walletBalance FROM accounts WHERE discordid =?", (discordid, ))
                            recipWallet = shopCur.fetchone()
                            if recipWallet == None:
                                msg = (f"{discordid} is not associated with a wallet. They will need to !register first")
                            else:
                                #try to update
                                recipWallet = recipWallet[0]
                                newBalance = int(recipWallet) + int(gift)
                                shopCur.execute("UPDATE accounts SET walletBalance = ? WHERE discordid =?", (newBalance, discordid))
                                shopCon.commit()

                                #remove coin from sender
                                senderCoin = int(senderCoin) - int(gift)
                                shopCur.execute("UPDATE accounts SET walletBalance = ? WHERE discordid =?", (senderCoin, senderDiscordID))
                                shopCon.commit()
                                msg = (f"{message.author.name} has sent a gift of {gift} Irrelevant Coin(s) to {discordid}")
                            
                    else:
                        #you broke
                        msg = ("Insufficient Balance")
                        
                    
                    shopCur.close()
                    shopCon.close()

            except Exception as e:
                print(f"Error in Gifting: {e}")
                msg = ("Error in Gifting, Try again later")
                pass
            await message.channel.send(msg)

client.run(discord_api_key)