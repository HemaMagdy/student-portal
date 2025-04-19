from flask import Flask, request, render_template_string
import pandas as pd
import numpy as np
import logging
from io import BytesIO

app = Flask(__name__)

# إعداد نظام التسجيل
logging.basicConfig(filename='student_portal.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def clean_and_prepare_data(file_path):
    """دالة لتنظيف وإعداد البيانات"""
    try:
        # تحميل البيانات
        data = pd.read_excel(file_path)
        
        # تنظيف عمود ID
        arabic_to_english = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
        data['ID'] = data['ID'].astype(str).apply(lambda x: x.translate(arabic_to_english))
        data['ID'] = data['ID'].str.replace(r'[^\d]', '', regex=True)
        data['ID'] = pd.to_numeric(data['ID'], errors='coerce')
        
        # معالجة القيم الفارغة في ID
        max_id = data['ID'].max() + 1
        data['ID'] = data['ID'].fillna(pd.Series([max_id + i for i in range(len(data))]))
        data['ID'] = data['ID'].astype(int)
        
        # تنظيف أرقام الهاتف
        data['Phone Number'] = data['Phone Number'].astype(str).str.replace(r'[^\d]', '', regex=True)
        data['Phone Number'] = data['Phone Number'].str[-11:]  # أخذ آخر 11 رقم
        
        # توحيد كتابة السنوات الدراسية
        year_mapping = {
            'الاولي': 'الأولى',
            'اولي': 'الأولى',
            'الثانية': 'الثانية',
            'الثالثة': 'الثالثة',
            'الرابعة': 'الرابعة',
            'غير ذلك': 'أخرى'
        }
        data['Year'] = data['Year'].replace(year_mapping).fillna('أخرى')
        
        # تنظيف أسماء الجامعات
        data['University'] = data['University'].str.replace('٫', ',', regex=False)
        data['University'] = data['University'].str.replace(r'^\W+', '', regex=True)
        
        # تنظيف أسماء المحافظات
        gov_mapping = {
            'الدقهليه': 'الدقهلية',
            'شرقيه': 'الشرقية',
            'الشرقيه': 'الشرقية',
            'الغربيه': 'الغربية'
        }
        data['From'] = data['From'].replace(gov_mapping)
        
        # تنظيف الأسماء العربية
        data['Name'] = data['Name'].str.replace(r'[^\w\s]', '', regex=True)
        
        # تحديد العمود كمفتاح رئيسي
        data = data.set_index('ID')
        
        logging.info("تم تنظيف البيانات بنجاح")
        return data
    
    except Exception as e:
        logging.error(f"خطأ في تنظيف البيانات: {str(e)}")
        raise

# تحميل وتنظيف البيانات عند بدء التشغيل
try:
    data = clean_and_prepare_data('final_exam_results.xlsx')
except Exception as e:
    logging.critical(f"فشل تحميل البيانات: {str(e)}")
    data = pd.DataFrame()  # إنشاء DataFrame فارغ لتجنب تعطيل التطبيق

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>بوابة الطلاب</title>
    <style>
        body { font-family: 'Arial', sans-serif; background-color: #f5f5f5; padding: 20px; }
        .container { max-width: 800px; margin: auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        h1 { color: #2c3e50; text-align: center; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input[type="text"], select { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }
        button { background-color: #3498db; color: white; border: none; padding: 10px 15px; border-radius: 5px; cursor: pointer; }
        button:hover { background-color: #2980b9; }
        .result { margin-top: 20px; padding: 15px; background: #f9f9f9; border-radius: 5px; }
        .error { color: #e74c3c; }
        .student-info { margin-bottom: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>نظام نتائج دورة اساسيات المحاسب المالي</h1>
        
        <form method="POST" action="/result">
            <div class="form-group">
                <label for="search_type">طريقة البحث:</label>
                <select id="search_type" name="search_type" required>
                    <option value="id">برقم المسلسل</option>
                    <option value="phone">برقم الهاتف</option>
                </select>
            </div>
            
            <div class="form-group">
                <label for="search_value">ادخل رقم الطالب أو الهاتف:</label>
                <input type="text" id="search_value" name="search_value" required>
            </div>
            
            <button type="submit">بحث</button>
        </form>
        
        {% if result %}
        <div class="result">
            <h2>نتيجة البحث</h2>
            {% if error %}
                <p class="error">{{ error }}</p>
            {% else %}
                {% for key, value in student_data.items() %}
                    <div class="student-info">
                        <strong>{{ key }}:</strong> {{ value }}
                    </div>
                {% endfor %}
            {% endif %}
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

@app.route('/', methods=['GET'])
def home():
    return render_template_string(HTML_TEMPLATE, result=False)

@app.route('/result', methods=['POST'])
def search_result():
    search_type = request.form.get('search_type')
    search_value = request.form.get('search_value', '').strip()
    
    try:
        if search_type == 'id':
            # البحث بالرقم الجامعي
            student_id = int(''.join(filter(str.isdigit, search_value)))
            student_data = data.loc[student_id]
        else:
            # البحث برقم الهاتف
            phone = ''.join(filter(str.isdigit, search_value))[-11:]
            matches = data[data['Phone Number'] == phone]
            
            if len(matches) == 0:
                raise ValueError("لا يوجد طالب بهذا الرقم")
            if len(matches) > 1:
                raise ValueError("يوجد أكثر من طالب بنفس رقم الهاتف")
                
            student_data = matches.iloc[0]
        
        # تحضير البيانات للعرض
        result_data = {
            'رقم المسلسل': student_data.name,
            'الاسم': student_data['Name'],
            'الاسم بالإنجليزية': student_data['Name English'],
            'رقم الهاتف': student_data['Phone Number'],
            'الجامعة': student_data['University'],
            'السنة الدراسية': student_data['Year'],
            'المحافظة': student_data['From'],
            ' درجة الاختبار النهائي': student_data['Score']
        }
        
        logging.info(f"تم العثور على الطالب: {student_data.name}")
        return render_template_string(HTML_TEMPLATE, result=True, student_data=result_data)
    
    except KeyError:
        error_msg = "لم يتم العثور على الطالب بالرقم المحدد"
        logging.warning(f"{error_msg}: {search_value}")
        return render_template_string(HTML_TEMPLATE, result=True, error=error_msg)
    except ValueError as e:
        logging.warning(f"قيمة غير صالحة: {str(e)}")
        return render_template_string(HTML_TEMPLATE, result=True, error=str(e))
    except Exception as e:
        logging.error(f"خطأ غير متوقع: {str(e)}")
        return render_template_string(HTML_TEMPLATE, result=True, error="حدث خطأ غير متوقع")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
