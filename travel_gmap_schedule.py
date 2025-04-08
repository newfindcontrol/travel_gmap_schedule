# -*- coding: utf-8 -*-
import streamlit as st
from datetime import datetime, timedelta
from urllib.parse import quote_plus
import requests
import os
from dotenv import load_dotenv
import pandas as pd

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

st.set_page_config(page_title="Google Maps", layout="wide")
st.title("🗺️ Google Maps")

# ------------------------------
# 📅 サイドバー UI
# ------------------------------
st.sidebar.markdown("🚩 **旅行プラン入力**")
date = st.sidebar.date_input("日付")
departure = st.sidebar.selectbox("出発時刻", [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 15, 30, 45)])
origin = st.sidebar.text_input("出発地", "")

st.sidebar.markdown("🧭 訪問リスト")
stop_count = st.sidebar.selectbox("設定数", list(range(1, 11)))
stops = []

for i in range(stop_count):
    place = st.sidebar.text_input(f"訪問地{i+1}", key=f"place{i}")
    mode = st.sidebar.selectbox(f"移動手段{i+1}（{i}→{i+1}）", ["徒歩", "車", "自転車", "電車"], key=f"mode{i}")
    is_last = i == stop_count - 1
    travel = st.sidebar.number_input(
        f"移動時間{i+1}（分・電車専用）", min_value=1, max_value=300, value=30, step=1, key=f"travel{i}"
    ) if (not is_last or mode == "電車") and mode == "電車" else None
    stay = 0 if is_last else st.sidebar.number_input(
        f"滞在時間{i+1}（分）", min_value=0, max_value=300, value=30, step=5, key=f"stay{i}"
    )
    if place:
        stops.append({"name": place, "mode": mode, "stay": stay, "travel": travel})

# ------------------------------
# 📍 Google Geocoding
# ------------------------------
def get_coordinates(place):
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={quote_plus(place)}&key={GOOGLE_API_KEY}"
    res = requests.get(url).json()
    if res["status"] == "OK":
        loc = res["results"][0]["geometry"]["location"]
        return loc["lat"], loc["lng"]
    else:
        st.warning(f"⚠️ 位置情報取得失敗: {place}")
        return 35.68, 139.76

# ------------------------------
# 🚗 Google Directions API
# ------------------------------
def get_travel_time_and_distance(origin_coord, dest_coord, mode):
    url = f"https://maps.googleapis.com/maps/api/directions/json?origin={origin_coord[0]},{origin_coord[1]}&destination={dest_coord[0]},{dest_coord[1]}&mode={mode}&key={GOOGLE_API_KEY}"
    res = requests.get(url).json()
    if res["status"] == "OK":
        leg = res["routes"][0]["legs"][0]
        duration_min = round(leg["duration"]["value"] / 60)
        distance_text = leg["distance"]["text"]
        return duration_min, distance_text
    else:
        st.warning(f"⚠️ Google Maps 経路取得失敗: {origin_coord} → {dest_coord}（{mode}）")
        return 15, "-"

# ------------------------------
# ✅ 実行処理
# ------------------------------
if st.button("✅ Google Mapsルート生成＆スケジュール表示"):
    all_places = [origin] + [s["name"] for s in stops]

    if not origin or not stops:
        st.warning("出発地と訪問地を入力してください。")
    elif len(set(all_places)) != len(all_places) and not all("ホテル" in p for p in all_places):
        st.error("❌ 同一箇所が選定or選択されています。（ホテル以外）")
    else:
        coordinates = [get_coordinates(p) for p in all_places]
        full_link = "https://www.google.com/maps/dir/" + "/".join([quote_plus(p) for p in all_places])
        link_list = []

        # 🕒 スケジュール生成
        current_time = datetime.combine(datetime.today(), datetime.strptime(departure, "%H:%M").time())
        schedule_rows = [{
            "地点": origin,
            "出発時刻": current_time.strftime("%H:%M"),
            "移動時間": "-",
            "距離": "-",
            "到着時刻": "-",
            "滞在時間": "-"
        }]

        for i, stop in enumerate(stops):
            mode = stop["mode"]
            if mode == "電車":
                travel_time = stop["travel"]
                distance = "-"
            else:
                gm_mode = {"徒歩": "walking", "車": "driving", "自転車": "bicycling"}.get(mode, "driving")
                travel_time, distance = get_travel_time_and_distance(coordinates[i], coordinates[i + 1], gm_mode)

            arrival_time = current_time + timedelta(minutes=travel_time)
            leave_time = arrival_time + timedelta(minutes=stop["stay"])
            schedule_rows.append({
                "地点": stop["name"],
                "出発時刻": leave_time.strftime("%H:%M"),
                "移動時間": f"{travel_time}分",
                "距離": distance,
                "到着時刻": arrival_time.strftime("%H:%M"),
                "滞在時間": f"{stop['stay']}分"
            })

            mode_url = "transit" if mode == "電車" else {"徒歩": "walking", "車": "driving", "自転車": "bicycling"}.get(mode, "driving")
            link_list.append((
                f"{all_places[i]} → {all_places[i+1]}（{mode}）",
                f"https://www.google.com/maps/dir/?api=1&origin={quote_plus(all_places[i])}&destination={quote_plus(all_places[i+1])}&travelmode={mode_url}"
            ))
            current_time = leave_time

        # 📋 表示部
        st.subheader("📋 訪問スケジュール（出発地→目的地ごとの移動・滞在）")
        df = pd.DataFrame(schedule_rows)
        st.dataframe(df)

        st.subheader("📎 移動区間ごとのGoogle Mapsリンク")
        for lbl, lnk in link_list:
            st.markdown(f"- [{lbl}]({lnk})")

        st.markdown("---")
        st.subheader("🌐 全体ルートのGoogle Mapsリンク")
        st.markdown(f"[Google Maps 全体リンク]({full_link})")
