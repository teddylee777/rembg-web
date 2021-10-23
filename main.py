from flask import Flask, render_template, request, flash, redirect, url_for
from flask.helpers import send_file
from werkzeug.utils import secure_filename
import os
import codecs
import json
from io import StringIO, BytesIO
import datetime

UPLOAD_FOLDER = './uploads'
ALLOWED_EXTENSIONS = {'ipynb'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html')

@app.route('/rembg', methods=['GET', 'POST'])
def rembg():
    return render_template('rembg.html')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def convert_file(filename_, settings):
    # if filename_.endswith('.ipynb'):
    #     data = folder + filename_ 
    # else:
    #     data = folder + filename_ + '.ipynb' 
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
                                v.insert(0, '<strong>[출력]</strong>')
                                cells.extend(v)
                                cells.append('\n')
                                break
                            elif 'text/plain' == key:
                                v = value
                                v = [v_.replace('\n', '') for v_ in v]
                                v.insert(0, '<pre>')
                                v.insert(0, '<strong>[출력]</strong>')
                                v.append('</pre>')
                                cells.extend(v)
                                break
                            elif 'image/png' == key:
                                k = 'image/png'
                                plain_image = value
                                plain_image = '<img src="data:image/png;base64,' + plain_image.replace('\n','') + '"/>\n'
                                cells.append(plain_image)
                                break


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

    final_output = f"""---
{settings}
---\n\n"""

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

        # check if the post request has the file part
        if 'file' not in request.files:
            # flash('No file part')
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

if __name__ == '__main__':
    # app.run(debug=True, port=5001)
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)