import flet as ft
import requests

data_json = requests.get('http://www.jma.go.jp/bosai/common/const/area.json').json()
data =requests.get('https://www.jma.go.jp/bosai/forecast/data/forecast/')
def main(page: ft.Page):
    page.add(ft.SafeArea(ft.Text("天気予報")))


ft.app(main)
