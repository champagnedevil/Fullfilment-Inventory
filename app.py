import os
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from database import init_db, get_db
import sqlite3
import pandas as pd
from datetime import datetime
import tempfile
import uuid

app = Flask(__name__)
app.secret_key = 'warehouse-secret-key-2024'
init_db()

# Функция для загрузки пользователей из файла
def load_users():
    users = {}
    try:
        with open('admins.txt', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and ';' in line:
                    username, password = line.split('/')
                    password = password.rstrip(';')
                    users[username] = password
    except FileNotFoundError:
        default_users = {
            'admin': '76543210',
            'roman': 'dirtus',
            'nikutip': '1s3l5f9e'
        }
        with open('admins.txt', 'w', encoding='utf-8') as f:
            for username, password in default_users.items():
                f.write(f'{username}/{password};\n')
        users = default_users
    return users

# Проверка аутентификации
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        users = load_users()
        
        if username in users and users[username] == password:
            session['logged_in'] = True
            session['username'] = username
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            return render_template('login.html', error='Неверное имя пользователя или пароль')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    db = get_db()
    zones = db.execute('SELECT * FROM zones ORDER BY name').fetchall()
    return render_template('index.html', zones=zones, username=session.get('username'))

@app.route('/zone/<int:zone_id>')
@login_required
def zone_detail(zone_id):
    db = get_db()
    zone = db.execute('SELECT * FROM zones WHERE id = ?', (zone_id,)).fetchone()
    boxes = db.execute('SELECT * FROM boxes WHERE zone_id = ? ORDER BY name', (zone_id,)).fetchall()
    return render_template('zone_detail.html', zone=zone, boxes=boxes, username=session.get('username'))

@app.route('/box/<int:box_id>')
@login_required
def box_detail(box_id):
    db = get_db()
    box = db.execute('''
        SELECT b.*, z.name as zone_name 
        FROM boxes b 
        JOIN zones z ON b.zone_id = z.id 
        WHERE b.id = ?
    ''', (box_id,)).fetchone()
    
    items = db.execute('''
        SELECT * FROM box_items 
        WHERE box_id = ? 
        ORDER BY product_name
    ''', (box_id,)).fetchall()
    
    return render_template('box_detail.html', box=box, items=items, username=session.get('username'))

# API endpoints
@app.route('/api/zones', methods=['POST'])
@login_required
def create_zone():
    data = request.get_json()
    db = get_db()
    cursor = db.execute('INSERT INTO zones (name, description) VALUES (?, ?)',
               (data['name'], data.get('description', '')))
    db.commit()
    return jsonify({'success': True, 'id': cursor.lastrowid})

@app.route('/api/zones/<int:zone_id>', methods=['PUT', 'DELETE'])
@login_required
def manage_zone(zone_id):
    db = get_db()
    if request.method == 'PUT':
        data = request.get_json()
        db.execute('UPDATE zones SET name = ?, description = ? WHERE id = ?',
                   (data['name'], data.get('description', ''), zone_id))
        db.commit()
        return jsonify({'success': True})
    elif request.method == 'DELETE':
        db.execute('DELETE FROM zones WHERE id = ?', (zone_id,))
        db.commit()
        return jsonify({'success': True})

@app.route('/api/boxes', methods=['POST'])
@login_required
def create_box():
    data = request.get_json()
    db = get_db()
    cursor = db.execute('INSERT INTO boxes (name, description, zone_id) VALUES (?, ?, ?)',
                        (data['name'], data.get('description', ''), data['zone_id']))
    db.commit()
    return jsonify({'success': True, 'id': cursor.lastrowid})

@app.route('/api/boxes/<int:box_id>', methods=['PUT', 'DELETE'])
@login_required
def manage_box(box_id):
    db = get_db()
    if request.method == 'PUT':
        data = request.get_json()
        db.execute('UPDATE boxes SET name = ?, description = ? WHERE id = ?',
                   (data['name'], data.get('description', ''), box_id))
        db.commit()
        return jsonify({'success': True})
    elif request.method == 'DELETE':
        db.execute('DELETE FROM boxes WHERE id = ?', (box_id,))
        db.commit()
        return jsonify({'success': True})

@app.route('/api/box_items', methods=['POST'])
@login_required
def add_box_item():
    try:
        data = request.get_json()
        if not data or 'box_id' not in data or 'product_name' not in data:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        db = get_db()
        
        existing = None
        if data.get('barcode'):
            existing = db.execute('''
                SELECT * FROM box_items 
                WHERE box_id = ? AND barcode = ?
            ''', (data['box_id'], data['barcode'])).fetchone()
        
        if existing:
            db.execute('''
                UPDATE box_items SET quantity = quantity + ? 
                WHERE id = ?
            ''', (data['quantity'], existing['id']))
        else:
            db.execute('''
                INSERT INTO box_items (box_id, product_name, barcode, quantity) 
                VALUES (?, ?, ?, ?)
            ''', (data['box_id'], data['product_name'], data.get('barcode'), data['quantity']))
        
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/box_items/<int:item_id>', methods=['PUT', 'DELETE'])
@login_required
def manage_box_item(item_id):
    db = get_db()
    if request.method == 'PUT':
        data = request.get_json()
        db.execute('UPDATE box_items SET product_name = ?, quantity = ? WHERE id = ?',
                   (data['product_name'], data['quantity'], item_id))
        db.commit()
        return jsonify({'success': True})
    elif request.method == 'DELETE':
        db.execute('DELETE FROM box_items WHERE id = ?', (item_id,))
        db.commit()
        return jsonify({'success': True})

@app.route('/api/check_product')
@login_required
def check_product():
    try:
        box_id = request.args.get('box_id')
        barcode = request.args.get('barcode')
        
        if not box_id or not barcode:
            return jsonify({'exists': False, 'error': 'Missing parameters'})
        
        db = get_db()
        product = db.execute('''
            SELECT * FROM box_items 
            WHERE box_id = ? AND barcode = ?
        ''', (box_id, barcode)).fetchone()
        
        if product:
            return jsonify({
                'exists': True,
                'product': {
                    'id': product['id'],
                    'product_name': product['product_name'],
                    'barcode': product['barcode'],
                    'quantity': product['quantity']
                }
            })
        else:
            return jsonify({'exists': False})
    except Exception as e:
        return jsonify({'exists': False, 'error': str(e)})

# НОВЫЙ ЭНДПОИНТ: Сборка товаров из Excel файла
@app.route('/api/process_collection', methods=['POST'])
@login_required
def process_collection():
    """Обработка файла для сборки товаров"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        if not file.filename.endswith('.xlsx'):
            return jsonify({'success': False, 'error': 'Only Excel files are supported'}), 400
        
        # Сохраняем временный файл
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            file_path = tmp.name
            file.save(file_path)
        
        # Читаем Excel файл
        df = pd.read_excel(file_path)
        
        # Определяем тип файла и столбцы
        file_type, barcode_col, quantity_col, name_col, article_col = detect_file_columns(df)
        
        db = get_db()
        
        # Получаем все товары из базы данных
        all_items = db.execute('''
            SELECT 
                bi.id as item_id,
                bi.product_name,
                bi.barcode,
                bi.quantity,
                b.name as box_name,
                z.name as zone_name,
                b.id as box_id
            FROM box_items bi
            JOIN boxes b ON bi.box_id = b.id
            JOIN zones z ON b.zone_id = z.id
            WHERE bi.quantity > 0
        ''').fetchall()
        
        # Создаем словарь для быстрого поиска
        items_dict = {}
        for item in all_items:
            barcode = str(item['barcode']).strip() if item['barcode'] else ''
            if barcode and barcode != 'nan':
                items_dict[barcode] = {
                    'item_id': item['item_id'],
                    'product_name': item['product_name'],
                    'quantity': item['quantity'],
                    'zone': item['zone_name'],
                    'box': item['box_name'],
                    'box_id': item['box_id']
                }
        
        # Обрабатываем файл сборки
        collection_plan = []
        total_needed = 0
        total_to_take = 0
        
        for index, row in df.iterrows():
            try:
                # Пропускаем пустые строки
                if pd.isna(row[barcode_col]) or pd.isna(row[quantity_col]):
                    continue
                
                barcode = str(row[barcode_col]).strip()
                needed_qty = int(row[quantity_col])
                product_name = str(row[name_col]) if name_col and not pd.isna(row.get(name_col)) else f"Товар {barcode}"
                article = str(row[article_col]) if article_col and not pd.isna(row.get(article_col)) else ""
                
                if not barcode or barcode == 'nan':
                    continue
                
                if barcode in items_dict:
                    item_info = items_dict[barcode]
                    available_qty = item_info['quantity']
                    
                    # Определяем сколько можем взять
                    take_qty = min(needed_qty, available_qty)
                    
                    if take_qty > 0:
                        collection_item = {
                            'barcode': barcode,
                            'article': article,
                            'product_name': product_name,
                            'needed': needed_qty,
                            'take': take_qty,
                            'zone': item_info['zone'],
                            'box': item_info['box'],
                            'remaining_after': available_qty - take_qty,
                            'item_id': item_info['item_id'],
                            'box_id': item_info['box_id']
                        }
                        
                        collection_plan.append(collection_item)
                        total_needed += needed_qty
                        total_to_take += take_qty
                        
            except Exception as e:
                print(f"Ошибка обработки строки {index + 2}: {e}")
                continue
        
        # Группируем по зонам и коробкам для оптимизированного плана
        optimized_plan = optimize_collection_plan(collection_plan)
        
        # Удаляем временный файл
        try:
            os.unlink(file_path)
        except:
            pass
        
        return jsonify({
            'success': True,
            'file_type': file_type,
            'total_items': len(collection_plan),
            'total_needed': total_needed,
            'total_to_take': total_to_take,
            'collection_plan': collection_plan,
            'optimized_plan': optimized_plan
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# НОВЫЙ ЭНДПОИНТ: Подтверждение сборки и обновление базы
@app.route('/api/confirm_collection', methods=['POST'])
@login_required
def confirm_collection():
    """Подтверждение сборки и обновление остатков"""
    try:
        data = request.get_json()
        if not data or 'collection_plan' not in data:
            return jsonify({'success': False, 'error': 'No collection plan provided'}), 400
        
        collection_plan = data['collection_plan']
        db = get_db()
        
        updated_count = 0
        for item in collection_plan:
            # Обновляем количество в базе данных
            db.execute('''
                UPDATE box_items 
                SET quantity = ? 
                WHERE id = ?
            ''', (item['remaining_after'], item['item_id']))
            updated_count += 1
        
        db.commit()
        
        return jsonify({
            'success': True,
            'updated_count': updated_count,
            'message': f'Сборка завершена! Обновлено {updated_count} позиций.'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def detect_file_columns(df):
    """Определяет тип файла и названия столбцов"""
    if 'Баркод' in df.columns and 'Количество, шт.' in df.columns:
        return 'shk_excel', 'Баркод', 'Количество, шт.', 'Предмет', 'Артикул поставщика'
    elif 'штрихкод' in df.columns and 'количество' in df.columns:
        return 'products_export', 'штрихкод', 'количество', 'имя (необязательно)', 'артикул'
    else:
        # Автоопределение
        barcode_col = None
        quantity_col = None
        name_col = None
        article_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'баркод' in col_lower or 'штрих' in col_lower or 'код' in col_lower:
                barcode_col = col
            elif 'колич' in col_lower or 'кол-во' in col_lower:
                quantity_col = col
            elif 'назван' in col_lower or 'имя' in col_lower or 'предмет' in col_lower:
                name_col = col
            elif 'артикул' in col_lower:
                article_col = col
        
        # Используем первые столбцы по умолчанию
        if not barcode_col and len(df.columns) > 0:
            barcode_col = df.columns[0]
        if not quantity_col and len(df.columns) > 1:
            quantity_col = df.columns[1]
        if not name_col and len(df.columns) > 2:
            name_col = df.columns[2]
        if not article_col and len(df.columns) > 3:
            article_col = df.columns[3]
            
        return 'auto_detected', barcode_col, quantity_col, name_col, article_col

def optimize_collection_plan(collection_plan):
    """Оптимизирует план сборки по зонам и коробкам"""
    zone_box_plan = {}
    
    for item in collection_plan:
        zone = item['zone']
        box = item['box']
        key = f"{zone}|{box}"
        
        if key not in zone_box_plan:
            zone_box_plan[key] = {
                'zone': zone,
                'box': box,
                'items': []
            }
        
        zone_box_plan[key]['items'].append(item)
    
    # Сортируем по зонам для оптимального маршрута
    optimized = sorted(zone_box_plan.values(), key=lambda x: x['zone'])
    
    return optimized

@app.route('/api/export_excel_all')
@login_required
def export_excel_all():
    """Простая выгрузка всех данных"""
    try:
        db = get_db()
        
        query = '''
            SELECT 
                z.name as "Зона",
                b.name as "Коробка", 
                bi.product_name as "Название товара",
                bi.barcode as "Штрих-код",
                bi.quantity as "Количество",
                bi.created_at as "Дата добавления"
            FROM box_items bi
            JOIN boxes b ON bi.box_id = b.id
            JOIN zones z ON b.zone_id = z.id
            ORDER BY z.name, b.name, bi.product_name
        '''
        
        df = pd.read_sql_query(query, db)
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            file_path = tmp.name
        
        df.to_excel(file_path, index=False, engine='openpyxl')
        
        download_name = f'warehouse_export_all_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        
        response = send_file(
            file_path,
            as_attachment=True,
            download_name=download_name,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        @response.call_on_close
        def cleanup():
            try:
                os.unlink(file_path)
            except:
                pass
                
        return response
        
    except Exception as e:
        print(f"Error in export_excel_all: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/export_excel_boxes')
@login_required
def export_excel_boxes():
    """Простая выгрузка по коробкам"""
    try:
        db = get_db()
        
        query = '''
            SELECT 
                z.name as "Зона",
                b.name as "Коробка",
                bi.product_name as "Название товара",
                bi.barcode as "Штрих-код", 
                bi.quantity as "Количество",
                bi.created_at as "Дата добавления"
            FROM box_items bi
            JOIN boxes b ON bi.box_id = b.id
            JOIN zones z ON b.zone_id = z.id
            ORDER BY z.name, b.name, bi.product_name
        '''
        
        df = pd.read_sql_query(query, db)
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            file_path = tmp.name
        
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            if df.empty:
                empty_df = pd.DataFrame({'Сообщение': ['Нет данных для экспорта']})
                empty_df.to_excel(writer, sheet_name='Данные', index=False)
            else:
                for (zone_name, box_name), group in df.groupby(['Зона', 'Коробка']):
                    sheet_name = f"{zone_name}_{box_name}"[:31]
                    sheet_name = ''.join(c for c in sheet_name if c.isalnum() or c in (' ', '_', '-')).strip()
                    if not sheet_name:
                        sheet_name = 'Лист1'
                    
                    group_data = group[['Название товара', 'Штрих-код', 'Количество', 'Дата добавления']].copy()
                    group_data.to_excel(writer, sheet_name=sheet_name, index=False)
        
        download_name = f'warehouse_export_boxes_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        
        response = send_file(
            file_path,
            as_attachment=True,
            download_name=download_name,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        @response.call_on_close
        def cleanup():
            try:
                os.unlink(file_path)
            except:
                pass
                
        return response
        
    except Exception as e:
        print(f"Error in export_excel_boxes: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/export_items_by_date')
@login_required
def export_items_by_date():
    """Выгрузка товаров по дате добавления"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not start_date or not end_date:
            return jsonify({'success': False, 'error': 'Start date and end date are required'}), 400
        
        db = get_db()
        
        query = '''
            SELECT 
                z.name as "Зона",
                b.name as "Коробка", 
                bi.product_name as "Название товара",
                bi.barcode as "Штрих-код",
                bi.quantity as "Количество",
                bi.created_at as "Дата добавления"
            FROM box_items bi
            JOIN boxes b ON bi.box_id = b.id
            JOIN zones z ON b.zone_id = z.id
            WHERE DATE(bi.created_at) BETWEEN ? AND ?
            ORDER BY bi.created_at DESC, z.name, b.name
        '''
        
        df = pd.read_sql_query(query, db, params=[start_date, end_date])
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            file_path = tmp.name
        
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            if not df.empty:
                df.to_excel(writer, sheet_name='Товары', index=False)
                
                stats_data = {
                    'Показатель': [
                        'Период', 
                        'Всего товаров', 
                        'Уникальных товаров', 
                        'Общее количество',
                        'Количество коробок',
                        'Количество зон',
                        'Дата выгрузки'
                    ],
                    'Значение': [
                        f"{start_date} - {end_date}",
                        len(df),
                        df['Название товара'].nunique(),
                        df['Количество'].sum(),
                        df['Коробка'].nunique(),
                        df['Зона'].nunique(),
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    ]
                }
                stats_df = pd.DataFrame(stats_data)
                stats_df.to_excel(writer, sheet_name='Статистика', index=False)
                
                daily_stats = df.groupby(pd.to_datetime(df['Дата добавления']).dt.date).agg({
                    'Название товара': 'count',
                    'Количество': 'sum'
                }).reset_index()
                daily_stats.columns = ['Дата', 'Количество записей', 'Общее количество товаров']
                daily_stats.to_excel(writer, sheet_name='По дням', index=False)
                
                zone_stats = df.groupby('Зона').agg({
                    'Название товара': 'count',
                    'Количество': 'sum',
                    'Коробка': 'nunique'
                }).reset_index()
                zone_stats.columns = ['Зона', 'Количество товаров', 'Общее количество', 'Количество коробок']
                zone_stats.to_excel(writer, sheet_name='По зонам', index=False)
            else:
                empty_df = pd.DataFrame({'Сообщение': [f'Нет данных за период {start_date} - {end_date}']})
                empty_df.to_excel(writer, sheet_name='Товары', index=False)
        
        download_name = f'items_export_{start_date}_to_{end_date}.xlsx'
        
        response = send_file(
            file_path,
            as_attachment=True,
            download_name=download_name,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        @response.call_on_close
        def cleanup():
            try:
                os.unlink(file_path)
            except:
                pass
                
        return response
        
    except Exception as e:
        print(f"Error in export_items_by_date: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/import_items_excel', methods=['POST'])
@login_required
def import_items_excel():
    """Импорт товаров из Excel файла в зоны и коробки"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        if not file.filename.endswith('.xlsx'):
            return jsonify({'success': False, 'error': 'Only Excel files are supported'}), 400
        
        import_mode = request.form.get('import_mode', 'add')
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            file_path = tmp.name
            file.save(file_path)
        
        df = pd.read_excel(file_path)
        
        required_columns = ['Название товара', 'Количество']
        for col in required_columns:
            if col not in df.columns:
                try:
                    os.unlink(file_path)
                except:
                    pass
                return jsonify({'success': False, 'error': f'Missing required column: {col}'}), 400
        
        db = get_db()
        imported_count = 0
        updated_count = 0
        errors = []
        
        if import_mode == 'replace':
            db.execute('DELETE FROM box_items')
            db.execute('DELETE FROM boxes')
            db.execute('DELETE FROM zones')
            db.commit()
        
        zones_cache = {}
        boxes_cache = {}
        
        for index, row in df.iterrows():
            try:
                if pd.isna(row['Название товара']) or pd.isna(row['Количество']):
                    continue
                
                product_name = str(row['Название товара'])
                quantity = int(row['Количество'])
                barcode = str(row['Штрих-код']) if 'Штрих-код' in df.columns and not pd.isna(row.get('Штрих-код')) else None
                zone_name = str(row['Зона']) if 'Зона' in df.columns and not pd.isna(row.get('Зона')) else 'Основная зона'
                box_name = str(row['Коробка']) if 'Коробка' in df.columns and not pd.isna(row.get('Коробка')) else 'Коробка 1'
                
                zone_key = zone_name
                if zone_key not in zones_cache:
                    zone = db.execute('SELECT id FROM zones WHERE name = ?', (zone_name,)).fetchone()
                    if not zone:
                        cursor = db.execute('INSERT INTO zones (name) VALUES (?)', (zone_name,))
                        zone_id = cursor.lastrowid
                    else:
                        zone_id = zone['id']
                    zones_cache[zone_key] = zone_id
                else:
                    zone_id = zones_cache[zone_key]
                
                box_key = f"{zone_id}_{box_name}"
                if box_key not in boxes_cache:
                    box = db.execute('SELECT id FROM boxes WHERE name = ? AND zone_id = ?', (box_name, zone_id)).fetchone()
                    if not box:
                        cursor = db.execute('INSERT INTO boxes (name, zone_id) VALUES (?, ?)', (box_name, zone_id))
                        box_id = cursor.lastrowid
                    else:
                        box_id = box['id']
                    boxes_cache[box_key] = box_id
                else:
                    box_id = boxes_cache[box_key]
                
                existing_item = None
                if barcode:
                    existing_item = db.execute(
                        'SELECT id, quantity FROM box_items WHERE box_id = ? AND barcode = ?', 
                        (box_id, barcode)
                    ).fetchone()
                
                if existing_item:
                    if import_mode == 'add':
                        db.execute(
                            'UPDATE box_items SET quantity = quantity + ? WHERE id = ?',
                            (quantity, existing_item['id'])
                        )
                        updated_count += 1
                    else:
                        db.execute(
                            'UPDATE box_items SET quantity = ? WHERE id = ?',
                            (quantity, existing_item['id'])
                        )
                        updated_count += 1
                else:
                    db.execute(
                        'INSERT INTO box_items (box_id, product_name, barcode, quantity) VALUES (?, ?, ?, ?)',
                        (box_id, product_name, barcode, quantity)
                    )
                    imported_count += 1
                
            except Exception as e:
                errors.append(f"Строка {index + 2}: {str(e)}")
                continue
        
        db.commit()
        
        try:
            os.unlink(file_path)
        except:
            pass
        
        if import_mode == 'replace':
            message = f'Данные заменены. Импортировано {imported_count} новых товаров, обновлено {updated_count} существующих товаров'
        else:
            message = f'Успешно добавлено {imported_count} новых товаров, обновлено {updated_count} существующих товаров'
        
        result = {
            'success': True, 
            'imported_count': imported_count,
            'updated_count': updated_count,
            'import_mode': import_mode,
            'message': message
        }
        
        if errors:
            result['errors'] = errors[:10]
            result['error_count'] = len(errors)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ЭНДПОИНТЫ ДЛЯ ПРИЁМОК
@app.route('/receipts')
@login_required
def receipts_page():
    """Страница приёмки товаров"""
    db = get_db()
    receipts = db.execute('''
        SELECT * FROM receipts 
        ORDER BY receipt_date DESC, created_at DESC
    ''').fetchall()
    return render_template('receipts.html', receipts=receipts, username=session.get('username'))

# НОВАЯ СТРАНИЦА: Сборка товаров
@app.route('/collection')
@login_required
def collection_page():
    """Страница сборки товаров"""
    return render_template('collection.html', username=session.get('username'))

@app.route('/receipt/<int:receipt_id>')
@login_required
def receipt_detail(receipt_id):
    """Детальная страница приёмки"""
    db = get_db()
    receipt = db.execute('SELECT * FROM receipts WHERE id = ?', (receipt_id,)).fetchone()
    items = db.execute('''
        SELECT * FROM receipt_items 
        WHERE receipt_id = ? 
        ORDER BY product_name
    ''', (receipt_id,)).fetchall()
    return render_template('receipt_detail.html', receipt=receipt, items=items, username=session.get('username'))

@app.route('/api/receipts', methods=['POST'])
@login_required
def create_receipt():
    """Создание новой приёмки"""
    try:
        data = request.get_json()
        if not data or 'receipt_date' not in data:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        db = get_db()
        
        receipt_number = f"REC-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        
        cursor = db.execute('''
            INSERT INTO receipts (receipt_number, receipt_date, description)
            VALUES (?, ?, ?)
        ''', (
            receipt_number,
            data['receipt_date'],
            data.get('description', '')
        ))
        
        receipt_id = cursor.lastrowid
        db.commit()
        
        return jsonify({
            'success': True, 
            'receipt_id': receipt_id,
            'receipt_number': receipt_number
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/receipts/<int:receipt_id>', methods=['DELETE'])
@login_required
def delete_receipt(receipt_id):
    """Удаление приёмки"""
    try:
        db = get_db()
        db.execute('DELETE FROM receipts WHERE id = ?', (receipt_id,))
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/receipts/<int:receipt_id>/items', methods=['POST'])
@login_required
def add_receipt_items(receipt_id):
    """Добавление товаров в приёмку"""
    try:
        data = request.get_json()
        if not data or 'items' not in data:
            return jsonify({'success': False, 'error': 'Missing items data'}), 400
        
        db = get_db()
        
        receipt = db.execute('SELECT id FROM receipts WHERE id = ?', (receipt_id,)).fetchone()
        if not receipt:
            return jsonify({'success': False, 'error': 'Receipt not found'}), 404
        
        total_quantity = 0
        total_products = len(data['items'])
        
        for item in data['items']:
            if not item.get('product_name') or not item.get('quantity'):
                continue
            
            db.execute('''
                INSERT INTO receipt_items (receipt_id, product_name, barcode, quantity, box_name, zone_name)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                receipt_id,
                item['product_name'],
                item.get('barcode'),
                item['quantity'],
                item.get('box_name'),
                item.get('zone_name')
            ))
            
            total_quantity += item['quantity']
        
        db.execute('''
            UPDATE receipts 
            SET total_quantity = ?, total_products = ? 
            WHERE id = ?
        ''', (total_quantity, total_products, receipt_id))
        
        db.commit()
        return jsonify({'success': True, 'added_items': total_products})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/receipts/import_excel', methods=['POST'])
@login_required
def import_receipts_excel():
    """Импорт приёмки из Excel файла"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        if not file.filename.endswith('.xlsx'):
            return jsonify({'success': False, 'error': 'Only Excel files are supported'}), 400
        
        receipt_date = request.form.get('receipt_date')
        description = request.form.get('description', '')
        
        if not receipt_date:
            return jsonify({'success': False, 'error': 'Receipt date is required'}), 400
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            file_path = tmp.name
            file.save(file_path)
        
        df = pd.read_excel(file_path)
        
        required_columns = ['Название товара', 'Количество']
        for col in required_columns:
            if col not in df.columns:
                try:
                    os.unlink(file_path)
                except:
                    pass
                return jsonify({'success': False, 'error': f'Missing required column: {col}'}), 400
        
        db = get_db()
        
        receipt_number = f"REC-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        
        cursor = db.execute('''
            INSERT INTO receipts (receipt_number, receipt_date, description)
            VALUES (?, ?, ?)
        ''', (receipt_number, receipt_date, description))
        
        receipt_id = cursor.lastrowid
        imported_count = 0
        total_quantity = 0
        
        for index, row in df.iterrows():
            try:
                if pd.isna(row['Название товара']) or pd.isna(row['Количество']):
                    continue
                
                quantity = int(row['Количество'])
                
                db.execute('''
                    INSERT INTO receipt_items (receipt_id, product_name, barcode, quantity, box_name, zone_name)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    receipt_id,
                    str(row['Название товара']),
                    str(row['Штрих-код']) if 'Штрих-код' in df.columns and not pd.isna(row.get('Штрих-код')) else None,
                    quantity,
                    str(row['Коробка']) if 'Коробка' in df.columns and not pd.isna(row.get('Коробка')) else None,
                    str(row['Зона']) if 'Зона' in df.columns and not pd.isna(row.get('Зона')) else None
                ))
                
                imported_count += 1
                total_quantity += quantity
                
            except Exception as e:
                print(f"Error importing row {index + 2}: {e}")
                continue
        
        db.execute('''
            UPDATE receipts 
            SET total_quantity = ?, total_products = ? 
            WHERE id = ?
        ''', (total_quantity, imported_count, receipt_id))
        
        db.commit()
        
        try:
            os.unlink(file_path)
        except:
            pass
        
        return jsonify({
            'success': True, 
            'receipt_id': receipt_id,
            'receipt_number': receipt_number,
            'imported_count': imported_count,
            'total_quantity': total_quantity,
            'message': f'Приёмка #{receipt_number} создана. Импортировано {imported_count} товаров'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/receipts/<int:receipt_id>/export_excel')
@login_required
def export_receipt_excel(receipt_id):
    """Экспорт приёмки в Excel"""
    try:
        db = get_db()
        
        receipt = db.execute('SELECT * FROM receipts WHERE id = ?', (receipt_id,)).fetchone()
        if not receipt:
            return jsonify({'success': False, 'error': 'Receipt not found'}), 404
        
        items = db.execute('''
            SELECT product_name, barcode, quantity, box_name, zone_name
            FROM receipt_items 
            WHERE receipt_id = ?
            ORDER BY product_name
        ''', (receipt_id,)).fetchall()
        
        data = []
        for item in items:
            data.append({
                'Название товара': item['product_name'],
                'Штрих-код': item['barcode'] or '',
                'Количество': item['quantity'],
                'Коробка': item['box_name'] or '',
                'Зона': item['zone_name'] or ''
            })
        
        df = pd.DataFrame(data)
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            file_path = tmp.name
        
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            if not df.empty:
                df.to_excel(writer, sheet_name='Товары', index=False)
            
            info_data = {
                'Поле': ['Номер приёмки', 'Дата приёмки', 'Всего товаров', 'Общее количество', 'Описание'],
                'Значение': [
                    receipt['receipt_number'],
                    receipt['receipt_date'],
                    receipt['total_products'],
                    receipt['total_quantity'],
                    receipt['description'] or ''
                ]
            }
            info_df = pd.DataFrame(info_data)
            info_df.to_excel(writer, sheet_name='Информация', index=False)
        
        download_name = f'receipt_{receipt["receipt_number"]}_{receipt["receipt_date"]}.xlsx'
        
        response = send_file(
            file_path,
            as_attachment=True,
            download_name=download_name,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        @response.call_on_close
        def cleanup():
            try:
                os.unlink(file_path)
            except:
                pass
                
        return response
        
    except Exception as e:
        print(f"Error in export_receipt_excel: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/receipts/stats')
@login_required
def get_receipts_stats():
    """Получение статистики по приёмкам"""
    try:
        db = get_db()
        
        total_receipts = db.execute('SELECT COUNT(*) as count FROM receipts').fetchone()['count']
        total_quantity = db.execute('SELECT SUM(total_quantity) as total FROM receipts').fetchone()['total'] or 0
        total_products = db.execute('SELECT SUM(total_products) as total FROM receipts').fetchone()['total'] or 0
        
        seven_days_stats = db.execute('''
            SELECT 
                DATE(receipt_date) as date,
                COUNT(*) as receipts_count,
                SUM(total_quantity) as total_quantity,
                SUM(total_products) as total_products
            FROM receipts 
            WHERE receipt_date >= DATE('now', '-7 days')
            GROUP BY DATE(receipt_date)
            ORDER BY date DESC
        ''').fetchall()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_receipts': total_receipts,
                'total_quantity': total_quantity,
                'total_products': total_products
            },
            'recent_stats': [dict(row) for row in seven_days_stats]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)