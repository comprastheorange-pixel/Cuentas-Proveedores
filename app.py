import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from fpdf import FPDF

# --- CONFIGURACIÓN Y BASE DE DATOS ---
st.set_page_config(page_title="Control de Deudas - Proveedores", layout="wide")

def get_connection():
    conn = sqlite3.connect("proveedores.db")
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS compras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            remision TEXT,
            proveedor TEXT,
            fruta TEXT,
            kilos REAL,
            precio_kg REAL,
            total REAL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS pagos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            proveedor TEXT,
            monto REAL,
            comprobante TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- CLASE BASE PARA REPORTES EN PDF ---
class PDFReport(FPDF):
    def __init__(self, titulo):
        super().__init__()
        self.titulo = titulo

    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(30, 58, 138)
        self.cell(0, 8, self.titulo, ln=True, align="C")
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align="C")
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Página {self.page_no()}", align="C")

# --- GENERADORES DE PDF ---
def generar_pdf_resumen(df_resumen, deuda_total):
    pdf = PDFReport("REPORTE DE CUENTAS POR PAGAR A PROVEEDORES")
    pdf.add_page()
    
    pdf.set_fill_color(240, 244, 248)
    pdf.set_draw_color(200, 200, 200)
    pdf.rect(10, 28, 190, 12, style="FD")
    
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(0, 0, 0)
    pdf.set_xy(15, 30)
    pdf.cell(90, 8, "TOTAL DEUDA PENDIENTE:")
    pdf.set_text_color(185, 28, 28)
    pdf.cell(80, 8, f"${deuda_total:,.2f}", align="R")
    pdf.ln(16)
    
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(60, 8, "Proveedor", border=1, fill=True)
    pdf.cell(40, 8, "Total Comprado", border=1, align="R", fill=True)
    pdf.cell(40, 8, "Total Abonado", border=1, align="R", fill=True)
    pdf.cell(50, 8, "Saldo Pendiente", border=1, align="R", fill=True)
    pdf.ln()
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 9)
    
    fill = False
    for _, row in df_resumen.iterrows():
        pdf.set_fill_color(248, 250, 252) if fill else pdf.set_fill_color(255, 255, 255)
        pdf.cell(60, 7, str(row['proveedor']), border=1, fill=fill)
        pdf.cell(40, 7, f"${row['total_compras']:,.2f}", border=1, align="R", fill=fill)
        pdf.cell(40, 7, f"${row['total_pagos']:,.2f}", border=1, align="R", fill=fill)
        
        if row['saldo_pendiente'] > 0:
            pdf.set_text_color(185, 28, 28)
            pdf.set_font("Helvetica", "B", 9)
        else:
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Helvetica", "", 9)
            
        pdf.cell(50, 7, f"${row['saldo_pendiente']:,.2f}", border=1, align="R", fill=fill)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 9)
        pdf.ln()
        fill = not fill
        
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(226, 232, 240)
    pdf.cell(60, 8, "TOTAL GENERAL", border=1, fill=True)
    pdf.cell(40, 8, f"${df_resumen['total_compras'].sum():,.2f}", border=1, align="R", fill=True)
    pdf.cell(40, 8, f"${df_resumen['total_pagos'].sum():,.2f}", border=1, align="R", fill=True)
    pdf.set_text_color(185, 28, 28)
    pdf.cell(50, 8, f"${deuda_total:,.2f}", border=1, align="R", fill=True)
    
    return bytes(pdf.output())

def generar_pdf_historial(df_c, df_p, filtro_prov="Todos", total_compras=0.0, total_pagos=0.0):
    pdf = PDFReport(f"ESTADO DE CUENTA - PROVEEDOR: {filtro_prov.upper()}")
    pdf.add_page()
    
    saldo_pendiente = total_compras - total_pagos
    pdf.set_fill_color(240, 244, 248)
    pdf.set_draw_color(200, 200, 200)
    pdf.rect(10, 28, 190, 14, style="FD")
    
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(0, 0, 0)
    pdf.set_xy(12, 31)
    pdf.cell(60, 8, f"Total Compras: ${total_compras:,.2f}")
    pdf.cell(60, 8, f"Total Abonos: ${total_pagos:,.2f}")
    
    if saldo_pendiente > 0:
        pdf.set_text_color(185, 28, 28)
    else:
        pdf.set_text_color(16, 185, 129)
    pdf.cell(65, 8, f"Saldo Pendiente: ${saldo_pendiente:,.2f}", align="R")
    
    pdf.ln(18)
    
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(30, 58, 138)
    pdf.cell(0, 8, "1. DESPACHOS Y ENTRADAS DE FRUTA", ln=True)
    
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 8)
    
    pdf.cell(22, 7, "Fecha", border=1, fill=True)
    pdf.cell(23, 7, "Remisión", border=1, fill=True)
    pdf.cell(45, 7, "Proveedor", border=1, fill=True)
    pdf.cell(35, 7, "Fruta", border=1, fill=True)
    pdf.cell(20, 7, "Kilos", border=1, align="R", fill=True)
    pdf.cell(22, 7, "Precio/Kg", border=1, align="R", fill=True)
    pdf.cell(23, 7, "Total", border=1, align="R", fill=True)
    pdf.ln()
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 8)
    
    fill = False
    for _, row in df_c.iterrows():
        kilos_val = float(row['kilos'])
        precio_val = float(row['precio_kg'])
        total_val = float(row['total'])
        
        pdf.set_fill_color(248, 250, 252) if fill else pdf.set_fill_color(255, 255, 255)
        pdf.cell(22, 6, str(row['fecha']), border=1, fill=fill)
        pdf.cell(23, 6, str(row['remision']) if row['remision'] else "-", border=1, fill=fill)
        pdf.cell(45, 6, str(row['proveedor'])[:24], border=1, fill=fill)
        pdf.cell(35, 6, str(row['fruta'])[:18], border=1, fill=fill)
        pdf.cell(20, 6, f"{kilos_val:,.1f}", border=1, align="R", fill=fill)
        pdf.cell(22, 6, f"${precio_val:,.0f}", border=1, align="R", fill=fill)
        pdf.cell(23, 6, f"${total_val:,.0f}", border=1, align="R", fill=fill)
        pdf.ln()
        fill = not fill
        
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(226, 232, 240)
    pdf.cell(167, 7, "TOTAL COMPRAS / DESPACHOS", border=1, fill=True, align="R")
    pdf.cell(23, 7, f"${total_compras:,.0f}", border=1, align="R", fill=True)
    pdf.ln(12)
    
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(30, 58, 138)
    pdf.cell(0, 8, "2. ABONOS Y PAGOS REGISTRADOS", ln=True)
    
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 8)
    
    pdf.cell(30, 7, "Fecha", border=1, fill=True)
    pdf.cell(60, 7, "Proveedor", border=1, fill=True)
    pdf.cell(50, 7, "Comprobante", border=1, fill=True)
    pdf.cell(50, 7, "Monto Abonado", border=1, align="R", fill=True)
    pdf.ln()
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 8)
    
    fill = False
    for _, row in df_p.iterrows():
        monto_val = float(row['monto'])
        pdf.set_fill_color(248, 250, 252) if fill else pdf.set_fill_color(255, 255, 255)
        pdf.cell(30, 6, str(row['fecha']), border=1, fill=fill)
        pdf.cell(60, 6, str(row['proveedor'])[:32], border=1, fill=fill)
        pdf.cell(50, 6, str(row['comprobante']) if row['comprobante'] else "-", border=1, fill=fill)
        pdf.cell(50, 6, f"${monto_val:,.0f}", border=1, align="R", fill=fill)
        pdf.ln()
        fill = not fill
        
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(226, 232, 240)
    pdf.cell(140, 7, "TOTAL ABONADO", border=1, fill=True, align="R")
    pdf.cell(50, 7, f"${total_pagos:,.0f}", border=1, align="R", fill=True)
    
    return bytes(pdf.output())

# --- INTERFAZ STREAMLIT ---
st.title("🍓 Control de Cuentas por Pagar a Proveedores")

opcion = st.sidebar.radio("Selecciona una opción:", [
    "📊 Reporte de Deudas (Para el Jefe)",
    "📦 Registrar Entrada de Fruta",
    "💵 Registrar Pago / Abono",
    "📜 Historial Detallado",
    "🗑️ Eliminar Registros"
])

# ----------------------------------------------------
# 1. REPORTE DE DEUDAS
# ----------------------------------------------------
if opcion == "📊 Reporte de Deudas (Para el Jefe)":
    st.header("Resumen de Cuentas por Pagar")
    
    conn = get_connection()
    df_compras = pd.read_sql_query("SELECT proveedor, SUM(total) as total_compras FROM compras GROUP BY proveedor", conn)
    df_pagos = pd.read_sql_query("SELECT proveedor, SUM(monto) as total_pagos FROM pagos GROUP BY proveedor", conn)
    conn.close()

    if not df_compras.empty:
        df_resumen = pd.merge(df_compras, df_pagos, on="proveedor", how="left").fillna(0)
        df_resumen["saldo_pendiente"] = df_resumen["total_compras"] - df_resumen["total_pagos"]

        deuda_total = float(df_resumen["saldo_pendiente"].sum())
        
        col1, col2, col3 = st.columns([2, 2, 2])
        col1.metric("Deuda Total Pendiente", f"${deuda_total:,.2f}")
        col2.metric("Proveedores con Deuda", len(df_resumen[df_resumen["saldo_pendiente"] > 0]))
        
        pdf_bytes = generar_pdf_resumen(df_resumen, deuda_total)
        col3.download_button(
            label="📄 Descargar Resumen General (PDF)",
            data=pdf_bytes,
            file_name=f"Resumen_Deudas_{datetime.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

        st.subheader("Estado por Proveedor")
        
        df_display = df_resumen.copy()
        df_display.columns = ["Proveedor", "Total Comprado ($)", "Total Abonado ($)", "Saldo Pendiente ($)"]
        
        st.dataframe(
            df_display.style.format({
                "Total Comprado ($)": "${:,.2f}",
                "Total Abonado ($)": "${:,.2f}",
                "Saldo Pendiente ($)": "${:,.2f}"
            }),
            use_container_width=True
        )
    else:
        st.info("Aún no hay compras registradas.")

# ----------------------------------------------------
# 2. REGISTRAR ENTRADA DE FRUTA
# ----------------------------------------------------
elif opcion == "📦 Registrar Entrada de Fruta":
    st.header("Ingresar Compra a Crédito")

    with st.form("form_compra", clear_on_submit=True):
        col1, col2 = st.columns(2)
        fecha = col1.date_input("Fecha de Entrada", datetime.now())
        remision = col2.text_input("Número de Remisión / Guía")
        
        proveedor = col1.text_input("Nombre del Proveedor / Agricultor").strip().title()
        fruta = col2.text_input("Tipo de Fruta (ej: Mango, Mora, Maracuyá 1ra)")
        
        kilos = col1.number_input("Kilos Recibidos", min_value=0.0, step=1.0)
        precio_kg = col2.number_input("Precio por Kilo ($)", min_value=0.0, step=50.0)

        guardar = st.form_submit_button("Guardar Entrada")

        if guardar:
            if proveedor and kilos > 0 and precio_kg > 0:
                total = kilos * precio_kg
                conn = get_connection()
                c = conn.cursor()
                c.execute(
                    "INSERT INTO compras (fecha, remision, proveedor, fruta, kilos, precio_kg, total) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (str(fecha), remision, proveedor, fruta, kilos, precio_kg, total)
                )
                conn.commit()
                conn.close()
                st.success(f"Entrada registrada con éxito. Total: ${total:,.2f}")
            else:
                st.error("Por favor completa todos los campos requeridos.")

# ----------------------------------------------------
# 3. REGISTRAR PAGO / ABONO
# ----------------------------------------------------
elif opcion == "💵 Registrar Pago / Abono":
    st.header("Registrar Abono a Proveedor")

    conn = get_connection()
    proveedores_df = pd.read_sql_query("SELECT DISTINCT proveedor FROM compras", conn)
    conn.close()

    lista_proveedores = proveedores_df["proveedor"].tolist() if not proveedores_df.empty else []

    if lista_proveedores:
        with st.form("form_pago", clear_on_submit=True):
            col1, col2 = st.columns(2)
            fecha_pago = col1.date_input("Fecha de Pago", datetime.now())
            proveedor_pago = col2.selectbox("Seleccionar Proveedor", lista_proveedores)
            
            monto = col1.number_input("Monto Abonado ($)", min_value=0.0, step=1000.0)
            comprobante = col2.text_input("Número de Comprobante / Transferencia")

            guardar_pago = st.form_submit_button("Registrar Pago")

            if guardar_pago:
                if monto > 0:
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute(
                        "INSERT INTO pagos (fecha, proveedor, monto, comprobante) VALUES (?, ?, ?, ?)",
                        (str(fecha_pago), proveedor_pago, monto, comprobante)
                    )
                    conn.commit()
                    conn.close()
                    st.success(f"Abono de ${monto:,.2f} registrado para {proveedor_pago}.")
                else:
                    st.error("El monto ingresado debe ser mayor a 0.")
    else:
        st.warning("Primero debes registrar entradas de fruta antes de realizar abonos.")

# ----------------------------------------------------
# 4. HISTORIAL DETALLADO
# ----------------------------------------------------
elif opcion == "📜 Historial Detallado":
    st.header("Consulta de Cuentas y Movimientos por Proveedor")
    
    conn = get_connection()
    df_c_all = pd.read_sql_query("SELECT fecha, remision, proveedor, fruta, kilos, precio_kg, total FROM compras ORDER BY id DESC", conn)
    df_p_all = pd.read_sql_query("SELECT fecha, proveedor, monto, comprobante FROM pagos ORDER BY id DESC", conn)
    conn.close()

    if not df_c_all.empty:
        lista_prov = ["Todos"] + sorted(list(df_c_all["proveedor"].unique()))
        
        col_filtro, col_pdf = st.columns([2, 2])
        prov_seleccionado = col_filtro.selectbox("Seleccionar Proveedor:", lista_prov)
        
        if prov_seleccionado != "Todos":
            df_c = df_c_all[df_c_all["proveedor"] == prov_seleccionado]
            df_p = df_p_all[df_p_all["proveedor"] == prov_seleccionado]
        else:
            df_c = df_c_all
            df_p = df_p_all

        tot_compras = float(df_c["total"].sum()) if not df_c.empty else 0.0
        tot_pagos = float(df_p["monto"].sum()) if not df_p.empty else 0.0
        saldo_p = tot_compras - tot_pagos

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Comprado", f"${tot_compras:,.2f}")
        c2.metric("Total Abonado", f"${tot_pagos:,.2f}")
        c3.metric("Saldo Pendiente", f"${saldo_p:,.2f}", delta_color="inverse")

        pdf_historial_bytes = generar_pdf_historial(df_c, df_p, prov_seleccionado, tot_compras, tot_pagos)
        col_pdf.write("")
        col_pdf.write("")
        col_pdf.download_button(
            label=f"📄 Imprimir Estado de Cuenta ({prov_seleccionado})",
            data=pdf_historial_bytes,
            file_name=f"Estado_Cuenta_{prov_seleccionado}_{datetime.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

        st.markdown("---")
        
        st.subheader(f"📦 Entradas de Fruta ({prov_seleccionado})")
        if not df_c.empty:
            st.dataframe(
                df_c.style.format({
                    "kilos": "{:,.1f}",
                    "precio_kg": "${:,.0f}",
                    "total": "${:,.2f}"
                }),
                use_container_width=True
            )
        else:
            st.info("No hay entradas de fruta para este proveedor.")

        st.subheader(f"💵 Abonos y Pagos ({prov_seleccionado})")
        if not df_p.empty:
            st.dataframe(
                df_p.style.format({
                    "monto": "${:,.2f}"
                }),
                use_container_width=True
            )
        else:
            st.info("No hay abonos registrados para este proveedor.")
    else:
        st.info("Aún no hay transacciones registradas.")

# ----------------------------------------------------
# 5. ELIMINAR REGISTROS INCORRECTOS
# ----------------------------------------------------
elif opcion == "🗑️ Eliminar Registros":
    st.header("Eliminar Facturas o Pagos Mal Registrados")
    st.warning("⚠️ Ten precaución: Al eliminar un registro se recalcularán automáticamente las deudas.")

    tipo = st.selectbox("¿Qué deseas eliminar?", ["Entrada de Fruta / Factura", "Pago / Abono"])
    conn = get_connection()

    if tipo == "Entrada de Fruta / Factura":
        df = pd.read_sql_query("SELECT id, fecha, remision, proveedor, fruta, kilos, total FROM compras ORDER BY id DESC", conn)
        if not df.empty:
            st.dataframe(df, use_container_width=True)
            
            # Crear desplegable con el ID y detalles
            opciones_del = [f"ID: {row['id']} | {row['fecha']} | {row['proveedor']} | {row['fruta']} | ${row['total']:,.2f}" for _, row in df.iterrows()]
            seleccion = st.selectbox("Selecciona el registro a eliminar:", opciones_del)
            id_eliminar = int(seleccion.split("|")[0].replace("ID:", "").strip())

            if st.button("🗑️ Eliminar Factura / Entrada"):
                c = conn.cursor()
                c.execute("DELETE FROM compras WHERE id = ?", (id_eliminar,))
                conn.commit()
                conn.close()
                st.success("✅ Registro eliminado correctamente.")
                st.rerun()
        else:
            st.info("No hay entradas registradas.")

    else:
        df = pd.read_sql_query("SELECT id, fecha, proveedor, monto, comprobante FROM pagos ORDER BY id DESC", conn)
        if not df.empty:
            st.dataframe(df, use_container_width=True)
            
            # Crear desplegable con el ID y detalles
            opciones_del = [f"ID: {row['id']} | {row['fecha']} | {row['proveedor']} | ${row['monto']:,.2f}" for _, row in df.iterrows()]
            seleccion = st.selectbox("Selecciona el pago a eliminar:", opciones_del)
            id_eliminar = int(seleccion.split("|")[0].replace("ID:", "").strip())

            if st.button("🗑️ Eliminar Pago / Abono"):
                c = conn.cursor()
                c.execute("DELETE FROM pagos WHERE id = ?", (id_eliminar,))
                conn.commit()
                conn.close()
                st.success("✅ Pago eliminado correctamente.")
                st.rerun()
        else:
            st.info("No hay pagos registrados.")
    
    if conn:
        conn.close()