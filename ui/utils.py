import hashlib
import json
import re
import smtplib
import ssl
import urllib

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from models.models import Job, ApiKeys
from ui import app, db


def search(find_crc):
    """ Queries ARMui db for the movie/show matching the query"""
    new_crc = re.sub('[^a-zA-Z0-9-]', '', find_crc)
    # print("search - q=" + str(new_crc))
    posts = db.session.query(Job).filter_by(crc_id=new_crc)
    # posts = Job.query.get(crc_id=new_crc)
    # print("search - posts=" + str(posts))
    r = {}
    i = 0
    for p in posts:
        # print("job obj = " + str(p.get_d()))
        x = p.get_d().items()
        r[i] = {}
        for key, value in iter(x):
            if key != 'user_id' and key != "job_id":
                r[i][str(key)] = str(value)
                # print(str(key) + "= " + str(value))
        i += 1
    success = False if i < 1 else True
    return {'success': success, 'mode': 'search', 'results': r}


def post(api_key, crc, title, year, video_type, imdb, tmdb, omdb, hasnicetitle, disctype, label):
    """
    Adds a new entry to the database if data passes validation
    :param api_key: the users api key - Do not let user add data without this!
    :param crc: the crc64 of dvd
    :param title: title of dvd
    :param year:  year of release of dvd
    :param video_type: the video type (movie or series)
    :param imdb: the imdb id for dvd
    :param tmdb: the tmdb id for dvd
    :param omdb: the omdb id for dvd
    :param hasnicetitle: did it have a nice title when it left the users ARM ?
    :param disctype: not needed!
    :param label: the original label for the dvd
    :return:
    """
    if api_key is None or api_key == "":
        return {'success': False, 'mode': 'post', "Error": "Not authorised1"}

    valid = db.session.query(ApiKeys).filter_by(key=api_key).first()
    if not bool(valid):
        return {'success': False, 'mode': 'post', "Error": "Not Authorised"}

    # Find any crc matching what the user gave us
    posts = db.session.query(Job).filter_by(crc_id=crc).first()
    if bool(posts):
        return {'success': False, 'mode': 'post', "Error": "DVD with that CRC64 exists"}

    # Make sure we have enough to add to the db
    if crc is None or crc == "" or title is None or year is None:
        return {'success': False, 'mode': 'post', "Error": "Not enough information"}

    # Reserve this for future use of validating users post data - ie make sure submitted isn't junk
    # - Current idea is calling imdb or tmdb to validate that id matches with the title/year the user is trying to add
    if not imdb and not tmdb:
        return {'success': False, 'mode': 'post', "Error": "At least 1 external id is required"}

    results = call_omdb_api("", "", imdb,"short")
    print(f"r = {results}")
    if results['Title'].lower() != title.strip().lower() or results['Year'] != year:
        return {'success': False, 'mode': 'post', "Error": "information provided doesnt match imdb"}

    job = Job(crc, title, year)
    job.user_id = api_key
    job.video_type = video_type

    job.imdb_id = imdb
    job.tmdb_id = tmdb
    job.omdb_id = omdb

    job.hasnicetitle = bool(hasnicetitle)
    job.disctype = disctype
    job.label = label
    job.validated = False
    x = job.get_d()
    # print(f" x = {x}")
    db.session.add(job)
    try:
        db.session.commit()
        success = True
    except Exception as e:
        success = False
        print(e)
        db.session.rollback()
    return {'success': success, 'mode': 'post', 'results': x}


def request_key(email):
    success = False
    x = hashlib.sha224(email.encode('utf-8')).hexdigest()  # This is not the ways its done on live, but for demo
    # print(x)
    api_key = ApiKeys(x)
    db.session.add(api_key)
    try:
        db.session.commit()
        print("writing to db worked")
        success = True
        send_api_key(email, x)
    except Exception as e:
        print("writing failed - " + str(e))
        db.session.rollback()
    return {'success': success, 'mode': 'Request key'}


def fetch_url(url):
    """Naive URL fetch."""
    fp = urllib.request.urlopen(url)
    s = fp.read().decode("utf8")
    return s


def get_burner_email_domains():
    """Using well maintained list of burner domains.
    This will drop Mailinator etc and all.
    """
    url = "https://raw.githubusercontent.com/wesbos/burner-email-providers/master/emails.txt"
    x = fetch_url(url)
    return x.split('\n')


def send_api_key(email, api_key):
    # Your app password - you need to create one in your gmail
    sender_email = "your.email@gmail.com"
    receiver_email = email
    # Your app password - you need to create one in your gmail
    password = "app_password_key"

    message = MIMEMultipart("alternative")
    message["Subject"] = "Automatic ripping machine - api key"
    message["From"] = sender_email
    message["To"] = receiver_email

    # Create the plain-text and HTML version of your message
    text = """\
    Hi,
    Here is your api key
    """ + api_key
    html = """\
    <html>
    <body>
        <p>Hi,<br>
        Here is your api key <br>
        """ + api_key + """
        </p>
    </body>
    </html>
    """

    # Turn these into plain/html MIMEText objects
    part1 = MIMEText(text, "plain")
    part2 = MIMEText(html, "html")

    # Add HTML/plain-text parts to MIMEMultipart message
    # The email client will try to render the last part first
    message.attach(part1)
    message.attach(part2)

    # Create secure connection with server and send email
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(sender_email, password)
        server.sendmail(
            sender_email, receiver_email, message.as_string()
        )
    print("finished sending mail")


def get_latest():
    c=db.session.query(Job).order_by(Job.job_id.desc()).limit(5)
    i=1
    x={}
    for p in c:
        x[i]=p.get_d()
        i+=1
        # print(p.get_d())
    return x


def call_omdb_api(title=None, year=None, imdbID=None, plot="short"):
    """ Queries OMDbapi.org for title/year confirmation
        This should stop any entries being added that dont match their imdb
    """
    omdb_api_key = ""

    if not omdb_api_key:
        print("no api key for omdb")
    if imdbID:
        strurl = "http://www.omdbapi.com/?i={1}&plot={2}&r=json&apikey={0}".format(omdb_api_key, imdbID, plot)
    elif title:
        # try:
        title = urllib.parse.quote(title)
        year = urllib.parse.quote(year)
        strurl = "http://www.omdbapi.com/?s={1}&y={2}&plot={3}&r=json&apikey={0}".format(omdb_api_key,
                                                                                         title, year, plot)
    else:
        print("no params")
        return None


    print("omdb - " + str(strurl))
    try:
        title_info_json = urllib.request.urlopen(strurl).read()
        title_info = json.loads(title_info_json.decode())
        print("omdb - " + str(title_info))
    except urllib.error.HTTPError as e:
        print(f"omdb call failed with error - {e}")
        return {'Title': "",'Year':""}
    print("omdb - call was successful")
    return title_info
