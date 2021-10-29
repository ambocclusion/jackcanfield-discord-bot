import os, random, discord, ffmpeg, textwrap, json, googleapiclient.discovery, requests, textdistance, pytesseract, nltk, re, \
asyncio, math, io, traceback, time

from discord.ext import tasks
from PIL import Image, ImageDraw, ImageFont
from urllib.parse import parse_qs, urlparse
from datetime import datetime, timedelta
from dateutil import parser
from nltk.corpus import brown
from nltk.corpus import stopwords
from wand.image import Image as wandImage
from wand.color import Color

log = {}
config = {}
state = {}
imageMetadata = {'datas':[]}
copyPastaData = {'copyPastas':[]}

configfile = 'config.json'
imageDataFile = 'imageMetaData.json'
copypastaFile = 'copypasta.json'

intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)

async def postCopypasta(message):
    randomChoice = random.choice(copyPastaData['copyPastas'])
    await message.reply(randomChoice)

async def addCopyPasta(message):
    pastaString = message.content.replace('!addcopypasta', '')
    copyPastaData['copyPastas'].append(pastaString)
    await message.reply('added, baby!')
    writeCopyPasta()

async def scanImage(filename):
    print('scanning')
    custom_oem_psm_config = r'--oem 3 --psm 6'
    words = set(nltk.corpus.words.words())
    brownwords = set(brown.words())
    regex = '^.+\d+'
    with wandImage(filename=filename) as image:
        image.crop(width=image.width, height=math.floor(image.height*0.3), gravity='south')
        image.auto_level()
        image.opaque_paint(target=Color('#FFFFFF'), fill=Color('black'), fuzz=image.quantum_range * 0.14, invert=True, channel='rgb')
        image.negate(channel='rgb')
        pil_image = Image.open(io.BytesIO(image.make_blob('png')))
        parsed = pytesseract.image_to_string(pil_image, config=custom_oem_psm_config)
        parsed = re.sub(regex, '', parsed)
        newparsed = ' '.join(w for w in nltk.wordpunct_tokenize(parsed.lower()) if ((w.lower() in words \
                             or w.lower() in brownwords) \
                             and len(w.lower()) > 1))
        print(newparsed)
        return newparsed

async def scanPictures(remote, force):
    channel = client.get_channel(config['pictureScanChannel'])
    latestDate = datetime.now() - timedelta(days=365 * 2)
    if len(imageMetadata['datas']) != 0:
        latest = imageMetadata['datas'][-1]
        latestDate = parser.parse(latest['created_at'])
    if remote == True:
        async for history in channel.history(after=latestDate, oldest_first=True, limit=100):
            try:
                print(history.attachments)
                if len(history.attachments) != 0:
                    for attachment in history.attachments:
                        response = requests.get(attachment.url)
                        if response.status_code == 200:
                            filename = config['pictureDownloadFolder'] + '/' + str(history.id) + '.png'
                            with open(filename, 'w+b') as file:
                                file.write(response.content)
                            data = {
                                'id' : str(history.id),
                                'created_at' : str(history.created_at)
                            }
                            imageMetadata['datas'].append(data)
                            print(history)
                writeMetadata()
            except Exception as e:
                print(e)
            await asyncio.sleep(.1)
    if len(imageMetadata['datas']) == 0:
        raise Exception('No imagemetadata')
    for idx, data in enumerate(imageMetadata['datas']):
        try:
            if force or 'words' not in imageMetadata['datas'][idx]:
                filename = config['pictureDownloadFolder'] + '/' + str(imageMetadata['datas'][idx]['id']) + '.png'
                imageMetadata['datas'][idx]['words'] = await scanImage(filename)
            writeMetadata()
        except Exception as e:
            print(e)
    print('finished scanning')

async def foodReviewerPick(message):
    try:
        matchlist = []
        before, keyword, stringy = message.content.lower().partition('think')
        stop_words = set(stopwords.words('english'))
        word_tokens = nltk.wordpunct_tokenize(stringy)
        filtered_sentence = set([w for w in word_tokens if not w.lower() in stop_words])
        for image in imageMetadata['datas']:
            matches = 0
            #For each input word, find best matching word in image
            for word in set(filtered_sentence):
                bestMatch = 0
                try:
                    foundWords = image['words']
                    foundWord_tokens = nltk.wordpunct_tokenize(foundWords)
                    for imageword in set(foundWord_tokens):
                        if textdistance.jaccard(word, imageword) >= 0.5:
                            bestMatch += 0.5
                        if textdistance.jaccard(word, imageword) >= 0.8:
                            bestMatch += 0.8
                        if textdistance.jaccard(word, imageword) == 1:
                            bestMatch += 1
                except:
                    print(traceback.format_exc())
                matches += bestMatch
            matchlist.append({'image' : image, 'matches' : matches})
        matchlist = [m for m in matchlist if 'words' in m['image']]
        matchlist.sort(key=lambda m: m['matches'])
        if len(matchlist) > 0:
            if matchlist[-1]['matches'] != 0:
                selections = [match for match in matchlist if match['matches'] > math.floor(matchlist[-1]['matches'] * 0.5) or match['matches'] == matchlist[-1]['matches']]
            else:
                selections = [match for match in matchlist if not match['image']['words']]
            retryCounter = 0
            while retryCounter < 4:
                try:
                    selection = random.choice(selections)
                    filepath = config['pictureDownloadFolder'] + '/' + selection['image']['id'] + '.png'
                    reviewerPic = open(filepath, 'rb')
                    file = discord.File(fp=reviewerPic)
                    break
                except:
                    retryCounter += 1
                    print(traceback.format_exc())
            #await message.channel.send(file=file)
            await message.reply(file=file)
            print('text: ' + ' '.join(filtered_sentence) + ' | words: ' +selection['image']['words'] + ' | matches: ' + str(selection['matches']) + ' | amount ' + str(len(selections)))
    except Exception as e:
        print(traceback.format_exc())

def GetAllPlaylistItems():
    url = config['playlistUrl']
    query = parse_qs(urlparse(url).query, keep_blank_values=True)
    playlist_id = query['list'][0]
    print(f'get all playlist items links from {playlist_id}')
    youtube = googleapiclient.discovery.build('youtube', 'v3', developerKey = config['youtubeApiKey'])

    request = youtube.playlistItems().list(
        part = 'snippet',
        playlistId = playlist_id,
        maxResults = 50
    )
    response = request.execute()

    playlist_items = []
    while request is not None:
        response = request.execute()
        playlist_items += response['items']
        request = youtube.playlistItems().list_next(request, response)

    return playlist_items

async def doSongOfTheDay(search = None):
    print('hot dad video of the day time!')
    message_channel = client.get_channel(config['publicChannel'])
    playlist_items = GetAllPlaylistItems()

    if search != None:
        print('search query is ' + search)
        filtered_playlist = [video for video in playlist_items if search in video['snippet']['title'].lower()]
        playlist_items = filtered_playlist

    randomVideo = random.choice(playlist_items)
    await message_channel.send(f'it\'s the hot dad song of the day!!! https://www.youtube.com/watch?v={randomVideo["snippet"]["resourceId"]["videoId"]}')

async def doNewMember(memberName):
    with open(config['welcomeFile'], 'rb') as j:
        welcomeQuotes = json.load(j)
        channel = client.get_channel(config['publicChannel'])
        newQuote = random.choice(welcomeQuotes['quotes'])
        image = Image.open(config['welcomeBg'])
        font = ImageFont.truetype(config['welcomeFont'], size=35)
        draw = ImageDraw.Draw(image)
        textToDraw = '\'' + newQuote.replace('[username]', memberName) + '\''

        stroke_width = 3

        (x, y) = (50, 120)
        quoteToUse = textwrap.fill(textToDraw, width=32)
        quoteToUse = quoteToUse + '\n\n - Jack Canfield'
        message = quoteToUse
        color = 'rgb(255, 255, 255)'
        strokeColor = 'rgb(0,0,0)'

        # strokes
        draw.multiline_text((x - stroke_width, y), message, fill=strokeColor, font=font, align='center')
        draw.multiline_text((x + stroke_width, y), message, fill=strokeColor, font=font, align='center')
        draw.multiline_text((x, y - stroke_width), message, fill=strokeColor, font=font, align='center')
        draw.multiline_text((x, y + stroke_width), message, fill=strokeColor, font=font, align='center')
        draw.multiline_text((x - stroke_width, y + stroke_width), message, fill=strokeColor, font=font, align='center')
        draw.multiline_text((x - stroke_width, y - stroke_width), message, fill=strokeColor, font=font, align='center')
        draw.multiline_text((x + stroke_width, y + stroke_width), message, fill=strokeColor, font=font, align='center')
        draw.multiline_text((x + stroke_width, y - stroke_width), message, fill=strokeColor, font=font, align='center')

        draw.multiline_text((x - (stroke_width / 2), y + (stroke_width / 2)), message, fill=strokeColor, font=font,
                            align='center')
        draw.multiline_text((x - (stroke_width / 2), y - (stroke_width / 2)), message, fill=strokeColor, font=font,
                            align='center')
        draw.multiline_text((x + (stroke_width / 2), y + (stroke_width / 2)), message, fill=strokeColor, font=font,
                            align='center')
        draw.multiline_text((x + (stroke_width / 2), y - (stroke_width / 2)), message, fill=strokeColor, font=font,
                            align='center')

        draw.multiline_text((x, y), message, fill=color, font=font,
                            align='center')  # , stroke_width=3, stroke_fill = (0,0,0))

        image.save(config['outputWelcomeImg'])
        file = open(config['outputWelcomeImg'], 'rb')
        discordFile = discord.File(fp=file)

        await channel.send(file=discordFile)

async def newMember(member):
    await doNewMember(member.name)

@client.event
async def on_member_join(member):
    await newMember(member)                     

@client.event
async def on_ready():
    print("bot online")
    channel = client.get_channel(config['ultimateChannel'])
    await channel.send("baby the big man's up")

async def sendQuote(channel, text, user):
    try:
        image = Image.open(config['quoteBg'])
        font = ImageFont.truetype(config['quoteFont'], size=45)
        draw = ImageDraw.Draw(image)
        textToDraw = text.replace('public', '')

        (x, y) = (475, 150)
        quoteToUse = textwrap.fill(textToDraw.split('quote', 1)[1], width=28)
        message = quoteToUse
        color = 'rgb(255, 255, 255)'

        draw.multiline_text((x, y), message, fill=color, font=font, align='center')

        image.save(config['outputjackquoteimg'])
        file = open(config['outputjackquoteimg'], 'rb')
        discordFile = discord.File(fp=file)

        newLogEntry = {'name': user.name, 'text': text}
        log['logs'].append(newLogEntry)
        writeLog()

        publicText = 'public'
        if publicText in text:
            message_channel = client.get_channel(config['publicChannel'])
            await message_channel.send(file=discordFile)
        else:
            await channel.send(file=discordFile)
    except Exception as e:
        await channel.send('Unexpected error: ' + e)

async def sendMessage(channel):
    videopath = config['videopath']
    videostats = ffmpeg.probe(videopath)['streams'][0]
    frames = videostats['nb_frames']
    frame = random.randint(0, int(frames) - 1)
    time = frame / 30
    os.system(f'ffmpeg -y -ss {time} -i { videopath } -frames:v 1 output/output.png')
    outputFile = open('output/output.png', 'rb')
    discordFile = discord.File(fp=outputFile)
    await channel.send(file=discordFile)

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    messageContent = message.content.lower()
    
    bob = "Odenkirk" 
    if bob.lower() in messageContent:
        await message.channel.send("bob odenkirk died from fucking the cholula fleshlight")

    bargain_mart = "ALDI"
    if bargain_mart.lower() in messageContent:
        await message.channel.send("Anonymously polled shoppers agree: ALDI rocks big time.")

    unsafe_word = "Jack Canfield"
    if unsafe_word.lower() in messageContent:
        await message.channel.send("Who, me?")

    copyPastaPrompt = 'gimme the pasta'
    if copyPastaPrompt.lower() in messageContent:
        await postCopypasta(message)

    lookingFor = 'inspir'
    if lookingFor in messageContent:
        await sendMessage(message.channel)

    amos = 'amos'
    if amos in message.content and message.mentions[0] == client.user:
        amosFile = open('media/amos.gif', 'rb')
        file = discord.File(fp=amosFile)
        await message.channel.send(file=file)

    if 'what does' in messageContent and 'think' in messageContent:
        if 'joe' in messageContent or 'jkm' in messageContent or 'joe is hungry' in\
                messageContent or 'paul' in messageContent or 'freddie' in messageContent or\
                'freddy' in messageContent or 'steve' in messageContent or 'jason' in messageContent or\
                'jack' in messageContent:
            await foodReviewerPick(message)
            return

    testing_role_ids = [role.name.lower() for role in message.author.roles]
    if 'mod mania' in testing_role_ids:
        newMemberLook = '!newmember'
        if newMemberLook in messageContent:
            print('new member test')
            member = message.content.split(' ', 2)
            if len(member) == 1:
                await doNewMember(message.author.name)
            else:
                await doNewMember(member[1])
        songLook = '!songoftheday'
        if songLook in messageContent:
            print('song test')
            search = message.content.split(' ', 2)
            if len(search) == 1:
                print('song of the day no search')
                await doSongOfTheDay()
            else:
                await doSongOfTheDay(search[1])
        scanLook = '!scan'
        if scanLook in messageContent:
            force = False
            if 'force' in messageContent: force = True
            asyncio.get_event_loop().create_task(scanPictures(True, force))
        localScanLook = '!localscan'
        if localScanLook in messageContent:
            force = False
            if 'force' in messageContent: force = True
            asyncio.get_event_loop().create_task(scanPictures(False, force))
        addQuote = '!addcopypasta'
        if addQuote in messageContent:
            await addCopyPasta(message)
    try:
        quoteText = 'quote'
        role_ids = [role.name.lower() for role in message.author.roles]
        canQuote = 'mod mania' in role_ids or 'hot patron' in role_ids or 'twitch subscriber' in role_ids or 'nitro booster' in role_ids
        if quoteText in message.content and message.mentions[0] == client.user and canQuote:
            await sendQuote(message.channel, message.content, message.author)
    except Exception as e:
        await message.channel.send('Unexpected error: ' + e)

@tasks.loop(minutes=1)
async def callOnLoop():
    if datetime.now().hour == 16 and datetime.now().minute == 20:
        await doSongOfTheDay()
    if datetime.now().minute == 59:
        asyncio.get_event_loop().create_task(scanPictures(True, False))

@callOnLoop.before_loop
async def before():
    await client.wait_until_ready()
    print('Finished waiting')

def writeLog():
    newJson = json.dumps(log)
    with open('log.json', 'w') as j:
        j.write(newJson)

def writeMetadata():
    newData = json.dumps(imageMetadata)
    with open(imageDataFile, 'w') as j:
        j.write(newData)

def writeCopyPasta():
    newData = json.dumps(copyPastaData)
    with open(copypastaFile, 'w') as j:
        j.write(newData)

try:
    with open('log.json', 'r') as j:
        log = json.load(j)
except:
    log = {'logs' : []}
try:
    with open(configfile, 'r') as j:
        config = json.load(j)
except:
    raise Exception("NO CONFIG FILE")
try:
    with open(imageDataFile, 'r') as j:
        imageMetadata = json.load(j)
except:
    imageMetadata = {'datas':[]}
try:
    with open(copypastaFile, 'r') as j:
        copyPastaData = json.load(j)
except:
    copyPastaData = {'copyPastas': []}

nltk.download('words')
nltk.download('brown')
nltk.download('stopwords')
callOnLoop.start()
client.run(config['botId'])
