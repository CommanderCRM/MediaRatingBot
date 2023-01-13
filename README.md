# MediaRatingBot
This bot provides information about media ratings from IMDb, Rotten Tomatoes, Metacritic, TheMovieDB, FilmAffinity. Second thread (serv.py) is a barebone Flask server to keep host alive.
# Commands
`/start` - welcoming message.
`/media` with arguments - name of the media to search for. Searches for everything (movies, TV series, podcasts).
# API
Calls different methods from https://imdb-api.com/ (Search, Rating, UserRatings).
