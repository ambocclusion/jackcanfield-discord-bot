import asyncio
import discord
import ffmpeg
import googleapiclient.discovery
import io
import json
import math
import nltk
import os
import pytesseract
import random
import re
import requests
import textwrap
import time
import traceback
from datetime import datetime, timedelta
from difflib import get_close_matches
from urllib.parse import parse_qs, urlparse

from PIL import Image, ImageDraw, ImageFont
from dateutil import parser
from discord.ext import tasks
from nltk.corpus import brown
from nltk.corpus import stopwords
from wand.color import Color
from wand.image import Image as wandImage

log = {}
config = {}
state = {}
imageMetadata = {'datas': []}
copyPastaData = {'copyPastas': []}
foodReviewerBlacklistData = {'blacklist': []}
litigationResponses = {'plaintiff': [], 'defendant': []}
textResponses = {'responses': []}
giveaway_data = {'messages': [], 'giveaway_message': 0}

litigationState = {
    'inProgress': False,
    'defendant': 0,
    'plaintiff': 0,
    'amount': 0,
    'lastTime': '',
    'litigationChannel': 0,
    'lastMessageFromJack': 0,
    'state': '',
    'defendantClose': False,
    'plaintiffClose': False,
    'plaintiffInitialResponse': False,
    'defendantChance': 0.0
}
currencyRegex = r'[\¢\€\$]\s*([.\d,]+)'

configfile = 'config.json'
imageDataFile = 'imageMetaData.json'
copypastaFile = 'copypasta.json'
blacklistFile = 'blacklist.json'
litigationResponseFile = './media/litigation.json'
textResponsesFile = 'textResponses.json'
giveaway_file = 'giveaway.json'

intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)


async def clear_giveaway(message):
    giveaway_data['giveaway_message'] = 0
    write_giveaway()
    await message.reply('Giveaway cleared!')

async def end_giveaway(message):
    if giveaway_data['giveaway_message'] == 0:
        await message.channel.send('There ain\'t no giveaway happening right now!')
        return

    channel = await client.fetch_channel(config['publicChannel'])
    giveawaymessage = await channel.fetch_message(giveaway_data['giveaway_message'])
    print(giveawaymessage.content)
    reactions = giveawaymessage.reactions
    entries = []

    if len(reactions) == 0:
        await message.reply('Nobody entered!')
        return

    for r in reactions:
        async for u in r.users():
            if u.id not in entries:
                entries.append(u.id)

    await message.reply('There were ' + str(len(reactions)) + ' emojis and ' + str(len(entries)) + ' users entered')

    choice = random.choice(entries)
    message = message.content.split('!endgiveaway', 1)[1].strip().replace('{WINNER}', client.get_user(choice).mention)
    await channel.send(message)


async def start_giveaway(message):
    if giveaway_data['giveaway_message'] != 0:
        await message.channel.send('There\'s already a giveaway happening! End the current one.')
        return

    item = message.content.split('!startgiveaway', 1)[1].strip()

    if item.isspace() or len(item) == 0:
        await message.channel.send('Send again with a message')
        return

    channel = client.get_channel(config['publicChannel'])
    giveaway_data['item'] = item
    giveaway_data['messages'] = []
    giveawaymessage = await channel.send(item)
    giveaway_data['giveaway_message'] = giveawaymessage.id
    write_giveaway()


async def gimme_brother(message):
    image_pool = [i for i in imageMetadata['datas'] if i['id'] not in foodReviewerBlacklistData['blacklist']]
    brothers = []
    for image in image_pool:
        try:
            if 'brother' in image['words'] and 'my brother' not in image['words'] and 'for brother' not in \
                    image['words']:
                brothers.append(image)
        except Exception as e:
            continue

    if len(brothers) == 0:
        return
    ran = random.choice(brothers)
    filepath = config['pictureDownloadFolder'] + '/' + ran['id'] + '.png'
    reviewer_pic = open(filepath, 'rb')
    file = discord.File(fp=reviewer_pic)
    await message.reply(file=file)


async def search_term(message):
    query = message.content.replace('!search', '')
    sentence = query.lower().strip()
    image_pool = [i for i in imageMetadata['datas'] if i['id'] not in foodReviewerBlacklistData['blacklist']]
    found = []
    for image in image_pool:
        try:
            if sentence in image['words']:
                found.append(image)
        except Exception as e:
            continue
    for image in found:
        try:
            filepath = config['pictureDownloadFolder'] + '/' + image['id'] + '.png'
            reviewer_pic = open(filepath, 'rb')
            file = discord.File(fp=reviewer_pic)
            await message.reply(file=file)
            await asyncio.sleep(0.1)
        except Exception as e:
            continue


async def litigation_end(message):
    channel = await client.fetch_channel(litigationState['litigationChannel'])
    litigationState['inProgress'] = False
    chance = random.random()
    if litigationState['plaintiffInitialResponse']:
        await channel.send('i have heard the defense and the prosecution and have come to a conclusion')
        await asyncio.sleep(2.0)
        await channel.send('i find the defendant <@' + str(litigationState['defendant']) + '>...')
        await asyncio.sleep(5.0)
        if chance <= litigationState['defendantChance']:
            await channel.send('NOT GUILTY')
            await asyncio.sleep(2.0)
            await channel.send(
                'i order the plaintiff <@' + str(litigationState['plaintiff']) + '> to pay user <@' + str(
                    litigationState['defendant']) + '>\'s legal fees, totaling $' + str(
                    litigationState['amount']) + '!')
        else:
            await channel.send('GUILTY')
            await asyncio.sleep(2.0)
            await channel.send(
                'i order the defendant <@' + str(litigationState['defendant']) + '> to pay user <@' + str(
                    litigationState['plaintiff']) + '> $' + str(litigationState['amount']) + '!')
    else:
        await channel.send('the plaintiff has not provided any evidence. CASE DISMISSED!')


async def start_closing_statements(message):
    await asyncio.sleep(3.0)
    reply_message = await message.channel.send(
        'before i present my conclusion, i would like to hear closing statements from <@' + str(
            litigationState['plaintiff']) + '> and <@' + str(litigationState['defendant']) + '>')
    litigationState['lastMessageFromJack'] = reply_message.id
    litigationState['lastTime'] = datetime.now().timestamp()
    litigationState['state'] = 'closingStatement'


async def defendant_respond(message):
    plaintiff = await client.fetch_user(litigationState['plaintiff'])
    defendant = await client.fetch_user(litigationState['defendant'])
    reply = random.choice(litigationResponses['defendant']).replace("{DEFENDANT}",
                                                                    str(litigationState['defendant'])).replace(
        "{PLAINTIFF}", str(litigationState['plaintiff']))
    litigationState['lastTime'] = datetime.now().timestamp()
    reply_message = await message.reply(reply)
    litigationState['lastMessageFromJack'] = reply_message.id
    litigationState['defendantChance'] += 0.25
    await start_closing_statements(message)


async def plaintiff_response(message):
    plaintiff = await client.fetch_user(litigationState['plaintiff'])
    defendant = await client.fetch_user(litigationState['defendant'])
    reply = random.choice(litigationResponses['plaintiff']).replace("{DEFENDANT}",
                                                                    str(litigationState['defendant'])).replace(
        "{PLAINTIFF}", str(litigationState['plaintiff']))
    litigationState['lastTime'] = datetime.now().timestamp()
    reply_message = await message.reply(reply)
    litigationState['lastMessageFromJack'] = reply_message.id
    litigationState['state'] = 'defendantRespond'
    litigationState['plaintiffInitialResponse'] = True


async def litigation_response(message):
    print(litigationState['state'])
    if litigationState['state'] == 'waitingForAmount':
        if message.author.id == litigationState['plaintiff']:
            amount = re.findall(r"'\$\s*([.\d,]+)'", message.content)
            if len(amount) != 0:
                print(amount[0])
                litigationState['amount'] = amount[0]
                if litigationState['amount'] != 0:
                    await continue_litigation_start(message)
    if message.reference is None or litigationState['inProgress'] is False:
        return
    referenced_message = await message.channel.fetch_message(message.reference.message_id)
    if referenced_message is not None and referenced_message.author == client.user:
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
                await plaintiff_response(message)
        elif litigationState['state'] == 'defendantRespond':
            if message.author.id != litigationState['defendant']:
                litigationState['lastTime'] = datetime.now().timestamp()
                await message.reply('order! order! i want to hear from the defense')
                return
            if message.author.id == litigationState['defendant']:
                await defendant_respond(message)
        elif litigationState['state'] == 'closingStatement':
            if message.author.id == litigationState['defendant']:
                litigationState['defendantClose'] = True
                litigationState['defendantChance'] += 0.1
            if message.author.id == litigationState['plaintiff']:
                litigationState['plaintiffClose'] = True
            if not litigationState['defendantClose']:
                await message.reply('and the defense?')
            if not litigationState['plaintiffClose']:
                await message.reply('and the plaintiff?')
            if litigationState['plaintiffClose'] is True and litigationState['defendantClose'] is True:
                await litigation_end(message)


async def continue_litigation_start(message):
    plaintiff = await client.fetch_user(litigationState['plaintiff'])
    await message.channel.send('hear ye, hear ye!')
    await asyncio.sleep(1.0)
    await message.channel.send('court is now in session!')
    await asyncio.sleep(3.0)
    file = open(config['judgeImg'], 'rb')
    discord_file = discord.File(fp=file)
    await message.channel.send(file=discord_file)
    await asyncio.sleep(3.0)
    await message.channel.send(
        'plaintiff <@' + str(litigationState['plaintiff']) + '> is getting litigious against defendant <@' + str(
            litigationState['defendant']) + '> for $' + litigationState['amount'] + '!')
    await asyncio.sleep(5.0)
    case_message = await message.channel.send(
        'user <@' + str(litigationState['plaintiff']) + '>, present your case (reply to this message)')
    litigationState['lastMessageFromJack'] = case_message.id
    litigationState['lastTime'] = datetime.now().timestamp()
    litigationState['state'] = 'plaintiffPresent'


async def start_litigation(message):
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
        await continue_litigation_start(message)
    else:
        litigationState['state'] = 'waitingForAmount'
        reply_message = await message.reply('state the amount you would like to sue for')
        litigationState['lastMessageFromJack'] = reply_message.id


async def litigation_loop(message):
    message_content = message.content.lower()
    litigation_prefix = 'taking'
    litigation_suffix = 'to court'
    if litigationState['inProgress'] is False and litigation_prefix in message_content \
            and litigation_suffix in message_content:
        await start_litigation(message)
    elif litigationState['inProgress'] is True and litigation_prefix in message_content \
            and litigation_suffix in message_content:
        await message.reply('court is already in session!')
    elif litigationState['inProgress']:
        await litigation_response(message)


async def post_copypasta(message):
    random_choice = random.choice(copyPastaData['copyPastas'])
    if message is not None:
        await message.reply(random_choice)
    else:
        channel = client.get_channel(config['publicChannel'])
        await channel.send(random_choice)


async def add_copypasta(message):
    pasta_string = message.content.replace('!addcopypasta', '')
    copyPastaData['copyPastas'].append(pasta_string)
    await message.reply('added, baby!')
    write_copypasta()


async def add_blacklist(message):
    referenced_message = await message.channel.fetch_message(message.reference.message_id)
    if referenced_message is not None and referenced_message.author == client.user:
        if referenced_message.attachments is None or len(referenced_message.attachments) == 0:
            await message.reply('can\'t do that, bucko. no pic!')
        else:
            embed_id = referenced_message.attachments[0].filename.replace('.png', '').replace('.jpg', '').replace(
                '.jpeg',
                '').replace(
                'downloads_', '')
            foodReviewerBlacklistData['blacklist'].append(embed_id)
            await message.reply('i got rid of it. i\'m sorry, friend')
    write_blacklist()


async def scan_image(filename):
    print('scanning')
    custom_oem_psm_config = r'--oem 3 --psm 6'
    words = set(nltk.corpus.words.words())
    brownwords = set(brown.words())
    regex = '^.+\d+'
    with wandImage(filename=filename) as image:
        image.crop(width=image.width, height=math.floor(image.height * 0.3), gravity='south')
        image.auto_level()
        image.opaque_paint(target=Color('#FFFFFF'), fill=Color('black'), fuzz=image.quantum_range * 0.14, invert=True, channel='rgb')
        image.negate(channel='rgb')
        pil_image = Image.open(io.BytesIO(image.make_blob('png')))
        parsed = pytesseract.image_to_string(pil_image, config=custom_oem_psm_config)
        parsed = re.sub(regex, '', parsed)
        newparsed = ' '.join(w for w in nltk.wordpunct_tokenize(parsed.lower()) if ((w.lower() in words or w.lower() in brownwords) and len(w.lower()) > 1))
        print(newparsed)
        return newparsed


async def scan_pictures(remote, force):
    await debug_log("scanning the screenshots, papi")
    channel = client.get_channel(config['pictureScanChannel'])
    latest_date = datetime.now() - timedelta(days=365 * 2)
    startAmount = len(imageMetadata['datas'])
    if len(imageMetadata['datas']) != 0:
        latest = imageMetadata['datas'][-1]
        latest_date = parser.parse(latest['created_at'])
    if remote is True:
        async for history in channel.history(after=latest_date, oldest_first=True, limit=config['pictureScanAmount']):
            try:
                print(history.attachments)
                if len(history.attachments) != 0:
                    for attachment in history.attachments:
                        response = requests.get(attachment.url)
                        if response.status_code == 200:
                            print(str(history.id))
                            filename = config['pictureDownloadFolder'] + '/' + str(history.id) + '.png'
                            with open(filename, 'w+b') as file:
                                file.write(response.content)
                            data = {
                                'id': str(history.id),
                                'created_at': str(history.created_at)
                            }
                            imageMetadata['datas'].append(data)
                            print(history)
                write_metadata()
            except Exception as e:
                await debug_log(str(e))
            await asyncio.sleep(.1)
    if len(imageMetadata['datas']) == 0:
        raise Exception('No image metadata')
    await debug_log("scanning metadata i got the magic touch _wheeze_")
    for idx, data in enumerate(imageMetadata['datas']):
        try:
            if force or 'words' not in imageMetadata['datas'][idx]:
                filename = config['pictureDownloadFolder'] + '/' + str(imageMetadata['datas'][idx]['id']) + '.png'
                imageMetadata['datas'][idx]['words'] = await scan_image(filename)
            write_metadata()
        except Exception as e:
            print(e)
    print('finished scanning')
    await debug_log("done scanning my bruddas")
    await debug_log("scanned " + str(len(imageMetadata['datas']) - startAmount) + " papis")


async def food_reviewer_pick(message):
    start_time = time.perf_counter()
    try:
        matchlist = []
        before, keyword, stringy = message.content.lower().partition('think')
        stop_words = set(stopwords.words('english'))
        word_tokens = nltk.wordpunct_tokenize(stringy)
        filtered_sentence = set([w for w in word_tokens if not w.lower() in stop_words])
        image_pool = [i for i in imageMetadata['datas'] if i['id'] not in foodReviewerBlacklistData['blacklist']]
        for image in image_pool:
            try:
                matches = 0
                found_words = [w for w in image['words'].split() if len(w) > 2]
                # For each input word, find best matching word in image
                for word in set(filtered_sentence):
                    best_match = 0
                    try:
                        match = get_close_matches(word, set(found_words), n=5, cutoff=0.6)
                        best_match += len(match)
                    except:
                        print(traceback.format_exc())
                    matches += best_match
                matchlist.append({'image': image, 'matches': matches})
            except:
                print(traceback.format_exc())
        matchlist = [m for m in matchlist if 'words' in m['image']]
        matchlist.sort(key=lambda m: m['matches'])
        if len(matchlist) > 0:
            if matchlist[-1]['matches'] != 0:
                selections = [match for match in matchlist if
                              match['matches'] > math.floor(matchlist[-1]['matches'] * 0.9) or match['matches'] ==
                              matchlist[-1]['matches']]
            else:
                selections = [match for match in matchlist if not match['image']['words']]
            retry_counter = 0
            while retry_counter < 4:
                try:
                    selection = random.choice(selections)
                    filepath = config['pictureDownloadFolder'] + '/' + selection['image']['id'] + '.png'
                    reviewer_pic = open(filepath, 'rb')
                    file = discord.File(fp=reviewer_pic)
                    break
                except:
                    retry_counter += 1
                    await debug_log(traceback.format_exc())
            # await message.channel.send(file=file)
            end_time = time.perf_counter()
            query_time = f'{end_time - start_time:0.4f}'
            await message.reply(file=file)
            await debug_log('text: ' + ' '.join(filtered_sentence) + ' | words: ' + selection['image'][
                'words'] + ' | matches: ' + str(selection['matches']) + ' | amount ' + str(
                len(selections)) + '\nquery took : ' + query_time + ' seconds')
    except Exception as e:
        print(e)
        await debug_log(traceback.format_exc())


def get_all_playlist_items():
    url = config['playlistUrl']
    query = parse_qs(urlparse(url).query, keep_blank_values=True)
    playlist_id = query[bytes('list')][0]
    print(f'get all playlist items links from {playlist_id}')
    youtube = googleapiclient.discovery.build('youtube', 'v3', developerKey=config['youtubeApiKey'])

    request = youtube.playlistItems().list(
        part='snippet',
        playlistId=playlist_id,
        maxResults=50
    )
    response = request.execute()

    playlist_items = []
    while request is not None:
        response = request.execute()
        playlist_items += response['items']
        request = youtube.playlistItems().list_next(request, response)

    return playlist_items


async def do_song_of_the_day(search=None):
    print('hot dad video of the day time!')
    message_channel = client.get_channel(config['publicChannel'])
    playlist_items = get_all_playlist_items()

    if search is not None:
        print('search query is ' + search)
        filtered_playlist = [video for video in playlist_items if search in video['snippet']['title'].lower()]
        playlist_items = filtered_playlist

    random_video = random.choice(playlist_items)
    url = f'https://www.youtube.com/watch?v={random_video["snippet"]["resourceId"]["videoId"]}'
    await message_channel.send(f'it\'s the hot dad song of the day!!! {url}')


async def do_new_member(member_name):
    with open(config['welcomeFile'], 'rb') as j:
        welcome_quotes = json.load(j)
        channel = client.get_channel(config['publicChannel'])
        new_quote = random.choice(welcome_quotes['quotes'])
        image = Image.open(config['welcomeBg'])
        font = ImageFont.truetype(config['welcomeFont'], size=35)
        draw = ImageDraw.Draw(image)
        text_to_draw = '\'' + new_quote.replace('[username]', member_name) + '\''

        stroke_width = 3

        (x, y) = (50, 120)
        quote_to_use = textwrap.fill(text_to_draw, width=32)
        quote_to_use = quote_to_use + '\n\n - Jack Canfield'
        message = quote_to_use
        color = 'rgb(255, 255, 255)'
        stroke_color = 'rgb(0,0,0)'

        # strokes
        draw.multiline_text((x - stroke_width, y), message, fill=stroke_color, font=font, align='center')
        draw.multiline_text((x + stroke_width, y), message, fill=stroke_color, font=font, align='center')
        draw.multiline_text((x, y - stroke_width), message, fill=stroke_color, font=font, align='center')
        draw.multiline_text((x, y + stroke_width), message, fill=stroke_color, font=font, align='center')
        draw.multiline_text((x - stroke_width, y + stroke_width), message, fill=stroke_color, font=font, align='center')
        draw.multiline_text((x - stroke_width, y - stroke_width), message, fill=stroke_color, font=font, align='center')
        draw.multiline_text((x + stroke_width, y + stroke_width), message, fill=stroke_color, font=font, align='center')
        draw.multiline_text((x + stroke_width, y - stroke_width), message, fill=stroke_color, font=font, align='center')

        draw.multiline_text((x - (stroke_width / 2), y + (stroke_width / 2)), message, fill=stroke_color, font=font,
                            align='center')
        draw.multiline_text((x - (stroke_width / 2), y - (stroke_width / 2)), message, fill=stroke_color, font=font,
                            align='center')
        draw.multiline_text((x + (stroke_width / 2), y + (stroke_width / 2)), message, fill=stroke_color, font=font,
                            align='center')
        draw.multiline_text((x + (stroke_width / 2), y - (stroke_width / 2)), message, fill=stroke_color, font=font,
                            align='center')

        draw.multiline_text((x, y), message, fill=color, font=font,
                            align='center')  # , stroke_width=3, stroke_fill = (0,0,0))

        image.save(config['outputWelcomeImg'])
        file = open(config['outputWelcomeImg'], 'rb')
        discord_file = discord.File(fp=file)

        await channel.send(file=discord_file)


async def new_member(member):
    await do_new_member(member.name)


@client.event
async def on_member_join(member):
    await new_member(member)


@client.event
async def on_ready():
    print("bot online")
    channel = client.get_channel(config['ultimateChannel'])
    # await channel.send("baby the big man's up")


async def send_quote(channel, text, user):
    try:
        image = Image.open(config['quoteBg'])
        font = ImageFont.truetype(config['quoteFont'], size=45)
        draw = ImageDraw.Draw(image)
        text_to_draw = text.replace('public', '')

        (x, y) = (475, 150)
        quote_to_use = textwrap.fill(text_to_draw.split('quote', 1)[1], width=28)
        message = quote_to_use
        color = 'rgb(255, 255, 255)'

        draw.multiline_text((x, y), message, fill=color, font=font, align='center')

        image.save(config['outputjackquoteimg'])
        file = open(config['outputjackquoteimg'], 'rb')
        discord_file = discord.File(fp=file)

        new_log_entry = {'name': user.name, 'text': text}
        log['logs'].append(new_log_entry)
        write_log()

        public_text = 'public'
        if public_text in text:
            message_channel = client.get_channel(config['publicChannel'])
            await message_channel.send(file=discord_file)
        else:
            await channel.send(file=discord_file)
    except Exception as e:
        await channel.send('Unexpected error: ' + str(e))


async def send_message(channel):
    video_path = config['videopath']
    video_stats = ffmpeg.probe(video_path)['streams'][0]
    frames = video_stats['nb_frames']
    frame = random.randint(0, int(frames) - 1)
    time = frame / 30
    os.system(f'ffmpeg -y -ss {time} -i {video_path} -frames:v 1 output/output.png')
    output_file = open('output/output.png', 'rb')
    discord_file = discord.File(fp=output_file)
    await channel.send(file=discord_file)



@client.event
async def on_message(message):
    if message.author == client.user:
        return

    message_content = message.content.lower()

    role_ids = [role.name.lower() for role in message.author.roles]
    elevated_user = 'mod mania' in role_ids or 'hot patron' in role_ids or 'twitch subscriber' in role_ids or \
                    'nitro booster' in role_ids
    if elevated_user is True:
        asyncio.get_event_loop().create_task(litigation_loop(message))

        if 'gimme a brother' in message_content:
            await gimme_brother(message)

    if '!search' in message_content and message.channel.id == config['logChannel']:
        await search_term(message)

    for i in range(len(textResponses['responses'])):
        if textResponses['responses'][i][0].lower() in message_content:
            await message.channel.send(textResponses['responses'][i][1])

    copypasta_prompt = 'gimme the pasta'
    if copypasta_prompt.lower() in message_content:
        await post_copypasta(message)

    looking_for = 'inspir'
    if looking_for in message_content:
        await send_message(message.channel)

    amos = 'amos'
    if amos in message.content and message.mentions[0] == client.user:
        amos_file = open('media/amos.gif', 'rb')
        file = discord.File(fp=amos_file)
        await message.channel.send(file=file)

    if 'what does' in message_content and 'think' in message_content:
        if 'joe' in message_content or 'jkm' in message_content or 'joe is hungry' in \
                message_content or 'paul' in message_content or 'freddie' in message_content or \
                'freddy' in message_content or 'steve' in message_content or 'jason' in message_content or \
                'jack' in message_content:
            asyncio.get_event_loop().create_task(food_reviewer_pick(message))

    testing_role_ids = [role.name.lower() for role in message.author.roles]
    if 'mod mania' in testing_role_ids or 'mediocre magistrates' in testing_role_ids:
        new_member_look = '!newmember'
        if new_member_look in message_content:
            print('new member test')
            member = message.content.split(' ', 2)
            if len(member) == 1:
                await do_new_member(message.author.name)
            else:
                await do_new_member(member[1])
        song_look = '!songoftheday'
        if song_look in message_content:
            print('song test')
            search = message.content.split(' ', 2)
            if len(search) == 1:
                print('song of the day no search')
                await do_song_of_the_day()
            else:
                await do_song_of_the_day(search[1])
        scan_look = '!scan'
        if scan_look in message_content:
            force = False
            if 'force' in message_content:
                force = True
            asyncio.get_event_loop().create_task(scan_pictures(True, force))
        local_scan_look = '!localscan'
        if local_scan_look in message_content:
            force = False
            if 'force' in message_content:
                force = True
            asyncio.get_event_loop().create_task(scan_pictures(False, force))
        add_quote = '!addcopypasta'
        if add_quote in message_content:
            await add_copypasta(message)
        blacklist_command = "blacklist this"
        if blacklist_command in message_content and message.reference is not None:
            await add_blacklist(message)
        if '!endgiveaway' in message_content:
            await end_giveaway(message)
        if '!startgiveaway' in message_content:
            await start_giveaway(message);
        if '!cleargiveaway' in message_content:
            await clear_giveaway(message)
    try:
        quote_text = 'quote'
        can_quote = 'mod mania' in role_ids or 'hot patron' in role_ids or 'twitch subscriber' in role_ids or 'nitro booster' in role_ids
        if quote_text in message.content and message.mentions[0] == client.user and can_quote:
            asyncio.get_event_loop().create_task(send_quote(message.channel, message.content, message.author))
    except Exception as e:
        await message.channel.send('Unexpected error: ' + str(e))


@tasks.loop(minutes=1)
async def call_on_loop():
    hour = datetime.now().hour
    minute = datetime.now().minute
    if hour == 16 and minute == 20:
        await do_song_of_the_day()
    if hour == 3 and minute == 30:
        scan_pictures(True, False)
    if minute == 8 and (hour == 0 or hour % config['copypastaQuoteRate'] == 0):
        await post_copypasta(None)


@tasks.loop(seconds=1)
async def call_every_second():
    if litigationState['inProgress'] is True and datetime.now().timestamp() > litigationState['lastTime'] + 120:
        await litigation_end(None)


@call_on_loop.before_loop
async def before():
    await client.wait_until_ready()
    print('Finished waiting')


async def debug_log(message):
    try:
        channel = await client.fetch_channel(config['logChannel'])
        await channel.send(message)
        print(message)
    except:
        print(traceback.format_exc())
        print(message)


def write_log():
    new_json = json.dumps(log)
    with open('log.json', 'w') as j:
        j.write(new_json)


def write_metadata():
    new_data = json.dumps(imageMetadata)
    with open(imageDataFile, 'w') as j:
        j.write(new_data)


def write_copypasta():
    new_data = json.dumps(copyPastaData)
    with open(copypastaFile, 'w') as j:
        j.write(new_data)


def write_blacklist():
    new_data = json.dumps(foodReviewerBlacklistData)
    with open(blacklistFile, 'w') as j:
        j.write(new_data)


def write_text_responses():
    new_data = json.dumps(textResponses)
    with open(textResponsesFile, 'w') as j:
        j.write(new_data)

def write_giveaway():
    new_data = json.dumps(giveaway_data)
    with open(giveaway_file, 'w') as j:
        j.write(new_data)


def load_file(path, default_obj):
    print(f'loading {path}')
    try:
        with open(path, 'r') as j:
            return json.load(j)
    except:
        return default_obj


def load_data():
    global log, config, imageMetadata, foodReviewerBlacklistData, copyPastaData, litigationResponses, textResponses, giveaway_data
    log = load_file('log.json', {'logs': []})
    config = load_file(configfile, None)
    if config is None:
        raise Exception("NO CONFIG FILE")
    imageMetadata = load_file(imageDataFile, {'datas': []})
    foodReviewerBlacklistData = load_file(blacklistFile, {'blacklist': []})
    copyPastaData = load_file(copypastaFile, {'copyPastas': []})
    litigationResponses = load_file(litigationResponseFile, {})
    textResponses = load_file(textResponsesFile, {'responses': []})
    giveaway_data = load_file(giveaway_file, {'messages': [], 'giveaway_message': 0})


if __name__ == "__main__":
    load_data()

    nltk.download('words')
    nltk.download('brown')
    nltk.download('stopwords')
    call_on_loop.start()
    call_every_second.start()
    client.run(config['botId'])
