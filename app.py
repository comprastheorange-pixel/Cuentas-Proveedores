import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import io
import re

# Configuración de la página
st.set_page_config(page_title="Control de Deudas y Presupuesto", page_icon="📈", layout="wide")

# --- CONEXIÓN A BASE DE DATOS Y TABLAS ---
DB_NAME = "proveedores.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Tabla de Compras y Registro de Facturas
    c.execute('''
        CREATE TABLE IF NOT EXISTS compras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            remision TEXT,
            proveedor TEXT,
            fruta TEXT,
            kilos REAL,
            precio_kg REAL,
            total REAL,
            tipo_pago TEXT DEFAULT 'A CRÉDITO'
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
            observacion TEXT,
            remision_asociada TEXT
        )
    ''')
    
    # Migraciones automáticas para columnas faltantes
    c.execute("PRAGMA table_info(compras)")
    columnas_compras = [col[1] for col in c.fetchall()]
    if 'tipo_pago' not in columnas_compras:
        c.execute("ALTER TABLE compras ADD COLUMN tipo_pago TEXT DEFAULT 'A CRÉDITO'")

    c.execute("PRAGMA table_info(pagos)")
    columnas_pagos = [col[1] for col in c.fetchall()]
    if 'observacion' not in columnas_pagos:
        c.execute("ALTER TABLE pagos ADD COLUMN observacion TEXT")
    if 'remision_asociada' not in columnas_pagos:
        c.execute("ALTER TABLE pagos ADD COLUMN remision_asociada TEXT")

    conn.commit()
    conn.close()

init_db()

# --- FUNCIONES AUXILIARES DE BASE DE DATOS ---
def obtener_compras():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM compras ORDER BY fecha DESC, id DESC", conn)
    conn.close()
    if not df.empty and 'tipo_pago' in df.columns:
        df['tipo_pago'] = df['tipo_pago'].fillna('A CRÉDITO')
    return df

def obtener_pagos():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM pagos ORDER BY fecha DESC, id DESC", conn)
    conn.close()
    return df

def generar_siguiente_codigo(prefijo, lista_codigos):
    max_num = 0
    pattern = re.compile(rf'^{prefijo}-(\d+)$', re.IGNORECASE)
    for cod in lista_codigos:
        if cod:
            match = pattern.match(str(cod).strip())
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num
    return f"{prefijo}-{(max_num + 1):03d}"

def insertar_compra(fecha, remision, proveedor, fruta, kilos, precio_kg, total, tipo_pago):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT INTO compras (fecha, remision, proveedor, fruta, kilos, precio_kg, total, tipo_pago)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (fecha, remision, proveedor.strip().upper(), fruta, kilos, precio_kg, total, tipo_pago))
    conn.commit()
    conn.close()

def insertar_pago(fecha, comprobante, proveedor, monto, observacion, remision_asociada):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT INTO pagos (fecha, comprobante, proveedor, monto, observacion, remision_asociada)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (fecha, comprobante, proveedor.strip().upper(), monto, observacion, remision_asociada))
    conn.commit()
    conn.close()

def eliminar_registro(tabla, id_registro):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(f"DELETE FROM {tabla} WHERE id = ?", (id_registro,))
    conn.commit()
    conn.close()

# --- FUNCIONES GENERADORAS DE PDF ---
def generar_pdf_presupuesto_semanal(f_inicio, f_fin, meta, contado, abonos, ejecutado, disponible, df_c_sem, df_p_sem):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(name='TitleStyle', parent=styles['Title'], fontSize=16, leading=20, textColor=colors.HexColor('#1E3A8A'))
    subtitle_style = ParagraphStyle(name='SubTitleStyle', parent=styles['Normal'], fontSize=10, leading=12, textColor=colors.gray)
    h2_style = ParagraphStyle(name='H2Style', parent=styles['Heading2'], fontSize=11, leading=13, textColor=colors.HexColor('#1F2937'))

    story.append(Paragraph("<b>INFORME DE PRESUPUESTO SEMANAL</b>", title_style))
    story.append(Paragraph(f"Período: {f_inicio} al {f_fin} | Fecha Emisión: {datetime.now().strftime('%Y-%m-%d %H:%M')}", subtitle_style))
    story.append(Spacer(1, 15))

    # Resumen Métricas
    data_resumen = [
        ["Meta Asignada", "Compras Contado", "Abonos / Pagos", "Ejecutado Total", "Disponible / Saldo"],
        [f"${meta:,.2f}", f"${contado:,.2f}", f"${abonos:,.2f}", f"${ejecutado:,.2f}", f"${disponible:,.2f}"]
    ]
    t_res = Table(data_resumen, colWidths=[108, 108, 108, 108, 110])
    t_res.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F3F4F6')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
        ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (4,1), (4,1), colors.HexColor('#059669') if disponible >= 0 else colors.HexColor('#DC2626')),
    ]))
    story.append(t_res)
    story.append(Spacer(1, 15))

    # Tabla Compras de Contado
    story.append(Paragraph("<b>Compras de Contado de la Semana</b>", h2_style))
    story.append(Spacer(1, 5))
    if not df_c_sem.empty:
        t_c_data = [["Fecha", "Remisión", "Proveedor", "Concepto", "Total"]]
        for _, r in df_c_sem.iterrows():
            t_c_data.append([
                str(r.get('fecha', '-')),
                str(r.get('remision', '-')),
                str(r.get('proveedor', '-')),
                str(r.get('fruta', '-')),
                f"${r.get('total', 0):,.2f}"
            ])
        t_c = Table(t_c_data, colWidths=[70, 80, 150, 130, 110])
        t_c.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#3B82F6')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('ALIGN', (-1,0), (-1,-1), 'RIGHT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F9FAFB')]),
        ]))
        story.append(t_c)
    else:
        story.append(Paragraph("No hay compras de contado registradas en este período.", styles['Normal']))

    story.append(Spacer(1, 15))

    # Tabla Abonos y Pagos
    story.append(Paragraph("<b>Abonos y Pagos Efectuados en la Semana</b>", h2_style))
    story.append(Spacer(1, 5))
    if not df_p_sem.empty:
        t_p_data = [["Fecha", "Comprobante", "Proveedor", "Factura Asociada", "Monto"]]
        for _, r in df_p_sem.iterrows():
            rem = r.get('remision_asociada', 'General')
            if pd.isna(rem) or str(rem).strip() == '':
                rem = 'General'
            t_p_data.append([
                str(r.get('fecha', '-')),
                str(r.get('comprobante', '-')),
                str(r.get('proveedor', '-')),
                str(rem),
                f"${r.get('monto', 0):,.2f}"
            ])
        t_p = Table(t_p_data, colWidths=[70, 90, 160, 110, 110])
        t_p.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#10B981')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('ALIGN', (-1,0), (-1,-1), 'RIGHT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F9FAFB')]),
        ]))
        story.append(t_p)
    else:
        story.append(Paragraph("No hay abonos ni pagos registrados en este período.", styles['Normal']))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generar_pdf_resumen(df_resumen, total_compra_gen, total_pago_gen, saldo_gen):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(name='TitleStyle', parent=styles['Title'], fontSize=18, leading=22, textColor=colors.HexColor('#1E3A8A'))
    subtitle_style = ParagraphStyle(name='SubTitleStyle', parent=styles['Normal'], fontSize=10, leading=12, textColor=colors.gray)

    story.append(Paragraph("<b>REPORTE GENERAL DE DEUDAS A PROVEEDORES</b>", title_style))
    story.append(Paragraph(f"Fecha de generación: {datetime.now().strftime('%Y-%m-%d %H:%M')}", subtitle_style))
    story.append(Spacer(1, 15))

    data_resumen_box = [
        ["Total Comprado (A Crédito)", "Total Abonado", "Saldo Pendiente Total"],
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

    saldo = total_c - total_p
    data_resumen = [
        ["Total Comprado (A Crédito)", "Total Abonado", "Saldo Pendiente"],
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

    story.append(Paragraph("<b>Registro de Compras / Facturas A Crédito</b>", h2_style))
    story.append(Spacer(1, 5))

    if not df_compras.empty:
        t_compras_data = [["Fecha", "Remisión/Factura", "Ítem/Concepto", "Cantidad", "Precio Unit.", "Total"]]
        for _, r in df_compras.iterrows():
            t_compras_data.append([
                str(r.get('fecha', '-')),
                str(r.get('remision', '-')),
                str(r.get('fruta', '-')),
                f"{r.get('kilos', 0):,}",
                f"${r.get('precio_kg', 0):,.2f}",
                f"${r.get('total', 0):,.2f}"
            ])
        t_c = Table(t_compras_data, colWidths=[70, 90, 100, 80, 90, 110])
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

    story.append(Paragraph("<b>Abonos y Pagos Realizados</b>", h2_style))
    story.append(Spacer(1, 5))

    if not df_pagos.empty:
        t_pagos_data = [["Fecha", "Comprobante", "Factura Aplicada", "Monto", "Observación"]]
        for _, r in df_pagos.iterrows():
            obs = r.get('observacion', '-')
            if pd.isna(obs) or str(obs).strip() == '':
                obs = '-'
            rem = r.get('remision_asociada', 'General')
            if pd.isna(rem) or str(rem).strip() == '':
                rem = 'General'
            t_pagos_data.append([
                str(r.get('fecha', '-')),
                str(r.get('comprobante', '-')),
                str(rem),
                f"${r.get('monto', 0):,.2f}",
                str(obs)
            ])
        t_p = Table(t_pagos_data, colWidths=[70, 90, 110, 100, 170])
        t_p.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#10B981')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('ALIGN', (3,0), (3,-1), 'RIGHT'),
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
    ["📊 Reporte de Deudas (Para el Jefe)", "🎯 Control de Presupuesto Semanal", "📦 Registrar Compra / Factura", "💵 Registrar Pago / Abono", "📜 Historial Detallado", "🗑️ Eliminar Registros"]
)

df_compras = obtener_compras()
df_pagos = obtener_pagos()

# Unificar lista de proveedores limpios en Mayúsculas
provs_c = df_compras['proveedor'].dropna().astype(str).str.strip().str.upper().tolist() if not df_compras.empty else []
provs_p = df_pagos['proveedor'].dropna().astype(str).str.strip().str.upper().tolist() if not df_pagos.empty else []
todos_proveedores = sorted(list(set(provs_c + provs_p)))

# ----------------------------------------------------
# CÁLCULOS DE PRESUPUESTO SEMANAL
# ----------------------------------------------------
hoy = datetime.today().date()
inicio_semana = hoy - timedelta(days=hoy.weekday()) # Lunes de la semana actual
fin_semana = inicio_semana + timedelta(days=6)       # Domingo de la semana actual

# ----------------------------------------------------
# OPCIÓN 1: REPORTE GENERAL DE DEUDAS
# ----------------------------------------------------
if menu == "📊 Reporte de Deudas (Para el Jefe)":
    st.title("📊 Resumen General de Deudas a Proveedores")

    if not todos_proveedores:
        st.info("Aún no se han registrado compras ni pagos en el sistema.")
    else:
        # Filtrar compras únicamente A CRÉDITO para la deuda del proveedor
        df_compras_credito = df_compras[df_compras['tipo_pago'] == 'A CRÉDITO'] if not df_compras.empty else df_compras

        resumen_data = []
        tot_compra_gen = 0
        tot_pago_gen = 0

        for prov in todos_proveedores:
            c_p = df_compras_credito[df_compras_credito['proveedor'].astype(str).str.strip().str.upper() == prov]['total'].sum() if not df_compras_credito.empty else 0
            p_p = df_pagos[df_pagos['proveedor'].astype(str).str.strip().str.upper() == prov]['monto'].sum() if not df_pagos.empty else 0
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

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Crédito Comprado", f"${tot_compra_gen:,.2f}")
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

        df_mostrar = df_resumen.copy()
        df_mostrar['Total Comprado'] = df_mostrar['Total Comprado'].apply(lambda x: f"${x:,.2f}")
        df_mostrar['Total Abonado'] = df_mostrar['Total Abonado'].apply(lambda x: f"${x:,.2f}")
        df_mostrar['Saldo Pendiente'] = df_mostrar['Saldo Pendiente'].apply(lambda x: f"${x:,.2f}")

        st.dataframe(df_mostrar, use_container_width=True)

# ----------------------------------------------------
# OPCIÓN 2: CONTROL DE PRESUPUESTO SEMANAL
# ----------------------------------------------------
elif menu == "🎯 Control de Presupuesto Semanal":
    st.title("🎯 Medidor de Presupuesto Semanal para Fruta / Insumos")

    col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
    with col_f1:
        f_inicio = st.date_input("Fecha Inicio de Semana", inicio_semana)
    with col_f2:
        f_fin = st.date_input("Fecha Fin de Semana", fin_semana)
    with col_f3:
        presupuesto_limite = st.number_input("Presupuesto Semanal Asignado ($)", min_value=100.0, value=10000.0, step=1000.0)

    # Convertir fechas a string para comparar
    str_f_inicio = str(f_inicio)
    str_f_fin = str(f_fin)

    # 1. Compras de Contado de la semana
    df_c_sem = pd.DataFrame()
    if not df_compras.empty:
        df_c_sem = df_compras[
            (df_compras['tipo_pago'] == 'DE CONTADO') & 
            (df_compras['fecha'] >= str_f_inicio) & 
            (df_compras['fecha'] <= str_f_fin)
        ]
        compras_contado_sem = df_c_sem['total'].sum()
    else:
        compras_contado_sem = 0.0

    # 2. Pagos/Abonos realizados en la semana
    df_p_sem = pd.DataFrame()
    if not df_pagos.empty:
        df_p_sem = df_pagos[
            (df_pagos['fecha'] >= str_f_inicio) & 
            (df_pagos['fecha'] <= str_f_fin)
        ]
        pagos_sem = df_p_sem['monto'].sum()
    else:
        pagos_sem = 0.0

    total_ejecutado = compras_contado_sem + pagos_sem
    diferencia = presupuesto_limite - total_ejecutado
    porcentaje_usado = min(total_ejecutado / presupuesto_limite, 1.0) if presupuesto_limite > 0 else 1.0
    pct_real = (total_ejecutado / presupuesto_limite * 100) if presupuesto_limite > 0 else 100

    col_title, col_dl = st.columns([3, 1])
    with col_title:
        st.markdown("### 📊 Estado Actual del Presupuesto")

    with col_dl:
        # Generar PDF para el presupuesto semanal
        pdf_presupuesto_bytes = generar_pdf_presupuesto_semanal(
            str_f_inicio, str_f_fin, presupuesto_limite,
            compras_contado_sem, pagos_sem, total_ejecutado, diferencia,
            df_c_sem, df_p_sem
        )
        
        st.download_button(
            label="📄 Descargar Informe Presupuesto (PDF)",
            data=pdf_presupuesto_bytes,
            file_name=f"Presupuesto_Semanal_{str_f_inicio}_al_{str_f_fin}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    # Mostrar barra de progreso con alerta según nivel
    st.progress(porcentaje_usado)

    if total_ejecutado > presupuesto_limite:
        st.error(f"🚨 **¡PRESUPUESTO EXCEDIDO!** Has sobrepasado la meta en **${abs(diferencia):,.2f}** ({pct_real:.1f}% gastado).")
    elif pct_real >= 80:
        st.warning(f"⚠️ **ALERTA DE CAJA:** Has consumido el **{pct_real:.1f}%** de tu presupuesto semanal. Te quedan **${diferencia:,.2f}**.")
    else:
        st.success(f"✅ **DENTRO DEL MARGEN:** Has ejecutado el **{pct_real:.1f}%** del presupuesto semanal. Dispones de **${diferencia:,.2f}**.")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Meta Semanal", f"${presupuesto_limite:,.2f}")
    m2.metric("Compras Contado (Semana)", f"${compras_contado_sem:,.2f}")
    m3.metric("Abonos / Pagos (Semana)", f"${pagos_sem:,.2f}")
    m4.metric("Ejecutado Total", f"${total_ejecutado:,.2f}", delta=f"${diferencia:,.2f} disponible", delta_color="normal" if diferencia >= 0 else "inverse")

    st.markdown("---")

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.subheader("🛒 Compras de Contado de esta Semana")
        if not df_c_sem.empty:
            df_c_sem_d = df_c_sem[['fecha', 'remision', 'proveedor', 'fruta', 'total']].copy()
            df_c_sem_d['total'] = df_c_sem_d['total'].apply(lambda x: f"${x:,.2f}")
            st.dataframe(df_c_sem_d, use_container_width=True)
        else:
            st.info("No hay compras de contado registradas en este rango de fechas.")

    with col_t2:
        st.subheader("💵 Abonos / Pagos Efectuados esta Semana")
        if not df_p_sem.empty:
            df_p_sem_d = df_p_sem[['fecha', 'comprobante', 'proveedor', 'remision_asociada', 'monto']].copy()
            df_p_sem_d['monto'] = df_p_sem_d['monto'].apply(lambda x: f"${x:,.2f}")
            st.dataframe(df_p_sem_d, use_container_width=True)
        else:
            st.info("No hay pagos registrados en este rango de fechas.")

# ----------------------------------------------------
# OPCIÓN 3: REGISTRAR COMPRA / FACTURA
# ----------------------------------------------------
elif menu == "📦 Registrar Compra / Factura":
    st.title("📦 Registrar Compra o Insumo")

    # Calcular consecutivo de Factura FC-xxx
    lista_remisiones = df_compras['remision'].tolist() if not df_compras.empty else []
    siguiente_fc = generar_siguiente_codigo("FC", lista_remisiones)

    col_tipo, col_prov = st.columns([2, 3])
    with col_tipo:
        tipo_pago_sel = st.selectbox("Modalidad de Pago:", ["A CRÉDITO", "DE CONTADO"], help="De Contado afecta el presupuesto semanal de inmediato. A Crédito suma a la deuda del proveedor.")

    with col_prov:
        opcion_prov = st.radio("¿Cómo deseas ingresar el proveedor?", ["Escribir nombre (Nuevo o Existente)", "Seleccionar de la lista de existentes"], horizontal=True)

    if opcion_prov == "Seleccionar de la lista de existentes" and todos_proveedores:
        proveedor_seleccionado = st.selectbox("Proveedor Existente:", todos_proveedores)
    else:
        proveedor_seleccionado = st.text_input("Nombre del Proveedor (Escribe libremente):")

    with st.form("form_compra", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            fecha = st.date_input("Fecha de Factura / Registro", datetime.today())
            remision = st.text_input("Número de Remisión / Factura", value=siguiente_fc)
            
        with col2:
            fruta = st.text_input("Ítem / Concepto (Ej: Fruta, Periódico, Bolsas, Empaques)").strip().upper()
            kilos = st.number_input("Cantidad / Kilos", min_value=0.0, step=0.1)
            precio_kg = st.number_input("Precio Unitario / Precio por Kilo ($)", min_value=0.0, step=50.0)

        total_calculado = kilos * precio_kg
        st.write(f"**Total Compra Calculado ({tipo_pago_sel}):** ${total_calculado:,.2f}")

        submitted = st.form_submit_button("Guardar Registro de Compra")
        if submitted:
            prov_final = proveedor_seleccionado.strip().upper() if proveedor_seleccionado else ""
            if not prov_final or not remision or not fruta or kilos <= 0 or precio_kg <= 0:
                st.error("Por favor completa todos los campos correctamente.")
            else:
                insertar_compra(str(fecha), remision, prov_final, fruta, kilos, precio_kg, total_calculado, tipo_pago_sel)
                st.success(f"¡Compra [{tipo_pago_sel}] guardada con éxito para {prov_final}! Número: {remision} | Total: ${total_calculado:,.2f}")
                st.rerun()

# ----------------------------------------------------
# OPCIÓN 4: REGISTRAR PAGO / ABONO
# ----------------------------------------------------
elif menu == "💵 Registrar Pago / Abono":
    st.title("💵 Registrar Pago o Abono a Proveedor")

    # Calcular consecutivo de Pago RP-xxx
    lista_comprobantes = df_pagos['comprobante'].tolist() if not df_pagos.empty else []
    siguiente_rp = generar_siguiente_codigo("RP", lista_comprobantes)

    opcion_prov_pago = st.radio("¿Cómo deseas ingresar el proveedor?", ["Escribir nombre (Nuevo o Existente)", "Seleccionar de la lista de existentes"], horizontal=True, key="pago_radio")

    if opcion_prov_pago == "Seleccionar de la lista de existentes" and todos_proveedores:
        proveedor_pago_sel = st.selectbox("Proveedor Existente:", todos_proveedores, key="pago_select")
    else:
        proveedor_pago_sel = st.text_input("Nombre del Proveedor (Escribe libremente):", key="pago_text")

    prov_pago_limpio = proveedor_pago_sel.strip().upper() if proveedor_pago_sel else ""

    # Búsqueda de facturas del proveedor únicamente A CRÉDITO
    opciones_facturas = ["General / Sin Factura Específica"]
    if prov_pago_limpio and not df_compras.empty:
        df_c_prov = df_compras[
            (df_compras['proveedor'].astype(str).str.strip().str.upper() == prov_pago_limpio) & 
            (df_compras['tipo_pago'] == 'A CRÉDITO')
        ]
        for _, row in df_c_prov.iterrows():
            rem = str(row['remision'])
            tot = row['total']
            if not df_pagos.empty and 'remision_asociada' in df_pagos.columns:
                df_p_prov = df_pagos[df_pagos['proveedor'].astype(str).str.strip().str.upper() == prov_pago_limpio]
                abono_previo = df_p_prov[df_p_prov['remision_asociada'].astype(str) == rem]['monto'].sum()
            else:
                abono_previo = 0
            saldo_rem = tot - abono_previo
            opciones_facturas.append(f"Factura: {rem} | Total: ${tot:,.2f} | Saldo Pendiente: ${saldo_rem:,.2f}")

    factura_seleccionada = st.selectbox("Aplicar abono a Factura/Remisión específica:", opciones_facturas)

    with st.form("form_pago", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            fecha = st.date_input("Fecha de Pago", datetime.today())
            comprobante = st.text_input("Número de Comprobante / Transferencia", value=siguiente_rp)

        with col2:
            monto = st.number_input("Monto Abonado ($)", min_value=0.0, step=1000.0)
            observacion = st.text_area("Observaciones / Notas")

        submitted = st.form_submit_button("Guardar Pago / Abono")
        if submitted:
            if not prov_pago_limpio or monto <= 0:
                st.error("Por favor ingresa un proveedor válido y un monto mayor a cero.")
            else:
                remision_final = "General"
                if "Factura: " in factura_seleccionada:
                    remision_final = factura_seleccionada.split("|")[0].replace("Factura:", "").strip()

                insertar_pago(str(fecha), comprobante, prov_pago_limpio, monto, observacion, remision_final)
                st.success(f"¡Pago de ${monto:,.2f} registrado con éxito para {prov_pago_limpio} (Comp: {comprobante} | Factura: {remision_final})!")
                st.rerun()

# ----------------------------------------------------
# OPCIÓN 5: HISTORIAL DETALLADO
# ----------------------------------------------------
elif menu == "📜 Historial Detallado":
    st.title("📜 Historial Detallado de Transacciones")

    col_select, col_pdf = st.columns([2, 2])

    with col_select:
        prov_seleccionado = st.selectbox("Seleccionar Proveedor:", ["Todos"] + todos_proveedores)

    if prov_seleccionado == "Todos":
        df_c = df_compras[df_compras['tipo_pago'] == 'A CRÉDITO'].copy() if not df_compras.empty else df_compras
        df_p = df_pagos.copy()
    else:
        df_c = df_compras[(df_compras['proveedor'].astype(str).str.strip().str.upper() == prov_seleccionado) & (df_compras['tipo_pago'] == 'A CRÉDITO')].copy() if not df_compras.empty else df_compras
        df_p = df_pagos[df_pagos['proveedor'].astype(str).str.strip().str.upper() == prov_seleccionado].copy() if not df_pagos.empty else df_pagos

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

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Comprado A Crédito", f"${tot_compras:,.2f}")
    c2.metric("Total Abonado", f"${tot_pagos:,.2f}")
    c3.metric("Saldo Pendiente Global", f"${saldo:,.2f}")

    st.markdown("---")

    st.subheader(f"📦 Estado de Facturas y Remisiones A Crédito ({prov_seleccionado})")
    if not df_c.empty:
        df_c_disp = df_c.copy()
        
        abonos_por_factura = []
        saldos_por_factura = []
        
        for _, row in df_c_disp.iterrows():
            rem = str(row['remision'])
            prov = str(row['proveedor']).strip().upper()
            if not df_p.empty and 'remision_asociada' in df_p.columns:
                df_p_prov = df_p[df_p['proveedor'].astype(str).str.strip().str.upper() == prov]
                abono_f = df_p_prov[df_p_prov['remision_asociada'].astype(str) == rem]['monto'].sum()
            else:
                abono_f = 0
            saldo_f = row['total'] - abono_f
            abonos_por_factura.append(abono_f)
            saldos_por_factura.append(saldo_f)

        df_c_disp['Total Abonado'] = abonos_por_factura
        df_c_disp['Saldo Factura'] = saldos_por_factura

        df_c_disp['precio_kg'] = df_c_disp['precio_kg'].apply(lambda x: f"${x:,.2f}")
        df_c_disp['total'] = df_c_disp['total'].apply(lambda x: f"${x:,.2f}")
        df_c_disp['Total Abonado'] = df_c_disp['Total Abonado'].apply(lambda x: f"${x:,.2f}")
        df_c_disp['Saldo Factura'] = df_c_disp['Saldo Factura'].apply(lambda x: f"${x:,.2f}")
        
        df_c_disp = df_c_disp.rename(columns={
            'fruta': 'item_concepto',
            'kilos': 'cantidad_kilos',
            'precio_kg': 'precio_unitario',
            'remision': 'factura_remision',
            'total': 'valor_factura'
        })
        cols_c = [c for c in ['fecha', 'factura_remision', 'proveedor', 'item_concepto', 'cantidad_kilos', 'precio_unitario', 'valor_factura', 'Total Abonado', 'Saldo Factura'] if c in df_c_disp.columns]
        st.dataframe(df_c_disp[cols_c], use_container_width=True)
    else:
        st.info("No hay compras ni facturas a crédito registradas.")

    st.subheader(f"💵 Historial de Abonos y Pagos ({prov_seleccionado})")
    if not df_p.empty:
        df_p_disp = df_p.copy()
        df_p_disp['monto'] = df_p_disp['monto'].apply(lambda x: f"${x:,.2f}")
        if 'remision_asociada' not in df_p_disp.columns:
            df_p_disp['remision_asociada'] = 'General'
        df_p_disp['remision_asociada'] = df_p_disp['remision_asociada'].fillna('General')
        df_p_disp = df_p_disp.rename(columns={'remision_asociada': 'factura_asociada'})
        cols_p = [c for c in ['fecha', 'comprobante', 'proveedor', 'factura_asociada', 'monto', 'observacion'] if c in df_p_disp.columns]
        st.dataframe(df_p_disp[cols_p], use_container_width=True)
    else:
        st.info("No hay pagos registrados.")

# ----------------------------------------------------
# OPCIÓN 6: ELIMINAR REGISTROS
# ----------------------------------------------------
elif menu == "🗑️ Eliminar Registros":
    st.title("🗑️ Eliminar Registros Incorrectos")
    st.warning("Cuidado: Al borrar un registro se actualizarán automáticamente las cuentas y deudas.")

    tipo_eliminar = st.radio("¿Qué deseas eliminar?", ["Compra / Factura", "Pago / Abono"])

    if tipo_eliminar == "Compra / Factura":
        if not df_compras.empty:
            df_compras['etiqueta'] = df_compras.apply(lambda r: f"ID: {r['id']} | Fecha: {r['fecha']} | Prov: {r['proveedor']} | Tipo: {r.get('tipo_pago', 'A CRÉDITO')} | Total: ${r['total']:,.2f} | Remisión: {r['remision']}", axis=1)
            opcion = st.selectbox("Selecciona la compra a eliminar:", df_compras['etiqueta'].tolist())
            id_eliminar = int(opcion.split("|")[0].replace("ID:", "").strip())

            if st.button("Confirmar y Eliminar Compra", type="primary"):
                eliminar_registro("compras", id_eliminar)
                st.success("Compra eliminada correctamente.")
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