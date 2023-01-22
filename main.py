import os
import re
import telebot
from serv import app
import threading
import requests
import numpy as np

# running Flask server for the bot to be always on on Replit
threading.Thread(target=lambda: app.run(host="0.0.0.0")).start()

api_key = os.getenv("BOT_API")
imdb_api_key = os.getenv("IMDB_API")

# persistent session
s = requests.Session()

# bot instance initialization
bot = telebot.TeleBot(f"{api_key}")


# start command, just a simple message
@bot.message_handler(commands=["start"])
def handle_start(message):
    bot.reply_to(
        message,
        "Hello, please use /media command to provide name of the media as its argument. You can also provide release date, media type (Short, TV Series, etc.) for better search. Example: /media Training Day or /media Training Day 2001.",
    )


# after user enters a media name
def handle_media_name(message, media_name):
    bot.reply_to(message, f"Searching for: {media_name}.")
    imdb_data = imdb_title_search(media_name)
    handle_imdb_title_response(message, imdb_data)


# outputs 10 first titles from the API response as a numbered list
def handle_imdb_title_response(message, imdb_data):
    if "errorMessage" in imdb_data:
        bot.send_message(chat_id=message.chat.id, text=imdb_data["errorMessage"])
        return
    if imdb_data:
        titles = imdb_data["results"][:10]
        message_text = "Titles:\n"
        for i, title in enumerate(titles, 1):
            if "description" in title and title["description"]:
                message_text += f"{i}. {title['title']} {title['description']}\n"
            else:
                message_text += f"{i}. {title['title']}\n"
        bot.send_message(chat_id=message.chat.id, text=message_text)
        bot.send_message(
            chat_id=message.chat.id,
            text="Choose a position (e.g. 1) to output its ratings and vote counts.",
        )
        bot.register_next_step_handler(message, convert_message_to_imdb_id, imdb_data)
    else:
        bot.send_message(chat_id=message.chat.id, text="Couldn't find anything!")


"""
ratings from 5 different websites, although they're coming from single API request. 
RT and Metacritic ones are normalized to 0-10 scale, others are on this scale already.
Average rating is counted using only available ratings.
"""


def handle_imdb_rating_response(message, imdb_rating_data):
    ratings = {}
    if imdb_rating_data["imDb"] != "":
        ratings["IMDB"] = float(imdb_rating_data["imDb"])
    else:
        ratings["IMDB"] = "Not available"
    if imdb_rating_data["metacritic"] != "":
        metacritic_normalized = np.interp(
            float(imdb_rating_data["metacritic"]), [0, 100], [0, 10]
        )
        metacritic_normalized_rounded = round(metacritic_normalized, 1)
        ratings["Metacritic"] = metacritic_normalized_rounded
    else:
        ratings["Metacritic"] = "Not available"
    if imdb_rating_data["theMovieDb"] != "":
        ratings["TheMovieDB"] = float(imdb_rating_data["theMovieDb"])
    else:
        ratings["TheMovieDB"] = "Not available"
    if imdb_rating_data["rottenTomatoes"] != "":
        rotten_tomatoes_normalized = np.interp(
            float(imdb_rating_data["rottenTomatoes"]), [0, 100], [0, 10]
        )
        rotten_tomatoes_normalized_rounded = round(rotten_tomatoes_normalized, 1)
        ratings["RottenTomatoes"] = rotten_tomatoes_normalized_rounded
    else:
        ratings["RottenTomatoes"] = "Not available"
    if imdb_rating_data["filmAffinity"] != "":
        ratings["FilmAffinity"] = float(imdb_rating_data["filmAffinity"])
    else:
        ratings["FilmAffinity"] = "Not available"

    if ratings:
        numeric_ratings = [
            rating for rating in ratings.values() if isinstance(rating, (int, float))
        ]
        average_score = sum(numeric_ratings) / len(numeric_ratings)
        average_score_rounded = round(average_score, 3)

        output = "\n".join([f"{name}: {rating}" for name, rating in ratings.items()])
        output += f"\n\nAverage rating (0-10): {average_score_rounded}"
        bot.send_message(chat_id=message.chat.id, text=output)
    else:
        bot.send_message(chat_id=message.chat.id, text="Couldn't find ratings!")


"""
API response doesn't contain a single number of votes, therefore US and nonUS ones are added together.
Handles cases where only one (e.g. nonUS) number is present, and when none are.
"""


def handle_imdb_vote_count_response(message, imdb_vote_count_data):
    if imdb_vote_count_data:
        us_votes = int(
            imdb_vote_count_data.get("usUsers", {}).get("votes", 0)
            if imdb_vote_count_data.get("usUsers") is not None
            else 0
        )
        non_us_votes = int(
            imdb_vote_count_data.get("nonUSUsers", {}).get("votes", 0)
            if imdb_vote_count_data.get("nonUSUsers") is not None
            else 0
        )
        total_votes = us_votes + non_us_votes
        if total_votes:
            output = "IMDb votes: " + str(total_votes)
            bot.send_message(chat_id=message.chat.id, text=output)
        else:
            bot.send_message(
                chat_id=message.chat.id, text="Couldn't find number of votes!"
            )
    else:
        bot.send_message(chat_id=message.chat.id, text="Couldn't find number of votes!")


"""
converts number entered by user to media ID from the API response,
sends messages with ratings and vote count, also IMDB link to the media
"""


def convert_message_to_imdb_id(message, imdb_data):
    try:
        position = int(message.text)
    except ValueError:
        bot.send_message(
            chat_id=message.chat.id,
            text="Invalid input. Please enter a number corresponding to one of positions in the list.",
        )
        bot.register_next_step_handler(message, convert_message_to_imdb_id, imdb_data)
    if position <= len(imdb_data["results"]) and position > 0:
        id = imdb_data["results"][position - 1]["id"]
        imdb_rating_data = imdb_ratings_search(id)
        imdb_vote_count_data = imdb_vote_count_search(id)
        handle_imdb_rating_response(message, imdb_rating_data)
        handle_imdb_vote_count_response(message, imdb_vote_count_data)
        bot.send_message(chat_id=message.chat.id, text=f"https://imdb.com/title/{id}")
    else:
        bot.send_message(
            chat_id=message.chat.id,
            text="Invalid input. Please enter a number corresponding to one of positions in the list.",
        )
        bot.register_next_step_handler(message, convert_message_to_imdb_id, imdb_data)


def imdb_title_search(media_name):
    url = f"https://imdb-api.com/en/API/Search/{imdb_api_key}/{media_name}"
    response = s.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        return None


def imdb_ratings_search(id):
    url = f"https://imdb-api.com/en/API/Ratings/{imdb_api_key}/{id}"
    response = s.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        return None


def imdb_vote_count_search(id):
    url = f"https://imdb-api.com/en/API/UserRatings/{imdb_api_key}/{id}"
    response = s.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        return None


# parses media name from the command argument, shows example if no argument is given
@bot.message_handler(
    commands=["media"], content_types=["text"], regexp=r"^\/media(\s+.*)?"
)
def handle_media(message):
    match = re.search(r"^\/media\s*(.*)", message.text)
    if match:
        media_name = match.group(1)
        if media_name:
            handle_media_name(message, media_name)
        else:
            bot.reply_to(message, "Command Usage: /media <media_name>")


bot.polling()
