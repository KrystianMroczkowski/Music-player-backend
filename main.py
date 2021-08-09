import requests
from tkinter.filedialog import askopenfilename
import os
import shutil
import io
import zipfile
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///localdb.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

filename = "token.txt"
SONG_FOLDER = 'C:/Users/mrocz/PycharmProjects/APITEST/songs'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mp3'}

#TODO
# nazwa z daty temp do zmiany z getmissing songs data
# check if someone is adding same file as other song


class User(db.Model):
    id = Column(Integer, primary_key=True)
    token = Column(String(100))
    hashed_name = Column(String(200))


class Songs(db.Model):
    id = Column(Integer, primary_key=True)
    title = Column(String(100))
    author = Column(String(100))
    category = Column(String(100))
    path = Column(String(300))
    user_hashed_name = Column(String(200))


db.create_all()


def get_user_data():
    user = User.query.first()
    if user:
        user_data = {"token": user.token.strip(), "hashed_name": user.hashed_name}
        return user_data
    return False


def logout_user(data):
    response = requests.post('http://127.0.0.1:5000/logout', data=data).json()
    print(response["message"])
    User.query.delete()
    db.session.commit()


def row_exists():
    user = User.query.all()
    if user:
        return True
    else:
        return False


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def add_song(songs, hashed_name):
    data = {"hashed_name": hashed_name, "songs": songs}
    response = requests.post('http://127.0.0.1:5000/add_song', json=data).json()
    if response["error"] == "1":
        print(f'RESPONSE: {response["message"]}')
        return response["updated_songs_id"]
    else:
        print(response["message"])
        return ""


def upload_files(hashed_name, songs_ids):
    songs = Songs.query.filter(Songs.id.in_(songs_ids)).all()
    file_list = []
    for i in songs:
        try:
            file = open(i.path, "rb")
            file_tuple = ('file', file)
            file_list.append(file_tuple)
        except IOError:
            input(f"Could not open file id: {i.id}!")
    data_to_request = {"songs_ids": songs_ids, "hashed_name": hashed_name}
    upload_response = requests.post('http://127.0.0.1:5000/upload_files', data=data_to_request, files=file_list).json()
    if upload_response["error"] == "1":
        print(upload_response["message"])
    else:
        print(upload_response["message"])


def download_files(data_temp):
    download_response = requests.post('http://127.0.0.1:5000/download_files', data=data_temp)
    z = zipfile.ZipFile(io.BytesIO(download_response.content))
    z.extractall(SONG_FOLDER)


def print_songs():
    user_data = get_user_data()
    user_hashed_name = user_data["hashed_name"]
    songs = Songs.query.filter_by(user_hashed_name=user_hashed_name)
    print("Your songs")
    for i in songs:
        print(f"Title: {i.title}, Author: {i.author}, Category: {i.category}")


def get_missing_songs_data(data_temp):
    '''
    checking if any songs are missing in local db if yes function gets their data from server
    :param data_temp: hashed name, all local songs ids, is_empty = True if list with songs ids is empty
    :return: True if any songs are missing in local db
    '''
    response = requests.post('http://127.0.0.1:5000/missing_songs_data', data=data_temp).json()
    missing_songs = []
    print("MISSING SONGS DATA")
    for item in response:
        print(item)
        missing_song = Songs(
            id=item["song_id"],
            title=item["title"],
            author=item["author"],
            category=item["cat"],
            path=SONG_FOLDER + "/" + item["filename"],
            user_hashed_name=data_temp["hashed_name"], )
        missing_songs.append(missing_song)
    if len(missing_songs) > 0:
        db.session.add_all(missing_songs)
        db.session.commit()
        print(f"Amount of missing songs in local db: {len(missing_songs)}")
        return True
    else:
        return False


def synchronize_songs():
    choice = int(input("Do you want to synchronize your songs? 1. Yes 2. No "))
    if row_exists():
        data = get_user_data()
        response = requests.post('http://127.0.0.1:5000/is_logged_in', data=data).json()
        hashed_name = data["hashed_name"]
        if response["error"] == "1":
            if choice == 1:
                songs_to_sync = Songs.query.filter_by(user_hashed_name="").all()
                # if song was added in offline mode(user hashed_name missing)
                if songs_to_sync:
                    songs = []
                    songs_ids = []
                    for i in songs_to_sync:
                        song = {"id": i.id, "title": i.title, "author": i.author, "category": i.category}
                        songs_ids.append(i.id)
                        songs.append(song)
                    Songs.query.filter(Songs.id.in_(songs_ids)).update({"user_hashed_name": hashed_name})
                    print("Songs hashed names Local updated")
                    updated_songs_id = add_song(songs, hashed_name)
                    if updated_songs_id != "":
                        upload_files(data["hashed_name"], updated_songs_id)
                else:
                    print("Everything up to date(local)")
                print("Checking if any songs are missing")
                all_songs = Songs.query.all()
                all_ids = []
                for i in all_songs:
                    all_ids.append(i.id)
                # if all_ids is empty flask is receiving None instead of empty list
                if len(all_ids) > 0:
                    data_temp = {"hashed_name": data["hashed_name"], "all_ids": all_ids, "is_empty": False}
                else:
                    data_temp = {"hashed_name": data["hashed_name"], "all_ids": all_ids, "is_empty": True}
                if get_missing_songs_data(data_temp):
                    download_files(data_temp)
        else:
            logout_user(data)
    else:
        print("You have been disconnected while synchronizing")
    db.session.commit()


choice = int(input("1. Register 2. Login 3. Logout 4. Logged in users only 5. Add song "))

if choice == 1:
    print("Register")
    email = input("Email address: ")
    username = input("Username: ")
    password = input("Password: ")
    data = {'email': email, "username": username, "password": password}
    response = requests.post('http://127.0.0.1:5000/register', data=data).json()
    if response["error"] == "1":
        print(response["message"])
    else:
        print(response["message"])

if choice == 2:
    if row_exists():
        data = get_user_data()
        response = requests.post('http://127.0.0.1:5000/login_t', data=data).json()
        if response["error"] != "1":
            User.query.delete()
            print(response["message"])
        else:
            print(response["message"])
            synchronize_songs()
            print_songs()
    elif not row_exists():
        email = input("Email: ")
        password = input("Password: ")
        data = {'email': email, 'password': password}
        response = requests.post('http://127.0.0.1:5000/login', data=data).json()
        if response["error"] != "1":
            print(response["message"])
        else:
            token = response["token"]
            user_hashed_name = response["hashed_name"]
            user = User(
                token=token,
                hashed_name=user_hashed_name
            )
            db.session.add(user)
            print(response["message"])
            synchronize_songs()
            print_songs()
    db.session.commit()

if choice == 3:
    if row_exists():
        data = get_user_data()
        logout_user(data)

if choice == 4:
    if row_exists():
        data = get_user_data()
        response = requests.post('http://127.0.0.1:5000/logged', data=data).json()
        if response["error"] != "1":
            logout_user(data)
        else:
            print(response["data"])
    else:
        print("You are not logged in")

if choice == 5:
    title = input("Title: ")
    author = input("Author: ")
    category = input("Category: ")
    filepath = askopenfilename()
    with open(filepath, 'rb') as f:
        filename = os.path.basename(filepath)
        filenames = os.listdir(SONG_FOLDER)
        if filename in filenames:
            print("File with that name already exists")
        else:
            if allowed_file(filepath):
                is_logged_in = True
                if row_exists():
                    data = get_user_data()
                    response = requests.post('http://127.0.0.1:5000/is_logged_in', data=data).json()
                    if response["error"] != "1":
                        logout_user(data)
                        is_logged_in = False
                else:
                    is_logged_in = False
                if is_logged_in:
                    song = Songs(
                        title=title,
                        author=author,
                        category=category,
                        path=SONG_FOLDER + '/' + filename,
                        user_hashed_name=data["hashed_name"]
                    )
                    db.session.add(song)
                    db.session.flush()
                    print("Song added LOCAL")
                    shutil.copy2(filepath, SONG_FOLDER)
                    song_to_add = {"id": song.id, "title": title, "author": author, "category": category}
                    song = [song_to_add]
                    updated_songs_id = add_song(song, data["hashed_name"])
                    print(updated_songs_id)
                    if updated_songs_id != "":
                        if len(updated_songs_id) == 1:
                            upload_files(data["hashed_name"], updated_songs_id)
                else:
                    song = Songs(
                        title=title,
                        author=author,
                        category=category,
                        path=SONG_FOLDER + '/' + filename,
                        user_hashed_name=""
                    )
                    db.session.add(song)
                    print("Song added LOCAL")
                    shutil.copy2(filepath, SONG_FOLDER)
            else:
                print("Not allowed file extension")
    db.session.commit()