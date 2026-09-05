"""
Aplicación web — Sistema de Gestión de Distribución y Transporte
==================================================================
Interfaz Streamlit que conecta los módulos de lógica de negocio:
  inventario.py | pedidos.py | transporte.py | rastreo.py | reportes.py

Ejecutar localmente:   streamlit run app.py
"""

from datetime import datetime, timedelta

import streamlit as st
import pandas as pd

from modelos import (
    Cliente, Conductor, EstadoEnvio, EstadoPedido, ItemPedido,
    Producto, Vehiculo,
)
from inventario import GestionInventario
from pedidos import GestionPedidos
from transporte import GestionTransporte
from rastreo import GestionRastreo
import reportes

st.set_page_config(page_title="Gestión de Distribución y Transporte", layout="wide", page_icon="📦")

# ---------------------------------------------------------------------------
# Datos ficticios de muestra — para que la app se vea en "etapa de funcionamiento"
# ---------------------------------------------------------------------------
def cargar_datos_demo():
    inventario = GestionInventario()
    pedidos_mgr = GestionPedidos(inventario)
    transporte = GestionTransporte()
    rastreo = GestionRastreo()

    productos = [
        Producto("SKU-001", "Cemento gris 50kg", "Materiales", 50, 0.03, 30),
        Producto("SKU-002", "Varilla 12mm", "Materiales", 8, 0.01, 60),
        Producto("SKU-003", "Pintura blanca 1 galón", "Acabados", 4.5, 0.005, 20),
        Producto("SKU-004", "Taladro percutor 650W", "Herramientas", 2.2, 0.004, 5),
        Producto("SKU-005", "Tubería PVC 1/2 pulgada", "Plomería", 1.1, 0.006, 40),
    ]
    stocks_iniciales = [180, 260, 15, 12, 300]
    for prod, stock in zip(productos, stocks_iniciales):
        inventario.registrar_producto(prod, stock_inicial=stock)

    clientes_data = [
        ("Ferretería El Tornillo", "Cra 10 #20-30, Cartagena", (5, 8)),
        ("Constructora Alfa", "Av Pedro de Heredia 45-12", (2, 3)),
        ("Depósito Central Bosque", "Zona Industrial El Bosque", (9, 1)),
        ("Distribuidora Manga", "Cl 24 #8-15, Manga", (4, 6)),
    ]
    clientes = [Cliente(n, d, c) for n, d, c in clientes_data]

    pedidos_seed = [
        (clientes[0], [(productos[0], 10), (productos[1], 20)]),
        (clientes[1], [(productos[0], 5), (productos[2], 8)]),
        (clientes[2], [(productos[1], 40)]),
        (clientes[3], [(productos[3], 3), (productos[4], 50)]),
    ]
    pedidos_creados = []
    for cliente, items in pedidos_seed:
        items_pedido = [ItemPedido(p, c) for p, c in items]
        pedido = pedidos_mgr.crear_pedido(cliente, items_pedido)
        pedidos_creados.append(pedido)

    # confirmar los tres primeros (dejamos uno en estado CREADO como pendiente)
    for pedido in pedidos_creados[:3]:
        pedidos_mgr.confirmar_pedido(pedido.id)

    vehiculos = [
        Vehiculo("ABC123", "camión", 1000, 5, 3500, 20000),
        Vehiculo("XYZ789", "furgón", 500, 2.5, 2200, 12000),
    ]
    for v in vehiculos:
        transporte.registrar_vehiculo(v)

    conductores = [
        Conductor("COND-001", "Carlos Pérez", "C2-45210", "300-111-2233"),
        Conductor("COND-002", "María Gómez", "C2-98871", "301-222-3344"),
    ]
    for c in conductores:
        transporte.registrar_conductor(c)

    # una ruta ya calculada con envío en tránsito, como muestra
    confirmados = pedidos_mgr.listar_por_estado(EstadoPedido.CONFIRMADO)
    asignados, _ = transporte.asignar_pedidos_a_vehiculo(confirmados[:2], vehiculos[0])
    ruta_demo = transporte.calcular_ruta_optima((0, 0), vehiculos[0], asignados)
    for p in asignados:
        pedidos_mgr.marcar_asignado(p.id)
    envio_demo = rastreo.crear_envio(ruta_demo)
    rastreo.actualizar_estado(envio_demo.id, EstadoEnvio.EN_RUTA, "Salió del centro de distribución")

    # un mantenimiento preventivo programado como muestra
    transporte.programar_mantenimiento(
        vehiculos[1].placa, "PREVENTIVO",
        datetime.now() + timedelta(days=2),
        datetime.now() + timedelta(days=2, hours=4),
        "Cambio de aceite y revisión de frenos",
    )

    return {
        "inventario": inventario, "pedidos_mgr": pedidos_mgr,
        "transporte": transporte, "rastreo": rastreo,
        "rutas": [ruta_demo], "envios": [envio_demo.id],
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
    fila1[3].metric("Alertas de stock bajo", len(inventario.productos_bajo_minimo()))

    fila2 = st.columns(4)
    fila2[0].metric("Vehículos en flota", len(transporte._flota))
    fila2[1].metric("Vehículos disponibles", len(transporte.vehiculos_disponibles()))
    fila2[2].metric("Conductores registrados", len(transporte._conductores))
    fila2[3].metric("Mantenimientos programados", len(transporte.listar_mantenimientos()))

    fila3 = st.columns(4)
    fila3[0].metric("Rutas calculadas", len(st.session_state.rutas))
    fila3[1].metric("Envíos generados", len(st.session_state.envios))
    en_ruta = sum(1 for eid in st.session_state.envios if rastreo.consultar_estado(eid) == EstadoEnvio.EN_RUTA)
    fila3[2].metric("Envíos en ruta", en_ruta)
    fila3[3].metric("Productos en catálogo", len(inventario._productos))

    st.divider()
    tab1, tab2 = st.tabs(["Pedidos por estado", "Alertas de inventario"])
    with tab1:
        if pedidos_mgr._pedidos:
            conteo = pd.Series([p.estado.value for p in pedidos_mgr._pedidos.values()]).value_counts()
            st.bar_chart(conteo)
        else:
            st.info("Aún no hay pedidos registrados.")
    with tab2:
        bajo_min = inventario.productos_bajo_minimo()
        if bajo_min:
            st.dataframe(
                pd.DataFrame([{"Código": p.codigo, "Nombre": p.nombre,
                                "Stock actual": inventario.consultar_stock(p.codigo),
                                "Stock mínimo": p.stock_minimo} for p in bajo_min]),
                use_container_width=True, hide_index=True,
            )
        else:
            st.success("Ningún producto está bajo el stock mínimo.")

# ===========================================================================
# INVENTARIO
# ===========================================================================
elif pagina == "📦 Inventario":
    st.title("Gestión de Inventario")
    tab_stock, tab_nuevo, tab_mov = st.tabs(["Stock actual", "➕ Nuevo producto", "↕️ Movimiento de stock"])

    with tab_stock:
        if inventario._productos:
            filas = [{
                "Código": c, "Nombre": p.nombre, "Categoría": p.categoria,
                "Stock": inventario.consultar_stock(c), "Stock mínimo": p.stock_minimo,
                "Bajo mínimo": "⚠️" if inventario.consultar_stock(c) < p.stock_minimo else "",
            } for c, p in inventario._productos.items()]
            st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)
        else:
            st.info("No hay productos registrados todavía.")

    with tab_nuevo:
        with st.form("form_producto"):
            c1, c2 = st.columns(2)
            codigo = c1.text_input("Código (SKU)")
            nombre = c2.text_input("Nombre del producto")
            c3, c4, c5 = st.columns(3)
            categoria = c3.text_input("Categoría")
            peso = c4.number_input("Peso unitario (kg)", min_value=0.0, step=0.1)
            volumen = c5.number_input("Volumen unitario (m³)", min_value=0.0, step=0.01)
            c6, c7 = st.columns(2)
            stock_min = c6.number_input("Stock mínimo", min_value=0, step=1)
            stock_inicial = c7.number_input("Stock inicial", min_value=0, step=1)
            if st.form_submit_button("Registrar producto"):
                if codigo and nombre:
                    producto = Producto(codigo, nombre, categoria, peso, volumen, stock_min)
                    inventario.registrar_producto(producto, stock_inicial=int(stock_inicial))
                    st.success(f"Producto {codigo} registrado.")
                else:
                    st.error("Código y nombre son obligatorios.")

    with tab_mov:
        if inventario._productos:
            codigo_sel = st.selectbox("Producto", list(inventario._productos.keys()))
            c1, c2, c3 = st.columns(3)
            cantidad = c1.number_input("Cantidad", min_value=1, step=1, key="mov_cant")
            tipo_mov = c2.selectbox("Tipo", ["ENTRADA", "SALIDA"])
            if c3.button("Aplicar movimiento", use_container_width=True):
                try:
                    if tipo_mov == "ENTRADA":
                        inventario.entrada_stock(codigo_sel, int(cantidad), referencia="ajuste manual")
                    else:
                        inventario.salida_stock(codigo_sel, int(cantidad), referencia="ajuste manual")
                    st.success("Movimiento aplicado.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
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
        tab_lista, tab_nuevo = st.tabs(["Pedidos registrados", "➕ Crear pedido"])

        with tab_nuevo:
            with st.form("form_pedido"):
                c1, c2 = st.columns(2)
                nombre_cliente = c1.text_input("Nombre del cliente")
                direccion = c2.text_input("Dirección")
                c3, c4 = st.columns(2)
                coord_x = c3.number_input("Coordenada X (ubicación simplificada)", step=1.0)
                coord_y = c4.number_input("Coordenada Y (ubicación simplificada)", step=1.0)

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
                        cliente = Cliente(nombre_cliente, direccion, (coord_x, coord_y))
                        items = [ItemPedido(inventario._productos[c], int(cantidades[c])) for c in items_sel]
                        pedido = pedidos_mgr.crear_pedido(cliente, items)
                        st.success(f"Pedido {pedido.id} creado.")
                    else:
                        st.error("Nombre del cliente y al menos un producto son obligatorios.")

        with tab_lista:
            if pedidos_mgr._pedidos:
                filas = [{
                    "ID": p.id, "Cliente": p.cliente.nombre, "Estado": p.estado.value,
                    "Peso (kg)": round(p.peso_total, 2), "Volumen (m³)": round(p.volumen_total, 2),
                } for p in pedidos_mgr._pedidos.values()]
                st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

                st.subheader("Confirmar o cancelar pedido")
                pedido_id = st.selectbox("Pedido", list(pedidos_mgr._pedidos.keys()))
                c1, c2 = st.columns(2)
                if c1.button("✅ Confirmar pedido", use_container_width=True):
                    try:
                        pedidos_mgr.confirmar_pedido(pedido_id)
                        st.success("Pedido confirmado y stock descontado.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
                if c2.button("❌ Cancelar pedido", use_container_width=True):
                    pedidos_mgr.cancelar_pedido(pedido_id)
                    st.success("Pedido cancelado.")
                    st.rerun()
            else:
                st.info("No hay pedidos todavía.")

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
                if st.form_submit_button("Registrar vehículo"):
                    if placa:
                        transporte.registrar_vehiculo(
                            Vehiculo(placa, tipo, cap_peso, cap_vol, costo_km, costo_fijo)
                        )
                        st.success(f"Vehículo {placa} registrado.")
                    else:
                        st.error("La placa es obligatoria.")

        if transporte._flota:
            filas = [{
                "Placa": v.placa, "Tipo": v.tipo, "Cap. peso (kg)": v.capacidad_peso_kg,
                "Cap. volumen (m³)": v.capacidad_volumen_m3, "Disponible": "Sí" if v.disponible else "No",
            } for v in transporte._flota.values()]
            st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)
        else:
            st.info("No hay vehículos registrados todavía.")

    with tab_cond:
        with st.expander("➕ Registrar conductor"):
            with st.form("form_conductor"):
                c1, c2 = st.columns(2)
                id_cond = c1.text_input("ID (ej. COND-003)")
                nombre_cond = c2.text_input("Nombre completo")
                c3, c4 = st.columns(2)
                licencia = c3.text_input("Licencia de conducción")
                telefono = c4.text_input("Teléfono")
                if st.form_submit_button("Registrar conductor"):
                    if id_cond and nombre_cond:
                        transporte.registrar_conductor(Conductor(id_cond, nombre_cond, licencia, telefono))
                        st.success(f"Conductor {nombre_cond} registrado.")
                    else:
                        st.error("ID y nombre son obligatorios.")

        if transporte._conductores:
            filas = [{
                "ID": c.id, "Nombre": c.nombre, "Licencia": c.licencia,
                "Teléfono": c.telefono, "Disponible": "Sí" if c.disponible else "No",
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
                notas = st.text_input("Notas")
                if st.form_submit_button("Programar mantenimiento"):
                    try:
                        inicio_dt = datetime.strptime(fecha_inicio, "%Y-%m-%d %H:%M")
                        fin_dt = datetime.strptime(fecha_fin, "%Y-%m-%d %H:%M")
                        transporte.programar_mantenimiento(placa_sel, tipo_mant, inicio_dt, fin_dt, notas)
                        st.success(f"Mantenimiento programado para {placa_sel} (vehículo marcado como no disponible).")
                        st.rerun()
                    except ValueError:
                        st.error("Formato de fecha inválido. Usa AAAA-MM-DD HH:MM.")

            mantenimientos = transporte.listar_mantenimientos()
            if mantenimientos:
                st.subheader("Mantenimientos")
                filas = [{
                    "ID": m.id, "Vehículo": m.vehiculo.placa, "Tipo": m.tipo,
                    "Inicio": m.inicio, "Fin": m.fin, "Estado": m.estado.value, "Notas": m.notas,
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

    pendientes = pedidos_mgr.listar_por_estado(EstadoPedido.CONFIRMADO)
    disponibles = transporte.vehiculos_disponibles()

    if not pendientes:
        st.info("No hay pedidos CONFIRMADOS pendientes de asignar. Confirma pedidos en el módulo **Pedidos**.")
    elif not disponibles:
        st.info("No hay vehículos disponibles. Registra uno en **Flota y Conductores** o completa un mantenimiento en curso.")
    else:
        placa_sel = st.selectbox("Vehículo", [v.placa for v in disponibles])
        c1, c2 = st.columns(2)
        origen_x = c1.number_input("Origen X (centro de distribución)", value=0.0, step=1.0)
        origen_y = c2.number_input("Origen Y (centro de distribución)", value=0.0, step=1.0)

        st.caption(f"Pedidos confirmados pendientes: {[p.id for p in pendientes]}")

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
                st.write(f"**Distancia total:** {ruta.distancia_km} km")
                st.write(f"**Costo estimado:** ${ruta.costo_estimado:,.0f}")
                if no_asignados:
                    st.warning(f"No cupieron en este viaje: {[p.id for p in no_asignados]}")

    st.divider()
    st.subheader("Historial de rutas calculadas")
    if st.session_state.rutas:
        st.dataframe(
            pd.DataFrame([{
                "Ruta": r.id, "Vehículo": r.vehiculo.placa,
                "Distancia (km)": r.distancia_km, "Costo ($)": r.costo_estimado,
                "Paradas": len(r.secuencia_pedidos),
            } for r in st.session_state.rutas]),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("Aún no se han calculated rutas.")

# ===========================================================================
# RASTREO
# ===========================================================================
elif pagina == "📍 Rastreo":
    st.title("Rastreo y Trazabilidad de Envíos")

    if not st.session_state.envios:
        st.info("Aún no se ha generado ningún envío. Calcula una ruta en **Rutas y Despacho** primero.")
    else:
        envio_id = st.selectbox("Envío", st.session_state.envios)
        estado_actual = rastreo.consultar_estado(envio_id)
        st.metric("Estado actual", estado_actual.value)

        nuevo_estado = st.selectbox("Actualizar estado a:", [e.value for e in EstadoEnvio])
        nota = st.text_input("Nota (opcional)")
        if st.button("Actualizar estado"):
            rastreo.actualizar_estado(envio_id, EstadoEnvio(nuevo_estado), nota)
            if EstadoEnvio(nuevo_estado) == EstadoEnvio.ENTREGADO:
                for p in rastreo._envios[envio_id].ruta.secuencia_pedidos:
                    pedidos_mgr.marcar_entregado(p.id)
            st.success("Estado actualizado.")
            st.rerun()

        st.subheader("Historial")
        hist = rastreo.historial(envio_id)
        df_hist = pd.DataFrame([{"Fecha": f, "Estado": e.value, "Nota": n} for f, e, n in hist])
        st.dataframe(df_hist, use_container_width=True, hide_index=True)

# ===========================================================================
# REPORTES
# ===========================================================================
elif pagina == "📈 Reportes":
    st.title("Reportes e Indicadores (KPI)")

    col1, col2, col3 = st.columns(3)
    col1.metric("Nivel de servicio", f"{reportes.nivel_servicio(pedidos_mgr)}%")
    col2.metric("Costo promedio por envío", f"${reportes.costo_promedio_envio(st.session_state.rutas):,.0f}")
    col3.metric("Utilización de flota", f"{reportes.utilizacion_flota(transporte)}%")

    st.divider()
    tab1, tab2 = st.tabs(["Productos bajo stock mínimo", "Rutas calculadas"])
    with tab1:
        bajo_min = inventario.productos_bajo_minimo()
        if bajo_min:
            st.dataframe(
                pd.DataFrame([{"Código": p.codigo, "Nombre": p.nombre} for p in bajo_min]),
                use_container_width=True, hide_index=True,
            )
        else:
            st.success("Ningún producto está bajo el stock mínimo.")
    with tab2:
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
