import streamlit as st
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
    page_title="Gestión de Compras y Presupuesto",
    page_icon="📦",
    layout="wide"
)

# ----------------------------------------------------
# INICIALIZACIÓN DE LA SESIÓN (PERSISTENCIA DE DATOS)
# ----------------------------------------------------
if 'presupuesto_limite' not in st.session_state:
    st.session_state['presupuesto_limite'] = 10000.0

if 'df_compras' not in st.session_state:
    st.session_state['df_compras'] = pd.DataFrame(columns=[
        'fecha', 'remision', 'proveedor', 'fruta', 'kilos', 'precio_kilo', 'tipo_pago', 'total'
    ])

if 'df_pagos' not in st.session_state:
    st.session_state['df_pagos'] = pd.DataFrame(columns=[
        'fecha', 'comprobante', 'proveedor', 'remision_asociada', 'monto', 'notas'
    ])

df_compras = st.session_state['df_compras']
df_pagos = st.session_state['df_pagos']

# ----------------------------------------------------
# FUNCIONES AUXILIARES PARA GENERAR PDFs
# ----------------------------------------------------
def generar_pdf_estado_cuenta(proveedor, compras_prov, pagos_prov, saldo):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor("#1E3A8A"),
        spaceAfter=10
    )
    
    story.append(Paragraph(f"Informe de Estado de Cuenta: {proveedor}", title_style))
    story.append(Paragraph(f"Fecha del informe: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
    story.append(Spacer(1, 15))

    # Resumen
    data_resumen = [
        ["Total Compras a Crédito", "Total Pagados / Abonos", "Saldo Pendiente"],
        [f"${compras_prov['total'].sum():,.2f}", f"${pagos_prov['monto'].sum():,.2f}", f"${saldo:,.2f}"]
    ]
    t_resumen = Table(data_resumen, colWidths=[180, 180, 180])
    t_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#3B82F6")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#EFF6FF")),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
    ]))
    story.append(t_resumen)
    story.append(Spacer(1, 20))

    # Tabla Compras
    story.append(Paragraph("<b>Detalle de Compras (Crédito)</b>", styles['Heading2']))
    if not compras_prov.empty:
        data_c = [["Fecha", "Remisión", "Fruta", "Kilos", "Total"]]
        for _, r in compras_prov.iterrows():
            data_c.append([str(r['fecha']), str(r['remision']), str(r['fruta']), f"{r['kilos']:,.2f}", f"${r['total']:,.2f}"])
        t_c = Table(data_c, colWidths=[90, 100, 150, 90, 110])
        t_c.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E293B")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#94A3B8")),
            ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
        ]))
        story.append(t_c)
    else:
        story.append(Paragraph("No hay registros de compras a crédito.", styles['Normal']))

    story.append(Spacer(1, 15))

    # Tabla Pagos
    story.append(Paragraph("<b>Detalle de Abonos / Pagos</b>", styles['Heading2']))
    if not pagos_prov.empty:
        data_p = [["Fecha", "Comprobante", "Remisión Asoc.", "Monto"]]
        for _, r in pagos_prov.iterrows():
            data_p.append([str(r['fecha']), str(r['comprobante']), str(r['remision_asociada']), f"${r['monto']:,.2f}"])
        t_p = Table(data_p, colWidths=[100, 120, 150, 170])
        t_p.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F766E")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#94A3B8")),
            ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
        ]))
        story.append(t_p)
    else:
        story.append(Paragraph("No hay registros de pagos para este proveedor.", styles['Normal']))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generar_pdf_presupuesto_semanal(f_ini, f_fin, presupuesto, compras_contado, pagos, ejecutado, diferencia, df_c, df_p):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()

    story.append(Paragraph(f"Control de Presupuesto Semanal ({f_ini} al {f_fin})", styles['Heading1']))
    story.append(Spacer(1, 10))

    # Resumen
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

    # Compras de Contado
    story.append(Paragraph("<b>Compras de Contado en la Semana</b>", styles['Heading2']))
    if not df_c.empty:
        data_c = [["Fecha", "Remisión", "Proveedor", "Fruta", "Total"]]
        for _, r in df_c.iterrows():
            data_c.append([str(r['fecha']), str(r['remision']), str(r['proveedor']), str(r['fruta']), f"${r['total']:,.2f}"])
        t_c = Table(data_c, colWidths=[80, 90, 150, 110, 110])
        t_c.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#334155")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ]))
        story.append(t_c)
    else:
        story.append(Paragraph("Sin compras de contado en el rango.", styles['Normal']))

    story.append(Spacer(1, 15))

    # Pagos de la Semana
    story.append(Paragraph("<b>Abonos / Pagos Efectuados en la Semana</b>", styles['Heading2']))
    if not df_p.empty:
        data_p = [["Fecha", "Comprobante", "Proveedor", "Remisión Asoc.", "Monto"]]
        for _, r in df_p.iterrows():
            data_p.append([str(r['fecha']), str(r['comprobante']), str(r['proveedor']), str(r['remision_asociada']), f"${r['monto']:,.2f}"])
        t_p = Table(data_p, colWidths=[80, 100, 150, 110, 100])
        t_p.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0D9488")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ]))
        story.append(t_p)
    else:
        story.append(Paragraph("Sin pagos en el rango.", styles['Normal']))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# ----------------------------------------------------
# BARRA LATERAL - NAVEGACIÓN Y REGISTRO DE DATOS
# ----------------------------------------------------
st.sidebar.title("📌 Menú Principal")
menu = st.sidebar.radio(
    "Selecciona una opción:",
    ["📊 Resumen de Saldos por Proveedor", "🎯 Control de Presupuesto Semanal", "📝 Registrar Compra / Pago"]
)

# Cálculo de rango de la semana actual
hoy = datetime.now().date()
inicio_semana = hoy - timedelta(days=hoy.weekday())
fin_semana = inicio_semana + timedelta(days=6)


# ----------------------------------------------------
# OPCIÓN 1: RESUMEN DE SALDOS POR PROVEEDOR
# ----------------------------------------------------
if menu == "📊 Resumen de Saldos por Proveedor":
    st.title("📊 Resumen de Cuentas por Pagar a Proveedores")

    if df_compras.empty:
        st.info("No hay registros de compras registrados aún.")
    else:
        # Filtrar solo compras a crédito
        compras_credito = df_compras[df_compras['tipo_pago'] == 'A CRÉDITO']
        
        # Obtener lista de proveedores
        proveedores = sorted(list(set(df_compras['proveedor'].unique())))
        
        selected_prov = st.selectbox("Selecciona un Proveedor para ver detalle:", proveedores)

        if selected_prov:
            c_prov = compras_credito[compras_credito['proveedor'] == selected_prov]
            p_prov = df_pagos[df_pagos['proveedor'] == selected_prov]

            tot_compras = c_prov['total'].sum()
            tot_pagos = p_prov['monto'].sum()
            saldo = tot_compras - tot_pagos

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Compras Crédito", f"${tot_compras:,.2f}")
            col2.metric("Total Abonado", f"${tot_pagos:,.2f}")
            col3.metric("Saldo Pendiente", f"${saldo:,.2f}")
            
            with col4:
                pdf_bytes = generar_pdf_estado_cuenta(selected_prov, c_prov, p_prov, saldo)
                st.download_button(
                    label="📄 Descargar Estado de Cuenta (PDF)",
                    data=pdf_bytes,
                    file_name=f"Estado_Cuenta_{selected_prov}.pdf",
                    mime="application/pdf"
                )

            st.markdown("---")
            col_left, col_right = st.columns(2)

            with col_left:
                st.subheader("📋 Compras a Crédito")
                st.dataframe(c_prov[['fecha', 'remision', 'fruta', 'kilos', 'total']], use_container_width=True)

            with col_right:
                st.subheader("💵 Abonos / Pagos")
                st.dataframe(p_prov[['fecha', 'comprobante', 'remision_asociada', 'monto']], use_container_width=True)


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
        # Guardado en sesión mediante key="presupuesto_limite"
        presupuesto_limite = st.number_input(
            "Presupuesto Semanal Asignado ($)", 
            min_value=100.0, 
            step=1000.0,
            key="presupuesto_limite"
        )

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
# OPCIÓN 3: REGISTRAR COMPRA / PAGO
# ----------------------------------------------------
elif menu == "📝 Registrar Compra / Pago":
    st.title("📝 Formulario de Registro")

    tab1, tab2 = st.tabs(["🛒 Registrar Nueva Compra", "💵 Registrar Pago / Abono"])

    with tab1:
        with st.form("form_compra", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            with col_a:
                f_compra = st.date_input("Fecha de Compra", hoy)
                remision = st.text_input("Número de Remisión / Factura")
                proveedor = st.text_input("Nombre del Proveedor")
                fruta = st.text_input("Producto / Fruta / Insumo")
            with col_b:
                kilos = st.number_input("Cantidad / Kilos", min_value=0.0, step=1.0)
                precio_kilo = st.number_input("Precio por Kilo ($)", min_value=0.0, step=100.0)
                tipo_pago = st.selectbox("Tipo de Pago", ["A CRÉDITO", "DE CONTADO"])

            submitted_c = st.form_submit_button("Guardar Compra")
            if submitted_c:
                if remision and proveedor:
                    total_calculado = kilos * precio_kilo
                    nueva_compra = pd.DataFrame([{
                        'fecha': str(f_compra),
                        'remision': remision,
                        'proveedor': proveedor.strip().title(),
                        'fruta': fruta,
                        'kilos': kilos,
                        'precio_kilo': precio_kilo,
                        'tipo_pago': tipo_pago,
                        'total': total_calculado
                    }])
                    st.session_state['df_compras'] = pd.concat([st.session_state['df_compras'], nueva_compra], ignore_index=True)
                    st.success(f"✅ Compra registrada correctamente. Total: ${total_calculado:,.2f}")
                else:
                    st.error("Por favor completa los campos requeridos (Remisión y Proveedor).")

    with tab2:
        with st.form("form_pago", clear_on_submit=True):
            col_x, col_y = st.columns(2)
            with col_x:
                f_pago = st.date_input("Fecha de Pago", hoy)
                comprobante = st.text_input("Comprobante / Recibo N°")
                proveedor_p = st.text_input("Proveedor a Abonar")
            with col_y:
                remision_aso = st.text_input("Remisión Asociada (Opcional)")
                monto = st.number_input("Monto del Pago ($)", min_value=0.0, step=1000.0)
                notas = st.text_area("Notas / Observaciones")

            submitted_p = st.form_submit_button("Guardar Pago")
            if submitted_p:
                if comprobante and proveedor_p and monto > 0:
                    nuevo_pago = pd.DataFrame([{
                        'fecha': str(f_pago),
                        'comprobante': comprobante,
                        'proveedor': proveedor_p.strip().title(),
                        'remision_asociada': remision_aso if remision_aso else "N/A",
                        'monto': monto,
                        'notas': notas
                    }])
                    st.session_state['df_pagos'] = pd.concat([st.session_state['df_pagos'], nuevo_pago], ignore_index=True)
                    st.success(f"✅ Pago de ${monto:,.2f} registrado correctamente para {proveedor_p}.")
                else:
                    st.error("Por favor completa los campos obligatorios (Comprobante, Proveedor y Monto mayor a 0).")