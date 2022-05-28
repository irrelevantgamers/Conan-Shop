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
paycheck_interval = int(config["SHOP"]["PayCheckInterval"])
if paycheck_interval == None:
    paycheck_interval = 30
paycheck_interval_seconds = paycheck_interval * 60
#Discord api key needed to run the bot
discord_api_key = config["DISCORD"]["APIKEY"]
currency = config["SHOP"]["CurrencyName"]
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
        await asyncio.sleep(paycheck_interval_seconds)  # task runs every 30 min by default, change paycheck_interval in config.ini to set how often this runs in minutes

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
                shopCur.execute(f"SELECT * FROM shop_items WHERE enabled = 1 AND category = '{cat}' ORDER BY id ASC")
                shop_items = shopCur.fetchall()


                for row in shop_items:
                    itemid = row[0]
                    name = row[1]
                    price = row[2]
                    count = row[4]
                    description = row[8]
                    category = [9]
                    
                    embedvar.add_field(name="ID: {} \tName: {} x {}".format(itemid, count, name), value="Price: {} {}\nDescription: {}".format(price, currency, description),inline=False)
                await channel.send(embed=embedvar)

        except Exception as e:
                print(f"Update Shop Error: {e}")
                pass
        shopCur.close()
        shopCon.close()
        
        
        await asyncio.sleep(600) #updates every 10 minutes

### Old purchase item routine ### NOT IN USE ###
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
                msg = (f"Couldn't find any {currency} for {senderID}. Try !register first.")
            else:
                senderCurrency = senderDetails[0]
                platformid = senderDetails[1]
                if int(senderCurrency) >= int(itemprice):
                    print(f"{senderID} Has enough {currency} to purchase {itemname} for {itemprice}")
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
                            #remove currency
                            newBalance = int(senderCurrency) - int(itemprice)
                            shopCur.execute(f"UPDATE accounts SET walletBalance = ? WHERE discordid =?",(int(newBalance), senderID))
                            shopCon.commit()
                            msg = f"Purchase successful! {itemcount} x {itemname} has been delivered. Your new {currency} balance is {newBalance}."
                            
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
################################################

async def placeOrder(senderID,userIN,channelID):
    sourcechannel = client.get_channel(channelID)
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
            order_number = "N/A"
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
            order_date = datetime.now()
            last_attempt = '0000-00-00 00:00:00'
            #get the wallet value of the user
            shopCur.execute(f"SELECT walletBalance,conanplatformid, steamplatformid FROM accounts WHERE discordid =?", (senderID, ))
            senderDetails = shopCur.fetchone()
            if senderDetails == None:
                msg = (f"Couldn't find any {currency} for {senderID}. Try !register first.")
            else:
                senderCurrency = senderDetails[0]
                platformid = senderDetails[1]
                steamid = senderDetails[2]
                if int(senderCurrency) >= int(itemprice):
                    print(f"{senderID} Has enough {currency} to purchase {itemname} for {itemprice}")
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
                        if itemType == 'single':
                            print("item type is single, placing order")
                            shopCur.execute("INSERT INTO order_processing (order_number, order_value, itemid, count, purchaser_platformid, purchaser_steamid, in_process, completed, refunded, order_date, last_attempt) values (?,?,?,?,?,?,0,0,0,?,?)",(order_number, itemprice, itemid, itemcount, platformid, steamid, order_date, last_attempt))
                            shopCon.commit()
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
                                    itemid = item[0]
                                    itemcount = item[1]
                                    shopCur.execute("INSERT INTO order_processing (order_number, order_value, itemid, count, purchaser_platformid, purchaser_steamid, in_process, completed, refunded, order_date, last_attempt) values (?,?,?,?,?,?,0,0,0,?,?)",(order_number, itemprice, itemid, itemcount, platformid, steamid, order_date, last_attempt))
                                    shopCon.commit()
                        else:
                            print("couldn't identify item type. Canceling order")
                            msg = "Couldn't identify item type. Canceling order"


                        
                        #log purchase
                        status = "Order Placed"
                        shopCur.execute("INSERT INTO shop_log (order_number, item, count, price, player, status, timestamp) VALUES (?,?,?,?,?,?,?)", (order_number, itemname, itemcount, itemprice, senderID, status, loadDate))
                        shopCon.commit()
                        #remove currency
                        newBalance = int(senderCurrency) - int(itemprice)
                        shopCur.execute(f"UPDATE accounts SET walletBalance = ? WHERE discordid =?",(int(newBalance), senderID))
                        shopCon.commit()
                        msg = f"Order# {order_number} has been placed. Your new {currency} balance is {newBalance}. You can refund pending orders with !refund {order_number}"

                else:
                    msg = "Insufficient Balance"
        shopCur.close()
        shopCon.close()
    except Exception as e:
            print(f"Error on DB: {e}")
            msg = ("Couldn't connect to DB. Try again later")
            pass
        
    message = await sourcechannel.send(msg)
    message_id = message.id
    discordChannelID = sourcechannel.id
    #insert message ID for order_num
    if msg != "Item not found":
        try:
            shopCon = sqlite3.connect(file_path_shop_db)
            shopCur = shopCon.cursor()
            shopCur.execute("UPDATE order_processing SET discordMessageID =?, discordChannelID =? WHERE order_number =?", (message_id, discordChannelID, order_number))
            shopCon.commit()
            shopCur.close()
            shopCon.close()
        except Exception as e:
            print(f"Failed to set discord message id for order {order_number}")
            pass

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

async def refundOrder(senderID,userIN,channelID):
    sourceChannel = client.get_channel(channelID)
    order_number = userIN
    print(f"Attempting to refund order {order_number}")
    #find if order is eligible (is the order not in process and not complete, has the order been refunded already, is the requester the original orderer)
    shopCon = sqlite3.connect(file_path_shop_db)
    shopCur = shopCon.cursor()
    shopCur.execute("SELECT id, order_number, order_value, itemid, in_process, completed, refunded, order_date, last_attempt, completed_date, discordMessageID, discordChannelID FROM order_processing WHERE order_number =?",(userIN, ))
    orderDetails = shopCur.fetchall()
    if orderDetails != None:
        refundedFound = 0
        inProcessFound = 0
        completedFound = 0
        order_value = 0
        order_number = 0
        for item in orderDetails:
            order_value = item[2]    
            inProcess = item[4]
            completed = item[5]
            refunded = item[6]
            order_number = item[1]
            if inProcess == 1:
                inProcessFound = 1
            if completed == 1:
                completedFound = 1
            if refunded == 1:
                refundedFound = 1

        if refundedFound == 1 or inProcessFound == 1 or completedFound == 1:
            msg = "Order is not eligible for refund."
        else:
            #get wallet balance of user and add order value back to wallet
            shopCur.execute("SELECT walletBalance from accounts WHERE discordID =?",(senderID, ))
            balance = shopCur.fetchone()
            if balance != None:
                balance = balance[0]
                newBalance = int(balance) + int(order_value)
                shopCur.execute("UPDATE accounts SET walletBalance =? WHERE discordID =?",(newBalance, senderID))
                shopCon.commit()
                #set order status to refunded
                shopCur.execute("UPDATE order_processing SET refunded ='1' WHERE order_number =?", (order_number,))
                shopCon.commit()
                msg = f"Refund has been processed. New wallet balance is {newBalance}"
            else:
                msg = f"Account not found for {senderID}. Please !register first"
    else:
        msg = "Order not found"
    shopCur.close()
    shopCon.close()
    await sourceChannel.send(msg)

async def processOrderLoop():
    print("Starting Order Processor")
    while True:
        shopCon = sqlite3.connect(file_path_shop_db)
        shopCur = shopCon.cursor()
        now = datetime.now()
        eligibleProcessTime = now - timedelta(minutes=5)
        
        #Get incomplete orders by newest
        shopCur.execute("SELECT order_number, itemid, count, purchaser_platformid, purchaser_steamid, order_date FROM order_processing WHERE completed !='1' AND in_process !='1' AND refunded !='1' AND last_attempt <= datetime(?) ORDER BY order_date ASC", (eligibleProcessTime, ))
        NewestOrder = shopCur.fetchone()
        try:
            if NewestOrder != None:
                #process order
                #mark order as in process for this order number
                orderNumber = NewestOrder[0]
                shopCur.execute("UPDATE order_processing SET in_process ='1' WHERE order_number =?",(orderNumber, ))
                shopCon.commit()

                #Get all items associated with order number
                shopCur.execute("SELECT id, order_number, itemid, count, purchaser_platformid, purchaser_steamid, order_date FROM order_processing WHERE order_number =?",(orderNumber, ))
                orderedItems = shopCur.fetchall()
                if orderedItems != None:
                    for item in orderedItems:
                        order_id = item[0]
                        order_number = item[1]
                        itemid = item[2]
                        itemcount = item[3]
                        platformid =item[4]
                        print(f"Processing {order_number}: Current order_processing_id {order_id}: Item ID {itemid}")
                        
                        #sync users
                        try:
                            p = subprocess.Popen(['python.exe', "currentUserSync.py"], stdout=PIPE)
                            p.wait()
                            result = p.communicate()
                            #print(result)
                            if "'playerlist' referenced before assignment" in str(result):
                                #print("out of karma")
                                outOfKarma = 1
                            else:
                                outOfKarma = 0
                        except Exception as e:
                            print(f"User sync failed, continueing anyway. Error {e}")
                            outOfKarma = 0
                            pass

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

                        if rconSuccess == 1:
                            #update order processing to show this is complete
                            completeTime = datetime.now()
                            shopCur.execute("UPDATE order_processing SET completed ='1', in_process ='0', completed_date =?, last_attempt =? WHERE id=?",(completeTime, completeTime, order_id))
                            shopCon.commit()
                        elif rconSuccess == 0:
                            #set in_process back to 0
                            #update last attempted date for order
                            attemptTime = datetime.now()
                            shopCur.execute("UPDATE order_processing SET last_attempt =?, in_process ='0' WHERE id=?",(attemptTime, order_id))
                            shopCon.commit()
                            if outOfKarma == 1:
                                print("Out of karma, pause processing for 10 minutes")
                                await asyncio.sleep(600)
                                outOfKarma = 0
        except Exception as e:
            print(f"exception: {e}")
            pass
        shopCur.close()
        shopCon.close()
        await asyncio.sleep(5) #sleep for 5 seconds between orders

async def orderStatusWatcher():
    while True:
        try:
            #get order status that have updated in the last 30 seconds
            windowTime = datetime.now() - timedelta(seconds=30)
            shopCon = sqlite3.connect(file_path_shop_db)
            shopCur = shopCon.cursor()
            shopCur.execute("SELECT id, order_number, itemid, in_process, completed, refunded, order_date, last_attempt, completed_date, discordMessageID, discordChannelID FROM order_processing WHERE orderCompleteNoticeSent IS NULL")
            changedOrders = shopCur.fetchall()
            if changedOrders != None:
                for order in changedOrders:
                    order_id = order[0]
                    order_number = order[1]
                    itemid = order[2]
                    in_process = order[3]
                    completed = order[4]
                    refunded = order[5]
                    order_date = order[6]
                    last_attempt = order[7]
                    completed_date = order[8]
                    discordMessageID = order[9]
                    discordChannelID = order[10]

                    #check if another item from orderis complete and mark status partially complete
                    completedFound = 0
                    incompleteFound = 0
                    shopCur.execute("SELECT id, completed FROM order_processing WHERE order_number =?",(order_number, ))
                    items = shopCur.fetchall()
                    if items != None:
                        if len(items) >= 2:
                            #this is a kit, check if there are both complete and incomplete items for order
                            for item in items:
                                if item[1] == 1:
                                    completedFound = 1
                                elif item[1] == 0:
                                    incompleteFound = 1

                    #update discord message ID as a test
                    if completedFound == 1 and incompleteFound == 1:
                        status = "Partial Delivery Complete"
                        embedvar = discord.Embed(title='Order Status', color = discord.Color.orange())
                        embedvar.add_field(name="Order #:{} \nStatus: {}".format(order_number, status), value="Order Date: {}".format(order_date, ))
                    
                    elif completed == 1 and refunded == 0:
                        status = "Complete"
                        embedvar = discord.Embed(title='Order Status', color = discord.Color.green())
                        embedvar.add_field(name="Order #:{} \nStatus: {}".format(order_number, status), value="Order Date: {}\nCompleted Date: {}".format(order_date, completed_date))
                        shopCur.execute("UPDATE order_processing SET orderCompleteNoticeSent ='1' WHERE ID =?",(order_id, ))
                        shopCon.commit()
                    elif refunded == 1:
                        status = "Refunded"
                        embedvar = discord.Embed(title='Order Status', color = discord.Color.red())
                        embedvar.add_field(name="Order #:{} \nStatus: {}".format(order_number, status), value="Order Date: {}\nLast delivery attempt date: {}".format(order_date, last_attempt))
                        shopCur.execute("UPDATE order_processing SET orderCompleteNoticeSent ='1' WHERE ID =?",(order_id, ))
                        shopCon.commit()
                    elif in_process == 1:
                        status = "Processing"
                        embedvar = discord.Embed(title='Order Status', color = discord.Color.blue())
                        embedvar.add_field(name="Order #:{} \nStatus: {}".format(order_number, status), value="Order Date: {}\nLast delivery attempt date: {}".format(order_date, last_attempt))
                    else:
                        status = "Placed pending processing."
                        embedvar = discord.Embed(title='Order Status', color = discord.Color.gold())
                        embedvar.add_field(name="Order #:{} \nStatus: {}".format(order_number, status), value="Order Date: {}\nLast delivery attempt date: {}".format(order_date, last_attempt))
                        
                    channel = client.get_channel(int(discordChannelID))
                    message = await channel.fetch_message(int(discordMessageID))
                
                    
                    
                    
                    await message.edit(embed=embedvar)
        except Exception as e:
            if "object has no attribute 'fetch_message'" in str(e):
                print(f"Order message went to DM, can't update?")
                shopCur.execute("UPDATE order_processing SET orderCompleteNoticeSent ='0' WHERE order_number =?",(order_number, ))
                shopCon.commit()
            else:
                print(f"error in order status watcher {e}")
            pass
        shopCur.close()
        shopCon.close()
        await asyncio.sleep(1)

async def currentUserSync():
    while True:
        #sync current users every 5 min by default users
        p = subprocess.call(['python.exe', "currentUserSync.py"], stdout=sys.stdout)
        await asyncio.sleep(300)

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))
    await client.change_presence(activity=discord.Game(name="Conan Exiles"))
    client.loop.create_task(registrationWatcher())
    client.loop.create_task(watchChat4Registration())
    client.loop.create_task(updateWalletforCurrentUsers())
    client.loop.create_task(updateShopList())
    client.loop.create_task(processOrderLoop())
    client.loop.create_task(orderStatusWatcher())
    client.loop.create_task(currentUserSync())

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

    if message.content == '!balance':
            discordID = message.author.name + '#' + message.author.discriminator
            discordObjID = message.author.id
            print(discordID)
            print(discordObjID)

            shopCon = sqlite3.connect(file_path_shop_db)
            # Get shopCursor
            shopCur = shopCon.cursor()

            # get wallet balance
            shopCur.execute("SELECT walletBalance FROM accounts WHERE discordid = ?",(discordID, ))
            balance = shopCur.fetchone()
            
            if balance == None:
                msg = "Couldn't find an account associated with your discord ID. Please !register first."
            else:
                balance = balance[0] 
                msg = (f"You have {balance} {currency}")
            shopCon.close()
            await message.channel.send(msg)

    if message.content.startswith('!buy'):
        userIN = message.content[5:]
        senderID = message.author.name + "#" + message.author.discriminator
        channelID = message.channel.id
        author = message.author
        #await purchaseItem(senderID,userIN,channelID,author)
        await placeOrder(senderID,userIN,channelID)

    if message.content.startswith('!gift'):

        senderDiscordID = message.author.name + "#" + message.author.discriminator
        pattern = re.compile(r'(?: <\S*[0-9]*>)?', re.IGNORECASE)
        match = pattern.findall(message.content)
        gift = clean_text(match, message.content)
        gift = gift[6:]
        mentioned = message.mentions
        mentionedCount = len(mentioned)
        senderCurrencyNeeded = int(gift) * mentionedCount
        #get senders balance, make sure it's enough, then send gift
        if int(gift) <= 0:
            msg = "Cannot send null value gift."
        else:
            try:
                shopCon = sqlite3.connect(file_path_shop_db)

                shopCur = shopCon.cursor()
                shopCur.execute(f"SELECT walletBalance FROM accounts WHERE discordid =?", (senderDiscordID, ))
                senderCurrency = shopCur.fetchone()
                if senderCurrency == None:
                    #YOU AINT GOT A WALLET
                    msg = ("Wallet not found. Try !register first")
                else:
                    senderCurrency = senderCurrency[0]
                    if int(senderCurrency) >= int(senderCurrencyNeeded):
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

                                #remove currency from sender
                                senderCurrency = int(senderCurrency) - int(gift)
                                shopCur.execute("UPDATE accounts SET walletBalance = ? WHERE discordid =?", (senderCurrency, senderDiscordID))
                                shopCon.commit()
                                msg = (f"{message.author.name} has sent a gift of {gift} {currency} to {discordid}")
                            
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
    if message.content.startswith('!refund'):
        userIN = message.content[8:]
        senderID = message.author.name + "#" + message.author.discriminator
        channelID = message.channel.id
        await refundOrder(senderID,userIN,channelID)

client.run(discord_api_key)