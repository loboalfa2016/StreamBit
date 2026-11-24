from app.core.database import Base
from app.models.catalog import Genre, Country, Language, movie_genres, movie_countries
from app.models.user import User
from app.models.movie import Movie
from app.models.provider import Provider
from app.models.source import Source
from app.models.community import Comment, Rating 
from app.models.sync_log import SyncLog 
from app.models.availability_log import MovieAvailabilityLog
from app.models.user_lists import Favorite, UserList, UserListItem