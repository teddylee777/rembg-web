from flask import Flask, render_template, request, flash, redirect, url_for, Response, send_from_directory
from flask.helpers import send_file
from flask_sitemap import Sitemap
from werkzeug.utils import secure_filename

from io import StringIO, BytesIO
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

import datetime
import os
import codecs
import json

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from mpl_finance import candlestick_ohlc

import FinanceDataReader as fdr
import pattern as pt

UPLOAD_FOLDER = './uploads'
ALLOWED_EXTENSIONS = {'ipynb'}

app = Flask(__name__, static_folder='static')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Sitemap & robots.txt 설정
ext = Sitemap(app=app)

@ext.register_generator
def index():
    yield 'index', {}

@ext.register_generator
def convert():
    yield 'convert', {} 

@ext.register_generator
def stock():
    yield 'stock', {} 

@ext.register_generator
def rembg():
    yield 'rembg', {} 

@app.route('/robots.txt')
def static_from_root():
    return send_from_directory(app.static_folder, request.path[1:])

# route 설정
@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html')

@app.route('/rembg', methods=['GET', 'POST'])
def rembg():
    return render_template('rembg.html')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def convert_file(filename_, settings):
    data = os.path.join(app.config['UPLOAD_FOLDER'], filename_)
    print(data)
    try:
        f = codecs.open(data, 'r')
        source = f.read()
    except UnicodeDecodeError:
        f = codecs.open(data, 'r', encoding='utf-8')
        source = f.read()
    except Exception as e:
        raise Exception("파일 변환에 실패 했습니다. 에러 메세지:" + e)

    y = json.loads(source)

    cells = []

    for i, x in enumerate(y['cells']):
        work_flag = True

        if x['cell_type'] == 'code':
            if 'source' in x.keys():
                cells.append('\n```python')
                code = x['source']
                code = [c.replace('\n', '') for c in code]
                cells.extend(code)
                cells.append('```\n')
                work_flag = False

            # code cell 인 경우
            outputs = x['outputs']
            if len(outputs) > 0:
                # 출력만 존재하는 셀
                for output in outputs:
                    if (type(output) == dict) and ('data' in output):
                        outputs_data = output['data']
                        for key, value in outputs_data.items():
                            if 'text/html' == key:
                                v = value
                                v = [v_.replace('\n', '') for v_ in v]
                                # v.insert(0, '<strong>[출력]</strong>')
                                cells.extend(v)
                                cells.append('\n')
                                break
                            elif 'text/plain' == key:
                                v = value
                                v = [v_.replace('\n', '') for v_ in v]
                                v.insert(0, '<pre>')
                                # v.insert(0, '<strong>[출력]</strong>')
                                v.append('</pre>')
                                cells.extend(v)
                                break
                            elif 'image/png' == key:
                                k = 'image/png'
                                plain_image = value
                                plain_image = '<img src="data:image/png;base64,' + plain_image.replace('\n','') + '"/>\n'
                                cells.append(plain_image)
                                break
                    elif ('output_type' in output) and (output['output_type'] == 'stream'):
                        v = output['text']
                        v = [v_.replace('\n', '') for v_ in v]
                        v.insert(0, '<pre>')
                        # v.insert(0, '<strong>[출력]</strong>')
                        v.append('</pre>')
                        cells.extend(v)


            else:
                # 코드만 존재하는 셀
                if work_flag:
                    cells.append('\n```python')
                    code = x['source']
                    code = [c.replace('\n', '') for c in code]
                    cells.extend(code)
                    cells.append('```\n')


        elif x['cell_type'] == 'markdown':
            cells.extend(x['source'])
            cells.append('\n')
    
    css = open(os.path.join(app.config['UPLOAD_FOLDER'], 'notebook_css.txt'), 'r').read()
    final_output = f"""---
{settings}
---

{css}


"""

    final_output += "\n".join(cells)

    output = StringIO()
    output.write(final_output)
    output.seek(0)

    # ByteIO 생성
    mem = BytesIO()
    mem.write(output.getvalue().encode())
    mem.seek(0)

    output.close()

    return mem

@app.route('/convert', methods=['GET', 'POST'])
def convert():
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)
        
        file = request.files['file']
        
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)

            saved_file = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(saved_file)

            # setting 설정 확인
            settings = request.form['settings']

            # 변환
            outfile = convert_file(filename, settings)
            
            # 출력 파일이름 생성
            timestring = datetime.datetime.now().strftime('%Y-%m-%d')
            attach_filename = file.filename.split('.')[0]

            if os.path.isfile(saved_file):
                os.remove(saved_file)

            return send_file(outfile,
                     mimetype='text/markdown',
                     attachment_filename=f'{timestring}-{attach_filename}.md',# 다운받아지는 파일 이름. 
                     as_attachment=True)
    return render_template('convert.html')

@app.route('/stock', methods=['GET', 'POST'])
def stock():
    if request.method == 'GET':
        now_time = datetime.datetime.now()
        current = now_time.strftime('%Y-%m-%d')
        past = now_time - datetime.timedelta(20)
        past = past.strftime('%Y-%m-%d')
        return render_template('stock.html', startdate=past, enddate=current)
    else:
        code = request.form['code']
        startdate = request.form['startdate']
        enddate = request.form['enddate']
        if request.form['action'] == '패턴검색':
            return redirect(url_for('pattern', startdate=startdate, enddate=enddate, code=code))
        elif request.form['action'] == '차트확인':
            return render_template('stock.html', startdate=startdate, enddate=enddate, code=code, chart=True)

@app.route('/plot.png', methods=['GET'])
def plot_png():
    code  = request.args.get('code', None)
    startdate  = request.args.get('startdate', None)
    enddate  = request.args.get('enddate', None)
    print(startdate)
    p = pt.PatternFinder()
    p.set_stock(code)
    result = p.search(startdate, enddate)
    print(result)
    if len(result) > 0:
        fig = p.plot_pattern(list(result.keys())[0])
        output = BytesIO()
        FigureCanvas(fig).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')

@app.route('/plotchart.png', methods=['GET'])
def plot_chart():
    code  = request.args.get('code', None)
    startdate  = request.args.get('startdate', None)
    enddate  = request.args.get('enddate', None)
    
    fig = plt.figure()
    fig.set_facecolor('w')
    gs = gridspec.GridSpec(2, 1, height_ratios=[3, 1])
    axes = []
    axes.append(plt.subplot(gs[0]))
    axes.append(plt.subplot(gs[1], sharex=axes[0]))
    axes[0].get_xaxis().set_visible(False)

    print(code)
    data = fdr.DataReader(code)
    data_ = data.loc[startdate:enddate]
    print(code, startdate, enddate)

    x = np.arange(len(data_.index))
    ohlc = data_[['Open', 'High', 'Low', 'Close']].values
    dohlc = np.hstack((np.reshape(x, (-1, 1)), ohlc))

    # 봉차트
    candlestick_ohlc(axes[0], dohlc, width=0.5, colorup='r', colordown='b')

    # 거래량 차트
    axes[1].bar(x, data_['Volume'], color='grey', width=0.6, align='center')
    axes[1].set_xticks(range(len(x)))
    axes[1].set_xticklabels(list(data_.index.strftime('%Y-%m-%d')), rotation=90)
    axes[1].get_yaxis().set_visible(False)

    plt.tight_layout()

    output = BytesIO()
    FigureCanvas(fig).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')

@app.route('/pattern', methods=['GET', 'POST'])
def pattern():
    if request.method == 'POST':
        code = request.form['code']
        startdate = request.form['startdate']
        enddate = request.form['enddate']
    else:
        code  = request.args.get('code', None)
        startdate  = request.args.get('startdate', None)
        enddate  = request.args.get('enddate', None)
    p = pt.PatternFinder()
    p.set_stock(code)
    result = p.search(startdate, enddate)
    N = 5
    preds = p.stat_prediction(result, period=N)

    if len(preds) > 0:
        avg_ = preds.mean() * 100
        min_ = preds.min() * 100
        max_ = preds.max() * 100
        size_ = len(preds)
        print(avg_, min_, max_, size_)
        return render_template('stock-result.html', code=code, startdate=startdate, enddate=enddate, avg=round(avg_, 2), min=round(min_, 2), max=round(max_, 2), size=size_)
    else:
        return render_template('stock-result.html', code=code, startdate=startdate, enddate=enddate, noresult=1)

if __name__ == '__main__':
    # app.run(debug=True, port=5001)
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)