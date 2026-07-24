import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import io

# Configuración de la página
st.set_page_config(page_title="Control de Deudas - Proveedores", page_icon="📈", layout="wide")

# --- CONEXIÓN A BASE DE DATOS Y TABLAS ---
DB_NAME = "proveedores.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Tabla de Entradas de Fruta (Compras)
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
    # Tabla de Abonos y Pagos
    c.execute('''
        CREATE TABLE IF NOT EXISTS pagos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            comprobante TEXT,
            proveedor TEXT,
            monto REAL,
            observacion TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- FUNCIONES AUXILIARES DE BASE DE DATOS ---
def obtener_compras():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM compras ORDER BY fecha DESC, id DESC", conn)
    conn.close()
    return df

def obtener_pagos():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM pagos ORDER BY fecha DESC, id DESC", conn)
    conn.close()
    return df

def insertar_compra(fecha, remision, proveedor, fruta, kilos, precio_kg, total):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT INTO compras (fecha, remision, proveedor, fruta, kilos, precio_kg, total)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (fecha, remision, proveedor, fruta, kilos, precio_kg, total))
    conn.commit()
    conn.close()

def insertar_pago(fecha, comprobante, proveedor, monto, observacion):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT INTO pagos (fecha, comprobante, proveedor, monto, observacion)
        VALUES (?, ?, ?, ?, ?)
    ''', (fecha, comprobante, proveedor, monto, observacion))
    conn.commit()
    conn.close()

def eliminar_registro(tabla, id_registro):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(f"DELETE FROM {tabla} WHERE id = ?", (id_registro,))
    conn.commit()
    conn.close()

# --- FUNCIONES GENERADORAS DE PDF ---
def generar_pdf_resumen(df_resumen, total_compra_gen, total_pago_gen, saldo_gen):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()

    # Estilos
    title_style = ParagraphStyle(name='TitleStyle', parent=styles['Title'], fontSize=18, leading=22, textColor=colors.HexColor('#1E3A8A'))
    subtitle_style = ParagraphStyle(name='SubTitleStyle', parent=styles['Normal'], fontSize=10, leading=12, textColor=colors.gray)

    # Encabezado
    story.append(Paragraph("<b>REPORTE GENERAL DE DEUDAS A PROVEEDORES</b>", title_style))
    story.append(Paragraph(f"Fecha de generación: {datetime.now().strftime('%Y-%m-%d %H:%M')}", subtitle_style))
    story.append(Spacer(1, 15))

    # Resumen General
    data_resumen_box = [
        ["Total Comprado", "Total Abonado", "Saldo Pendiente Total"],
        [f"${total_compra_gen:,.2f}", f"${total_pago_gen:,.2f}", f"${saldo_gen:,.2f}"]
    ]
    t_resumen = Table(data_resumen_box, colWidths=[180, 180, 180])
    t_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F3F4F6')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#111827')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#E5E7EB')),
        ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (2,1), (2,1), colors.HexColor('#DC2626')),
    ]))
    story.append(t_resumen)
    story.append(Spacer(1, 20))

    # Tabla Detalle por Proveedor
    table_data = [["Proveedor", "Total Comprado", "Total Abonado", "Saldo Pendiente"]]
    for _, row in df_resumen.iterrows():
        table_data.append([
            str(row['Proveedor']),
            f"${row['Total Comprado']:,.2f}",
            f"${row['Total Abonado']:,.2f}",
            f"${row['Saldo Pendiente']:,.2f}"
        ])

    t_tabla = Table(table_data, colWidths=[200, 110, 110, 120])
    t_tabla.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
        ('ALIGN', (0,0), (0,-1), 'LEFT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#D1D5DB')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F9FAFB')]),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_tabla)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generar_pdf_historial(df_compras, df_pagos, proveedor_nombre, total_c, total_p):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(name='TitleStyle', parent=styles['Title'], fontSize=16, leading=20, textColor=colors.HexColor('#1E3A8A'))
    h2_style = ParagraphStyle(name='H2Style', parent=styles['Heading2'], fontSize=12, leading=14, textColor=colors.HexColor('#1F2937'))

    story.append(Paragraph(f"<b>ESTADO DE CUENTA: {proveedor_nombre.upper()}</b>", title_style))
    story.append(Paragraph(f"Fecha de reporte: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
    story.append(Spacer(1, 15))

    # Resumen
    saldo = total_c - total_p
    data_resumen = [
        ["Total Comprado", "Total Abonado", "Saldo Pendiente"],
        [f"${total_c:,.2f}", f"${total_p:,.2f}", f"${saldo:,.2f}"]
    ]
    t_resumen = Table(data_resumen, colWidths=[180, 180, 180])
    t_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F3F4F6')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#E5E7EB')),
        ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (2,1), (2,1), colors.HexColor('#DC2626')),
    ]))
    story.append(t_resumen)
    story.append(Spacer(1, 15))

    # Compras
    story.append(Paragraph("<b>Entradas de Fruta (Compras)</b>", h2_style))
    story.append(Spacer(1, 5))

    if not df_compras.empty:
        t_compras_data = [["Fecha", "Remisión", "Fruta", "Kilos", "Precio/Kg", "Total"]]
        for _, r in df_compras.iterrows():
            t_compras_data.append([
                str(r['fecha']),
                str(r['remision']),
                str(r['fruta']),
                f"{r['kilos']:,}",
                f"${r['precio_kg']:,.2f}",
                f"${r['total']:,.2f}"
            ])
        t_c = Table(t_compras_data, colWidths=[70, 80, 90, 70, 100, 130])
        t_c.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#3B82F6')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('ALIGN', (3,0), (-1,-1), 'RIGHT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F9FAFB')]),
        ]))
        story.append(t_c)
    else:
        story.append(Paragraph("No hay registros de compras.", styles['Normal']))

    story.append(Spacer(1, 15))

    # Pagos
    story.append(Paragraph("<b>Abonos y Pagos Realizados</b>", h2_style))
    story.append(Spacer(1, 5))

    if not df_pagos.empty:
        t_pagos_data = [["Fecha", "Comprobante", "Monto", "Observación"]]
        for _, r in df_pagos.iterrows():
            t_pagos_data.append([
                str(r['fecha']),
                str(r['comprobante']),
                f"${r['monto']:,.2f}",
                str(r['observacion']) if r['observacion'] else "-"
            ])
        t_p = Table(t_pagos_data, colWidths=[80, 100, 120, 240])
        t_p.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#10B981')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('ALIGN', (2,0), (2,-1), 'RIGHT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F9FAFB')]),
        ]))
        story.append(t_p)
    else:
        story.append(Paragraph("No hay registros de pagos.", styles['Normal']))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# --- INTERFAZ DE USUARIO CON STREAMLIT ---
st.sidebar.title("Selecciona una opción:")
menu = st.sidebar.radio(
    "",
    ["📊 Reporte de Deudas (Para el Jefe)", "📦 Registrar Entrada de Fruta", "💵 Registrar Pago / Abono", "📜 Historial Detallado", "🗑️ Eliminar Registros"]
)

df_compras = obtener_compras()
df_pagos = obtener_pagos()

# ----------------------------------------------------
# OPCIÓN 1: REPORTE GENERAL DE DEUDAS
# ----------------------------------------------------
if menu == "📊 Reporte de Deudas (Para el Jefe)":
    st.title("📊 Resumen de Deudas a Proveedores")

    # Lista de proveedores únicos
    provs_compras = df_compras['proveedor'].dropna().unique().tolist() if not df_compras.empty else []
    provs_pagos = df_pagos['proveedor'].dropna().unique().tolist() if not df_pagos.empty else []
    todos_proveedores = sorted(list(set(provs_compras + provs_pagos)))

    if not todos_proveedores:
        st.info("Aún no se han registrado compras ni pagos en el sistema.")
    else:
        resumen_data = []
        tot_compra_gen = 0
        tot_pago_gen = 0

        for prov in todos_proveedores:
            c_p = df_compras[df_compras['proveedor'] == prov]['total'].sum() if not df_compras.empty else 0
            p_p = df_pagos[df_pagos['proveedor'] == prov]['monto'].sum() if not df_pagos.empty else 0
            saldo_p = c_p - p_p

            tot_compra_gen += c_p
            tot_pago_gen += p_p

            resumen_data.append({
                "Proveedor": prov,
                "Total Comprado": c_p,
                "Total Abonado": p_p,
                "Saldo Pendiente": saldo_p
            })

        df_resumen = pd.DataFrame(resumen_data)
        saldo_gen = tot_compra_gen - tot_pago_gen

        # Métricas Principales
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Comprado (Global)", f"${tot_compra_gen:,.2f}")
        c2.metric("Total Abonado (Global)", f"${tot_pago_gen:,.2f}")
        c3.metric("Saldo Pendiente Total", f"${saldo_gen:,.2f}")

        st.markdown("---")

        col_left, col_right = st.columns([3, 1])
        with col_left:
            st.subheader("Detalle Por Proveedor")
        with col_right:
            pdf_bytes = generar_pdf_resumen(df_resumen, tot_compra_gen, tot_pago_gen, saldo_gen)
            st.download_button(
                label="📄 Imprimir Estado de Cuenta (Para el Jefe)",
                data=pdf_bytes,
                file_name=f"Reporte_Deudas_Jefe_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

        # Mostrar tabla de resumen formateada
        df_mostrar = df_resumen.copy()
        df_mostrar['Total Comprado'] = df_mostrar['Total Comprado'].apply(lambda x: f"${x:,.2f}")
        df_mostrar['Total Abonado'] = df_mostrar['Total Abonado'].apply(lambda x: f"${x:,.2f}")
        df_mostrar['Saldo Pendiente'] = df_mostrar['Saldo Pendiente'].apply(lambda x: f"${x:,.2f}")

        st.dataframe(df_mostrar, use_container_width=True)

# ----------------------------------------------------
# OPCIÓN 2: REGISTRAR ENTRADA DE FRUTA
# ----------------------------------------------------
elif menu == "📦 Registrar Entrada de Fruta":
    st.title("📦 Registrar Entrada de Fruta (Compra)")

    with st.form("form_compra", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            fecha = st.date_input("Fecha", datetime.today())
            remision = st.text_input("Número de Remisión / Factura")
            proveedor = st.text_input("Nombre del Proveedor").strip().upper()
        with col2:
            fruta = st.text_input("Tipo de Fruta").strip().upper()
            kilos = st.number_input("Kilos Ingresados", min_value=0.0, step=0.1)
            precio_kg = st.number_input("Precio por Kilo ($)", min_value=0.0, step=50.0)

        total_calculado = kilos * precio_kg
        st.write(f"**Total Compra Calculado:** ${total_calculado:,.2f}")

        submitted = st.form_submit_button("Guardar Entrada de Fruta")
        if submitted:
            if not proveedor or not remision or kilos <= 0 or precio_kg <= 0:
                st.error("Por favor completa todos los campos correctamente.")
            else:
                insertar_compra(str(fecha), remision, proveedor, fruta, kilos, precio_kg, total_calculado)
                st.success(f"¡Entrada guardada con éxito! Total: ${total_calculado:,.2f}")
                st.rerun()

# ----------------------------------------------------
# OPCIÓN 3: REGISTRAR PAGO / ABONO
# ----------------------------------------------------
elif menu == "💵 Registrar Pago / Abono":
    st.title("💵 Registrar Pago o Abono a Proveedor")

    # Obtener lista existente de proveedores
    provs_compras = df_compras['proveedor'].dropna().unique().tolist() if not df_compras.empty else []
    provs_pagos = df_pagos['proveedor'].dropna().unique().tolist() if not df_pagos.empty else []
    todos_proveedores = sorted(list(set(provs_compras + provs_pagos)))

    with st.form("form_pago", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            fecha = st.date_input("Fecha de Pago", datetime.today())
            comprobante = st.text_input("Número de Comprobante / Transferencia")
            
            if todos_proveedores:
                opcion_prov = st.radio("Seleccionar Proveedor:", ["Elegir existente", "Escribir nuevo"])
                if opcion_prov == "Elegir existente":
                    proveedor = st.selectbox("Proveedor", todos_proveedores)
                else:
                    proveedor = st.text_input("Nombre del Nuevo Proveedor").strip().upper()
            else:
                proveedor = st.text_input("Nombre del Proveedor").strip().upper()

        with col2:
            monto = st.number_input("Monto Abonado ($)", min_value=0.0, step=1000.0)
            observacion = st.text_area("Observaciones / Notas")

        submitted = st.form_submit_button("Guardar Pago / Abono")
        if submitted:
            if not proveedor or monto <= 0:
                st.error("Por favor ingresa un proveedor válido y un monto mayor a cero.")
            else:
                insertar_pago(str(fecha), comprobante, proveedor, monto, observacion)
                st.success(f"¡Pago de ${monto:,.2f} registrado con éxito para {proveedor}!")
                st.rerun()

# ----------------------------------------------------
# OPCIÓN 4: HISTORIAL DETALLADO
# ----------------------------------------------------
elif menu == "📜 Historial Detallado":
    st.title("📜 Historial Detallado de Transacciones")

    provs_compras = df_compras['proveedor'].dropna().unique().tolist() if not df_compras.empty else []
    provs_pagos = df_pagos['proveedor'].dropna().unique().tolist() if not df_pagos.empty else []
    todos_proveedores = sorted(list(set(provs_compras + provs_pagos)))

    col_select, col_pdf = st.columns([2, 2])

    with col_select:
        prov_seleccionado = st.selectbox("Seleccionar Proveedor:", ["Todos"] + todos_proveedores)

    # Filtrar dataframes
    if prov_seleccionado == "Todos":
        df_c = df_compras.copy()
        df_p = df_pagos.copy()
    else:
        df_c = df_compras[df_compras['proveedor'] == prov_seleccionado].copy()
        df_p = df_pagos[df_pagos['proveedor'] == prov_seleccionado].copy()

    tot_compras = df_c['total'].sum() if not df_c.empty else 0
    tot_pagos = df_p['monto'].sum() if not df_p.empty else 0
    saldo = tot_compras - tot_pagos

    with col_pdf:
        pdf_historial_bytes = generar_pdf_historial(df_c, df_p, prov_seleccionado, tot_compras, tot_pagos)
        st.download_button(
            label=f"📄 Imprimir Estado de Cuenta ({prov_seleccionado})",
            data=pdf_historial_bytes,
            file_name=f"Estado_Cuenta_{prov_seleccionado}_{datetime.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    # Métricas
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Comprado", f"${tot_compras:,.2f}")
    c2.metric("Total Abonado", f"${tot_pagos:,.2f}")
    c3.metric("Saldo Pendiente", f"${saldo:,.2f}")

    st.markdown("---")

    st.subheader(f"📦 Entradas de Fruta ({prov_seleccionado})")
    if not df_c.empty:
        df_c_disp = df_c.copy()
        df_c_disp['precio_kg'] = df_c_disp['precio_kg'].apply(lambda x: f"${x:,.2f}")
        df_c_disp['total'] = df_c_disp['total'].apply(lambda x: f"${x:,.2f}")
        st.dataframe(df_c_disp[['fecha', 'remision', 'proveedor', 'fruta', 'kilos', 'precio_kg', 'total']], use_container_width=True)
    else:
        st.info("No hay entradas de fruta registradas.")

    st.subheader(f"💵 Abonos y Pagos ({prov_seleccionado})")
    if not df_p.empty:
        df_p_disp = df_p.copy()
        df_p_disp['monto'] = df_p_disp['monto'].apply(lambda x: f"${x:,.2f}")
        st.dataframe(df_p_disp[['fecha', 'comprobante', 'proveedor', 'monto', 'observacion']], use_container_width=True)
    else:
        st.info("No hay pagos registrados.")

# ----------------------------------------------------
# OPCIÓN 5: ELIMINAR REGISTROS
# ----------------------------------------------------
elif menu == "🗑️ Eliminar Registros":
    st.title("🗑️ Eliminar Registros Incorrectos")
    st.warning("Cuidado: Al borrar un registro se actualizarán automáticamente las cuentas y deudas.")

    tipo_eliminar = st.radio("¿Qué deseas eliminar?", ["Entrada de Fruta (Compra)", "Pago / Abono"])

    if tipo_eliminar == "Entrada de Fruta (Compra)":
        if not df_compras.empty:
            df_compras['etiqueta'] = df_compras.apply(lambda r: f"ID: {r['id']} | Fecha: {r['fecha']} | Prov: {r['proveedor']} | Total: ${r['total']:,.2f} | Remisión: {r['remision']}", axis=1)
            opcion = st.selectbox("Selecciona la entrada a eliminar:", df_compras['etiqueta'].tolist())
            id_eliminar = int(opcion.split("|")[0].replace("ID:", "").strip())

            if st.button("Confirmar y Eliminar Compra", type="primary"):
                eliminar_registro("compras", id_eliminar)
                st.success("Entrada de fruta eliminada correctamente.")
                st.rerun()
        else:
            st.info("No hay compras para eliminar.")

    else:
        if not df_pagos.empty:
            df_pagos['etiqueta'] = df_pagos.apply(lambda r: f"ID: {r['id']} | Fecha: {r['fecha']} | Prov: {r['proveedor']} | Monto: ${r['monto']:,.2f} | Comp: {r['comprobante']}", axis=1)
            opcion = st.selectbox("Selecciona el pago a eliminar:", df_pagos['etiqueta'].tolist())
            id_eliminar = int(opcion.split("|")[0].replace("ID:", "").strip())

            if st.button("Confirmar y Eliminar Pago", type="primary"):
                eliminar_registro("pagos", id_eliminar)
                st.success("Pago/Abono eliminado correctamente.")
                st.rerun()
        else:
            st.info("No hay pagos para eliminar.")