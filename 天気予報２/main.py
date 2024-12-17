import flet as ft
import requests
import sqlite3

# DB接続
conn = sqlite3.connect('weather.db')
cur = conn.cursor()

# テーブルが存在しない場合は作成
cur.execute('''
        CREATE TABLE IF NOT EXISTS weather (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            area_code TEXT,
            area_name TEXT,
            time TEXT,
            weather TEXT,
            min_temp TEXT,
            max_temp TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(area_code, time)
        )
    ''')

# テーブルに必要なカラムが存在しない場合は追加
try:
    cur.execute('SELECT min_temp FROM weather LIMIT 1')
except sqlite3.OperationalError:
    cur.execute('ALTER TABLE weather ADD COLUMN min_temp TEXT')

try:
    cur.execute('SELECT max_temp FROM weather LIMIT 1')
except sqlite3.OperationalError:
    cur.execute('ALTER TABLE weather ADD COLUMN max_temp TEXT')

conn.commit()
conn.close()

# 天気予報データを取得する関数
def get_weather_data(area_code):
    url = f"https://www.jma.go.jp/bosai/forecast/data/forecast/{area_code}.json"
    response = requests.get(url)
    if response.status_code == 200:
        try:
            weather_data = response.json()
            # 天気データが空でないことを確認
            if weather_data and isinstance(weather_data, list):
                return weather_data
            else:
                print(f"天気情報が正しく取得できませんでした: {response.text}")
                return None
        except Exception as e:
            print(f"JSON解析エラー: {e}")
            return None
    else:
        print(f"APIレスポンス失敗: {response.status_code}")
        print(response.text)
        return None

# 天気情報をデータベースに保存する関数
def save_weather_data(area_code, area_name, time, weather, min_temp, max_temp):
    conn = sqlite3.connect('weather.db')
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT INTO weather (area_code, area_name, time, weather, min_temp, max_temp)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(area_code, time) DO UPDATE SET weather=excluded.weather, min_temp=excluded.min_temp, max_temp=excluded.max_temp
        ''', (area_code, area_name, time, weather, min_temp, max_temp))
        conn.commit()
    except sqlite3.Error as e:
        print(f"データベースエラー: {e}")
    finally:
        conn.close()

# 天気情報をデータベースから取得する関数
def get_weather_from_db(area_code):
    conn = sqlite3.connect('weather.db')
    cur = conn.cursor()
    cur.execute('''
        SELECT area_name, time, weather, min_temp, max_temp FROM weather
        WHERE area_code = ?
        ORDER BY time
    ''', (area_code,))
    rows = cur.fetchall()
    conn.close()
    return rows

# 地域データを取得する関数
def get_area_data():
    area_url = "http://www.jma.go.jp/bosai/common/const/area.json"
    response = requests.get(area_url)
    return response.json()

# 地域コードに対応する子地域コードのリストを返す関数
def get_children_codes(parent_code, area_data):
    offices = area_data["offices"]
    if parent_code in offices:
        return offices[parent_code].get("children", [])
    return []

# メインのアプリケーション
def main(page: ft.Page):
    # ウインドウサイズを設定
    page.window_width = 2000
    page.window_height = 2000
    
    # 地域データを取得
    area_data = get_area_data()
    
    # 地域センター情報（大まかな地域）
    centers = area_data["centers"]
    
    # センターリストを表示する関数
    def show_centers():
        center_buttons = []
        for center_code, center_info in centers.items():
            center_buttons.append(
                ft.ListTile(
                    title=ft.Text(center_info["name"]),
                    on_click=lambda e, center_code=center_code: show_subregions(center_code)  # サブ地域を表示
                )
            )
        
        # 初期ページに地域リストのボタンを表示
        page.controls.clear()
        page.add(ft.Text("地域リストを選択してください"))
        page.add(ft.Column(center_buttons))
        page.update()

    # サブ地域（細分化された地域）のボタンを表示する関数
    def show_subregions(center_code=None):
        offices = area_data["offices"]
        subregion_buttons = []
        if center_code:
            subregions = centers[center_code]["children"]
            for subregion_code in subregions:
                subregion_name = offices.get(subregion_code, {}).get("name", "不明な地域")
                subregion_buttons.append(
                    ft.ListTile(
                        title=ft.Text(subregion_name),
                        on_click=lambda e, subregion_code=subregion_code: show_weather(subregion_code, center_code)  # 天気を表示
                    )
                )
            
            # 現在のページをクリアしてサブ地域のボタンを表示
            page.controls.clear()
            page.add(ft.Text(f"{centers[center_code]['name']} の細分化地域を選択"))
            page.add(ft.Column(subregion_buttons))
            page.add(ft.ElevatedButton("戻る", on_click=lambda e: show_centers()))  # 戻るボタン
            page.update()

    # 天気予報を表示する関数
    def show_weather(subregion_code, center_code):
        weather_data = get_weather_data(subregion_code)
        page.controls.clear()
        if weather_data:
            try:
                area_found = False  # 地域情報が見つかったかどうかのフラグ
                for time_series in weather_data[0]["timeSeries"]:
                    if "areas" not in time_series:
                        continue  # エリア情報がない場合はスキップ
            
                    times = time_series.get("timeDefines", [])
                    for area in time_series["areas"]:
                        area_code = area.get("area", {}).get("code")
                        print(f"Checking area code: {area_code} against subregion_code: {subregion_code}")
                        if area_code == subregion_code or area_code in get_children_codes(subregion_code, area_data):
                            area_found = True
                            area_name = area["area"]["name"]
                            page.add(ft.Text(f"地域: {area_name}"))
                    
                            # 天気情報の表示
                            if "weathers" in area:
                                weathers = area.get("weathers", [])
                                if len(times) == len(weathers):
                                    page.add(ft.Text("天気:"))
                                    for time, weather in zip(times, weathers):
                                        page.add(ft.Text(f"{time}: {weather}"))
                                        # 天気情報をデータベースに保存
                                        save_weather_data(area_code, area_name, time, weather, None, None)

                            # 気温情報の表示
                            if "tempsMin" in area and "tempsMax" in area:
                                temps_min = area.get("tempsMin", [])
                                temps_max = area.get("tempsMax", [])
                                if len(times) == len(temps_min) == len(temps_max):
                                    page.add(ft.Text("気温:"))
                                    for time, temp_min, temp_max in zip(times, temps_min, temps_max):
                                        page.add(ft.Text(f"{time}: 最低気温 {temp_min}°C, 最高気温 {temp_max}°C"))
                                        # 気温情報をデータベースに保存
                                        save_weather_data(area_code, area_name, time, None, temp_min, temp_max)

                if not area_found:
                    page.add(ft.Text("指定された地域の天気情報が見つかりませんでした。"))
            except KeyError as ke:
                page.add(ft.Text(f"キーエラーが発生しました: {ke}"))
            except IndexError as ie:
                page.add(ft.Text(f"インデックスエラーが発生しました: {ie}"))
            except Exception as e:
                page.add(ft.Text(f"不明なエラーが発生しました: {e}"))
        else:
            page.add(ft.Text("天気予報データの取得に失敗しました。"))

        # データベースから天気情報を取得して表示
        weather_rows = get_weather_from_db(subregion_code)
        if weather_rows:
            page.add(ft.Text("データベースから取得した天気情報:"))
            for area_name, time, weather, min_temp, max_temp in weather_rows:
                weather_info = f"{time}: {weather}"
                if min_temp and max_temp:
                    weather_info += f", 最低気温 {min_temp}°C, 最高気温 {max_temp}°C"
                page.add(ft.Text(weather_info))

        # 戻るボタンを表示
        page.add(ft.ElevatedButton("戻る", on_click=lambda e: show_subregions(center_code)))
        page.update()

    # 最初の地域リストを表示
    show_centers()

# アプリケーションを実行
ft.app(target=main)

