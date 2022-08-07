import os, random, discord, ffmpeg, textwrap, json, googleapiclient.discovery, requests, pytesseract, nltk, re, \
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
from difflib import SequenceMatcher, get_close_matches

log = {}
config = {}
state = {}
imageMetadata = {'datas':[]}
copyPastaData = {'copyPastas':[]}
foodReviewerBlacklistData = {'blacklist':[]}
litigationResponses = {'plaintiff':[], 'defendant':[]}
textResponses = {'responses' : []}

litigationState = {
    'inProgress':False,
    'defendant':0,
    'plaintiff':0,
    'amount':0,
    'lastTime':'',
    'litigationChannel':0,
    'lastMessageFromJack':0,
    'state':'',
    'defendantClose':False,
    'plaintiffClose':False,
    'plaintiffInitialResponse':False,
    'defendantChance':0.0
}
currencyRegex = '\$\s*([.\d,]+)'

configfile = 'config.json'
imageDataFile = 'imageMetaData.json'
copypastaFile = 'copypasta.json'
blacklistFile = 'blacklist.json'
litigationResponseFile = './media/litigation.json'
textResponsesFile = 'textResponses.json'

intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)

async def gimmeBrother(message):
    imagePool = [i for i in imageMetadata['datas'] if i['id'] not in foodReviewerBlacklistData['blacklist']]
    brothers = []
    for image in imagePool:
        foundWords = [w for w in image['words'].split() if len(w) > 2]
        for word in foundWords:
            if 'brother' in word:
                brothers.append(image)
    ran = random.choice(brothers)
    filepath = config['pictureDownloadFolder'] + '/' + ran['id'] + '.png'
    reviewerPic = open(filepath, 'rb')
    file = discord.File(fp=reviewerPic)
    await message.reply(file=file)

async def searchTerm(message):
    query = message.content.replace('!search', '')
    sentence = query.lower().strip()
    imagePool = [i for i in imageMetadata['datas'] if i['id'] not in foodReviewerBlacklistData['blacklist']]
    for image in imagePool:
        try:
            await checkAndPostSearch(sentence, image['words'], image, message)
        except Exception as e:
            continue


async def checkAndPostSearch(sentence, foundWords, image, message):
    if sentence in foundWords:
        filepath = config['pictureDownloadFolder'] + '/' + image['id'] + '.png'
        reviewerPic = open(filepath, 'rb')
        file = discord.File(fp=reviewerPic)
        await message.reply(file=file)
        await asyncio.sleep(0.1)


async def litigationEnd(message):
    channel = await client.fetch_channel(litigationState['litigationChannel'])
    litigationState['inProgress'] = False
    chance = random.random()
    if litigationState['plaintiffInitialResponse'] == True:
        await channel.send('i have heard the defense and the prosecution and have come to a conclusion')
        await asyncio.sleep(2.0)
        await channel.send('i find the defendant <@' + str(litigationState['defendant']) + '>...')
        await asyncio.sleep(5.0)
        if chance <= litigationState['defendantChance']:
            await channel.send('NOT GUILTY')
            await asyncio.sleep(2.0)
            await channel.send('i order the plaintiff <@' + str(litigationState['plaintiff']) + '> to pay user <@' + str(litigationState['defendant']) + '>\'s legal fees, totaling $' + str(litigationState['amount']) + '!')
        else:
            await channel.send('GUILTY')
            await asyncio.sleep(2.0)
            await channel.send('i order the defendant <@' + str(litigationState['defendant']) + '> to pay user <@' + str(litigationState['plaintiff']) + '> $' + str(litigationState['amount']) + '!')
    else:
        await channel.send('the plaintiff has not provided any evidence. CASE DISMISSED!')

async def startClosingStatements(message):
    await asyncio.sleep(3.0)
    replyMessage = await message.channel.send('before i present my conclusion, i would like to hear closing statements from <@' + str(litigationState['plaintiff']) + '> and <@' + str(litigationState['defendant']) + '>')
    litigationState['lastMessageFromJack'] = replyMessage.id
    litigationState['lastTime'] = datetime.now().timestamp()
    litigationState['state'] = 'closingStatement'

async def defendantRespond(message):
    plaintiff = await client.fetch_user(litigationState['plaintiff'])
    defendant = await client.fetch_user(litigationState['defendant'])
    reply = random.choice(litigationResponses['defendant']).replace("{DEFENDANT}", str(litigationState['defendant'])).replace("{PLAINTIFF}", str(litigationState['plaintiff']))
    litigationState['lastTime'] = datetime.now().timestamp()
    replyMessage = await message.reply(reply)
    litigationState['lastMessageFromJack'] = replyMessage.id
    litigationState['defendantChance'] += 0.25
    await startClosingStatements(message)

async def plaintiffRespond(message):
    plaintiff = await client.fetch_user(litigationState['plaintiff'])
    defendant = await client.fetch_user(litigationState['defendant'])
    reply = random.choice(litigationResponses['plaintiff']).replace("{DEFENDANT}", str(litigationState['defendant'])).replace("{PLAINTIFF}", str(litigationState['plaintiff']))
    litigationState['lastTime'] = datetime.now().timestamp()
    replyMessage = await message.reply(reply)
    litigationState['lastMessageFromJack'] = replyMessage.id
    litigationState['state'] = 'defendantRespond'
    litigationState['plaintiffInitialResponse'] = True

async def litigationResponse(message):
    print(litigationState['state'])
    if litigationState['state'] == 'waitingForAmount':
        if message.author.id == litigationState['plaintiff']:
            amount = re.findall(currencyRegex, message.content)
            if len(amount) != 0:
                print(amount[0])
                litigationState['amount'] = amount[0]
                if litigationState['amount'] != 0:
                    await continueLitigationStart(message)
    if message.reference == None or litigationState['inProgress'] == False:
        return
    referencedMessage = await message.channel.fetch_message(message.reference.message_id)
    if referencedMessage != None and referencedMessage.author == client.user:
        if litigationState['state'] == 'waitingForAmount':
            if message.author.id != litigationState['plaintiff']:
                litigationState['lastTime'] = datetime.now().timestamp()
                await message.reply('order! the plaintiff is stating the damages')
                return
        if litigationState['state'] == 'plaintiffPresent':
            if message.author.id != litigationState['plaintiff']:
                litigationState['lastTime'] = datetime.now().timestamp()
                await message.reply('order in the court! the plaintiff is presenting their case')
                return
            if message.author.id == litigationState['plaintiff']:
                await plaintiffRespond(message)
        elif litigationState['state'] == 'defendantRespond':
            if message.author.id != litigationState['defendant']:
                litigationState['lastTime'] = datetime.now().timestamp()
                await message.reply('order! order! i want to hear from the defense')
                return
            if message.author.id == litigationState['defendant']:
                await defendantRespond(message)
        elif litigationState['state'] == 'closingStatement':
            if message.author.id == litigationState['defendant']:
                litigationState['defendantClose'] = True
                litigationState['defendantChance'] += 0.1
            if message.author.id == litigationState['plaintiff']:
                litigationState['plaintiffClose'] = True
            if litigationState['defendantClose'] == False:
                await message.reply('and the defense?')
            if litigationState['plaintiffClose'] == False:
                await message.reply('and the plaintiff?')
            if litigationState['plaintiffClose'] == True and litigationState['defendantClose'] == True:
                await litigationEnd(message)

async def continueLitigationStart(message):
    plaintiff = await client.fetch_user(litigationState['plaintiff'])
    await message.channel.send('hear ye, hear ye!')
    await asyncio.sleep(1.0)
    await message.channel.send('court is now in session!')
    await asyncio.sleep(3.0)
    file = open(config['judgeImg'], 'rb')
    discordFile = discord.File(fp=file)
    await message.channel.send(file=discordFile)
    await asyncio.sleep(3.0)
    await message.channel.send('plaintiff <@' + str(litigationState['plaintiff']) + '> is getting litigious against defendant <@' + str(litigationState['defendant']) + '> for $' + litigationState['amount'] + '!')
    await asyncio.sleep(5.0)
    caseMessage = await message.channel.send('user <@' + str(litigationState['plaintiff']) + '>, present your case (reply to this message)')
    litigationState['lastMessageFromJack'] = caseMessage.id
    litigationState['lastTime'] = datetime.now().timestamp()
    litigationState['state'] = 'plaintiffPresent'

async def startLitigation(message):
    if len(message.mentions) == 0:
        await message.channel.send('can\'t litigate, no targets!!!')
        return
    litigationState['lastTime'] = datetime.now().timestamp()
    litigationState['inProgress'] = True
    litigationState['defendant'] = message.mentions[0].id
    litigationState['plaintiff'] = message.author.id
    litigationState['plaintiffClose'] = False
    litigationState['defendantClose'] = False
    litigationState['plaintiffInitialResponse'] = False
    litigationState['litigationChannel'] = message.channel.id
    litigationState['state'] = 'opening'
    litigationState['defendantChance'] = 0.05
    litigationState['amount'] = 0
    amount = re.findall(currencyRegex, message.content)
    if len(amount) != 0:
        print(amount[0])
        litigationState['amount'] = amount[0]
    if litigationState['amount'] != 0:
        await continueLitigationStart(message)
    else:
        litigationState['state'] = 'waitingForAmount'
        replyMessage = await message.reply('state the amount you would like to sue for')
        litigationState['lastMessageFromJack'] = replyMessage.id

async def litigationLoop(message):
    messageContent = message.content.lower()
    litigationPrefix = 'taking'
    litigationSuffix = 'to court'
    if litigationState['inProgress'] == False and litigationPrefix in messageContent and litigationSuffix in messageContent:
        await startLitigation(message)
    elif litigationState['inProgress'] == True and litigationPrefix in messageContent and litigationSuffix in messageContent:
        await message.reply('court is already in session!')
    elif litigationState['inProgress']:
        await litigationResponse(message)

async def postCopypasta(message):
    randomChoice = random.choice(copyPastaData['copyPastas'])
    if message != None:
        await message.reply(randomChoice)
    else:
        channel = client.get_channel(config['publicChannel'])
        await channel.send(randomChoice)

async def addCopyPasta(message):
    pastaString = message.content.replace('!addcopypasta', '')
    copyPastaData['copyPastas'].append(pastaString)
    await message.reply('added, baby!')
    writeCopyPasta()

async def addBlacklist(message):
    referencedMessage = await message.channel.fetch_message(message.reference.message_id)
    if referencedMessage != None and referencedMessage.author == client.user:
        if referencedMessage.attachments == None or len(referencedMessage.attachments) == 0:
            await message.reply('can\'t do that, bucko. no pic!')
        else:
            embedId = referencedMessage.attachments[0].filename.replace('.png','').replace('.jpg','').replace('.jpeg','').replace('downloads_','')
            foodReviewerBlacklistData['blacklist'].append(embedId)
            await message.reply('i got rid of it. i\'m sorry, friend')
    writeBlacklist()

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
    await debugLog("scanning the screenshots, papi")
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
    await debugLog("done scanning my bruddas")

async def foodReviewerPick(message):
    startTime = time.perf_counter()
    try:
        matchlist = []
        before, keyword, stringy = message.content.lower().partition('think')
        stop_words = set(stopwords.words('english'))
        word_tokens = nltk.wordpunct_tokenize(stringy)
        filtered_sentence = set([w for w in word_tokens if not w.lower() in stop_words])
        imagePool = [i for i in imageMetadata['datas'] if i['id'] not in foodReviewerBlacklistData['blacklist']]
        for image in imagePool:
            try:
                matches = 0
                foundWords = [w for w in image['words'].split() if len(w) > 2]
                #For each input word, find best matching word in image
                for word in set(filtered_sentence):
                    bestMatch = 0
                    try:
                        match = get_close_matches(word, set(foundWords), n=5, cutoff=0.6)
                        bestMatch += len(match)
                    except:
                        print(traceback.format_exc())
                    matches += bestMatch
                matchlist.append({'image' : image, 'matches' : matches})
            except:
                print(traceback.format_exc())
        matchlist = [m for m in matchlist if 'words' in m['image']]
        matchlist.sort(key=lambda m: m['matches'])
        if len(matchlist) > 0:
            if matchlist[-1]['matches'] != 0:
                selections = [match for match in matchlist if match['matches'] > math.floor(matchlist[-1]['matches'] * 0.9) or match['matches'] == matchlist[-1]['matches']]
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
                    await debugLog(traceback.format_exc())
            #await message.channel.send(file=file)
            endTime = time.perf_counter()
            queryTime = f'{endTime - startTime:0.4f}'
            await message.reply(file=file)
            await debugLog('text: ' + ' '.join(filtered_sentence) + ' | words: ' +selection['image']['words'] + ' | matches: ' + str(selection['matches']) + ' | amount ' + str(len(selections)) + '\nquery took : ' + queryTime + ' seconds')
    except Exception as e:
        await debugLog(traceback.format_exc())

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
    #await channel.send("baby the big man's up")

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

    role_ids = [role.name.lower() for role in message.author.roles]
    elevatedUser = 'mod mania' in role_ids or 'hot patron' in role_ids or 'twitch subscriber' in role_ids or 'nitro booster' in role_ids
    if elevatedUser == True:
        asyncio.get_event_loop().create_task(litigationLoop(message))

        if 'gimme a brother' in messageContent:
            await gimmeBrother(message)


    for i in range(len(textResponses['responses'])):
        if textResponses['responses'][i][0].lower() in messageContent:
            await message.channel.send(textResponses['responses'][i][1])

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
            asyncio.get_event_loop().create_task(foodReviewerPick(message))

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
        blacklistCommand = "blacklist this"
        if blacklistCommand in messageContent and message.reference != None:
            await addBlacklist(message)
        if '!search' in messageContent and message.channel.id == config['logChannel']:
            await searchTerm(message)
    try:
        quoteText = 'quote'
        canQuote = 'mod mania' in role_ids or 'hot patron' in role_ids or 'twitch subscriber' in role_ids or 'nitro booster' in role_ids
        if quoteText in message.content and message.mentions[0] == client.user and canQuote:
            asyncio.get_event_loop().create_task(sendQuote(message.channel, message.content, message.author))
    except Exception as e:
        await message.channel.send('Unexpected error: ' + e)

@tasks.loop(minutes=1)
async def callOnLoop():
    if datetime.now().hour == 16 and datetime.now().minute == 20:
        await doSongOfTheDay()
    if datetime.now().hour == 3 and datetime.now().minute == 30:
        asyncio.get_event_loop().create_task(scanPictures(True, False))
    if datetime.now().minute == 8 and (datetime.now().hour == 0 or datetime.now().hour % config['copypastaQuoteRate'] == 0):
        await postCopypasta(None)

@tasks.loop(seconds=1)
async def callEverySecond():
    if litigationState['inProgress'] == True and datetime.now().timestamp() > litigationState['lastTime'] + 120:
        await litigationEnd(None)

@callOnLoop.before_loop
async def before():
    await client.wait_until_ready()
    print('Finished waiting')

async def debugLog(message):
    try:
        channel = await client.fetch_channel(config['logChannel'])
        await channel.send(message)
        print(message)
    except:
        print(traceback.format_exc())
        print(message)

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

def writeBlacklist():
    newData = json.dumps(foodReviewerBlacklistData)
    with open(blacklistFile, 'w') as j:
        j.write(newData)

def writeTextResponses():
    newData = json.dumps(textResponses)
    with open(textResponsesFile, 'w') as j:
        j.write(newData)

def loadFile(path, defaultObj):
    print(f'loading {path}')
    try:
        with open(path, 'r') as j:
            return json.load(j)
    except:
        return defaultObj

def loadData():
    global log, config, imageMetadata, foodReviewerBlacklistData, copyPastaData, litigationResponses, textResponses
    log = loadFile('log.json', {'logs': []})
    config = loadFile(configfile, None)
    if config == None:
        raise Exception("NO CONFIG FILE")
    imageMetadata = loadFile(imageDataFile, {'datas': []})
    foodReviewerBlacklistData = loadFile(blacklistFile, {'blacklist': []})
    copyPastaData = loadFile(copypastaFile, {'copyPastas': []})
    litigationResponses = loadFile(litigationResponseFile, {})
    textResponses = loadFile(textResponsesFile, {'responses':[]})

if __name__ == "__main__":
    loadData()

    nltk.download('words')
    nltk.download('brown')
    nltk.download('stopwords')
    callOnLoop.start()
    callEverySecond.start()
    client.run(config['botId'])
