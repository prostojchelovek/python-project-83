from flask import Flask, redirect, render_template, request, \
    flash, get_flashed_messages, url_for
import os
import psycopg2
import datetime
import validators
from urllib.parse import urlparse, urlunparse
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

app = Flask(__name__)
load_dotenv()
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
DB_URL = os.getenv('DATABASE_URL')
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

FLASH_EXIST = 'Страница уже существует'
FLASH_ADDED = 'Страница успешно добавлена'
FLASH_CHECKED = 'Страница успешно проверена'
FLASH_EXCEPTION = 'Произошла ошибка при проверке'


@app.route('/')
def main():
    msg = get_flashed_messages(with_categories=True)
    return render_template('index.html', messages=msg)


@app.post('/urls')
def urls():
    url = request.form.get('url', '')
    errors = validate_url(url)
    if errors:
        flash(errors[0], 'alert-danger')
        msg = get_flashed_messages(with_categories=True)
        return render_template('index.html', messages=msg), 422
    o = urlparse(url)
    normalized_url = str(urlunparse([o.scheme, o.hostname, '', '', '', '']))
    page_id = get_id(normalized_url)
    if page_id:
        flash(FLASH_EXIST, 'alert-info')
        return redirect(url_for('url_id', id=page_id))
    today = datetime.datetime.now().date()
    page_id = add_to_db(normalized_url, today)
    flash(FLASH_ADDED, 'alert-success')
    return redirect(url_for('url_id', id=page_id))


@app.get('/urls')
def urls_get():
    rows = get_all_urls()
    msg = get_flashed_messages(with_categories=True)
    return render_template('all.html', messages=msg, rows=rows)


@app.get('/urls/<int:id>')
def url_id(id):
    msg = get_flashed_messages(with_categories=True)
    data = get_data(id)
    checks = get_checks(id)
    return render_template('edit_page.html',
                           messages=msg,
                           id=id,
                           name=data[1],
                           created_at=data[2],
                           rows=checks)


@app.post('/urls/<int:id>/checks')
def check_url(id):
    url = get_data(id)[1]
    try:
        r = requests.get(url)
    except Exception:
        flash(FLASH_EXCEPTION, 'alert-danger')
        return redirect(url_for('url_id', id=id), 302)
    if r.status_code != 200:
        flash(FLASH_EXCEPTION, 'alert-danger')
        return redirect(url_for('url_id', id=id), 302)
    tags = find_tags(url)
    add_new_check(id, r.status_code, tags['title'], tags['h1'], tags['desc'])
    flash(FLASH_CHECKED, 'alert-info')
    return redirect(url_for('url_id', id=id), 302)


def validate_url(data):
    errors = []
    if not data:
        errors.append('Поле не должно быть пустым!')
    if len(data) > 255:
        errors.append('URL превышает 255 символов')
    if not validators.url(data):
        errors.append('Некорректный URL')
    return errors


def get_id(data):
    cur.execute("SELECT * FROM urls WHERE name=%s;", (data,))
    if cur.rowcount > 0:
        result = cur.fetchone()[0]
        conn.commit()
        return result
    conn.commit()
    return None


def add_to_db(url, created_at):
    cur.execute("""INSERT INTO urls (name, created_at)
                VALUES (%s, %s);""", (url, created_at))
    conn.commit()
    return get_id(url)


def get_data(id):
    cur.execute('''SELECT * FROM urls WHERE id=%s
                ORDER BY created_at DESC, name ASC;''', (id,))
    result = cur.fetchone()
    conn.commit()
    return result


def add_new_check(id, status, title, h1, desc):
    cur.execute('''INSERT INTO url_checks (url_id,
                        created_at,
                        status_code,
                        title,
                        h1,
                        description)
                VALUES (%s, %s, %s, %s, %s, %s);''',
                (id,
                 datetime.datetime.now().date(),
                 status,
                 title[:255] if title else None,
                 h1[:255] if h1 else None,
                 desc[:255] if desc else None))
    conn.commit()
    return


def get_checks(id):
    cur.execute("""SELECT url_checks.id,
                    status_code,
                    h1,
                    title,
                    description,
                    url_checks.created_at
                FROM url_checks
                INNER JOIN urls
                ON urls.id = url_checks.url_id
                WHERE urls.id = %s
                ORDER BY url_checks.id DESC;""", (id,))
    result = cur.fetchall()
    conn.commit()
    return result


def get_all_urls():
    cur.execute('''
                DROP VIEW IF EXISTS filter;

                CREATE VIEW filter AS
                SELECT url_id, MAX(id) AS max_id FROM url_checks
                GROUP BY url_id;

                SELECT urls.id,
                    name,
                    max_id,
                    status_code,
                    url_checks.created_at
                FROM urls
                LEFT JOIN filter
                ON urls.id = filter.url_id
                LEFT JOIN url_checks
                ON url_checks.id = filter.max_id
                ORDER BY url_checks.created_at DESC NULLS LAST, name;
                    ''')
    result = cur.fetchall()
    conn.commit()
    return result


def find_tags(url):
    r = requests.get(url).text
    soup = BeautifulSoup(r, 'html.parser')
    title = None
    h1 = None
    desc = None
    try:
        title = soup.title.text
    except Exception:
        pass
    try:
        h1 = soup.h1.text
    except Exception:
        pass
    meta = soup.select('meta[name="description"]')
    for attr in meta:
        desc = attr.get('content')
    return {'title': title,
            'h1': h1,
            'desc': desc}
