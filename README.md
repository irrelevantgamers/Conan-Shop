# Conan-Shop
SQLite version of conan shop
Shop keeps track of current players on server and awards them with coin(currency) to spend in the shop. This is given out every 30 minutes by default.
Set the starting cash and how much each player gets on interval in config.ini

Getting Started

Requirements

1.	Python version 3-3.9 (https://www.python.org/downloads/)
2.	Discord and python-valve modules
3.	Discord API key for the bot
4.	Server Information to populate the DB

Python

1.	Install python version 3.9
2.	Add python-valve and discord modules
a.	For windows use an administrative command prompt with the following commands
i.	Python -m pip install discord
ii.	Python -m pip install python-valve

Discord
1.	Go to https://discord.com/developers/applications
2.	
    -Once signed in create a new application
    
    -Name the app
    
    -Click on Bot then Add Bot
    
    -Get your API key (if you haven’t already) by clicking Reset Token on this page
    
    -Copy your token here to the config.ini of the shop bot for the Discord APIKEY setting
    
    -Enable Server Members Intent
    
    -Invite your bot to your discord. Go to OAuth2 > URL Generator and create a URL then access it to invite to discord. (These are general settings I use for bots you can probably get away with less)
    
    -Copy the link into your browser. Then invite the bot to your server 
    
    -Create a shop items channel that the bot will use to show what’s available for purchase. Once you’ve made a channel right click on it and get the ID. We will use this ID for the “shopListChannelId” in the config.ini Make sure you give your bot permissions to the channel. Send, Read, Manage
  
DB Setup

1.	Open the shop.db (you can do this with DB Browser for SQLite if you don’t already have it https://sqlitebrowser.org/)
2.	In the servers table add an entry for each server you want to participate in shop. Database location and LogLocation should be full file path to game.db and ConanSandbox.log respectively. If you do not have a dedicated host make sure you set dedicated to False as we will not be able to read game.db or the conansandbox.log in real time. You can leave the fields blank or put NA.  
3.	Make sure you save changes

Running the bot

1.	Run the bot with start-shop.py

Adding Items to the shop

1.	Open the DB with DB Browser or another tool
2.	Go to shop_items table 
3.	For single items you’ll need to fill out
a.	Name – display name of the item
b.	Price – how much the item costs
c.	Itemid – get this from hovering over the item ingame or browsing a conan item list wiki (Cannot spawn thralls as they don’t have IDs)
d.	Count – how many should be spawned
e.	Enabled – Sets the item as buyable. Useful to keep event items or special things in db but not always buyable
f.	itemType – If this is a single item use “single” here, if it’s a kit use “kit”
g.	kitId – if item type is kit put a number here to reference for kit id (can be anything just don’t overlap them)
h.	description – a description to display on discord store
i.	Category – a category for discord organization
j.	Cooldown – How often a player can buy this item in minutes
4.	For a kit item you will fill out the same above except itemID. You then need to add the items to shop_kits
a.	kitID – the ID for the kit you created above
b.	Name – the single item name to spawn
c.	itemId - get this from hovering over the item ingame or browsing a conan item list wiki (Cannot spawn thralls as they don’t have IDs)
d.	count – how many should be spawned
5.	Kit Example
 
Bot Commands

•	!register – This command is used for players to register their discord id to their conan account. Once a player sends the register command a unique code is generated and sent to the player. The code is then entered into game chat to complete the registration. If you are not running a dedicated server or the bot doesn’t have access to game.db and conansandbox.log in real time this command will not work
 
•	!coin – Checks the players account balance
 
•	!buy – Players use !buy followed by the item ID displayed in the shop channel you created to purchase and item. Example !buy 18
 
•	!gift – Players can gift coin to eachother using discord mentions !gift followed by @discordID#0000 1000 would gift the other player 1000 coin.
 
