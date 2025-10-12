# ===================== ORDER.PY (v8.0 - LAUNDRY VERSION) =====================
import streamlit as st
import pandas as pd
import datetime
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import requests
import urllib.parse

# ================= CONFIG ==================
SPREADSHEET_ID = "1OsnO1xQFniBtEFCvGksR2KKrPt-9idE-w6-poM-wXKU"
SHEET_ORDER = "Order"      # Sheet utama (ganti dari Servis)
SHEET_ADMIN = "Admin"      # Ambil harga laundry dari sheet Admin
CONFIG_FILE = "config.json"
DATA_FILE = "order_data.csv"  # cache lokal

# =============== AUTH GOOGLE ===============
def authenticate_google():
    creds_dict = st.secrets["gcp_service_account"]
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(credentials)
    return client

def get_worksheet(sheet_name):
    client = authenticate_google()
    sh = client.open_by_key(SPREADSHEET_ID)
    return sh.worksheet(sheet_name)

# =============== CONFIG FILE ===============
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {
        "nama_toko": "TR Laundry",
        "alamat": "Jl.Buluh Cina, Panam",
        "telepon": "087899913595"
    }

# =============== REALTIME WIB ===============
@st.cache_data(ttl=300)
def get_cached_internet_date():
    try:
        res = requests.get("https://worldtimeapi.org/api/timezone/Asia/Jakarta", timeout=5)
        if res.status_code == 200:
            data = res.json()
            dt = datetime.datetime.fromisoformat(data["datetime"].replace("Z", "+00:00"))
            return dt
    except Exception as e:
        print("⚠️ Gagal ambil waktu internet:", e)
    return datetime.datetime.now()

# =============== CACHE CSV ===============
def load_local_data():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    return pd.DataFrame(columns=[
        "No Nota", "Tanggal Masuk", "Estimasi Selesai",
        "Nama Pelanggan", "No HP",
        "Jenis Pakaian", "Layanan", "Berat (Kg)", "Harga/kg", "Subtotal",
        "Parfum", "Diskon", "Total", "Jenis Transaksi", "Status", "uploaded"
    ])

def save_local_data(df):
    df.to_csv(DATA_FILE, index=False)

# =============== NOMOR NOTA ===============
def get_next_nota_from_sheet(prefix):
    try:
        ws = get_worksheet(SHEET_ORDER)
        data = ws.col_values(1)
        if len(data) <= 1:
            return f"{prefix}0000001"
        last_nota = None
        for val in reversed(data):
            if val.strip():
                last_nota = val.strip()
                break
        if last_nota and last_nota.startswith(prefix):
            num = int(last_nota.replace(prefix, ""))
        else:
            num = 0
        return f"{prefix}{num+1:07d}"
    except Exception as e:
        print("Error generate nota:", e)
        return f"{prefix}0000001"

# =============== SPREADSHEET OPS ===============
def append_to_sheet(sheet_name, data: dict):
    ws = get_worksheet(sheet_name)
    headers = ws.row_values(1)
    row = [data.get(h, "") for h in headers]
    ws.append_row(row, value_input_option="USER_ENTERED")

@st.cache_data(ttl=120)
def read_admin_harga():
    try:
        ws = get_worksheet(SHEET_ADMIN)
        df = pd.DataFrame(ws.get_all_records())
        return df
    except:
        return pd.DataFrame(columns=["Layanan", "Harga"])

# =============== SYNC CACHE ===============
def sync_local_cache():
    df = load_local_data()
    if df.empty:
        return
    not_uploaded = df[df["uploaded"] == False]
    if not not_uploaded.empty:
        st.info(f"🔁 Upload ulang {len(not_uploaded)} data...")
        for _, row in not_uploaded.iterrows():
            try:
                append_to_sheet(SHEET_ORDER, row.to_dict())
                df.loc[df["No Nota"] == row["No Nota"], "uploaded"] = True
            except Exception as e:
                st.warning(f"Gagal upload {row['No Nota']}: {e}")
        save_local_data(df)
        st.success("✅ Sinkronisasi selesai!")

# =============== PAGE APP ===============
def show():
    cfg = load_config()
    sync_local_cache()
    st.title("🧺 Transaksi Laundry")

    with st.form("form_laundry"):
        waktu_sekarang = get_cached_internet_date()
        tanggal_masuk = waktu_sekarang
        estimasi_selesai = waktu_sekarang + datetime.timedelta(days=3)

        nama = st.text_input("Nama Pelanggan")
        no_hp = st.text_input("Nomor WhatsApp")

        jenis_pakaian = st.selectbox(
            "Jenis Pakaian",
            ["Baju Biasa", "Sprei", "Selimut", "Bed Cover", "Jas", "Jacket", "Sepatu"]
        )
        layanan_list = ["Cuci Lipat", "Cuci Setrika", "Cuci Lipat Express", "Cuci Setrika Express"]
        layanan = st.selectbox("Layanan", layanan_list)

        # Ambil harga default dari Sheet Admin
        admin_df = read_admin_harga()
        harga_default = 0
        if not admin_df.empty and layanan in admin_df["Layanan"].values:
            harga_default = int(admin_df.loc[admin_df["Layanan"] == layanan, "Harga"].values[0])
        harga_per_kg = st.number_input("Harga per Kg", value=float(harga_default), min_value=0.0, format="%.0f")
        berat = st.number_input("Berat (Kg)", min_value=0.0, format="%.2f")

        parfum_list = ["Sakura", "Gardenia", "Lily", "Jasmine", "Violet", "Lavender",
                       "Ocean Fresh", "Snappy", "Sweet Poppy", "Aqua Fresh", "Lainnya..."]
        parfum_pilihan = st.selectbox("Pilih Parfum", parfum_list)
        parfum_manual = ""
        if parfum_pilihan == "Lainnya...":
            parfum_manual = st.text_input("Nama Parfum Lainnya")
        parfum_final = parfum_manual if parfum_manual else parfum_pilihan

        diskon = st.number_input("Diskon (Rp)", min_value=0.0, format="%.0f")
        jenis_transaksi = st.radio("Jenis Transaksi", ["Cash", "Transfer"], horizontal=True)

        subtotal = harga_per_kg * berat
        total = subtotal - diskon
        status = st.selectbox("Status Pembayaran", ["BELUM BAYAR", "LUNAS"])

        st.markdown(f"### 💰 Subtotal: Rp {subtotal:,.0f}   |   Total: Rp {total:,.0f}".replace(",", "."))

        submitted = st.form_submit_button("💾 Simpan Transaksi")

    if submitted:
        if not nama or berat <= 0:
            st.error("Nama pelanggan dan berat wajib diisi!")
            return

        nota = get_next_nota_from_sheet("TRX/")
        tgl_masuk_str = tanggal_masuk.strftime("%d/%m/%Y - %H:%M")
        tgl_estimasi_str = estimasi_selesai.strftime("%d/%m/%Y - %H:%M")

        data_order = {
            "No Nota": nota,
            "Tanggal Masuk": tgl_masuk_str,
            "Estimasi Selesai": tgl_estimasi_str,
            "Nama Pelanggan": nama,
            "No HP": no_hp,
            "Jenis Pakaian": jenis_pakaian,
            "Layanan": layanan,
            "Berat (Kg)": berat,
            "Harga/kg": harga_per_kg,
            "Subtotal": subtotal,
            "Parfum": parfum_final,
            "Diskon": diskon,
            "Total": total,
            "Jenis Transaksi": jenis_transaksi,
            "Status": status,
            "uploaded": False
        }

        df = load_local_data()
        df = pd.concat([df, pd.DataFrame([data_order])], ignore_index=True)
        try:
            append_to_sheet(SHEET_ORDER, data_order)
            df.loc[df["No Nota"] == nota, "uploaded"] = True
            st.success(f"✅ Transaksi Laundry {jenis_pakaian} berhasil disimpan!")
        except Exception as e:
            st.warning(f"⚠️ Gagal upload ke Sheet: {e}. Disimpan lokal dulu.")
        save_local_data(df)

        msg = f"""*NOTA ELEKTRONIK*

{cfg['nama_toko']}
{cfg['alamat']}
HP : {cfg['telepon']}

=======================
No Nota : {nota}

Pelanggan : {nama}
Tanggal Masuk    : {tgl_masuk_str}
Estimasi Selesai : {tgl_estimasi_str}

=======================
- Jenis Pakaian = {jenis_pakaian}
- {berat:.2f} Kg ({layanan})
{berat:.2f} x {harga_per_kg:,.0f} = Rp {subtotal:,.0f}

=======================
Parfum  : {parfum_final}
Status  : {status}

=======================
SubTotal = Rp {subtotal:,.0f}
Diskon   = Rp {diskon:,.0f}
Total    = Rp {total:,.0f}
=======================
"""
        hp = str(no_hp).replace("+", "").replace(" ", "").replace("-", "").strip()
        if hp:
            if hp.startswith("0"): hp = "62" + hp[1:]
            elif not hp.startswith("62"): hp = "62" + hp
            wa_link = f"https://wa.me/{hp}?text={requests.utils.quote(msg)}"
            st.markdown(f"[📲 KIRIM NOTA VIA WHATSAPP]({wa_link})", unsafe_allow_html=True)

if __name__ == "__main__":
    show()
