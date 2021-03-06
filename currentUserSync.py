import valve.source.a2s
import valve.rcon
import time
import sqlite3
import configparser
from datetime import datetime, timedelta, timezone

# read config
config = configparser.ConfigParser()
config.read("config.ini")
file_path_shop_db = config["SHOP"]["Database"]

def syncPlayers(serverid):
    print(f"Syncing current users for server id {serverid}")
    #get server config from db
    shopCon = sqlite3.connect(file_path_shop_db)
    shopCur = shopCon.cursor()
    shopCur.execute("SELECT ServerName, dedicated, rcon_host, rcon_port, rcon_pass, SteamQueryPort, DatabaseLocation FROM servers where Enabled ='True' and ID =?",(serverid, ))
    serverInfo = shopCur.fetchone()
    if serverInfo != None:
        serverName = serverInfo[0]
        dedicated = serverInfo[1]
        rcon_host = serverInfo[2]
        rcon_port = serverInfo[3]
        rcon_pass = serverInfo[4]
        steamQueryPort = serverInfo[5]
        file_path_db = serverInfo[6]
    else:
        print("CurrentUserSync Error: Server info cannot be retrieved from DB")
        exit(1)
    loadDate = (datetime.now()).strftime("%m-%d-%Y-%H-%M-%S")
    success = 0
    #create currentUsers table
    currentUsers_query1 = f"""CREATE TABLE "{serverName}_currentUsers" (
            "conid"	TEXT,
            "player"	TEXT,
            "userid"	TEXT,
            "platformid"	TEXT,
            "steamPlatformId"	TEXT,
            "X" TEXT,
            "Y" TEXT,
            "loadDate"	TEXT
            );"""
    #drop currentUsers table
    currentUsers_query2 = f"""DROP TABLE "{serverName}_currentUsers";
            CREATE TABLE "{serverName}_currentUsers" (
            "conid"	TEXT,
            "player"	TEXT,
            "userid"	TEXT,
            "platformid"	TEXT,
            "steamPlatformId"	TEXT,
            "X" TEXT,
            "Y" TEXT,
            "loadDate"	TEXT
            );"""
    #create historicalUsers table
    historicalUsers_query1 = f"""CREATE TABLE "{serverName}_historicalUsers" (
            "conid"	TEXT,
            "player"	TEXT,
            "userid"	TEXT,
            "platformid"	TEXT,
            "steamPlatformId"	TEXT,
            "X" TEXT,
            "Y" TEXT,
            "loadDate"	TEXT
            );"""
    connection = sqlite3.connect(file_path_shop_db)
    cursor = connection.cursor()
    try:
        cursor.executescript(currentUsers_query1)
        connection.commit()
    except Exception as e:
        if "already exists" in str(e):
            connection = sqlite3.connect(file_path_shop_db)
            cursor = connection.cursor()
            cursor.executescript(currentUsers_query2)
            connection.commit()
            pass

    try:
        connection = sqlite3.connect(file_path_shop_db)
        cursor = connection.cursor()
        cursor.executescript(historicalUsers_query1)
        connection.commit()
    except Exception as e:
        if "already exists" in str(e):
            pass
        else:
            print(f"Something went wrong in creating historical users table: {e}")
            connection.close()
            exit(1)

    #get playerlist from steam
    SERVER_ADDRESS = (rcon_host, int(steamQueryPort))

    with valve.source.a2s.ServerQuerier(SERVER_ADDRESS) as server:
        info = server.info()
        players = server.players()
        server
    userlist = []
    #print("{player_count}/{max_players} {server_name}".format(**info))
    for player in sorted(players["players"],key=lambda p: p["score"], reverse=True):
        userlist.append("{name}".format(**player))


    
    attempts = 0
    while success == 0 and attempts <= 5:
        try:
            with valve.rcon.RCON((rcon_host, int(rcon_port)), rcon_pass) as rcon:
                response = rcon.execute("listplayers")
                rcon.close()
                response_text = response.body.decode('utf-8', 'ignore')
                #print(response_text)
            playerlist = response_text.split('\n')
            success = 1
        except Exception:
            success = 0
            attempts = attempts + 1
            time.sleep(1)
    i = 0    
    for index in range(len(playerlist) - 1):
        try:
            item = playerlist[index].replace(userlist[i],"")
            item = item.split(' | ')
            conid = str(item[0].strip())
            player = item[1].strip()
            userid = str(userlist[i])
            platformid = str(item[3].strip())
            steamPlatformId = str(item[4].strip())
            if conid != "Idx":
                i+=1
            if conid != 'Idx':
                if player != "":
                    #get player x and player y if dedicated server
                    if dedicated == 'True':
                        print("dedicated is true")
                        gameCon = sqlite3.connect(file_path_db)
                        gameCur = gameCon.cursor()
                        gameCur.execute("SELECT a.id, a.user, a.online, c.char_name, c.id, p.x, p.y FROM account as a INNER JOIN characters as c ON a.id = c.playerid INNER JOIN actor_position as p ON c.id = p.id WHERE a.online =1 AND a.user =?", (platformid, ))
                        result = gameCur.fetchone()
                        playerX = result[5]
                        playerY = result[6]
                        gameCur.close()
                        gameCon.close()
                    else:
                        playerX = 0
                        playerY = 0
                    cursor.execute(f"INSERT INTO {serverName}_currentUsers (conid, player, userid, platformid, steamPlatformId, X, Y, loadDate) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (conid, player, userid, platformid, steamPlatformId, int(playerX), int(playerY), loadDate))
                    cursor.execute(f"INSERT INTO {serverName}_historicalUsers (conid, player, userid, platformid, steamPlatformId, X, Y, loadDate) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (conid, player, userid, platformid, steamPlatformId, int(playerX), int(playerY), loadDate))
                    
                    connection.commit()
        except Exception as e:
            if "index out of range" in str(e):
                pass
            else:
                print(f"UserSyncError: {e}")
                pass
    cursor.close()
    connection.close()    
shopCon = sqlite3.connect(file_path_shop_db)
shopCur = shopCon.cursor()
shopCur.execute("Select ID FROM servers WHERE Enabled ='True'")
servers = shopCur.fetchall()
if servers != None:
        for server in servers:
            serverid = server[0]
            try:
                syncPlayers(serverid)
            except Exception as e:
                print(f"Could not sync players for ServerID {serverid}.\nError: {e}")
                pass
    
shopCon.close()