# -*- coding: utf-8 -*-

from collections import OrderedDict
from flask import Flask, abort, make_response, render_template, url_for, request, session, redirect
from io import BytesIO
import openslide
from flask_sqlalchemy import SQLAlchemy
from openslide import OpenSlide, OpenSlideError
from openslide.deepzoom import DeepZoomGenerator
import os
from optparse import OptionParser
from threading import Lock
from flask_cors import CORS
from pathlib import Path
from sqlalchemy import text


#SLIDE_DIR = 'E:/image_dir2/ISO_202010/2020'
SLIDE_DIR = '//192.168.0.198/c/iso/2020'
#SLIDE_DIR = "//JHKANG-DEV/image_dir2/ISO_202010/2020"
#SLIDE_DIR = '/home/ubuntu/images'
#SLIDE_DIR = os.path.join('str(Path.home())', 'images') 

SLIDE_CACHE_SIZE = 10
DEEPZOOM_FORMAT = 'jpeg'
DEEPZOOM_TILE_SIZE = 254
DEEPZOOM_OVERLAP = 1
DEEPZOOM_LIMIT_BOUNDS = True
DEEPZOOM_TILE_QUALITY = 75

app = Flask(__name__)
app.config.from_object(__name__)
app.config.from_envvar('DEEPZOOM_MULTISERVER_SETTINGS', silent=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:ydd1223@127.0.0.1:3306/proficiency_211105'
#app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:1103@15.164.13.70:3306/proficiency'
cors = CORS(app, resources={r"/*": {"origins": "*"}})
app.secret_key = "b5aC869R"

db = SQLAlchemy(app)

class User(db.Model):
	""" Create user table"""
	id = db.Column(db.Integer, primary_key=True)
	username = db.Column(db.String(45), unique=True)
	password = db.Column(db.String(45))

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    qid = db.Column(db.Integer)
    name = db.Column(db.String(50))
    organ = db.Column(db.String(50))
    age = db.Column(db.String(30))
    sex = db.Column(db.String(30))
    clinical_note = db.Column(db.Text())
    url = db.Column(db.String(50))
    type = db.Column(db.String(45))
    show_YN = db.Column(db.String(1))
    slides = db.relationship('Slide', backref='question')


class Slide(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    question_id = db.Column(db.Integer, db.ForeignKey('question.qid'))

class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    q1 = db.Column(db.Text())
    q2 = db.Column(db.Text())
    q3 = db.Column(db.Text())
    q4 = db.Column(db.String(10))
    q5 = db.Column(db.String(10))
    q6 = db.Column(db.String(10))
    q7 = db.Column(db.Text())
    q8 = db.Column(db.Text())
    q9 = db.Column(db.Text())
    q10 = db.Column(db.Text())
    q11 = db.Column(db.Text())
    q12 = db.Column(db.Text())
    q13 = db.Column(db.Text())
    q14 = db.Column(db.Text())
    q15 = db.Column(db.Text())
    q16 = db.Column(db.String(10))
    q17 = db.Column(db.String(10))
    q18 = db.Column(db.Text())
    q19 = db.Column(db.String(10))
    q20 = db.Column(db.Text())
    q21 = db.Column(db.String(10))
    q22 = db.Column(db.String(10))
    q23 = db.Column(db.Text())
    q24 = db.Column(db.Text())
    q25 = db.Column(db.Text())
    q26 = db.Column(db.Text())
    q27 = db.Column(db.Text())
    q28 = db.Column(db.Text())
    q29 = db.Column(db.Text())
    q30 = db.Column(db.Text())
    q31 = db.Column(db.Text())
    q32 = db.Column(db.Text())
    q33 = db.Column(db.Text())
    q34 = db.Column(db.String(10))
    q35 = db.Column(db.Text())
    q36 = db.Column(db.Text())
    q37 = db.Column(db.Text())
    q38 = db.Column(db.Text())
    q39 = db.Column(db.Text())
    q40 = db.Column(db.String(10))
    q41 = db.Column(db.Text())
    q42 = db.Column(db.Text())
    q43 = db.Column(db.Text())
    q44 = db.Column(db.Text())
    q45 = db.Column(db.Text())
    q46 = db.Column(db.Text())
    q47 = db.Column(db.Text())
    q48 = db.Column(db.Text())
    q49 = db.Column(db.Text())
    q50 = db.Column(db.Text())


class PILBytesIO(BytesIO):
    def fileno(self):
        '''Classic PIL doesn't understand io.UnsupportedOperation.'''
        raise AttributeError('Not supported')


class _SlideCache(object):
    def __init__(self, cache_size, dz_opts):
        self.cache_size = cache_size
        self.dz_opts = dz_opts
        self._lock = Lock()
        self._cache = OrderedDict()

    def get(self, path):
        with self._lock:
            if path in self._cache:
                # Move to end of LRU
                slide = self._cache.pop(path)
                self._cache[path] = slide
                return slide

        osr = OpenSlide(path)
        slide = DeepZoomGenerator(osr, **self.dz_opts)
        try:
            mpp_x = osr.properties[openslide.PROPERTY_NAME_MPP_X]
            mpp_y = osr.properties[openslide.PROPERTY_NAME_MPP_Y]
            slide.mpp = (float(mpp_x) + float(mpp_y)) / 2
        except (KeyError, ValueError):
            slide.mpp = 0

        with self._lock:
            if path not in self._cache:
                if len(self._cache) == self.cache_size:
                    self._cache.popitem(last=False)
                self._cache[path] = slide
        return slide


class _Directory(object):
    def __init__(self, basedir, relpath=''):
        self.name = os.path.basename(relpath)
        self.children = []
        for name in sorted(os.listdir(os.path.join(basedir, relpath))):
            cur_relpath = os.path.join(relpath, name)
            cur_path = os.path.join(basedir, cur_relpath)
            if os.path.isdir(cur_path):
                cur_dir = _Directory(basedir, cur_relpath)
                if cur_dir.children:
                    self.children.append(cur_dir)
            elif OpenSlide.detect_format(cur_path):
                self.children.append(_SlideFile(cur_relpath))


class _SlideFile(object):
    def __init__(self, relpath):
        self.name = os.path.basename(relpath)
        self.url_path = relpath


@app.before_first_request
def _setup():
    app.basedir = os.path.abspath(app.config['SLIDE_DIR'])
    config_map = {
        'DEEPZOOM_TILE_SIZE': 'tile_size',
        'DEEPZOOM_OVERLAP': 'overlap',
        'DEEPZOOM_LIMIT_BOUNDS': 'limit_bounds',
    }
    opts = dict((v, app.config[k]) for k, v in config_map.items())
    app.cache = _SlideCache(app.config['SLIDE_CACHE_SIZE'], opts)


def _get_slide(path):
    path = os.path.abspath(os.path.join(app.basedir, path))
    if not path.startswith(app.basedir + os.path.sep):
        # Directory traversal
        abort(404)
    if not os.path.exists(path):
        abort(404)
    try:
        slide = app.cache.get(path)
        slide.filename = os.path.basename(path)
        return slide
    except OpenSlideError:
        abort(404)


@app.route('/')
def index():
    return redirect("/login")

@app.route('/submit',  methods=['POST'])
def submit():
    answer = request.form["question"]
    qid = request.form["qid"]
    print(answer)
    print(qid)
    submit_answer = db.session.query(Answer).filter(Answer.id == session["id"]).update({"q"+qid: answer})
    db.session.commit()
    return "success"

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login Form"""
    session["logged_in"]=False
    session.pop("username", None)
    session.pop("id", None)
    if request.method == 'GET':
        return render_template('login.html')
    else:
        name = request.form['username']
        passw = request.form['password']
        try:
            data = User.query.filter_by(username=name, password=passw).first()
            if data is not None:
                session['id'] = data.id
                session['username'] = data.username
                session["logged_in"] = True
                #로그인 후 첫화면, 첫번째 문제
                return redirect("/89Of7hsvBr5X34Bb")
            else:
                return render_template('login.html', 
                                retry = True
        )
        except:
            return "Login Error(except)"



@app.route('/guide')
def guide():
    return render_template('guide.html')


@app.route('/<path:path>')
def slide(path):
    try:
        if session["logged_in"] == False:
            return redirect(url_for("login"))

    except:
        return redirect(url_for("login"))


    question = Question.query.filter_by(url=str(path)).first()
    questionList = Question.query.filter_by(show_YN="Y").all()


    #answer = Answer.query.filter_by(id=session["id"]).first()
    #print(answer("q3"))
    if question :
        #첫번째 슬라이드
        answer = db.session.query(text('q'+str(question.qid))).from_statement( text('SELECT q'+str(question.qid)+' FROM proficiency_211105.answer where id='+str(session["id"])+'')).first()

        slide_path = question.url+"/"+question.slides[0].name
        print(slide_path)
        print(question.url)
        slide = _get_slide(slide_path)
        slide_url = url_for('dzi', path=slide_path)   
        return render_template('slide-fullpage.html', 
                                slide_url=slide_url, slide_filename=slide.filename, slide_mpp=slide.mpp,
                                slide_url_remove_dzi=slide_url,
                                question_url = question.url,
                                qid = question.qid,
                                #qname = question.name,
                                qname = question.name,
                                organ=question.organ,
                                age=question.age,
                                sex=question.sex,
                                clinical_note=question.clinical_note,
                                slides=question.slides,
                                questionList = questionList,
                                type = question.type,
                                stored_answer = answer[0],
                                username = session["username"]
        )
    else:   
        print("not found")
        return "not found"
        

@app.route('/<path:path>.dzi')
def dzi(path):
    slide = _get_slide(path)
    format = app.config['DEEPZOOM_FORMAT']
    resp = make_response(slide.get_dzi(format))
    resp.mimetype = 'application/xml'
    return resp


@app.route('/<path:path>_files/<int:level>/<int:col>_<int:row>.<format>')
def tile(path, level, col, row, format):
    slide = _get_slide(path)
    format = format.lower()
    if format != 'jpeg' and format != 'png':
        # Not supported by Deep Zoom
        abort(404)
    try:
        tile = slide.get_tile(level, (col, row))
    except ValueError:
        # Invalid level or coordinates
        abort(404)
    buf = PILBytesIO()
    tile.save(buf, format, quality=app.config['DEEPZOOM_TILE_QUALITY'])
    resp = make_response(buf.getvalue())
    resp.mimetype = 'image/%s' % format
    return resp


if __name__ == '__main__':
    parser = OptionParser(usage='Usage: %prog [options] [slide-directory]')
    parser.add_option('-B', '--ignore-bounds', dest='DEEPZOOM_LIMIT_BOUNDS',
                default=True, action='store_false',
                help='display entire scan area')
    parser.add_option('-c', '--config', metavar='FILE', dest='config',
                help='config file')
    parser.add_option('-d', '--debug', dest='DEBUG', action='store_true',
                help='run in debugging mode (insecure)')
    parser.add_option('-e', '--overlap', metavar='PIXELS',
                dest='DEEPZOOM_OVERLAP', type='int',
                help='overlap of adjacent tiles [1]')
    parser.add_option('-f', '--format', metavar='{jpeg|png}',
                dest='DEEPZOOM_FORMAT',
                help='image format for tiles [jpeg]')
    parser.add_option('-l', '--listen', metavar='ADDRESS', dest='host',
                default='127.0.0.1',
                help='address to listen on [127.0.0.1]')
    parser.add_option('-p', '--port', metavar='PORT', dest='port',
                type='int', default=5000,
                help='port to listen on [5000]')
    parser.add_option('-Q', '--quality', metavar='QUALITY',
                dest='DEEPZOOM_TILE_QUALITY', type='int',
                help='JPEG compression quality [75]')
    parser.add_option('-s', '--size', metavar='PIXELS',
                dest='DEEPZOOM_TILE_SIZE', type='int',
                help='tile size [254]')

    (opts, args) = parser.parse_args()
    # Load config file if specified
    if opts.config is not None:
        app.config.from_pyfile(opts.config)
    # Overwrite only those settings specified on the command line
    for k in dir(opts):
        if not k.startswith('_') and getattr(opts, k) is None:
            delattr(opts, k)
    app.config.from_object(opts)
    # Set slide directory
    try:
        app.config['SLIDE_DIR'] = args[0]
    except IndexError:
        pass

    app.run(host=opts.host, port=opts.port, threaded=True)