# Module Imports
import sys
import sqlite3
import configparser
import subprocess

config = configparser.ConfigParser()
config.read("config.ini")
file_path_shop_db = config["SHOP"]["Database"]
StartingCash = config["SHOP"]["StartingCash"]
PayCheck = int(config["SHOP"]["PayCheck"])

def updateWallets():
    
    #sync users
    p = subprocess.call(['python.exe', "currentUserSync.py"], stdout=sys.stdout)
    # Connect to SQLite shop DB Platform
    shopCon = sqlite3.connect(file_path_shop_db)
    
    shopCursor = shopCon.cursor()
    #get servernames
    shopCursor.execute("Select ServerName from servers WHERE enabled ='True'")
    serverNames = shopCursor.fetchall()
    if serverNames != None:
        for serverName in serverNames:
            server = serverName[0]
            shopCursor.execute(f"SELECT player, userid, platformid, steamPlatformId FROM {server}_currentUsers")
            users = shopCursor.fetchall()

            print(f"Updating Wallets for {server}")
            for user in users:
                #add user to mariadb account if it doesn't exist
                try:
                    shopCursor.execute("INSERT INTO accounts (conanplayer, conanuserid, conanplatformid, walletBalance, steamPlatformId) VALUES (?,?,?,?,?)", (user[0], user[1], user[2],StartingCash,user[3]))
                    shopCon.commit()
                except Exception as e:

                    if "UNIQUE constraint failed" in str(e):
                        
                        shopCursor.execute("SELECT walletBalance, earnratemultiplier FROM accounts WHERE conanplatformid = ?", (user[2], ))
                        walletDetails = shopCursor.fetchone()
                        walletBalance = walletDetails[0]
                        multiplier = walletDetails[1]
                        newBalance = walletBalance + (PayCheck * multiplier)
                        shopCursor.execute("UPDATE accounts SET walletBalance=?, steamPlatformId=?, conanplayer=? WHERE conanplatformid = ?", (newBalance, user[3], user[0], user[2]))
                        shopCon.commit()
                    else:
                        print(f"failed to insert {e}")
                    pass
    shopCursor.close()
    shopCon.close()


updateWallets()

