import datetime

from flask_login import login_user, logout_user, login_required

from app import app, db, login_manager, bcrypt
from flask import render_template, redirect, url_for, request, abort

from app.forms import NightForm, PlaceForm, LoginForm
from app.models import Night, Place, User
from app.util import is_safe_url

login_manager.login_view = 'login'
db.create_all()

# if no user found, create admin from config
if User.nb_users() == 0:
    u = app.config['ADMIN_USER']
    p = app.config['ADMIN_PASSWORD']
    User.create(u, p)


@login_manager.user_loader
def load_user(username):
    return User.query.get(username)


@app.route('/')
@login_required
def homepage():
    nights = Night.query.order_by(Night.day).all()
    nb = len(nights)
    first = nights[0].day
    last = nights[-1].day
    nbmissing = nb - (last - first).days - 1
    return render_template('index.html', nb_nights=nb, first_date=first, last_date=last, nbmissing=nbmissing)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.get(form.username.data)
        if user:
            if bcrypt.check_password_hash(user.password, form.password.data):
                login_user(user, remember=True)
                next = request.args.get('next')
                # is_safe_url should check if the url is safe for redirects.
                # See http://flask.pocoo.org/snippets/62/ for an example.
                if not is_safe_url(next):
                    return abort(400)
                return redirect(next or url_for('homepage'))
    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('homepage'))


@app.route('/places/', methods=['GET'])
@login_required
def show_places():
    placelist = Place.query.all()
    return render_template('places-home.html', places=placelist)


@app.route('/places/new', methods=['GET', 'POST'])
@login_required
def add_place():
    form = PlaceForm()
    
    if form.validate_on_submit():
        place = Place()
        form.populate_obj(place)
        db.session.add(place)
        db.session.commit()
        return redirect(url_for('show_places'))
    
    return render_template('place-form.html', form=form)


@app.route('/places/<int:pid>', methods=['GET', 'POST'])
@login_required
def place(pid):
    place = Place.query.get_or_404(pid)
    form = PlaceForm()

    if form.validate_on_submit():
        form.populate_obj(place)

        db.session.commit()
        return redirect(url_for('show_places'))

    form.name.data = place.name
    form.latitude.data = place.latitude
    form.longitude.data = place.longitude

    return render_template('place-form.html', form=form)


@app.route('/nights/', methods=['GET'])
@login_required
def show_nights():
    date = datetime.date.today()
    datelist = [(date.strftime('%Y%m%d'), date.strftime('%d/%m/%Y'))]
    dt = datetime.timedelta(days=1)
    for _ in range(7):
        date = date - dt
        datelist.append((date.strftime('%Y%m%d'), date.strftime('%d/%m/%Y')))

    return render_template('nights-home.html', dates=datelist)


@app.route('/nights/<string:datestr>', methods=['GET', 'POST'])
@login_required
def night(datestr):
    """
    Create a night, or edit it if it already exists
    """
    try:
        date = datetime.datetime.strptime(datestr, '%Y%m%d').date()
    except Exception as e:
        # TODO redirect to previous page (request.referrer)
        abort(400)

    # Forbid a date in the future
    if date > datetime.date.today():
        # TODO redirect to previous page (request.referrer)
        abort(400)

    night = Night.from_date(date)

    form = NightForm()
    form.day.data = date

    if form.validate_on_submit():
        print('form date : {}'.format(form.day.data))
        # populate night with form data
        is_new_night = night is None

        if is_new_night:
            night = Night()

        form.populate_obj(night)

        night.to_bed = form.to_bed_datetime()
        night.to_rise = form.to_rise_datetime()

        if is_new_night:
            db.session.add(night)
            print('new night', night)
        else:
            print('updated night', night)

        db.session.commit()
        return redirect(url_for('night', datestr=datestr))

    previousd = (date - datetime.timedelta(days=1)).strftime('%Y%m%d')
    nextd = (date + datetime.timedelta(days=1)).strftime('%Y%m%d')

    if night is not None:
        # populate form with night data
        form.to_bed.data = night.to_bed.time()
        form.to_rise.data = night.to_rise.time()
        form.amount.data = night.amount
        form.place.data = night.place
        form.alone.data = night.alone
        form.sleepless.data = night.sleepless

    return render_template('night-form.html', form=form, date=date.strftime('%Y%m%d'), previous=previousd, next=nextd)
