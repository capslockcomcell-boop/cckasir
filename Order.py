# ===================== ORDER.PY (Laundry v1.1) - with Print Receipt =====================
import streamlit as st
import pandas as pd
import datetime
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import requests
import urllib.parse
from Setting import load_config

# ============ KONFIGURASI ============
SPREADSHEET_ID = "1v_3sXsGw9lNmGPSbIHytYzHzPTxa4yp4HhfS9tgXweA"
SHEET_ORDER = "Order"
SHEET_ADMIN = "Admin"
CONFIG_FILE = "config.json"

# ============ AUTH GOOGLE ============
def authenticate_google():
    creds_dict = st.secrets["gcp_service_account"]
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(credentials)
    return client

# ============ FUNCTION TO GET WORKSHEET ============
def get_worksheet(sheet_name):
    client = authenticate_google()
    sh = client.open_by_key(SPREADSHEET_ID)
    return sh.worksheet(sheet_name)

# ============ WIB TANGGAL ============
@st.cache_data(ttl=300)
def get_cached_internet_datetime():
    try:
        res = requests.get("https://worldtimeapi.org/api/timezone/Asia/Jakarta", timeout=5)
        if res.status_code == 200:
            data = res.json()
            dt = datetime.datetime.fromisoformat(data["datetime"].replace("Z", "+00:00"))
            return dt
    except Exception:
        pass
    return datetime.datetime.now()

# ============ NOMOR NOTA ============
def get_next_nota_from_sheet(sheet_name, prefix):
    try:
        ws = get_worksheet(sheet_name)
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
    except Exception:
        return f"{prefix}0000001"

# ============ HARGA LAYANAN ============
@st.cache_data(ttl=120)
def get_admin_prices():
    ws = get_worksheet(SHEET_ADMIN)
    df = pd.DataFrame(ws.get_all_records())
    if df.empty:
        return {}
    if "Jenis Layanan" not in df.columns or "Harga per Kg" not in df.columns:
        return {}
    return {row["Jenis Layanan"]: row["Harga per Kg"] for _, row in df.iterrows()}

# ============ SIMPAN ORDER ============
def append_to_sheet(sheet_name, data: dict):
    ws = get_worksheet(sheet_name)
    headers = ws.row_values(1)
    if "Status Antrian" not in headers:
        ws.update_cell(1, len(headers) + 1, "Status Antrian")
        headers.append("Status Antrian")
    data.setdefault("Status Antrian", "Antrian")
    row = [data.get(h, "") for h in headers]
    ws.append_row(row, value_input_option="USER_ENTERED")

# ============ UI ============
def show():
    cfg = load_config()
    st.title("🧺 Transaksi Laundry")
    now = get_cached_internet_datetime()
    tanggal_masuk = st.date_input("Tanggal Masuk", value=now.date())
    estimasi_selesai = st.date_input("Estimasi Selesai", value=(now + datetime.timedelta(days=3)).date())
    jam_otomatis = now.strftime("%H:%M")
    nama = st.text_input("Nama Pelanggan")
    no_hp = st.text_input("Nomor WhatsApp")
    jenis_pakaian = st.selectbox("Jenis Pakaian", ["Baju Biasa", "Sprei", "Selimut", "Bed Cover", "Jas", "Jacket", "Sepatu"])
    layanan_list = ["Cuci Lipat", "Cuci Setrika", "Cuci Lipat Express", "Cuci Setrika Express"]
    jenis_layanan = st.selectbox("Jenis Layanan", layanan_list)
    admin_harga = get_admin_prices()
    harga_default = admin_harga.get(jenis_layanan, 0)
    harga_per_kg = st.number_input("Harga per Kg", value=float(harga_default), min_value=0.0, step=500.0, format="%.0f")
    st.subheader("Berat Pakaian")
    kg = st.number_input("Kg", min_value=0, step=1)
    gram = st.number_input("Gram", min_value=0, max_value=999, step=50)
    berat = kg + gram / 1000
    st.markdown(f"**Berat total:** {berat:.2f} Kg")
    parfum_list = ["Sakura", "Gardenia", "Lily", "Jasmine", "Violet", "Lavender", "Ocean Fresh", "Snappy", "Sweet Poppy", "Aqua Fresh"]
    parfum_pilihan = st.selectbox("Pilih Parfum", parfum_list)
    parfum_custom = st.text_input("Parfum Custom (opsional)")
    parfum_final = parfum_custom if parfum_custom else parfum_pilihan
    diskon = st.number_input("Diskon (Rp)", min_value=0.0, step=100.0)
    jenis_transaksi = st.radio("Jenis Transaksi", ["Cash", "Transfer"], horizontal=True)
    status = st.radio("Status Pembayaran", ["BELUM BAYAR", "LUNAS"], horizontal=True)
    subtotal = berat * harga_per_kg
    total = subtotal - diskon
    st.markdown(f"### 💰 Total: Rp {total:,.0f}".replace(",", "."))
    if st.button("💾 Simpan Transaksi"):
        if not nama or not no_hp or berat <= 0 or harga_per_kg <= 0:
            st.error("⚠️ Nama, No HP, berat, dan harga harus diisi.")
            return
        nota = get_next_nota_from_sheet(SHEET_ORDER, "TRX/")
        tanggal_masuk_str = f"{tanggal_masuk.strftime('%d/%m/%Y')} - {jam_otomatis}"
        estimasi_selesai_str = f"{estimasi_selesai.strftime('%d/%m/%Y')} - {jam_otomatis}"
        order_data = {
            "No Nota": nota,
            "Tanggal Masuk": tanggal_masuk_str,
            "Estimasi Selesai": estimasi_selesai_str,
            "Nama Pelanggan": nama,
            "No HP": no_hp,
            "Jenis Pakaian": jenis_pakaian,
            "Jenis Layanan": jenis_layanan,
            "Berat (Kg)": berat,
            "Harga per Kg": harga_per_kg,
            "Subtotal": subtotal,
            "Diskon": diskon,
            "Total": total,
            "Parfum": parfum_final,
            "Jenis Transaksi": jenis_transaksi,
            "Status": status,
            "Uploaded": True
        }
        try:
            append_to_sheet(SHEET_ORDER, order_data)
            st.success(f"✅ Transaksi Laundry {nota} berhasil disimpan!")
        except Exception as e:
            st.error(f"❌ Gagal simpan ke Google Sheet: {e}")
            return
        msg = f"""NOTA ELEKTRONIK
{cfg['nama_toko']}
{cfg['alamat']}
HP : {cfg['telepon']}
=======================
No Nota : {nota}
Pelanggan : {nama}
Tanggal Masuk    : {tanggal_masuk_str}
Estimasi Selesai : {estimasi_selesai_str}
=======================
- Jenis Pakaian = {jenis_pakaian}
- Kiloan ({jenis_layanan})
{berat:.2f} Kg x {harga_per_kg:,.0f} = Rp {subtotal:,.0f}
=======================
Parfum  : {parfum_final}
Status  : {status}
=======================
SubTotal = Rp {subtotal:,.0f}
Diskon   = Rp {diskon:,.0f}
Total    = Rp {total:,.0f}
=======================
Terima kasih 🙏
"""
        hp = str(no_hp).replace("+", "").replace(" ", "").replace("-", "")
        if hp.startswith("0"):
            hp = "62" + hp[1:]
        elif not hp.startswith("62"):
            hp = "62" + hp
        wa_link = f"https://wa.me/{hp}?text={requests.utils.quote(msg)}"
        st.markdown(f"[📲 KIRIM NOTA VIA WHATSAPP]({wa_link})", unsafe_allow_html=True)

if __name__ == "__main__":
    show()
