import configparser
from time import sleep
import sqlite3
import re
from datetime import datetime, timedelta, timezone
import os
import optparse

#take in arguements
parser = optparse.OptionParser()
parser.add_option('--server', help='Pass the server name to chat log bot')
#parse arguements
(opts, args) = parser.parse_args()

if not opts.server:
	print('--server is required')
	exit(1)

Server = opts.server
config = configparser.ConfigParser()
config.read("config.ini")
file_path_shop_db = config["SHOP"]["Database"]
timezone = int(config["TIME"]["Timezone"])

#Get server information
shopCon = sqlite3.connect(file_path_shop_db)
shopCur = shopCon.cursor()
shopCur.execute("Select LogLocation, DatabaseLocation FROM servers WHERE ID =?", (Server, ))
file_paths = shopCur.fetchone()
if file_paths != None:
    file_path_log = file_paths[0]
    file_path_db = file_paths[1]
else:
    print(f"No game log file found in DB for server ID {Server}")
    exit(1)
# check log filesize (for detect new logfile)
global file_size_log
file_size_log = os.stat(file_path_log).st_size

# read logfile
def read_log(logfile):
    global file_size_log
    logfile.seek(0, 2)
    while True:
        line = logfile.readline()
        if len(line) < 2:
            if file_size_log > os.stat(file_path_log).st_size:
                print(os.stat(file_path_log).st_size)
                exit()
            file_size_log = os.stat(file_path_log).st_size
            sleep(0.1)
            continue
        else:
            yield line
# convert time
def convert_time(time):
    time = datetime.strptime(time, "%Y.%m.%d-%H.%M.%S:%f") + timedelta(hours=timezone)
    time = time.strftime("%Y-%m-%d %H:%M:%S")
    return time

# open logfile
try:
    logfile = open(file_path_log, "r", encoding="utf-8", errors="ignore")
except OSError as err:
    print(f"an error occurred while opening the chat logfile ({err})")
    pass

# read logfile line
for line in read_log(logfile):

    # detect Chatmessages
    if "ChatWindow:" in line:
        log_time = re.findall("\[(.*?)\]", line)
        log_character = re.findall("(?<=Character )(.*)(?= said)", line)
        log_text = re.findall("(?<=said: )(.*)", line)
        
        # convert datetime
        log_time = convert_time(log_time[0])
        
        # check for registration codes
        if "!register " in log_text[0]:
            inputcode = log_text[0]
            inputcode = inputcode.strip("!register ")    
            shopCon = sqlite3.connect(file_path_shop_db)
            shopCur = shopCon.cursor()
            shopCur.execute("SELECT discordID, registrationcode FROM registration_codes WHERE status = 0")
            results = shopCur.fetchall()
            for row in results:
                discordID = row[0]
                code = row[1]

                if code == inputcode:
                    try:
                        # open game db connection
                        connection = sqlite3.connect(file_path_db)
                        cursor = connection.cursor()

                        
                        #find character ID
                        cursor.execute(f"SELECT c.id, c.playerid, c.char_name, a.user, a.online as PlatformID FROM characters c LEFT JOIN account a on c.playerid = a.id WHERE c.char_name =? and a.online =1", (log_character[0], ))
                        result_id = cursor.fetchone()
                        print(f"Character-ID: {result_id[0]}")
                        print(f"Character-Player-ID: {result_id[1]}")
                        print(f"Character-Name: {result_id[2]}")
                        print(f"Platform-ID: {result_id[3]}")
                        
                        platformid = result_id[3]

                        cursor.close()
                        connection.close()
                        print(f"Setting discord ID to {discordID} for {platformid}")
                        shopCur.execute("UPDATE accounts SET discordid = ? WHERE conanplatformid = ?", (discordID, platformid))
                        shopCon.commit()

                        #check if registration successful 
                        shopCur.execute("Select discordid FROM accounts WHERE conanplatformid = ?", (platformid, ))
                        checkResult = shopCur.fetchone()
                        if checkResult == None:
                            print("could not register user. Perhaps not in account list yet")
                        else:
                            #update registration status
                            shopCur.execute("UPDATE registration_codes SET status = 1 WHERE registrationCode = ?", (inputcode, ))
                            shopCon.commit()
                    except Exception as e:
                        print(e)
                        pass
                    shopCon.close()