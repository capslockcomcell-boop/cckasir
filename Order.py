# ===================== ORDER.PY (Laundry v1.1) =====================
import streamlit as st
import pandas as pd
import datetime
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import requests
import urllib.parse

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

def get_worksheet(sheet_name):
    client = authenticate_google()
    sh = client.open_by_key(SPREADSHEET_ID)
    return sh.worksheet(sheet_name)

# ============ CONFIG TOKO ============
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {
        "nama_toko": "TR Laundry",
        "alamat": "Jl.Buluh Cina, Panam",
        "telepon": "087899913595"
    }

# ============ WIB TANGGAL ============
@st.cache_data(ttl=300)
def get_cached_internet_datetime():
    """
    Mengambil waktu sekarang dari internet (Asia/Jakarta).
    Jika gagal, fallback ke waktu lokal server.
    """
    try:
        res = requests.get("https://worldtimeapi.org/api/timezone/Asia/Jakarta", timeout=5)
        if res.status_code == 200:
            data = res.json()
            # API returns ISO datetime with offset; normalize for fromisoformat
            dt = datetime.datetime.fromisoformat(data["datetime"].replace("Z", "+00:00"))
            return dt
    except Exception:
        # silent fail, gunakan lokal
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
    except Exception as e:
        print("Error nota:", e)
        return f"{prefix}0000001"

# ============ HARGA LAYANAN ============
@st.cache_data(ttl=120)
def get_admin_prices():
    """
    Kembalikan dict: { "Jenis Layanan": Harga per Kg, ... }
    Sumber: Sheet "Admin"
    """
    ws = get_worksheet(SHEET_ADMIN)
    df = pd.DataFrame(ws.get_all_records())
    # hati-hati jika sheet kosong
    if df.empty:
        return {}
    # pastikan kolom sesuai
    if "Jenis Layanan" not in df.columns or "Harga per Kg" not in df.columns:
        return {}
    harga_dict = {row["Jenis Layanan"]: row["Harga per Kg"] for _, row in df.iterrows()}
    return harga_dict

# ============ SIMPAN ORDER ============
def append_to_sheet(sheet_name, data: dict):
    """
    Menambahkan baris ke sheet sesuai urutan header yang ada.
    Jika kolom 'Status Antrian' belum ada, akan ditambahkan.
    """
    ws = get_worksheet(sheet_name)
    headers = ws.row_values(1)

    # Pastikan kolom Status Antrian ada
    if "Status Antrian" not in headers:
        ws.update_cell(1, len(headers) + 1, "Status Antrian")
        headers.append("Status Antrian")

    # Set default Status Antrian jadi "Antrian" jika belum ada
    data.setdefault("Status Antrian", "Antrian")

    # Susun row berdasarkan headers (kolom kosong bila key tidak ada)
    row = [data.get(h, "") for h in headers]
    ws.append_row(row, value_input_option="USER_ENTERED")

# ============ UI ============
def show():
    cfg = load_config()
    st.title("🧺 Transaksi Laundry")

    # Ambil waktu terkini (cached)
    now = get_cached_internet_datetime()

    # Tanggal input masih ada, tapi jam dihilangkan dari form.
    tanggal_masuk = st.date_input("Tanggal Masuk", value=now.date())
    estimasi_selesai = st.date_input("Estimasi Selesai", value=(now + datetime.timedelta(days=3)).date())

    # Jam otomatis (di background) diambil dari `now`
    jam_otomatis = now.strftime("%H:%M")

    nama = st.text_input("Nama Pelanggan")
    no_hp = st.text_input("Nomor WhatsApp")

    jenis_pakaian = st.selectbox(
        "Jenis Pakaian",
        ["Baju Biasa", "Sprei", "Selimut", "Bed Cover", "Jas", "Jacket", "Sepatu"]
    )

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
        # Validasi
        if not nama or not no_hp or berat <= 0 or harga_per_kg <= 0:
            st.error("⚠️ Nama, No HP, berat, dan harga harus diisi.")
            return

        # Nomor nota
        nota = get_next_nota_from_sheet(SHEET_ORDER, "TRX/")

        # Gunakan jam otomatis di sini
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
            # "Status Antrian" otomatis ditambahkan di append_to_sheet()
        }

        try:
            append_to_sheet(SHEET_ORDER, order_data)
            st.success(f"✅ Transaksi Laundry {nota} berhasil disimpan!")
        except Exception as e:
            st.error(f"❌ Gagal simpan ke Google Sheet: {e}")
            return

        # === Nota WA ===
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
        # Normalisasi nomor HP untuk format wa.me (62...)
        hp = str(no_hp).replace("+", "").replace(" ", "").replace("-", "")
        if hp.startswith("0"):
            hp = "62" + hp[1:]
        elif not hp.startswith("62"):
            hp = "62" + hp
        wa_link = f"https://wa.me/{hp}?text={requests.utils.quote(msg)}"
        st.markdown(f"[📲 KIRIM NOTA VIA WHATSAPP]({wa_link})", unsafe_allow_html=True)

if __name__ == "__main__":
    show()
