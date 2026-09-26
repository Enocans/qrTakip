import base64
import json
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone, timedelta
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import qrcode
from flask import Flask, abort, jsonify, render_template, request, send_file, session
from openpyxl import Workbook
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')
DATA_DIR = Path(os.environ.get('DATA_DIR', str(BASE_DIR / 'data')))
ON_VERCEL = bool(os.environ.get('VERCEL'))
DATABASE_URL = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL')
if ON_VERCEL and (not DATABASE_URL or not os.environ.get('SECRET_KEY')):
    raise RuntimeError('Vercel requires DATABASE_URL and a persistent SECRET_KEY.')
if not ON_VERCEL:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
app = Flask(__name__)
secret = os.environ.get('SECRET_KEY')
if not secret:
    secret_file = DATA_DIR / '.session-secret'
    try:
        with secret_file.open('x') as file:
            file.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    secret = secret_file.read_text()
app.config.update(SECRET_KEY=secret, MAX_CONTENT_LENGTH=16384,
                  PERMANENT_SESSION_LIFETIME=timedelta(days=365),
                  SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                  SESSION_COOKIE_SECURE=ON_VERCEL or os.environ.get('COOKIE_SECURE') == '1',
                  DATABASE_URL=DATABASE_URL,
                  DATABASE=str(DATA_DIR / 'tracker.sqlite3'))
SUBJECTS = [('turkce', 'Türkçe', 'Tü'), ('matematik', 'Matematik', 'Ma'),
            ('fen', 'Fen Bilimleri', 'Fe'), ('inkilap', 'İnkılap Tarihi', 'İn'),
            ('ingilizce', 'İngilizce', 'En'), ('din', 'Din Kültürü', 'Di')]


@contextmanager
def db():
    if app.config.get('DATABASE_URL'):
        from storage import PostgresConnection
        conn = PostgresConnection(app.config['DATABASE_URL'])
    else:
        conn = sqlite3.connect(app.config['DATABASE'], timeout=15)
        conn.row_factory = sqlite3.Row
    try:
        conn.execute('CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, owner TEXT NOT NULL, created TEXT NOT NULL, payload TEXT NOT NULL, notifications TEXT NOT NULL)')
        conn.execute('CREATE INDEX IF NOT EXISTS records_owner ON records(owner)')
        conn.commit()
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def identity():
    if 'owner' not in session:
        session['owner'] = secrets.token_urlsafe(32)
        session['csrf'] = secrets.token_urlsafe(32)
    session.permanent = True
    return session['owner']


def configured():
    return all(os.environ.get(key) for key in ('TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_WHATSAPP_FROM', 'TWILIO_DAILY_CONTENT_SID'))


def phone(value):
    digits = re.sub(r'[\s()+-]', '', str(value))
    if digits.startswith('00'):
        digits = digits[2:]
    if len(digits) == 11 and digits.startswith('0'):
        digits = '90' + digits[1:]
    elif len(digits) == 10 and digits.startswith('5'):
        digits = '90' + digits
    if not re.fullmatch(r'[1-9][0-9]{9,14}', digits):
        raise ValueError('Telefon numaralarını ülke koduyla gir. Örnek: +90 5xx xxx xx xx')
    return '+' + digits


def validate(data):
    def field(key, label):
        value = data.get(key, '')
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > 100:
            raise ValueError(f'{label} alanını doldur (en fazla 100 karakter).')
        return value.strip()
    result = {'kind': 'daily', 'student_name': field('student_name', 'Ad soyad')}
    try:
        study_date = date.fromisoformat(data.get('date', ''))
    except (ValueError, TypeError):
        raise ValueError('Geçerli bir çalışma tarihi seç.')
    if study_date > date.today():
        raise ValueError('Çalışma tarihi gelecekte olamaz.')
    result['date'] = study_date.isoformat()
    result['notes'] = str(data.get('notes', ''))[:500]
    result['father_phone'] = phone(data.get('father_phone', ''))
    result['teacher_phone'] = phone(os.environ.get('TEACHER_PHONE') or data.get('teacher_phone', ''))
    if data.get('consent') is not True:
        raise ValueError('WhatsApp paylaşım onayını işaretle.')
    result['subjects'] = []
    for key, label, _ in SUBJECTS:
        values = []
        for suffix in ('correct', 'wrong', 'blank'):
            raw = data.get(f'{key}_{suffix}', '0')
            if raw == '':
                raw = '0'
            if isinstance(raw, bool) or not re.fullmatch(r'[0-9]{1,4}', str(raw)):
                raise ValueError(f'{label}: soru sayılarını 0–9999 arasında tam sayı olarak gir.')
            values.append(int(raw))
        correct, wrong, blank = values
        result['subjects'].append(dict(key=key, label=label, correct=correct, wrong=wrong,
                                       blank=blank, total=correct+wrong+blank))
    result['correct'] = sum(s['correct'] for s in result['subjects'])
    result['wrong'] = sum(s['wrong'] for s in result['subjects'])
    result['blank'] = sum(s['blank'] for s in result['subjects'])
    result['total_questions'] = result['correct']+result['wrong']+result['blank']
    if result['total_questions'] == 0:
        raise ValueError('En az bir ders için çalıştığın soru sayısını gir.')
    return result


def send_whatsapp(destination, record):
    if not configured():
        return 'not_configured'
    sid = os.environ['TWILIO_ACCOUNT_SID']
    summary = ' / '.join(f"{s['label']}: {s['total']} soru ({s['correct']} D, {s['wrong']} Y, {s['blank']} B)" for s in record['subjects'] if s['total'])
    body = urlencode({'To': 'whatsapp:' + destination,
                      'From': 'whatsapp:' + os.environ['TWILIO_WHATSAPP_FROM'].removeprefix('whatsapp:'),
                      'ContentSid': os.environ['TWILIO_DAILY_CONTENT_SID'],
                      'ContentVariables': json.dumps({'1': record['student_name'], '2': record['date'],
                                                     '3': str(record['total_questions']), '4': summary}, ensure_ascii=False)}).encode()
    auth = base64.b64encode(f"{sid}:{os.environ['TWILIO_AUTH_TOKEN']}".encode()).decode()
    req = Request(f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json', data=body,
                  headers={'Authorization': 'Basic ' + auth, 'Content-Type': 'application/x-www-form-urlencoded'})
    try:
        with urlopen(req, timeout=12) as response:
            payload = json.load(response)
        return 'accepted' if payload.get('sid') else 'unknown'
    except HTTPError:
        return 'failed'
    except (URLError, TimeoutError, OSError, ValueError):
        return 'unknown'


@app.after_request
def headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['X-Frame-Options'] = 'DENY'
    if request.path.startswith('/api/') or request.path in ('/', '/report', '/panel', '/download'):
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.get('/')
@app.get('/report')
@app.get('/panel')
def index():
    identity()
    return render_template('index.html', subjects=SUBJECTS, today=date.today().isoformat(),
                           teacher_locked=bool(os.environ.get('TEACHER_PHONE')))


@app.get('/api/session')
def bootstrap():
    identity()
    return jsonify(csrf=session['csrf'], whatsapp_ready=configured())


@app.get('/api/records')
def records():
    owner = identity()
    with db() as conn:
        rows = conn.execute("SELECT * FROM records WHERE owner=? AND json_extract(payload, '$.kind')='daily' ORDER BY json_extract(payload, '$.date') DESC, created DESC", (owner,)).fetchall()
    return jsonify([dict(id=r['id'], **json.loads(r['payload']), notifications=json.loads(r['notifications'])) for r in rows])


@app.post('/api/records')
def create_record():
    owner = identity()
    if not secrets.compare_digest(request.headers.get('X-CSRF-Token', ''), session['csrf']):
        return jsonify(error='Oturum yenilendi. Sayfayı yenileyip tekrar dene.'), 403
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error='Geçerli form verisi gönder.'), 400
    record_id = data.get('id', '')
    if not isinstance(record_id, str) or not re.fullmatch(r'[a-zA-Z0-9-]{20,64}', record_id):
        return jsonify(error='Kayıt kimliği geçersiz. Sayfayı yenile.'), 400
    with db() as conn:
        existing = conn.execute('SELECT * FROM records WHERE id=?', (record_id,)).fetchone()
        if existing:
            if existing['owner'] != owner:
                abort(409)
            return jsonify(id=record_id, **json.loads(existing['payload']), notifications=json.loads(existing['notifications']))
    try:
        record = validate(data)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    statuses = dict(father='pending', teacher='pending')
    with db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        recent = conn.execute('SELECT COUNT(*) AS count FROM records WHERE owner=? AND created>=?', (owner, datetime.now(timezone.utc).strftime('%Y-%m-%d'))).fetchone()['count']
        if recent >= 20:
            return jsonify(error='Bugün için 20 kayıt sınırına ulaştın.'), 429
        try:
            conn.execute('INSERT INTO records VALUES (?, ?, ?, ?, ?)',
                         (record_id, owner, datetime.now(timezone.utc).isoformat(), json.dumps(record), json.dumps(statuses)))
        except sqlite3.IntegrityError:
            return jsonify(error='Bu kayıt işleniyor. Geçmişinden kontrol et.'), 409
    for recipient in statuses:
        statuses[recipient] = send_whatsapp(record[recipient+'_phone'], record)
        with db() as conn:
            conn.execute('UPDATE records SET notifications=? WHERE id=?', (json.dumps(statuses), record_id))
    return jsonify(id=record_id, **record, notifications=statuses), 201


@app.get('/download')
def download():
    owner = identity()
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Günlük Soru Takibi'
    sheet.append(['Tarih', 'Öğrenci', 'Toplam Soru', 'Doğru', 'Yanlış', 'Boş'])
    with db() as conn:
        rows = conn.execute("SELECT payload FROM records WHERE owner=? AND json_extract(payload, '$.kind')='daily' ORDER BY json_extract(payload, '$.date'), created", (owner,)).fetchall()
    for row in rows:
        record = json.loads(row['payload'])
        sheet.append([record[k] for k in ('date', 'student_name', 'total_questions', 'correct', 'wrong', 'blank')])
        for cell in sheet[sheet.max_row]:
            if isinstance(cell.value, str):
                cell.data_type = 's'
    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name='lgs-gunluk-soru-takibi.xlsx')


@app.get('/qr')
def qr():
    buffer = BytesIO()
    qrcode.make(os.environ.get('PUBLIC_URL') or request.host_url).save(buffer, format='PNG')
    buffer.seek(0)
    return send_file(buffer, mimetype='image/png')


@app.get('/sw.js')
def service_worker():
    response = app.send_static_file('sw.js')
    response.headers['Cache-Control'] = 'no-cache'
    return response


if __name__ == '__main__':
    from waitress import serve
    serve(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), threads=8)
