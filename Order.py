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
import streamlit.components.v1 as components

# ============ KONFIGURASI ============
SPREADSHEET_ID = "1v_3sXsGw9lNmGPSbIHytYzHzPTxa4yp4HhfS9tgXweA"
SHEET_ORDER = "Order"
SHEET_ADMIN = "Admin"
CONFIG_FILE = "config.json"

# ============ AUTH GOOGLE ============
def authenticate_google():
    creds_dict = st.secrets.get("gcp_service_account")
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

# ============ ESC/POS BLUETOOTH PRINT HELPERS ============
# We'll try to use python-escpos Serial backend for Bluetooth (pyserial required).
try:
    from escpos.printer import Serial as EscposSerial
    ESC_POS_AVAILABLE = True
except Exception:
    ESC_POS_AVAILABLE = False


def print_via_escpos_serial(devfile, lines, baudrate=9600, cut=True):
    """Print list of lines via escpos Serial backend. devfile example: 'COM5' or '/dev/rfcomm0'"""
    if not ESC_POS_AVAILABLE:
        raise RuntimeError("python-escpos not installed on server")
    p = None
    try:
        p = EscposSerial(devfile=devfile, baudrate=baudrate, timeout=1)
        for ln in lines:
            p.text(str(ln) + "
")
        if cut:
            try:
                p.cut()
            except Exception:
                pass
    finally:
        try:
            if p:
                if hasattr(p, 'close'):
                    p.close()
        except Exception:
            pass


def build_order_print_lines(cfg, order_data, now_dt):
    # approx 32-36 chars per line for 57mm
    lines = []
    lines.append(cfg.get('nama_toko', '').center(32))
    lines.append(cfg.get('alamat', ''))
    lines.append('HP: ' + cfg.get('telepon', ''))
    lines.append('-' * 32)
    lines.append(f"No Nota : {order_data.get('No Nota')}")
    # split tanggal if contains ' - ' (we store date - time)
    tanggal = order_data.get('Tanggal Masuk', '')
    lines.append(f"Tgl: {tanggal}")
    lines.append(f"Nama: {order_data.get('Nama Pelanggan')}")
    lines.append('-' * 32)
    lines.append(f"Jenis Pakaian: {order_data.get('Jenis Pakaian')}")
    lines.append(f"Layanan      : {order_data.get('Jenis Layanan')}")
    berat = order_data.get('Berat (Kg)', 0)
    harga = order_data.get('Harga per Kg', 0)
    try:
        berat_str = f"{float(berat):.2f} Kg"
    except Exception:
        berat_str = str(berat)
    lines.append(f"Berat: {berat_str}")
    try:
        lines.append(f"Harga/Kg: Rp {float(harga):,.0f}")
    except Exception:
        lines.append(f"Harga/Kg: {harga}")
    lines.append(f"Subtotal: Rp {float(order_data.get('Subtotal',0)) :,.0f}")
    lines.append(f"Diskon  : Rp {float(order_data.get('Diskon',0)) :,.0f}")
    lines.append('-' * 32)
    lines.append(f"TOTAL   : Rp {float(order_data.get('Total',0)) :,.0f}")
    lines.append('-' * 32)
    parfum = order_data.get('Parfum','')
    if parfum:
        lines.append(f"Parfum: {parfum}")
    lines.append(f"Status: {order_data.get('Status')}")
    lines.append('-' * 32)
    lines.append('Terima kasih!')
    lines.append(now_dt.strftime('%d/%m/%Y %H:%M'))
    return lines

# ============ UI ============
def show():
    cfg = load_config()
    st.title("🧺 Transaksi Laundry")

    # Printer config UI in sidebar (so user can input COM port if st.secrets not set)
    with st.sidebar.expander("Printer ESC/POS (Bluetooth)", expanded=False):
        st.markdown("Masukkan port Bluetooth printer (contoh: COM5 atau /dev/rfcomm0). Jika kosong, app akan coba membaca dari st.secrets['escpos'].
")
        user_port = st.text_input("Port Printer (Bluetooth)", value="")
        user_baud = st.number_input("Baudrate", value=9600, step=1)
        test_print = st.button("Tes Print (cetak contoh)")

    # determine port from secrets if not provided
    escpos_cfg = None
    try:
        escpos_cfg = st.secrets.get('escpos')
    except Exception:
        escpos_cfg = None

    # prefer user input
    port_to_use = None
    if user_port:
        port_to_use = user_port
    elif escpos_cfg and isinstance(escpos_cfg, dict):
        # allow secrets to contain {'type':'serial','devfile':'COM5','baudrate':9600}
        if escpos_cfg.get('type') in ['serial', 'usb', 'network']:
            if escpos_cfg.get('type') == 'serial':
                port_to_use = escpos_cfg.get('devfile')
                user_baud = int(escpos_cfg.get('baudrate', user_baud))
        elif escpos_cfg.get('devfile'):
            port_to_use = escpos_cfg.get('devfile')

    # show basic status
    if port_to_use:
        st.sidebar.success(f"Printer port: {port_to_use}")
    else:
        st.sidebar.info("Printer port tidak di-set. Masukkan port untuk aktifkan print ESC/POS.")

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

        # === Nota WA (tetap ditampilkan sebagai link) ===
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

        # ===================== PRINT ESC/POS BLUETOOTH (Serial)
        # If ESC/POS available and port configured, try direct serial print (no preview)
        now_dt = datetime.datetime.now()
        if port_to_use and ESC_POS_AVAILABLE:
            try:
                lines = build_order_print_lines(cfg, order_data, now_dt)
                print_via_escpos_serial(port_to_use, lines, baudrate=int(user_baud))
                st.info("🖨️ Nota terkirim ke printer Bluetooth (ESC/POS).")
            except Exception as e:
                st.warning(f"⚠️ Gagal cetak via ESC/POS (Bluetooth): {e}")
                # fallback: render printable HTML (optional) - we avoid showing preview per user request
        else:
            if not ESC_POS_AVAILABLE:
                st.warning("📌 Module 'python-escpos' belum terpasang di server. Tambahkan ke requirements dan install: pip install python-escpos pyserial")
            else:
                st.info("🔌 Port printer Bluetooth belum diset. Masukkan di sidebar atau st.secrets['escpos'] untuk aktifkan printing.")

        # keep original behaviour: (we do not render HTML preview by default to honor 'no preview')

    if 'test_print' in locals() and test_print and port_to_use:
        # allow quick test from sidebar button
        try:
            now_dt = datetime.datetime.now()
            sample = {
                'No Nota': 'TEST/0001',
                'Tanggal Masuk': now_dt.strftime('%d/%m/%Y %H:%M'),
                'Nama Pelanggan': 'Test User',
                'Jenis Pakaian': 'Baju Biasa',
                'Jenis Layanan': 'Cuci Lipat',
                'Berat (Kg)': 1.0,
                'Harga per Kg': 5000,
                'Subtotal': 5000,
                'Diskon': 0,
                'Total': 5000,
                'Parfum': 'Sakura',
                'Status': 'LUNAS'
            }
            lines = build_order_print_lines(cfg, sample, now_dt)
            print_via_escpos_serial(port_to_use, lines, baudrate=int(user_baud))
            st.sidebar.success('Tes print dikirim ke printer')
        except Exception as e:
            st.sidebar.error(f'Tes print gagal: {e}')

if __name__ == "__main__":
    show()
