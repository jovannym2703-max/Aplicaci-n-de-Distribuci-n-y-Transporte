"""
Aplicación web — Sistema de Gestión de Distribución y Transporte
==================================================================
Interfaz Streamlit que conecta los módulos de lógica de negocio:
  modelos.py | inventario.py | pedidos.py | transporte.py | rastreo.py | reportes.py

Ejecutar localmente:   streamlit run app.py
"""

import math
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from modelos import (
    Cliente, Conductor, EstadoEnvio, EstadoPedido, ItemPedido,
    Prioridad, Producto, Vehiculo,
)
from inventario import GestionInventario
from pedidos import GestionPedidos
from transporte import GestionTransporte
from rastreo import GestionRastreo
import reportes

st.set_page_config(page_title="Gestión de Distribución y Transporte", layout="wide", page_icon="📦")

# ---------------------------------------------------------------------------
# Coordenadas de referencia — el centro de distribución se ubica en
# Cartagena de Indias. Las coordenadas (x, y) internas del modelo son un
# plano simplificado en kilómetros; se transforman a lat/lon únicamente
# para las visualizaciones geográficas.
# ---------------------------------------------------------------------------
LAT_ORIGEN, LON_ORIGEN = 10.3910, -75.4794


def coords_a_latlon(coord):
    x, y = coord
    lat = LAT_ORIGEN + (y / 111.32)
    lon = LON_ORIGEN + (x / (111.32 * math.cos(math.radians(LAT_ORIGEN))))
    return lat, lon


def badge_abc(clase: str) -> str:
    return {"A": "🟢 A", "B": "🟡 B", "C": "🔴 C"}.get(clase, "—")


# ---------------------------------------------------------------------------
# Datos ficticios de muestra — escenario operativo completo con pedidos en
# distintos estados (creado, confirmado, backorder, cancelado, asignado,
# entregado), rutas ya calculadas, envíos en distintas fases de tránsito
# (entregado a tiempo, en ruta, con incidencia) y mantenimientos programados
# y completados, para que la app se vea en plena "etapa de funcionamiento".
# ---------------------------------------------------------------------------
def cargar_datos_demo():
    inventario = GestionInventario()
    pedidos_mgr = GestionPedidos(inventario)
    transporte = GestionTransporte()
    rastreo = GestionRastreo()

    # --- Catálogo de productos (10 SKU en 6 categorías, con parámetros
    #     realistas de costo, demanda y lead time para EOQ / ROP / ABC) ---
    productos_data = [
        # código, nombre, categoría, peso_kg, volumen_m3, stock_min, stock_seg,
        # costo_unit, precio_venta, lead_time_dias, demanda_diaria, stock_inicial
        ("SKU-001", "Cemento gris 50kg", "Materiales", 50, 0.030, 30, 15, 24000, 31000, 4, 14, 210),
        ("SKU-002", "Varilla corrugada 12mm x 6m", "Materiales", 8.5, 0.015, 60, 25, 32000, 41000, 6, 20, 340),
        ("SKU-003", "Pintura blanca 1 galón", "Acabados", 4.5, 0.005, 20, 8, 42000, 58000, 3, 6, 26),
        ("SKU-004", "Taladro percutor 650W", "Herramientas", 2.2, 0.004, 5, 2, 185000, 249000, 10, 1.2, 9),
        ("SKU-005", "Tubería PVC 1/2 pulgada x 3m", "Plomería", 1.1, 0.006, 40, 15, 9500, 13200, 5, 11, 260),
        ("SKU-006", "Cable eléctrico THHN #12 (rollo 100m)", "Eléctricos", 9.0, 0.020, 10, 4, 210000, 268000, 7, 1.8, 22),
        ("SKU-007", "Tornillo autorroscante 1\" (caja x100)", "Ferretería", 0.9, 0.001, 25, 10, 8500, 12500, 4, 4.5, 55),
        ("SKU-008", "Adhesivo para porcelanato 25kg", "Acabados", 25, 0.018, 15, 6, 22000, 29500, 5, 5.5, 40),
        ("SKU-009", "Interruptor doble sencillo", "Eléctricos", 0.15, 0.0003, 50, 20, 4200, 6900, 6, 9, 130),
        ("SKU-010", "Guante de carnaza (par)", "Seguridad Industrial", 0.3, 0.0008, 30, 10, 6800, 10500, 4, 3, 6),
    ]
    productos = {}
    for cod, nombre, cat, peso, vol, smin, sseg, costo, precio, lt, dda, stock0 in productos_data:
        prod = Producto(cod, nombre, cat, peso, vol, stock_minimo=smin, stock_seguridad=sseg,
                         costo_unitario=costo, precio_venta=precio, lead_time_dias=lt,
                         demanda_diaria_promedio=dda)
        inventario.registrar_producto(prod, stock_inicial=stock0)
        productos[cod] = prod
    inventario.clasificar_abc()

    # --- Clientes distribuidos en distintas zonas de Cartagena y alrededores ---
    clientes_data = [
        ("Ferretería El Tornillo", "Cra 10 #20-30, Centro", (5, 8), "Centro", "Minorista"),
        ("Constructora Alfa S.A.S.", "Av. Pedro de Heredia 45-12", (2, 3), "Pie de la Popa", "Institucional"),
        ("Depósito Central Bosque", "Zona Industrial El Bosque", (9, 1), "El Bosque", "Mayorista"),
        ("Distribuidora Manga", "Cl 24 #8-15, Manga", (4, 6), "Manga", "Minorista"),
        ("Materiales Turbaco Ltda.", "Vía Turbaco km 3", (14, 10), "Turbaco", "Mayorista"),
        ("Ferretería Bocagrande", "Cra 1 #7-20, Bocagrande", (-3, -2), "Bocagrande", "Minorista"),
        ("Constructora del Caribe", "Zona Franca La Candelaria", (11, -6), "Mamonal", "Institucional"),
        ("Home Center Express", "Anillo Vial km 8", (7, 12), "Anillo Vial", "Minorista"),
    ]
    clientes = [Cliente(n, d, c, zona=z, tipo_cliente=t) for n, d, c, z, t in clientes_data]

    ahora = datetime.now()
    pedidos_seed = [
        # índice_cliente, [(código, cantidad)], prioridad, días_atrás
        (0, [("SKU-001", 10), ("SKU-002", 20)], Prioridad.ALTA, 9),
        (1, [("SKU-001", 5), ("SKU-003", 8)], Prioridad.NORMAL, 8),
        (2, [("SKU-002", 40)], Prioridad.NORMAL, 7),
        (3, [("SKU-004", 3), ("SKU-005", 50)], Prioridad.URGENTE, 6),
        (4, [("SKU-006", 6), ("SKU-009", 30)], Prioridad.NORMAL, 5),
        (5, [("SKU-007", 10), ("SKU-010", 15)], Prioridad.BAJA, 4),
        (6, [("SKU-008", 20)], Prioridad.ALTA, 3),
        (7, [("SKU-003", 4), ("SKU-009", 15)], Prioridad.NORMAL, 2),
        (0, [("SKU-004", 8)], Prioridad.URGENTE, 1),      # probable BACKORDER (poco stock del taladro)
        (2, [("SKU-001", 25)], Prioridad.NORMAL, 0),
    ]
    pedidos_creados = []
    for cli_idx, items, prioridad, dias in pedidos_seed:
        items_pedido = [ItemPedido(productos[cod], cant) for cod, cant in items]
        pedido = pedidos_mgr.crear_pedido(clientes[cli_idx], items_pedido, prioridad=prioridad)
        pedido.fecha_creacion = ahora - timedelta(days=dias, hours=3)
        lead_time_max = max(i.producto.lead_time_dias for i in items_pedido)
        pedido.fecha_entrega_estimada = pedido.fecha_creacion + timedelta(days=lead_time_max + 1)
        pedidos_creados.append(pedido)

    # confirmar todo lo posible; lo que no tenga stock suficiente queda en BACKORDER
    for pedido in pedidos_creados:
        try:
            pedidos_mgr.confirmar_pedido(pedido.id)
        except ValueError:
            pass

    # cancelar un pedido ya confirmado, para mostrar el reintegro automático de stock
    if pedidos_creados[1].estado == EstadoPedido.CONFIRMADO:
        pedidos_mgr.cancelar_pedido(pedidos_creados[1].id)

    # se reserva el pedido de "Home Center Express" (si quedó confirmado) para que el
    # usuario pueda experimentar manualmente el módulo de Rutas y Despacho
    pedido_reservado_id = pedidos_creados[7].id
    confirmados = pedidos_mgr.listar_por_estado(EstadoPedido.CONFIRMADO)
    confirmados_para_rutas = [p for p in confirmados if p.id != pedido_reservado_id]

    # --- Flota: 4 vehículos con distintas capacidades y costos operativos ---
    vehiculo1 = Vehiculo("ABC-123", "Camión sencillo", 1000, 5.0, 3200, 18000,
                          velocidad_promedio_kmh=45, tipo_combustible="Diésel", rendimiento_km_por_galon=8)
    vehiculo2 = Vehiculo("XYZ-789", "Furgón mediano", 500, 2.5, 2100, 10000,
                          velocidad_promedio_kmh=55, tipo_combustible="Diésel", rendimiento_km_por_galon=11)
    vehiculo3 = Vehiculo("JKL-456", "Furgón mediano", 450, 2.2, 2000, 9500,
                          velocidad_promedio_kmh=55, tipo_combustible="Gasolina", rendimiento_km_por_galon=13)
    vehiculo4 = Vehiculo("MOT-321", "Moto carguera", 80, 0.3, 550, 3000,
                          velocidad_promedio_kmh=38, tipo_combustible="Gasolina", rendimiento_km_por_galon=35)
    for v in (vehiculo1, vehiculo2, vehiculo3, vehiculo4):
        transporte.registrar_vehiculo(v)

    conductor1 = Conductor("COND-001", "Carlos Pérez", "C2-45210", "300-111-2233", turno="Diurno", calificacion=4.8, viajes_completados=132)
    conductor2 = Conductor("COND-002", "María Gómez", "C2-98871", "301-222-3344", turno="Diurno", calificacion=4.6, viajes_completados=98)
    conductor3 = Conductor("COND-003", "Andrés Julio", "C1-77410", "302-333-4455", turno="Nocturno", calificacion=4.3, viajes_completados=64)
    conductor4 = Conductor("COND-004", "Kelly Padilla", "C2-65510", "304-444-5566", turno="Diurno", calificacion=4.9, viajes_completados=210)
    for c in (conductor1, conductor2, conductor3, conductor4):
        transporte.registrar_conductor(c)

    # --- Planificación automática de rutas para 3 de los 4 vehículos ---
    plan = transporte.asignar_pedidos_a_flota(confirmados_para_rutas, [vehiculo1, vehiculo2, vehiculo3])
    rutas_creadas = []
    envios_creados = []
    conductores_disponibles_seed = [conductor1, conductor2, conductor3]
    tratamientos = ["entregado", "en_ruta", "incidencia"]

    for idx, (placa, lista_pedidos) in enumerate(plan.items()):
        if not lista_pedidos:
            continue
        vehiculo = transporte._flota[placa]
        ruta = transporte.calcular_ruta_optima((0, 0), vehiculo, lista_pedidos)
        for p in lista_pedidos:
            pedidos_mgr.marcar_asignado(p.id)
        envio = rastreo.crear_envio(ruta)
        rutas_creadas.append(ruta)
        envios_creados.append(envio.id)

        conductor_asignado = conductores_disponibles_seed[idx] if idx < len(conductores_disponibles_seed) else None
        if conductor_asignado is not None:
            transporte.asignar_conductor(ruta.id, conductor_asignado.id)

        tratamiento = tratamientos[idx % len(tratamientos)]
        if tratamiento == "entregado":
            rastreo.avanzar_envio(envio.id, 100)
            rastreo.actualizar_estado(envio.id, EstadoEnvio.ENTREGADO, "Entrega confirmada por el cliente")
            for p in lista_pedidos:
                pedidos_mgr.marcar_entregado(p.id)
                p.fecha_entrega_real = p.fecha_entrega_estimada - timedelta(hours=6)  # entrega a tiempo
            transporte.liberar_vehiculo(placa)
            if conductor_asignado is not None:
                transporte.liberar_conductor(conductor_asignado.id)
        elif tratamiento == "en_ruta":
            rastreo.avanzar_envio(envio.id, 65)
        else:
            rastreo.avanzar_envio(envio.id, 30)
            rastreo.registrar_incidencia(envio.id, "Vía cerrada temporalmente por obras — se reprograma la entrega")

    # --- Mantenimiento: uno completado (histórico) y uno programado a futuro ---
    mant_pasado = transporte.programar_mantenimiento(
        vehiculo4.placa, "CORRECTIVO",
        ahora - timedelta(days=5), ahora - timedelta(days=5, hours=-2),
        notas="Cambio de llanta delantera por pinchazo", costo=95000,
    )
    transporte.completar_mantenimiento(mant_pasado.id)

    transporte.programar_mantenimiento(
        vehiculo1.placa, "PREVENTIVO",
        ahora + timedelta(days=2), ahora + timedelta(days=2, hours=3),
        notas="Cambio de aceite y revisión de frenos", costo=280000,
    )

    return {
        "inventario": inventario, "pedidos_mgr": pedidos_mgr,
        "transporte": transporte, "rastreo": rastreo,
        "rutas": rutas_creadas, "envios": envios_creados,
    }


def inicializar_estado(forzar: bool = False):
    if forzar or "inventario" not in st.session_state:
        datos = cargar_datos_demo()
        for k, v in datos.items():
            st.session_state[k] = v


def limpiar_estado():
    st.session_state.inventario = GestionInventario()
    st.session_state.pedidos_mgr = GestionPedidos(st.session_state.inventario)
    st.session_state.transporte = GestionTransporte()
    st.session_state.rastreo = GestionRastreo()
    st.session_state.rutas = []
    st.session_state.envios = []


inicializar_estado()

inventario: GestionInventario = st.session_state.inventario
pedidos_mgr: GestionPedidos = st.session_state.pedidos_mgr
transporte: GestionTransporte = st.session_state.transporte
rastreo: GestionRastreo = st.session_state.rastreo

# ---------------------------------------------------------------------------
# Navegación
# ---------------------------------------------------------------------------
st.sidebar.title("📦 Distribución y Transporte")
st.sidebar.caption("Centro de distribución — Cartagena de Indias")
pagina = st.sidebar.radio(
    "Módulo",
    ["📊 Dashboard", "📦 Inventario", "🧾 Pedidos", "🚛 Flota y Conductores",
     "🗺️ Rutas y Despacho", "📍 Rastreo", "📈 Reportes"],
)

st.sidebar.divider()
st.sidebar.caption("Datos de muestra")
c1, c2 = st.sidebar.columns(2)
if c1.button("🔄 Recargar demo", use_container_width=True):
    inicializar_estado(forzar=True)
    st.rerun()
if c2.button("🗑️ Limpiar todo", use_container_width=True):
    limpiar_estado()
    st.rerun()

with st.sidebar.expander("ℹ️ Metodología aplicada"):
    st.markdown(
        "- **EOQ** (modelo de Wilson) y **punto de reorden** para inventarios.\n"
        "- **Clasificación ABC** por valor de consumo anual (80/15/5).\n"
        "- Ruteo con **vecino más cercano + mejora 2-opt** (heurística clásica de VRP).\n"
        "- Asignación de pedidos a flota tipo **First Fit Decreasing** por capacidad.\n"
        "- Indicadores **OTIF**, **Fill Rate** y costo logístico unitario."
    )

# ===========================================================================
# DASHBOARD
# ===========================================================================
if pagina == "📊 Dashboard":
    st.title("Panel operativo")
    st.caption("Resumen de operación, alertas y actividad reciente.")

    fila1 = st.columns(4)
    fila1[0].metric("Pedidos totales", len(pedidos_mgr._pedidos))
    fila1[1].metric("Pedidos confirmados", len(pedidos_mgr.listar_por_estado(EstadoPedido.CONFIRMADO)))
    fila1[2].metric("Pedidos entregados", len(pedidos_mgr.listar_por_estado(EstadoPedido.ENTREGADO)))
    fila1[3].metric("Pedidos en backorder", len(pedidos_mgr.listar_por_estado(EstadoPedido.BACKORDER)))

    fila2 = st.columns(4)
    fila2[0].metric("OTIF", f"{reportes.otif(pedidos_mgr)}%", help="On Time In Full: entregas a tiempo y sin faltantes")
    fila2[1].metric("Fill rate", f"{pedidos_mgr.fill_rate()}%", help="% de pedidos confirmados sin caer en backorder")
    fila2[2].metric("Nivel de servicio", f"{reportes.nivel_servicio(pedidos_mgr)}%")
    fila2[3].metric("Tiempo de ciclo prom.", f"{pedidos_mgr.tiempo_ciclo_promedio()} días")

    fila3 = st.columns(4)
    fila3[0].metric("Vehículos en flota", len(transporte._flota))
    fila3[1].metric("Vehículos disponibles", len(transporte.vehiculos_disponibles()))
    fila3[2].metric("Rutas calculadas", len(st.session_state.rutas))
    fila3[3].metric("Alertas de stock bajo", len(inventario.productos_bajo_minimo()))

    st.divider()
    col_izq, col_der = st.columns([1, 1])

    with col_izq:
        st.subheader("Pedidos por estado")
        if pedidos_mgr._pedidos:
            conteo = pd.Series([p.estado.value for p in pedidos_mgr._pedidos.values()]).value_counts().reset_index()
            conteo.columns = ["Estado", "Cantidad"]
            fig = px.pie(conteo, names="Estado", values="Cantidad", hole=0.45,
                         color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=320)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Aún no hay pedidos registrados.")

    with col_der:
        st.subheader("Pedidos creados por día")
        if pedidos_mgr._pedidos:
            df_fechas = pd.DataFrame({
                "Fecha": [p.fecha_creacion.date() for p in pedidos_mgr._pedidos.values()]
            })
            conteo_fechas = df_fechas.groupby("Fecha").size().reset_index(name="Pedidos")
            fig2 = px.bar(conteo_fechas, x="Fecha", y="Pedidos", color_discrete_sequence=["#3B82F6"])
            fig2.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=320)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Aún no hay pedidos registrados.")

    st.subheader("Ubicación de clientes y centro de distribución")
    puntos = [{"lat": LAT_ORIGEN, "lon": LON_ORIGEN, "tipo": "Centro de distribución"}]
    clientes_vistos = {}
    for p in pedidos_mgr._pedidos.values():
        if p.cliente.nombre not in clientes_vistos:
            lat, lon = coords_a_latlon(p.cliente.coordenadas)
            puntos.append({"lat": lat, "lon": lon, "tipo": p.cliente.zona})
            clientes_vistos[p.cliente.nombre] = True
    if len(puntos) > 1:
        st.map(pd.DataFrame(puntos), latitude="lat", longitude="lon", size=60)
    else:
        st.info("Aún no hay clientes con pedidos para ubicar en el mapa.")

    st.divider()
    st.subheader("Alertas de inventario bajo punto de reorden")
    bajo_rop = inventario.productos_bajo_punto_reorden()
    if bajo_rop:
        st.dataframe(
            pd.DataFrame([{
                "Código": p.codigo, "Nombre": p.nombre,
                "Stock actual": inventario.consultar_stock(p.codigo),
                "Punto de reorden": inventario.calcular_punto_reorden(p.codigo),
                "Stock mínimo": p.stock_minimo,
                "Clase ABC": badge_abc(p.clasificacion_abc),
            } for p in bajo_rop]),
            use_container_width=True, hide_index=True,
        )
    else:
        st.success("Ningún producto está por debajo de su punto de reorden.")

# ===========================================================================
# INVENTARIO
# ===========================================================================
elif pagina == "📦 Inventario":
    st.title("Gestión de Inventario")
    tab_stock, tab_repos, tab_nuevo, tab_mov, tab_kardex = st.tabs(
        ["Stock actual", "📐 Análisis de reposición", "➕ Nuevo producto", "↕️ Movimiento de stock", "📜 Kardex"]
    )

    with tab_stock:
        if inventario._productos:
            inventario.clasificar_abc()
            filas = [{
                "Código": c, "Nombre": p.nombre, "Categoría": p.categoria,
                "Stock": inventario.consultar_stock(c), "Stock mínimo": p.stock_minimo,
                "Clase ABC": badge_abc(p.clasificacion_abc),
                "Bajo mínimo": "⚠️" if inventario.consultar_stock(c) < p.stock_minimo else "",
                "Valor en stock ($)": round(inventario.consultar_stock(c) * p.costo_unitario, 0),
            } for c, p in inventario._productos.items()]
            st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

            col1, col2, col3 = st.columns(3)
            col1.metric("Valor total del inventario", f"${inventario.valor_inventario_total():,.0f}")
            col2.metric("Productos en catálogo", len(inventario._productos))
            col3.metric("Alertas bajo mínimo", len(inventario.productos_bajo_minimo()))

            df_stock = pd.DataFrame([{
                "Producto": p.nombre,
                "Stock actual": inventario.consultar_stock(c),
                "Stock mínimo": p.stock_minimo,
            } for c, p in inventario._productos.items()])
            fig = px.bar(df_stock, x="Producto", y=["Stock actual", "Stock mínimo"], barmode="group",
                         color_discrete_sequence=["#3B82F6", "#EF4444"])
            fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=380, xaxis_tickangle=-30)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay productos registrados todavía.")

    with tab_repos:
        if inventario._productos:
            inventario.clasificar_abc()
            filas = [{
                "Código": c, "Nombre": p.nombre,
                "Demanda diaria prom.": p.demanda_diaria_promedio,
                "Lead time (días)": p.lead_time_dias,
                "EOQ sugerido": inventario.calcular_eoq(c),
                "Punto de reorden": inventario.calcular_punto_reorden(c),
                "Pedidos/año est.": inventario.calcular_numero_pedidos_anuales(c),
                "Costo total anual ($)": inventario.costo_total_anual_inventario(c),
                "Rotación": inventario.rotacion_inventario(c),
                "Días de cobertura": inventario.dias_inventario_disponible(c),
                "Clase ABC": badge_abc(p.clasificacion_abc),
            } for c, p in inventario._productos.items()]
            st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

            st.caption(
                "EOQ = √(2·D·S / H), con D = demanda anual, S = costo de ordenar y "
                "H = costo unitario de mantener el inventario. Punto de reorden = "
                "demanda diaria × lead time + stock de seguridad."
            )

            conteo_abc = pd.Series([p.clasificacion_abc for p in inventario._productos.values()]).value_counts().reset_index()
            conteo_abc.columns = ["Clase", "Cantidad de productos"]
            fig_abc = px.pie(conteo_abc, names="Clase", values="Cantidad de productos", hole=0.45,
                              color="Clase", color_discrete_map={"A": "#22C55E", "B": "#EAB308", "C": "#EF4444"})
            fig_abc.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=320)
            st.plotly_chart(fig_abc, use_container_width=True)
        else:
            st.info("Registra productos para ver el análisis de reposición.")

    with tab_nuevo:
        with st.form("form_producto"):
            c1, c2 = st.columns(2)
            codigo = c1.text_input("Código (SKU)")
            nombre = c2.text_input("Nombre del producto")
            c3, c4, c5 = st.columns(3)
            categoria = c3.text_input("Categoría")
            peso = c4.number_input("Peso unitario (kg)", min_value=0.0, step=0.1)
            volumen = c5.number_input("Volumen unitario (m³)", min_value=0.0, step=0.01)
            c6, c7, c8 = st.columns(3)
            stock_min = c6.number_input("Stock mínimo", min_value=0, step=1)
            stock_seg = c7.number_input("Stock de seguridad", min_value=0, step=1)
            stock_inicial = c8.number_input("Stock inicial", min_value=0, step=1)
            c9, c10, c11 = st.columns(3)
            costo_unit = c9.number_input("Costo unitario ($)", min_value=0.0, step=1000.0)
            precio_venta = c10.number_input("Precio de venta ($)", min_value=0.0, step=1000.0)
            lead_time = c11.number_input("Lead time del proveedor (días)", min_value=1, step=1, value=3)
            c12, c13 = st.columns(2)
            demanda_diaria = c12.number_input("Demanda diaria promedio", min_value=0.0, step=0.5)
            costo_pedido = c13.number_input("Costo de ordenar un pedido ($)", min_value=0.0, step=1000.0, value=50000.0)
            if st.form_submit_button("Registrar producto"):
                if codigo and nombre:
                    if codigo in inventario._productos:
                        st.error(f"El código {codigo} ya existe.")
                    else:
                        producto = Producto(
                            codigo, nombre, categoria or "Sin categoría", peso, volumen,
                            stock_minimo=int(stock_min), stock_seguridad=int(stock_seg),
                            costo_unitario=costo_unit, precio_venta=precio_venta,
                            lead_time_dias=int(lead_time), demanda_diaria_promedio=demanda_diaria,
                            costo_pedido=costo_pedido,
                        )
                        inventario.registrar_producto(producto, stock_inicial=int(stock_inicial))
                        st.success(f"Producto {codigo} registrado.")
                        st.rerun()
                else:
                    st.error("Código y nombre son obligatorios.")

    with tab_mov:
        if inventario._productos:
            codigo_sel = st.selectbox("Producto", list(inventario._productos.keys()), key="mov_producto")
            c1, c2, c3 = st.columns(3)
            cantidad = c1.number_input("Cantidad", min_value=1, step=1, key="mov_cant")
            tipo_mov = c2.selectbox("Tipo", ["ENTRADA", "SALIDA"], key="mov_tipo")
            referencia = c3.text_input("Referencia", value="Ajuste manual", key="mov_ref")
            if st.button("Aplicar movimiento", use_container_width=True):
                try:
                    if tipo_mov == "ENTRADA":
                        inventario.entrada_stock(codigo_sel, int(cantidad), referencia=referencia)
                    else:
                        inventario.salida_stock(codigo_sel, int(cantidad), referencia=referencia)
                    st.success("Movimiento aplicado.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
        else:
            st.info("Registra un producto primero.")

    with tab_kardex:
        if inventario._productos:
            codigo_sel_k = st.selectbox("Producto", list(inventario._productos.keys()), key="kardex_producto")
            movimientos = inventario.kardex_producto(codigo_sel_k)
            if movimientos:
                df_kardex = pd.DataFrame([{
                    "Fecha": m.fecha, "Tipo": m.tipo, "Cantidad": m.cantidad, "Referencia": m.referencia,
                } for m in movimientos]).sort_values("Fecha", ascending=False)
                st.dataframe(df_kardex, use_container_width=True, hide_index=True)
            else:
                st.info("Este producto no tiene movimientos registrados.")
        else:
            st.info("Registra un producto primero.")

# ===========================================================================
# PEDIDOS
# ===========================================================================
elif pagina == "🧾 Pedidos":
    st.title("Gestión de Pedidos")

    if not inventario._productos:
        st.warning("Registra al menos un producto en el módulo **Inventario** antes de crear pedidos.")
    else:
        tab_lista, tab_nuevo, tab_back = st.tabs(
            ["Pedidos registrados", "➕ Crear pedido", "⏳ Backorders"]
        )

        with tab_nuevo:
            with st.form("form_pedido"):
                c1, c2 = st.columns(2)
                nombre_cliente = c1.text_input("Nombre del cliente")
                direccion = c2.text_input("Dirección")
                c3, c4, c5 = st.columns(3)
                coord_x = c3.number_input("Coordenada X (km desde el CD)", step=1.0)
                coord_y = c4.number_input("Coordenada Y (km desde el CD)", step=1.0)
                zona = c5.text_input("Zona", value="Sin zona")
                prioridad_sel = st.selectbox("Prioridad", [p.value for p in Prioridad], index=1)

                st.caption("Productos del pedido")
                items_sel = st.multiselect("Selecciona productos", list(inventario._productos.keys()))
                cantidades = {}
                for codigo in items_sel:
                    cantidades[codigo] = st.number_input(
                        f"Cantidad de {inventario._productos[codigo].nombre}",
                        min_value=1, step=1, key=f"cant_{codigo}"
                    )

                if st.form_submit_button("Crear pedido"):
                    if nombre_cliente and items_sel:
                        cliente = Cliente(nombre_cliente, direccion, (coord_x, coord_y), zona=zona or "Sin zona")
                        items = [ItemPedido(inventario._productos[c], int(cantidades[c])) for c in items_sel]
                        pedido = pedidos_mgr.crear_pedido(cliente, items, prioridad=Prioridad(prioridad_sel))
                        st.success(f"Pedido {pedido.id} creado con estado CREADO. Confírmalo para descontar inventario.")
                        st.rerun()
                    else:
                        st.error("Nombre del cliente y al menos un producto son obligatorios.")

        with tab_lista:
            if pedidos_mgr._pedidos:
                filtro_estado = st.multiselect(
                    "Filtrar por estado", [e.value for e in EstadoPedido],
                    default=[e.value for e in EstadoPedido],
                )
                filas = [{
                    "ID": p.id, "Cliente": p.cliente.nombre, "Estado": p.estado.value,
                    "Prioridad": p.prioridad.value if hasattr(p.prioridad, "value") else p.prioridad,
                    "Peso (kg)": round(p.peso_total, 2), "Volumen (m³)": round(p.volumen_total, 2),
                    "Valor ($)": round(p.valor_total, 0),
                    "Creado": p.fecha_creacion.strftime("%Y-%m-%d"),
                    "Entrega estimada": p.fecha_entrega_estimada.strftime("%Y-%m-%d") if p.fecha_entrega_estimada else "—",
                } for p in pedidos_mgr._pedidos.values() if p.estado.value in filtro_estado]
                st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

                st.subheader("Confirmar o cancelar pedido")
                pedido_id = st.selectbox("Pedido", list(pedidos_mgr._pedidos.keys()), key="pedido_accion")
                c1, c2 = st.columns(2)
                if c1.button("✅ Confirmar pedido", use_container_width=True):
                    try:
                        pedidos_mgr.confirmar_pedido(pedido_id)
                        st.success("Pedido confirmado y stock descontado.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
                if c2.button("❌ Cancelar pedido", use_container_width=True):
                    try:
                        pedidos_mgr.cancelar_pedido(pedido_id)
                        st.success("Pedido cancelado (se reintegra el stock si ya había sido descontado).")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
            else:
                st.info("No hay pedidos todavía.")

        with tab_back:
            backorders = pedidos_mgr.listar_por_estado(EstadoPedido.BACKORDER)
            if backorders:
                st.warning(f"{len(backorders)} pedido(s) con faltante de inventario.")
                for p in backorders:
                    with st.expander(f"{p.id} — {p.cliente.nombre} ({p.prioridad.value if hasattr(p.prioridad,'value') else p.prioridad})"):
                        for item in p.items:
                            disponible = inventario.consultar_stock(item.producto.codigo)
                            st.write(
                                f"- **{item.producto.nombre}**: solicitado {item.cantidad}, "
                                f"disponible {disponible} "
                                f"({'✅ suficiente' if disponible >= item.cantidad else '⚠️ falta ' + str(item.cantidad - disponible)})"
                            )
                        if st.button("🔁 Reintentar confirmación", key=f"retry_{p.id}"):
                            try:
                                pedidos_mgr.confirmar_pedido(p.id)
                                st.success("Pedido confirmado con éxito.")
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))
            else:
                st.success("No hay pedidos en backorder actualmente.")

# ===========================================================================
# FLOTA Y CONDUCTORES
# ===========================================================================
elif pagina == "🚛 Flota y Conductores":
    st.title("Flota y Conductores")
    tab_veh, tab_cond, tab_mant = st.tabs(["🚚 Vehículos", "🧑‍✈️ Conductores", "🔧 Mantenimiento"])

    with tab_veh:
        with st.expander("➕ Registrar vehículo"):
            with st.form("form_vehiculo"):
                c1, c2 = st.columns(2)
                placa = c1.text_input("Placa")
                tipo = c2.text_input("Tipo (camión, furgón, moto...)")
                c3, c4 = st.columns(2)
                cap_peso = c3.number_input("Capacidad de peso (kg)", min_value=0.0, step=10.0)
                cap_vol = c4.number_input("Capacidad de volumen (m³)", min_value=0.0, step=0.5)
                c5, c6 = st.columns(2)
                costo_km = c5.number_input("Costo por km ($)", min_value=0.0, step=100.0)
                costo_fijo = c6.number_input("Costo fijo de despacho ($)", min_value=0.0, step=1000.0)
                c7, c8 = st.columns(2)
                velocidad = c7.number_input("Velocidad promedio (km/h)", min_value=1.0, value=40.0, step=1.0)
                combustible = c8.selectbox("Tipo de combustible", ["Diésel", "Gasolina", "Eléctrico", "GNV"])
                if st.form_submit_button("Registrar vehículo"):
                    if placa:
                        if placa in transporte._flota:
                            st.error(f"La placa {placa} ya está registrada.")
                        else:
                            transporte.registrar_vehiculo(
                                Vehiculo(placa, tipo or "Sin especificar", cap_peso, cap_vol, costo_km, costo_fijo,
                                         velocidad_promedio_kmh=velocidad, tipo_combustible=combustible)
                            )
                            st.success(f"Vehículo {placa} registrado.")
                            st.rerun()
                    else:
                        st.error("La placa es obligatoria.")

        if transporte._flota:
            filas = [{
                "Placa": v.placa, "Tipo": v.tipo, "Cap. peso (kg)": v.capacidad_peso_kg,
                "Cap. volumen (m³)": v.capacidad_volumen_m3, "Costo/km ($)": v.costo_km,
                "Combustible": v.tipo_combustible, "Vel. prom. (km/h)": v.velocidad_promedio_kmh,
                "Disponible": "Sí" if v.disponible else "No",
            } for v in transporte._flota.values()]
            st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)
            st.metric("Utilización de flota (vehículos en uso)", f"{reportes.utilizacion_flota(transporte)}%")
        else:
            st.info("No hay vehículos registrados todavía.")

    with tab_cond:
        with st.expander("➕ Registrar conductor"):
            with st.form("form_conductor"):
                c1, c2 = st.columns(2)
                id_cond = c1.text_input("ID (ej. COND-005)")
                nombre_cond = c2.text_input("Nombre completo")
                c3, c4 = st.columns(2)
                licencia = c3.text_input("Licencia de conducción")
                telefono = c4.text_input("Teléfono")
                turno = st.selectbox("Turno", ["Diurno", "Nocturno"])
                if st.form_submit_button("Registrar conductor"):
                    if id_cond and nombre_cond:
                        if id_cond in transporte._conductores:
                            st.error(f"El ID {id_cond} ya existe.")
                        else:
                            transporte.registrar_conductor(Conductor(id_cond, nombre_cond, licencia, telefono, turno=turno))
                            st.success(f"Conductor {nombre_cond} registrado.")
                            st.rerun()
                    else:
                        st.error("ID y nombre son obligatorios.")

        if transporte._conductores:
            filas = [{
                "ID": c.id, "Nombre": c.nombre, "Licencia": c.licencia,
                "Teléfono": c.telefono, "Turno": c.turno, "Calificación": c.calificacion,
                "Viajes completados": c.viajes_completados,
                "Disponible": "Sí" if c.disponible else "No",
            } for c in transporte._conductores.values()]
            st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)
        else:
            st.info("No hay conductores registrados todavía.")

    with tab_mant:
        if not transporte._flota:
            st.info("Registra al menos un vehículo primero.")
        else:
            with st.form("form_mantenimiento"):
                placa_sel = st.selectbox("Vehículo", list(transporte._flota.keys()))
                tipo_mant = st.selectbox("Tipo", ["PREVENTIVO", "CORRECTIVO"])
                c1, c2 = st.columns(2)
                fecha_inicio = c1.text_input("Inicio (AAAA-MM-DD HH:MM)", value=datetime.now().strftime("%Y-%m-%d %H:%M"))
                fecha_fin = c2.text_input("Fin (AAAA-MM-DD HH:MM)", value=(datetime.now() + timedelta(hours=4)).strftime("%Y-%m-%d %H:%M"))
                c3, c4 = st.columns(2)
                notas = c3.text_input("Notas")
                costo_mant = c4.number_input("Costo estimado ($)", min_value=0.0, step=10000.0)
                if st.form_submit_button("Programar mantenimiento"):
                    try:
                        inicio_dt = datetime.strptime(fecha_inicio, "%Y-%m-%d %H:%M")
                        fin_dt = datetime.strptime(fecha_fin, "%Y-%m-%d %H:%M")
                        if fin_dt <= inicio_dt:
                            st.error("La fecha de fin debe ser posterior a la de inicio.")
                        else:
                            transporte.programar_mantenimiento(placa_sel, tipo_mant, inicio_dt, fin_dt, notas, costo_mant)
                            st.success(f"Mantenimiento programado para {placa_sel} (vehículo marcado como no disponible).")
                            st.rerun()
                    except ValueError:
                        st.error("Formato de fecha inválido. Usa AAAA-MM-DD HH:MM.")

            mantenimientos = transporte.listar_mantenimientos()
            if mantenimientos:
                st.subheader("Mantenimientos")
                filas = [{
                    "ID": m.id, "Vehículo": m.vehiculo.placa, "Tipo": m.tipo,
                    "Inicio": m.inicio, "Fin": m.fin, "Costo ($)": m.costo,
                    "Estado": m.estado.value, "Notas": m.notas,
                } for m in mantenimientos]
                st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

                pendientes = [m for m in mantenimientos if m.estado.value != "COMPLETADO"]
                if pendientes:
                    mant_sel = st.selectbox("Marcar como completado", [m.id for m in pendientes])
                    if st.button("✅ Completar mantenimiento"):
                        transporte.completar_mantenimiento(mant_sel)
                        st.success("Mantenimiento completado — vehículo disponible de nuevo.")
                        st.rerun()

# ===========================================================================
# RUTAS Y DESPACHO
# ===========================================================================
elif pagina == "🗺️ Rutas y Despacho":
    st.title("Cálculo de Rutas y Despacho")
    st.caption("Ruteo por vecino más cercano con mejora 2-opt, y asignación de pedidos por capacidad (peso/volumen).")

    pendientes = pedidos_mgr.listar_por_estado(EstadoPedido.CONFIRMADO)
    disponibles = transporte.vehiculos_disponibles()

    if not pendientes:
        st.info("No hay pedidos CONFIRMADOS pendientes de asignar. Confirma pedidos en el módulo **Pedidos**.")
    elif not disponibles:
        st.info("No hay vehículos disponibles. Registra uno en **Flota y Conductores** o completa un mantenimiento en curso.")
    else:
        modo = st.radio("Modo de despacho", ["Un solo vehículo", "Toda la flota disponible"], horizontal=True)
        c1, c2 = st.columns(2)
        origen_x = c1.number_input("Origen X (centro de distribución)", value=0.0, step=1.0)
        origen_y = c2.number_input("Origen Y (centro de distribución)", value=0.0, step=1.0)
        st.caption(f"Pedidos confirmados pendientes: {[p.id for p in pendientes]}")

        if modo == "Un solo vehículo":
            placa_sel = st.selectbox("Vehículo", [v.placa for v in disponibles])
            if st.button("🚚 Asignar y calcular ruta óptima"):
                vehiculo = transporte._flota[placa_sel]
                asignados, no_asignados = transporte.asignar_pedidos_a_vehiculo(pendientes, vehiculo)
                if not asignados:
                    st.error("Ningún pedido cabe en la capacidad de este vehículo.")
                else:
                    ruta = transporte.calcular_ruta_optima((origen_x, origen_y), vehiculo, asignados)
                    for p in asignados:
                        pedidos_mgr.marcar_asignado(p.id)
                    envio = rastreo.crear_envio(ruta)
                    st.session_state.rutas.append(ruta)
                    st.session_state.envios.append(envio.id)

                    st.success(f"Ruta {ruta.id} calculada — Envío {envio.id} creado.")
                    st.write(f"**Secuencia de entrega:** {' → '.join(p.cliente.nombre for p in ruta.secuencia_pedidos)}")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Distancia total", f"{ruta.distancia_km} km")
                    c2.metric("Costo estimado", f"${ruta.costo_estimado:,.0f}")
                    c3.metric("Tiempo estimado", f"{ruta.tiempo_estimado_horas} h")
                    c4, c5 = st.columns(2)
                    c4.progress(min(int(ruta.utilizacion_peso), 100), text=f"Uso de peso: {ruta.utilizacion_peso}%")
                    c5.progress(min(int(ruta.utilizacion_volumen), 100), text=f"Uso de volumen: {ruta.utilizacion_volumen}%")
                    if no_asignados:
                        st.warning(f"No cupieron en este viaje: {[p.id for p in no_asignados]}")

                    disponibles_cond = transporte.conductores_disponibles()
                    if disponibles_cond:
                        cond_sel = st.selectbox("Asignar conductor a esta ruta", [c.id for c in disponibles_cond], key=f"cond_{ruta.id}")
                        if st.button("👤 Asignar conductor", key=f"btn_cond_{ruta.id}"):
                            transporte.asignar_conductor(ruta.id, cond_sel)
                            st.success("Conductor asignado.")
                            st.rerun()
        else:
            if st.button("🚛 Planificar y despachar toda la flota disponible"):
                plan = transporte.asignar_pedidos_a_flota(pendientes, disponibles)
                if not plan:
                    st.error("Ningún pedido cabe en la capacidad de la flota disponible.")
                else:
                    resumen = []
                    for placa, lista_pedidos in plan.items():
                        vehiculo = transporte._flota[placa]
                        ruta = transporte.calcular_ruta_optima((origen_x, origen_y), vehiculo, lista_pedidos)
                        for p in lista_pedidos:
                            pedidos_mgr.marcar_asignado(p.id)
                        envio = rastreo.crear_envio(ruta)
                        st.session_state.rutas.append(ruta)
                        st.session_state.envios.append(envio.id)
                        resumen.append({
                            "Ruta": ruta.id, "Vehículo": placa, "Envío": envio.id,
                            "Paradas": len(ruta.secuencia_pedidos), "Distancia (km)": ruta.distancia_km,
                            "Costo ($)": ruta.costo_estimado,
                        })
                    st.success(f"Se despacharon {len(resumen)} vehículo(s) con {sum(r['Paradas'] for r in resumen)} pedido(s).")
                    st.dataframe(pd.DataFrame(resumen), use_container_width=True, hide_index=True)

                    asignados_ids = {p.id for lista in plan.values() for p in lista}
                    restantes = [p for p in pendientes if p.id not in asignados_ids]
                    if restantes:
                        st.warning(f"Pedidos que no cupieron en ningún vehículo: {[p.id for p in restantes]}")

    st.divider()
    st.subheader("Historial de rutas calculadas")
    if st.session_state.rutas:
        st.dataframe(
            pd.DataFrame([{
                "Ruta": r.id, "Vehículo": r.vehiculo.placa, "Algoritmo": r.algoritmo,
                "Distancia (km)": r.distancia_km, "Costo ($)": r.costo_estimado,
                "Tiempo (h)": r.tiempo_estimado_horas, "Paradas": len(r.secuencia_pedidos),
                "Conductor": r.conductor.nombre if r.conductor else "Sin asignar",
                "Uso peso (%)": r.utilizacion_peso, "Uso volumen (%)": r.utilizacion_volumen,
            } for r in st.session_state.rutas]),
            use_container_width=True, hide_index=True,
        )

        st.subheader("Visualización de una ruta")
        ruta_sel_id = st.selectbox("Selecciona una ruta", [r.id for r in st.session_state.rutas])
        ruta_sel = next(r for r in st.session_state.rutas if r.id == ruta_sel_id)
        puntos_ruta = [{"x": ruta_sel.origen[0], "y": ruta_sel.origen[1], "orden": 0, "lugar": "Centro de distribución"}]
        for i, p in enumerate(ruta_sel.secuencia_pedidos, start=1):
            puntos_ruta.append({"x": p.cliente.coordenadas[0], "y": p.cliente.coordenadas[1], "orden": i, "lugar": p.cliente.nombre})
        puntos_ruta.append({"x": ruta_sel.origen[0], "y": ruta_sel.origen[1], "orden": len(puntos_ruta), "lugar": "Regreso al CD"})
        df_ruta = pd.DataFrame(puntos_ruta)
        fig_ruta = px.line(df_ruta, x="x", y="y", text="lugar", markers=True,
                            title=f"Secuencia de entrega — {ruta_sel.id} ({ruta_sel.algoritmo})")
        fig_ruta.update_traces(textposition="top center")
        fig_ruta.update_layout(height=420, xaxis_title="X (km)", yaxis_title="Y (km)")
        st.plotly_chart(fig_ruta, use_container_width=True)
    else:
        st.info("Aún no se han calculado rutas.")

# ===========================================================================
# RASTREO
# ===========================================================================
elif pagina == "📍 Rastreo":
    st.title("Rastreo y Trazabilidad de Envíos")

    if not st.session_state.envios:
        st.info("Aún no se ha generado ningún envío. Calcula una ruta en **Rutas y Despacho** primero.")
    else:
        envio_id = st.selectbox("Envío", st.session_state.envios)
        envio = rastreo.obtener_envio(envio_id)

        c1, c2, c3 = st.columns(3)
        c1.metric("Estado actual", envio.estado.value)
        c2.metric("Avance", f"{envio.porcentaje_avance:.0f}%")
        c3.metric("ETA", envio.eta.strftime("%Y-%m-%d %H:%M") if envio.eta else "—")
        st.progress(min(int(envio.porcentaje_avance), 100))

        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Actualizar estado")
            nuevo_estado = st.selectbox("Nuevo estado", [e.value for e in EstadoEnvio])
            nota = st.text_input("Nota (opcional)")
            if st.button("Actualizar estado"):
                rastreo.actualizar_estado(envio_id, EstadoEnvio(nuevo_estado), nota)
                if EstadoEnvio(nuevo_estado) == EstadoEnvio.ENTREGADO:
                    for p in envio.ruta.secuencia_pedidos:
                        try:
                            pedidos_mgr.marcar_entregado(p.id)
                        except KeyError:
                            pass
                st.success("Estado actualizado.")
                st.rerun()

        with col_b:
            st.subheader("Avanzar posición del envío")
            nuevo_avance = st.slider("Porcentaje de avance", 0, 100, int(envio.porcentaje_avance))
            if st.button("Actualizar avance"):
                rastreo.avanzar_envio(envio_id, nuevo_avance)
                st.success("Posición actualizada.")
                st.rerun()
            if st.button("⚠️ Registrar incidencia"):
                rastreo.registrar_incidencia(envio_id, nota or "Incidencia reportada por el conductor")
                st.warning("Incidencia registrada.")
                st.rerun()

        st.divider()
        st.subheader("Ubicación aproximada del envío")
        lat_cd, lon_cd = coords_a_latlon(envio.ruta.origen)
        puntos_mapa = [{"lat": lat_cd, "lon": lon_cd, "tipo": "Centro de distribución"}]
        for p in envio.ruta.secuencia_pedidos:
            lat_c, lon_c = coords_a_latlon(p.cliente.coordenadas)
            puntos_mapa.append({"lat": lat_c, "lon": lon_c, "tipo": p.cliente.nombre})
        if envio.ubicacion_actual:
            lat_act, lon_act = coords_a_latlon(envio.ubicacion_actual)
            puntos_mapa.append({"lat": lat_act, "lon": lon_act, "tipo": "📍 Ubicación actual del vehículo"})
        st.map(pd.DataFrame(puntos_mapa), latitude="lat", longitude="lon", size=80)

        st.subheader("Historial")
        hist = rastreo.historial(envio_id)
        df_hist = pd.DataFrame([{"Fecha": f, "Estado": e.value, "Nota": n} for f, e, n in hist])
        st.dataframe(df_hist, use_container_width=True, hide_index=True)

# ===========================================================================
# REPORTES
# ===========================================================================
elif pagina == "📈 Reportes":
    st.title("Reportes e Indicadores (KPI)")

    st.subheader("Indicadores de servicio al cliente")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Nivel de servicio", f"{reportes.nivel_servicio(pedidos_mgr)}%")
    col2.metric("OTIF", f"{reportes.otif(pedidos_mgr)}%")
    col3.metric("Fill rate", f"{pedidos_mgr.fill_rate()}%")
    col4.metric("Entregas a tiempo", f"{pedidos_mgr.tasa_entregas_a_tiempo()}%")

    st.subheader("Indicadores de costo y capacidad logística")
    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Costo promedio por envío", f"${reportes.costo_promedio_envio(st.session_state.rutas):,.0f}")
    col6.metric("Costo por km", f"${reportes.costo_por_km(st.session_state.rutas):,.0f}")
    col7.metric("Costo por kg transportado", f"${reportes.costo_por_kg_transportado(st.session_state.rutas):,.0f}")
    col8.metric("Utilización de flota", f"{reportes.utilizacion_flota(transporte)}%")

    st.subheader("Indicadores de inventario")
    col9, col10, col11 = st.columns(3)
    col9.metric("Valor de inventario inmovilizado", f"${reportes.valor_inventario_inmovilizado(inventario):,.0f}")
    col10.metric("Rotación promedio", reportes.rotacion_inventario_promedio(inventario))
    col11.metric("Utilización capacidad flota (peso)", f"{reportes.utilizacion_capacidad_flota(st.session_state.rutas)}%")

    st.divider()
    tab1, tab2, tab3 = st.tabs(["Productos bajo stock mínimo", "Clasificación ABC", "Rutas calculadas"])
    with tab1:
        bajo_min = inventario.productos_bajo_minimo()
        if bajo_min:
            st.dataframe(
                pd.DataFrame([{
                    "Código": p.codigo, "Nombre": p.nombre,
                    "Stock actual": inventario.consultar_stock(p.codigo), "Stock mínimo": p.stock_minimo,
                } for p in bajo_min]),
                use_container_width=True, hide_index=True,
            )
        else:
            st.success("Ningún producto está bajo el stock mínimo.")
    with tab2:
        if inventario._productos:
            inventario.clasificar_abc()
            st.dataframe(
                pd.DataFrame([{
                    "Código": c, "Nombre": p.nombre, "Clase": badge_abc(p.clasificacion_abc),
                    "Valor de consumo anual ($)": round(p.demanda_diaria_promedio * 365 * p.costo_unitario, 0),
                } for c, p in inventario._productos.items()]).sort_values("Valor de consumo anual ($)", ascending=False),
                use_container_width=True, hide_index=True,
            )
        else:
            st.info("No hay productos registrados.")
    with tab3:
        if st.session_state.rutas:
            st.dataframe(
                pd.DataFrame([{
                    "Ruta": r.id, "Vehículo": r.vehiculo.placa,
                    "Distancia (km)": r.distancia_km, "Costo ($)": r.costo_estimado,
                } for r in st.session_state.rutas]),
                use_container_width=True, hide_index=True,
            )
        else:
            st.info("Aún no se han calculado rutas.")
