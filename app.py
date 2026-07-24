import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ----------------------------------------------------
# CONFIGURACIÓN DE PÁGINA
# ----------------------------------------------------
st.set_page_config(
    page_title="The Oranges - Control de Compras y Bodega",
    page_icon="🍊",
    layout="wide"
)

st.title("🍊 Sistema de Control de Compras, Bodega y Presupuesto")

# ----------------------------------------------------
# BASE DE DATOS LOCAL (SQLITE)
# ----------------------------------------------------
DB_NAME = "compras_oranges.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Tabla de Planeación Semanal
    c.execute("""
    CREATE TABLE IF NOT EXISTS programacion_semanal (
        id_programacion INTEGER PRIMARY KEY AUTOINCREMENT,
        id_semana TEXT NOT NULL,
        fecha_inicio DATE NOT NULL,
        fecha_fin DATE NOT NULL,
        fruta TEXT NOT NULL,
        proveedor TEXT NOT NULL,
        cantidad_pactada REAL NOT NULL,
        precio_pactado REAL NOT NULL
    )
    """)
    
    # 2. Tabla de Ingresos / Entradas a Bodega
    c.execute("""
    CREATE TABLE IF NOT EXISTS ingresos_bodega (
        id_ingreso INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha_ingreso DATE NOT NULL,
        factura_ds TEXT,
        id_semana_ref TEXT NOT NULL,
        fruta TEXT NOT NULL,
        proveedor TEXT NOT NULL,
        cantidad_pactada REAL NOT NULL,
        precio_pactado REAL NOT NULL,
        ingreso_bodega REAL NOT NULL,
        precio_final REAL NOT NULL,
        tipo_pago TEXT DEFAULT 'A CRÉDITO',
        conductor TEXT,
        observaciones TEXT
    )
    """)

    # 3. Tabla de Pagos / Abonos
    c.execute("""
    CREATE TABLE IF NOT EXISTS pagos_proveedores (
        id_pago INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha_pago DATE NOT NULL,
        comprobante TEXT NOT NULL,
        proveedor TEXT NOT NULL,
        remision_asociada TEXT,
        monto REAL NOT NULL,
        notas TEXT
    )
    """)

    # 4. Tabla de Configuración (Presupuesto persistente)
    c.execute("""
    CREATE TABLE IF NOT EXISTS configuracion (
        clave TEXT PRIMARY KEY,
        valor REAL
    )
    """)

    # Inicializar presupuesto límite si no existe
    c.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES ('presupuesto_limite', 10000.0)")

    conn.commit()
    conn.close()

init_db()

# Cargar presupuesto desde SQLite al session_state
if 'presupuesto_limite' not in st.session_state:
    conn = sqlite3.connect(DB_NAME)
    res = conn.cursor().execute("SELECT valor FROM configuracion WHERE clave='presupuesto_limite'").fetchone()
    conn.close()
    st.session_state['presupuesto_limite'] = res[0] if res else 10000.0

def actualizar_presupuesto_db():
    nuevo_val = st.session_state['presupuesto_limite']
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE configuracion SET valor = ? WHERE clave = 'presupuesto_limite'", (nuevo_val,))
    conn.commit()
    conn.close()

LISTA_FRUTAS = [
    "CHULUPA", "FRESA", "GUANABANA", "GUAYABA", "LIMON",
    "LULO", "MANGO", "MARACUYA", "MORA", "NARANJA",
    "PIÑA", "TOMATE ARBOL", "UVA"
]

# ----------------------------------------------------
# FUNCIONES GENERADORAS DE REPORTES PDF
# ----------------------------------------------------
def generar_pdf_presupuesto_semanal(f_ini, f_fin, presupuesto, compras_contado, pagos, ejecutado, diferencia, df_c, df_p):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()

    story.append(Paragraph(f"<b>Control de Presupuesto Semanal ({f_ini} al {f_fin})</b>", styles['Heading1']))
    story.append(Spacer(1, 10))

    data_res = [
        ["Presupuesto Meta", "Compras Contado", "Abonos/Pagos", "Ejecutado Total", "Disponible"],
        [f"${presupuesto:,.2f}", f"${compras_contado:,.2f}", f"${pagos:,.2f}", f"${ejecutado:,.2f}", f"${diferencia:,.2f}"]
    ]
    t_res = Table(data_res, colWidths=[108, 108, 108, 108, 108])
    t_res.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
    ]))
    story.append(t_res)
    story.append(Spacer(1, 15))

    story.append(Paragraph("<b>Entradas de Contado en la Semana</b>", styles['Heading2']))
    if not df_c.empty:
        data_c = [["Fecha", "Factura/DS", "Proveedor", "Fruta", "Total"]]
        for _, r in df_c.iterrows():
            data_c.append([str(r['fecha_ingreso']), str(r['factura_ds']), str(r['proveedor']), str(r['fruta']), f"${r['total_pagar']:,.2f}"])
        t_c = Table(data_c, colWidths=[80, 90, 150, 110, 110])
        t_c.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#334155")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ]))
        story.append(t_c)
    else:
        story.append(Paragraph("Sin compras de contado registradas en el rango.", styles['Normal']))

    story.append(Spacer(1, 15))

    story.append(Paragraph("<b>Abonos / Pagos Efectuados en la Semana</b>", styles['Heading2']))
    if not df_p.empty:
        data_p = [["Fecha", "Comprobante", "Proveedor", "Remisión Asoc.", "Monto"]]
        for _, r in df_p.iterrows():
            data_p.append([str(r['fecha_pago']), str(r['comprobante']), str(r['proveedor']), str(r['remision_asociada']), f"${r['monto']:,.2f}"])
        t_p = Table(data_p, colWidths=[80, 100, 150, 110, 100])
        t_p.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0D9488")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ]))
        story.append(t_p)
    else:
        story.append(Paragraph("Sin pagos registrados en el rango.", styles['Normal']))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# ----------------------------------------------------
# INTERFAZ POR PESTAÑAS (WORKFLOW COMPLETO)
# ----------------------------------------------------
tab1, tab2, tab3 = st.tabs([
    "📋 Planeación Semanal (Compras)",
    "🚚 Recepción de Fruta (Bodega)",
    "📊 Control, Conciliación y Presupuesto"
])

# ----------------------------------------------------
# PESTAÑA 1: PLANEACIÓN SEMANAL
# ----------------------------------------------------
with tab1:
    st.header("Programación de Compra Semanal")
    
    with st.form("form_planeacion", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            id_semana = st.text_input("ID de la Semana", placeholder="SEM-2026-29")
            fruta = st.selectbox("Fruta a Programar", LISTA_FRUTAS)
        with col2:
            fecha_inicio = st.date_input("Fecha Inicio de Semana")
            proveedor = st.text_input("Nombre del Proveedor")
        with col3:
            fecha_fin = st.date_input("Fecha Fin de Semana")
            cantidad_pactada = st.number_input("Cantidad Pactada (Kg)", min_value=0.0, step=10.0)
            precio_pactado = st.number_input("Precio Pactado por Kg ($)", min_value=0.0, step=50.0)

        submitted = st.form_submit_button("Guardar Programación")

        if submitted:
            if id_semana and proveedor and cantidad_pactada > 0 and precio_pactado > 0:
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                c.execute("""
                INSERT INTO programacion_semanal (id_semana, fecha_inicio, fecha_fin, fruta, proveedor, cantidad_pactada, precio_pactado)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (id_semana, fecha_inicio, fecha_fin, fruta, proveedor.strip().title(), cantidad_pactada, precio_pactado))
                conn.commit()
                conn.close()
                st.success(f"✅ Programación para {fruta} ({proveedor}) registrada exitosamente.")
            else:
                st.error("⚠️ Por favor completa todos los campos con valores válidos.")

    st.subheader("Planeaciones Registradas")
    conn = sqlite3.connect(DB_NAME)
    df_plan = pd.read_sql_query("SELECT id_semana, fecha_inicio, fecha_fin, fruta, proveedor, cantidad_pactada, precio_pactado, (cantidad_pactada * precio_pactado) as total_proyectado FROM programacion_semanal", conn)
    conn.close()

    if not df_plan.empty:
        st.dataframe(df_plan, use_container_width=True)
    else:
        st.info("No hay programaciones cargadas en la base de datos.")


# ----------------------------------------------------
# PESTAÑA 2: RECEPCIÓN DE BODEGA
# ----------------------------------------------------
with tab2:
    st.header("Registro de Ingresos a Bodega")

    conn = sqlite3.connect(DB_NAME)
    df_plan_ref = pd.read_sql_query("SELECT DISTINCT id_semana, fruta, proveedor, cantidad_pactada, precio_pactado FROM programacion_semanal", conn)
    conn.close()

    if df_plan_ref.empty:
        st.warning("⚠️ No hay programaciones semanales registradas. Se debe ingresar la planeación antes de recibir la fruta.")
    else:
        opciones_ref = df_plan_ref.apply(lambda r: f"{r['id_semana']} | {r['fruta']} - {r['proveedor']}", axis=1).tolist()
        seleccion = st.selectbox("Selecciona la Programación Semanal de Referencia", opciones_ref)
        
        fila_sel = df_plan_ref.iloc[opciones_ref.index(seleccion)]

        with st.form("form_bodega", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                fecha_ingreso = st.date_input("Fecha de Ingreso a Bodega")
                factura_ds = st.text_input("Número de Factura / Documento Soporte")
                ingreso_bodega = st.number_input("Cantidad Real Ingresada a Bodega (Kg)", min_value=0.0, step=10.0)
                precio_final = st.number_input("Precio Final Cobrado por Kg ($)", min_value=0.0, value=float(fila_sel['precio_pactado']), step=50.0)
            
            with col2:
                tipo_pago = st.selectbox("Tipo de Pago", ["A CRÉDITO", "DE CONTADO"])
                conductor = st.text_input("Nombre del Conductor / Encargado")
                observaciones = st.text_area("Observaciones / Novedades")

            submitted_bodega = st.form_submit_button("Registrar Entrada a Bodega")

            if submitted_bodega:
                if ingreso_bodega > 0 and precio_final > 0:
                    conn = sqlite3.connect(DB_NAME)
                    c = conn.cursor()
                    c.execute("""
                    INSERT INTO ingresos_bodega 
                    (fecha_ingreso, factura_ds, id_semana_ref, fruta, proveedor, cantidad_pactada, precio_pactado, ingreso_bodega, precio_final, tipo_pago, conductor, observaciones)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        fecha_ingreso, factura_ds, fila_sel['id_semana'], fila_sel['fruta'], 
                        fila_sel['proveedor'], fila_sel['cantidad_pactada'], fila_sel['precio_pactado'], 
                        ingreso_bodega, precio_final, tipo_pago, conductor, observaciones
                    ))
                    conn.commit()
                    conn.close()
                    st.success("✅ Ingreso de fruta registrado permanentemente en la base de datos.")
                else:
                    st.error("⚠️ La cantidad ingresada y el precio deben ser mayores a cero.")


# ----------------------------------------------------
# PESTAÑA 3: CONTROL, CONCILIACIÓN Y PRESUPUESTO
# ----------------------------------------------------
with tab3:
    st.header("📊 Control, Conciliación y Presupuesto Semanal")

    # Modulo de Presupuesto Semanal Persistente
    st.subheader("🎯 Medidor de Presupuesto Semanal")
    
    hoy = datetime.now().date()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    fin_semana = inicio_semana + timedelta(days=6)

    col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
    with col_f1:
        f_inicio = st.date_input("Fecha Inicio de Semana", inicio_semana)
    with col_f2:
        f_fin = st.date_input("Fecha Fin de Semana", fin_semana)
    with col_f3:
        presupuesto_limite = st.number_input(
            "Presupuesto Semanal Asignado ($)", 
            min_value=100.0, 
            step=1000.0,
            key="presupuesto_limite",
            on_change=actualizar_presupuesto_db
        )

    str_f_inicio = str(f_inicio)
    str_f_fin = str(f_fin)

    conn = sqlite3.connect(DB_NAME)
    
    # Entradas de Contado de la semana
    df_c_sem = pd.read_sql_query(
        "SELECT fecha_ingreso, factura_ds, proveedor, fruta, (ingreso_bodega * precio_final) as total_pagar "
        "FROM ingresos_bodega WHERE tipo_pago = 'DE CONTADO' AND fecha_ingreso >= ? AND fecha_ingreso <= ?",
        conn, params=(str_f_inicio, str_f_fin)
    )
    compras_contado_sem = df_c_sem['total_pagar'].sum() if not df_c_sem.empty else 0.0

    # Pagos/Abonos de la semana
    df_p_sem = pd.read_sql_query(
        "SELECT fecha_pago, comprobante, proveedor, remision_asociada, monto "
        "FROM pagos_proveedores WHERE fecha_pago >= ? AND fecha_pago <= ?",
        conn, params=(str_f_inicio, str_f_fin)
    )
    pagos_sem = df_p_sem['monto'].sum() if not df_p_sem.empty else 0.0

    conn.close()

    total_ejecutado = compras_contado_sem + pagos_sem
    diferencia = presupuesto_limite - total_ejecutado
    porcentaje_usado = min(total_ejecutado / presupuesto_limite, 1.0) if presupuesto_limite > 0 else 1.0
    pct_real = (total_ejecutado / presupuesto_limite * 100) if presupuesto_limite > 0 else 100

    col_title, col_dl = st.columns([3, 1])
    with col_title:
        st.progress(porcentaje_usado)

    with col_dl:
        pdf_bytes = generar_pdf_presupuesto_semanal(
            str_f_inicio, str_f_fin, presupuesto_limite,
            compras_contado_sem, pagos_sem, total_ejecutado, diferencia,
            df_c_sem, df_p_sem
        )
        st.download_button(
            label="📄 Descargar Informe (PDF)",
            data=pdf_bytes,
            file_name=f"Presupuesto_{str_f_inicio}_al_{str_f_fin}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    if total_ejecutado > presupuesto_limite:
        st.error(f"🚨 **¡PRESUPUESTO EXCEDIDO!** Sobrepasado en **${abs(diferencia):,.2f}** ({pct_real:.1f}% ejecutado).")
    elif pct_real >= 80:
        st.warning(f"⚠️ **ALERTA DE CAJA:** Consumido el **{pct_real:.1f}%**. Te quedan **${diferencia:,.2f}**.")
    else:
        st.success(f"✅ **DENTRO DEL MARGEN:** Ejecutado **{pct_real:.1f}%**. Dispones de **${diferencia:,.2f}**.")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Meta Semanal", f"${presupuesto_limite:,.2f}")
    m2.metric("Compras Contado", f"${compras_contado_sem:,.2f}")
    m3.metric("Abonos / Pagos", f"${pagos_sem:,.2f}")
    m4.metric("Ejecutado Total", f"${total_ejecutado:,.2f}", delta=f"${diferencia:,.2f} disponible", delta_color="normal" if diferencia >= 0 else "inverse")

    st.markdown("---")

    # Tabla general de Conciliación de Fruta
    st.subheader("📑 Registros Históricos de Bodega y Desviaciones")
    conn = sqlite3.connect(DB_NAME)
    df_ingresos = pd.read_sql_query(
        "SELECT fecha_ingreso, factura_ds, id_semana_ref, fruta, proveedor, cantidad_pactada, "
        "precio_pactado, ingreso_bodega, precio_final, tipo_pago, (ingreso_bodega * precio_final) as total_pagar "
        "FROM ingresos_bodega", conn
    )
    conn.close()

    if not df_ingresos.empty:
        df_ingresos['merma_kg'] = df_ingresos['cantidad_pactada'] - df_ingresos['ingreso_bodega']
        st.dataframe(df_ingresos, use_container_width=True)
    else:
        st.info("Aún no hay registros de bodega para consultar.")